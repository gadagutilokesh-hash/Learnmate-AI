import json
import pytest
from unittest.mock import patch, MagicMock
import httpx

from app.core.config import settings
from app.core.ai_provider import (
    get_ai_provider,
    reset_provider_cache,
    GeminiProvider,
    GroqProvider,
    NvidiaNemotronProvider,
    AIAuthError,
    AIQuotaExceededError,
    AIServiceUnavailableError,
    UnsupportedCapabilityError,
    AIOutputParsingError,
    sanitize_ai_error,
    ai_service
)
from app.core.gemini import (
    gemini_service,
    GeminiQuotaExceededError,
    GeminiServiceUnavailableError
)
from app.services.tutor.grounded_tutor import grounded_tutor
from app.services.assessment.generator import assessment_service, AssessmentGenerateRequest
from app.models.schema import TutorQueryRequest, AssessmentQuestion

@pytest.fixture(autouse=True)
def clean_provider_state():
    reset_provider_cache()
    gemini_service.reset_quota_cooldown()
    yield
    reset_provider_cache()
    gemini_service.reset_quota_cooldown()


# ==============================================================================
# 1. Provider Registry & Factory Validation
# ==============================================================================
def test_provider_factory_valid_names():
    reset_provider_cache()
    p_gemini = get_ai_provider("gemini")
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.provider_name == "gemini"

    p_google = get_ai_provider("google-genai")
    assert isinstance(p_google, GeminiProvider)

    p_groq = get_ai_provider("groq")
    assert isinstance(p_groq, GroqProvider)
    assert p_groq.provider_name == "groq"
    assert p_groq.model_name in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b")

    p_nvidia = get_ai_provider("nvidia")
    assert isinstance(p_nvidia, NvidiaNemotronProvider)
    assert p_nvidia.provider_name == "nvidia"
    assert "nemotron" in p_nvidia.model_name.lower()


def test_provider_factory_invalid_name():
    reset_provider_cache()
    with pytest.raises(ValueError) as exc:
        get_ai_provider("anthropic_claude")
    assert "Unsupported AI_PROVIDER 'anthropic_claude'" in str(exc.value)
    assert "Supported providers are: 'gemini', 'groq', 'nvidia'" in str(exc.value)


# ==============================================================================
# 2. Capability Matrix Checks
# ==============================================================================
def test_provider_capabilities():
    gemini = get_ai_provider("gemini")
    assert gemini.get_capabilities() == {
        "text_generation": True,
        "structured_output": True,
        "multimodal_image": True,
        "multimodal_video": True,
        "embeddings": True
    }

    groq = get_ai_provider("groq")
    assert groq.get_capabilities() == {
        "text_generation": True,
        "structured_output": True,
        "multimodal_image": False,
        "multimodal_video": False,
        "embeddings": False
    }

    nvidia = get_ai_provider("nvidia")
    assert nvidia.get_capabilities() == {
        "text_generation": True,
        "structured_output": True,
        "multimodal_image": False,
        "multimodal_video": False,
        "embeddings": False
    }


# ==============================================================================
# 3. Successful Text Generation (Groq & NVIDIA)
# ==============================================================================
def test_groq_text_generation_success():
    reset_provider_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": "Gradient descent minimizes the objective loss function."}}
        ]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("httpx.Client.post", return_value=mock_resp) as mock_post:

        groq = get_ai_provider("groq")
        assert groq.is_configured()
        out = groq.generate_text("Explain gradient descent.")

        assert out == "Gradient descent minimizes the objective loss function."
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "Bearer gsk_test_key_12345" in call_kwargs["headers"]["Authorization"]
        assert call_kwargs["json"]["model"] in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b")


def test_nvidia_nemotron_text_generation_success():
    reset_provider_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": "```json\n{\"answer\": \"Nemotron explanation\"}\n```"}}
        ]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "nvidia"), \
         patch("app.core.config.settings.NVIDIA_API_KEY", "nvapi-test_key_67890"), \
         patch("httpx.Client.post", return_value=mock_resp) as mock_post:

        nvidia = get_ai_provider("nvidia")
        assert nvidia.is_configured()
        out = nvidia.generate_text("Explain Nemotron.")

        # Verifies surrounding markdown fences are stripped cleanly
        assert out == '{"answer": "Nemotron explanation"}'
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "Bearer nvapi-test_key_67890" in call_kwargs["headers"]["Authorization"]


# ==============================================================================
# 4. Structured Assessment Generation with Groq
# ==============================================================================
def test_groq_structured_assessment_generation():
    reset_provider_cache()
    mock_assessment_json = json.dumps({
        "prompt": "What is the primary role of the learning rate alpha in gradient descent?",
        "question_type": "mcq",
        "options": [
            "A) Determines step size towards the loss minimum",
            "B) Calculates the exact dataset size",
            "C) Standardizes input feature variance",
            "D) Eliminates numerical underflow completely"
        ],
        "correct_answer": "A) Determines step size towards the loss minimum",
        "explanation": "Alpha governs the magnitude of the parameter update vector.",
        "difficulty": "medium",
        "topic": "Gradient Descent",
        "concept": "Learning Rate",
        "rubric": {
            "key_concepts": ["step size", "convergence", "parameter update"]
        }
    })

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": mock_assessment_json}}]
    }

    mock_chunks = [{
        "id": "c1",
        "document_id": "d1",
        "course_id": "CS229",
        "content": "Gradient descent uses learning rate alpha to update parameters iteratively.",
        "filename": "Lecture_02.pptx",
        "source_type": "pptx",
        "slide_number": 4,
        "page_number": None,
        "topic": "Gradient Descent",
        "concept": "Learning Rate",
        "chunk_type": "text",
        "metadata": {}
    }]

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("app.services.assessment.generator.storage.get_chunks_for_course", return_value=mock_chunks), \
         patch("httpx.Client.post", return_value=mock_resp):

        import uuid
        res = assessment_service.generate_assessment(
            AssessmentGenerateRequest(
                course_id="CS229",
                user_id=f"test_groq_{uuid.uuid4()}",
                question_count=1,
                question_type="mcq",
                difficulty="medium",
                topic="Gradient Descent",
                allow_revision=True
            )
        )

        assert res.total_questions == 1
        q = res.questions[0]
        assert "learning rate" in q.prompt.lower()
        assert len(q.options) == 4
        assert q.question_type == "mcq"


# ==============================================================================
# 5. Unsupported-Question Rejection & Citation Provenance under Groq
# ==============================================================================
def test_unsupported_question_rejection_groq():
    reset_provider_cache()
    # Mock LLM declaring insufficient grounding
    mock_unsupported_json = json.dumps({
        "answer": "The provided excerpts do not mention quantum entanglement.",
        "is_sufficiently_grounded": False,
        "cited_source_indices": [],
        "unsupported_reason": "Topic absent from provided excerpts."
    })

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": mock_unsupported_json}}]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("httpx.Client.post", return_value=mock_resp):

        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="CS229", query="Explain quantum entanglement in CS229.", top_k=2)
        )

        assert not res.is_grounded
        assert len(res.citations) == 0
        assert "excerpts do not contain" in res.answer or "insufficient" in res.answer.lower() or not res.is_grounded


def test_citation_provenance_rejects_hallucinated_indices():
    reset_provider_cache()
    # LLM hallucinates out-of-bound indices 99 and 999
    mock_hallucinated_json = json.dumps({
        "answer": "Gradient descent uses learning rate alpha.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [1, 99, 999],
        "unsupported_reason": None
    })

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": mock_hallucinated_json}}]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("httpx.Client.post", return_value=mock_resp):

        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="CS229", query="Explain gradient descent update rule.", top_k=2)
        )

        # Only valid retrieved chunk index 1 must be retained; 99 and 999 must be dropped
        assert res.is_grounded
        assert len(res.citations) == 1
        assert res.citations[0].source_file.endswith((".pdf", ".pptx"))


# ==============================================================================
# 6. Error Handling: 429 Quota Exhaustion & Cooldown Fail-Closed
# ==============================================================================
def test_groq_quota_429_fail_closed():
    reset_provider_cache()
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = '{"error": {"message": "Rate limit reached for model llama-3.3-70b-versatile: 429 Too Many Requests"}}'
    mock_429.headers = {"retry-after": "60"}

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("httpx.Client.post", return_value=mock_429) as mock_post:

        groq = get_ai_provider("groq")

        # 1. First call triggers 429 and enters cooldown
        with pytest.raises(AIQuotaExceededError) as exc_info:
            groq.generate_text("Prompt 1")
        assert "temporarily unavailable because the ai service has reached its current usage limit" in str(exc_info.value).lower()
        assert issubclass(AIQuotaExceededError, GeminiQuotaExceededError)
        assert groq.is_quota_exhausted()

        # 2. Second call during active cooldown aborts immediately WITHOUT network request
        mock_post.reset_mock()
        with pytest.raises(AIQuotaExceededError):
            groq.generate_text("Prompt 2")
        assert not mock_post.called


# ==============================================================================
# 7. Error Handling: 503 Transient Overload Bounded Retries
# ==============================================================================
def test_groq_transient_503_retry_and_recovery():
    reset_provider_cache()
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "Service Unavailable"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Recovered successfully"}}]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("time.sleep") as mock_sleep, \
         patch("httpx.Client.post", side_effect=[resp_503, resp_503, resp_200]) as mock_post:

        groq = get_ai_provider("groq")
        out = groq.generate_text("Test prompt")
        assert out == "Recovered successfully"
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2


def test_groq_transient_503_exhausts_retries():
    reset_provider_cache()
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "503 High Demand Overloaded"

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("time.sleep"), \
         patch("httpx.Client.post", return_value=resp_503) as mock_post:

        groq = get_ai_provider("groq")
        with pytest.raises(AIServiceUnavailableError) as exc_info:
            groq.generate_text("Test prompt")
        assert "temporarily unavailable due to high model demand" in str(exc_info.value).lower()
        assert issubclass(AIServiceUnavailableError, GeminiServiceUnavailableError)
        # Bounded retry: initial attempt + 3 retries = 4 total attempts
        assert mock_post.call_count == 4


# ==============================================================================
# 8. Authentication Errors: Immediate Fail Fast
# ==============================================================================
def test_groq_auth_401_no_retries():
    reset_provider_cache()
    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = '{"error": {"message": "Invalid API Key provided: gsk_secret_bad_key"}}'

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_secret_bad_key"), \
         patch("time.sleep") as mock_sleep, \
         patch("httpx.Client.post", return_value=resp_401) as mock_post:

        groq = get_ai_provider("groq")
        with pytest.raises(AIAuthError) as exc_info:
            groq.generate_text("Test prompt")
        assert "authentication failed" in str(exc_info.value).lower()
        # Must fail immediately with 0 retries
        assert mock_post.call_count == 1
        assert not mock_sleep.called


# ==============================================================================
# 9. Embedding Vector Space Protection (Phase 4)
# ==============================================================================
def test_unsupported_embeddings_capability_protection():
    reset_provider_cache()
    groq = get_ai_provider("groq")
    with pytest.raises(UnsupportedCapabilityError) as exc_groq:
        groq.get_embedding("Test text")
    assert "does not support generating compatible 768-dimensional embeddings" in str(exc_groq.value)

    nvidia = get_ai_provider("nvidia")
    with pytest.raises(UnsupportedCapabilityError) as exc_nv:
        nvidia.get_embeddings_batch(["Text 1", "Text 2"])
    assert "does not support dense embeddings" in str(exc_nv.value)


# ==============================================================================
# 10. Multimodal Ingestion Capability Check (Phase 5)
# ==============================================================================
def test_unsupported_multimodal_vision_capability():
    reset_provider_cache()
    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch.object(gemini_service, "is_gemini_configured", return_value=False):
        with pytest.raises(UnsupportedCapabilityError) as exc_info:
            ai_service.generate_multimodal_description(
                image_bytes=b"\x89PNG\r\n\x1a\nfake_image_bytes",
                mime_type="image/png"
            )
        assert "does not support multimodal image analysis" in str(exc_info.value)
        assert "GEMINI_API_KEY" in str(exc_info.value)


# ==============================================================================
# 11. Redaction of API Secrets (Phase 2 & 6)
# ==============================================================================
def test_secrets_redaction_across_all_providers():
    err_text = (
        "Failed with key=AIzaSyD-123456789012345678901234567890 "
        "and gsk_abcdef12345678901234567890abcdef and "
        "nvapi-9876543210abcdef9876543210 and Bearer secret_bearer_token"
    )
    sanitized = sanitize_ai_error(Exception(err_text))

    assert "AIzaSyD" not in sanitized
    assert "gsk_abcdef" not in sanitized
    assert "nvapi-" not in sanitized
    assert "secret_bearer_token" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized


# ==============================================================================
# 12. Course Isolation under Multi-Provider Mode
# ==============================================================================
def test_course_isolation_under_groq():
    reset_provider_cache()
    mock_cs229_json = json.dumps({
        "answer": "CS229 Supervised learning uses input vectors mapping to targets.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [1],
        "unsupported_reason": None
    })

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": mock_cs229_json}}]
    }

    with patch("app.core.config.settings.AI_PROVIDER", "groq"), \
         patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_key_12345"), \
         patch("httpx.Client.post", return_value=mock_resp):

        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="CS229", query="Explain supervised learning.", top_k=3)
        )

        assert res.is_grounded
        for cit in res.citations:
            # Must strictly belong to CS229; never leak other courses
            assert "cs229" in cit.source_file.lower() or "lecture" in cit.source_file.lower()
