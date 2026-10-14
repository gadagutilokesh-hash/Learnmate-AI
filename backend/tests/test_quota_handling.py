import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.gemini import (
    GeminiService, GeminiQuotaExceededError, is_gemini_quota_error,
    extract_gemini_retry_delay, format_human_retry_delay,
    get_friendly_quota_message, sanitize_error
)
from app.models.schema import TutorQueryRequest
from app.services.tutor.grounded_tutor import GroundedTutorService
from app.services.assessment.generator import AssessmentService

client = TestClient(app)

# ==============================================================================
# 1. Detection of HTTP 429 and RESOURCE_EXHAUSTED
# ==============================================================================

def test_is_gemini_quota_error_status_codes():
    """Detects quota errors via HTTP status code 429 on various exception shapes."""
    class MockErrorWithCode(Exception):
        def __init__(self, code):
            self.code = code

    class MockErrorWithStatusCode(Exception):
        def __init__(self, sc):
            self.status_code = sc

    class MockErrorWithResponse(Exception):
        def __init__(self, sc):
            self.response = MagicMock(status_code=sc)

    assert is_gemini_quota_error(MockErrorWithCode(429)) is True
    assert is_gemini_quota_error(MockErrorWithStatusCode(429)) is True
    assert is_gemini_quota_error(MockErrorWithResponse(429)) is True
    assert is_gemini_quota_error(GeminiQuotaExceededError()) is True

    # Non-429 codes must NOT be identified as quota errors
    assert is_gemini_quota_error(MockErrorWithCode(400)) is False
    assert is_gemini_quota_error(MockErrorWithCode(403)) is False
    assert is_gemini_quota_error(MockErrorWithCode(500)) is False

def test_is_gemini_quota_error_signatures():
    """Detects quota errors via provider signature strings in exception message."""
    test_cases = [
        "429 RESOURCE_EXHAUSTED",
        "Resource has been exhausted (e.g. check quota).",
        "Quota exceeded for quota metric 'Generate Content Requests'",
        "Rate limit exceeded: Please wait before submitting more requests.",
        "generativelanguage.googleapis.com/generate_content_free_tier_requests",
        "generaterequestsperdayperprojectpermodel-freetier",
        "Too Many Requests: exceeded your current quota"
    ]
    for msg in test_cases:
        err = Exception(msg)
        assert is_gemini_quota_error(err) is True, f"Failed to detect quota in: {msg}"

    # Non-quota strings
    assert is_gemini_quota_error(Exception("Connection timed out")) is False
    assert is_gemini_quota_error(Exception("Invalid JSON format in response")) is False
    assert is_gemini_quota_error(Exception("Document not found")) is False

# ==============================================================================
# 2. Retry Delay Metadata Extraction & Human Estimates
# ==============================================================================

def test_extract_retry_delay_from_provider_json():
    """Extracts seconds from nested RPC/JSON and formats into non-promising estimate."""
    raw_provider_error = (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource has been exhausted.', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '35088s'}]}}"
    )
    sec, human = extract_gemini_retry_delay(Exception(raw_provider_error))
    assert sec == 35088.0
    assert human is not None
    assert "hour" in human

def test_extract_retry_delay_from_various_formats():
    """Tests diverse provider representations: headers, durations, and seconds."""
    # 60 seconds
    sec1, human1 = extract_gemini_retry_delay(Exception("rate limited, retry in 60s"))
    assert sec1 == 60.0
    assert human1 == "in about 1 minute"

    # 15 minutes (900s)
    sec2, human2 = extract_gemini_retry_delay(Exception("quota exhausted, retry after 900 seconds"))
    assert sec2 == 900.0
    assert human2 == "in about 15 minutes"

    # From HTTP header on response
    mock_resp = MagicMock()
    mock_resp.headers = {"Retry-After": "120"}
    err_with_resp = Exception("429 Too Many Requests")
    err_with_resp.response = mock_resp
    sec3, human3 = extract_gemini_retry_delay(err_with_resp)
    assert sec3 == 120.0
    assert human3 == "in about 2 minutes"

def test_missing_retry_delay_metadata():
    """When provider omits retry metadata, return (None, None) and base friendly message."""
    err = Exception("429 RESOURCE_EXHAUSTED without retry info")
    sec, human = extract_gemini_retry_delay(err)
    assert sec is None
    assert human is None

    friendly = get_friendly_quota_message(err)
    assert friendly == "Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later."
    assert "estimated" not in friendly

def test_friendly_message_with_retry_estimate():
    """When retry estimate is available, append non-promising human estimate."""
    err = Exception("429 RESOURCE_EXHAUSTED {'retryDelay': '600s'}")
    friendly = get_friendly_quota_message(err)
    assert friendly.startswith("Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later.")
    assert "estimated retry in about 10 minutes" in friendly

# ==============================================================================
# 3. Sanitization & Protection of Secrets & Internal Stack Traces
# ==============================================================================

def test_sanitize_error_redacts_keys_and_tokens():
    """Ensures API keys, Bearer tokens, and GCP paths are completely scrubbed."""
    with patch("app.core.gemini.settings.GEMINI_API_KEY", "AIzaSyTestSecretKey12345678901234"):
        raw_err = (
            "Request to https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
            "?key=AIzaSyTestSecretKey12345678901234 failed with Bearer secret_auth_token_xyz"
        )
        sanitized = sanitize_error(Exception(raw_err))
        assert "AIzaSyTestSecretKey12345678901234" not in sanitized
        assert "secret_auth_token_xyz" not in sanitized
        assert "[REDACTED" in sanitized

def test_sanitize_error_scrubs_raw_rpc_payloads():
    """Scrubs raw nested JSON/RPC payloads to prevent internal metadata leakage."""
    raw_payload = (
        "500 Internal Server Error: {'error': {'code': 500, 'message': 'Internal back-end pipeline failure in worker node 42.', "
        "'status': 'INTERNAL', 'details': [{'internal_trace': 'at google.rpc.internal.Pipeline.run(Line 342)'}]}}"
    )
    sanitized = sanitize_error(Exception(raw_payload))
    assert "{'error':" not in sanitized
    assert "google.rpc.internal" not in sanitized
    assert "worker node 42" in sanitized or "Gemini API error:" in sanitized

def test_sanitize_quota_error_never_exposes_raw_details():
    """When an error is a quota error, sanitize_error returns the friendly user-facing text."""
    raw_quota_err = Exception(
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource has been exhausted (e.g. check quota).', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', "
        "'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests'}]}]}}"
    )
    sanitized = sanitize_error(raw_quota_err)
    assert sanitized.startswith("Live AI generation is temporarily unavailable")
    assert "generativelanguage.googleapis.com" not in sanitized
    assert "violations" not in sanitized
    assert "QuotaFailure" not in sanitized

# ==============================================================================
# 4. Quota Cooldown & Prevention of Repeated Throttled Calls (Requirement 9)
# ==============================================================================

def test_quota_cooldown_activates_and_aborts_repeated_calls():
    """When a quota error occurs, service enters cooldown and immediately aborts subsequent calls."""
    svc = GeminiService()
    svc.api_key = "test_key"
    svc._client = MagicMock()

    # Configure client to throw 429 on generate_content
    quota_exception = Exception("429 RESOURCE_EXHAUSTED {'retryDelay': '300s'}")
    svc._client.models.generate_content.side_effect = quota_exception

    # First call encounters quota exhaustion
    with pytest.raises(GeminiQuotaExceededError) as exc_info:
        svc.generate_text("Test prompt")
    assert svc.is_quota_exhausted() is True
    assert exc_info.value.retry_delay_seconds == 300.0

    # Second call must immediately raise GeminiQuotaExceededError WITHOUT calling the client!
    svc._client.models.generate_content.reset_mock()
    with pytest.raises(GeminiQuotaExceededError) as exc_cooldown:
        svc.generate_text("Second prompt during cooldown")

    # Verify client was NOT called during active cooldown
    svc._client.models.generate_content.assert_not_called()
    assert "temporarily unavailable" in str(exc_cooldown.value)

    # Cooldown reset restores ability to attempt calls
    svc.reset_quota_cooldown()
    assert svc.is_quota_exhausted() is False

# ==============================================================================
# 5. Grounded Tutor Behavior: No Fake Grounded Answers on Quota Failure
# ==============================================================================

def test_grounded_tutor_handles_quota_without_fake_answer():
    """
    Requirements 5 & 6: Live generation failures must not silently produce a fake answer
    or invent citations. Must return structured is_error=True with quota_exceeded.
    """
    tutor = GroundedTutorService()
    mock_retrieved = [{
        "id": "c1",
        "filename": "Lecture_01.pdf",
        "source_type": "pdf",
        "page_number": 2,
        "slide_number": None,
        "start_timestamp": None,
        "end_timestamp": None,
        "content": "Supervised learning uses labeled training examples.",
        "hybrid_score": 0.85,
        "topic": "Supervised Learning",
        "concept": "Hypothesis"
    }]

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True):
            with patch(
                "app.services.tutor.grounded_tutor.gemini_service.generate_text",
                side_effect=GeminiQuotaExceededError(
                    retry_delay_seconds=600.0,
                    retry_after_human="in about 10 minutes"
                )
            ):
                req = TutorQueryRequest(course_id="test_course", query="What is supervised learning?")
                res = tutor.answer_query(req)

                # Must NOT claim grounding or fabricate citations
                assert res.is_grounded is False
                assert len(res.citations) == 0
                assert res.is_error is True
                assert res.error_type == "quota_exceeded"
                assert res.retry_after == "in about 10 minutes"
                assert "Live AI generation is temporarily unavailable" in res.answer
                # Must NOT be misclassified as an unsupported course topic
                assert res.unsupported_reason is None

def test_grounded_tutor_handles_quota_during_retrieval():
    """When dense vector retrieval encounters quota limits, cleanly return quota error."""
    tutor = GroundedTutorService()
    with patch(
        "app.services.tutor.grounded_tutor.hybrid_retriever.retrieve",
        side_effect=GeminiQuotaExceededError(
            retry_delay_seconds=120.0,
            retry_after_human="in about 2 minutes"
        )
    ):
        req = TutorQueryRequest(course_id="test_course", query="Explain gradient descent")
        res = tutor.answer_query(req)

        assert res.is_grounded is False
        assert len(res.citations) == 0
        assert res.is_error is True
        assert res.error_type == "quota_exceeded"
        assert "Live AI generation is temporarily unavailable" in res.answer

# ==============================================================================
# 6. Assessment Router & Generator Quota Handling
# ==============================================================================

def test_assessment_generation_router_quota_error_response():
    """Assessment generation returns HTTP 429 with sanitized friendly detail on quota failure."""
    with patch(
        "app.routers.assessment.assessment_service.generate_assessment",
        side_effect=GeminiQuotaExceededError(
            retry_delay_seconds=300.0,
            retry_after_human="in about 5 minutes"
        )
    ):
        res = client.post("/api/assessments/generate", json={
            "course_id": "test_course",
            "question_count": 3
        })
        assert res.status_code == 429
        data = res.json()
        assert "temporarily unavailable" in data["detail"]
        assert "300" in res.headers.get("retry-after", "")

def test_assessment_generation_stops_repeated_retries_on_quota():
    """When GeminiQuotaExceededError occurs, generator immediately aborts question loop."""
    service = AssessmentService()
    mock_chunks = [{
        "id": "c1", "filename": "Test.pdf", "content": "Sample content",
        "topic": "Topic 1", "concept": "Concept 1", "source_type": "pdf"
    }]

    with patch("app.services.assessment.generator.storage.get_chunks_for_course", return_value=mock_chunks):
        with patch(
            "app.services.assessment.generator.gemini_service.generate_text",
            side_effect=GeminiQuotaExceededError()
        ):
            with patch("app.services.assessment.generator.gemini_service.is_configured", return_value=True):
                from app.models.schema import AssessmentGenerateRequest
                req = AssessmentGenerateRequest(course_id="c1", question_count=5)
                with pytest.raises(GeminiQuotaExceededError):
                    service.generate_assessment(req)

# ==============================================================================
# 7. Non-Quota Error Handling Preserved
# ==============================================================================

def test_non_quota_error_propagation_and_sanitization():
    """Non-quota errors (e.g. 500 internal errors) are properly sanitized and not masked as quota."""
    tutor = GroundedTutorService()
    mock_retrieved = [{
        "id": "c1", "filename": "Test.pdf", "content": "Sample content",
        "topic": "Topic 1", "source_type": "pdf"
    }]

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True):
            with patch(
                "app.services.tutor.grounded_tutor.gemini_service.generate_text",
                side_effect=RuntimeError("Upstream server timeout after 30 seconds")
            ):
                req = TutorQueryRequest(course_id="test_course", query="What is regression?")
                res = tutor.answer_query(req)

                assert res.is_error is True
                assert res.error_type == "service_error"
                assert "AI Tutor service error:" in res.answer
                assert "upstream server timeout" in res.answer.lower()


# ==============================================================================
# 8. Phase C — Critical Quota Safety & Adversarial Benchmark Verification
# ==============================================================================

def test_quota_exception_actual_gemini_service_path_explicit_error():
    """
    Phase C Requirement 1 & 2:
    A quota exception from the actual Gemini service path results in an explicit
    sanitized quota error with is_grounded=False, citations=[], and no sensitive leak.
    """
    svc = GeminiService()
    svc.api_key = "test_quota_key"
    svc._client = MagicMock()
    # Provider returns HTTP 429 quota exhaustion
    svc._client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded")

    mock_retrieved = [{
        "id": "c1",
        "filename": "Lecture_02.pptx",
        "source_type": "pptx",
        "slide_number": 4,
        "content": "Gradient descent parameter update rule.",
        "hybrid_score": 0.90,
        "topic": "Optimization",
        "concept": "Gradient Descent"
    }]

    tutor = GroundedTutorService()
    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service", svc):
            req = TutorQueryRequest(course_id="test_course", query="Explain gradient descent.")
            res = tutor.answer_query(req)

            # Must fail-closed without claiming grounding
            assert res.is_grounded is False
            assert len(res.citations) == 0
            assert res.is_error is True
            assert res.error_type == "quota_exceeded"
            assert "temporarily unavailable" in res.answer
            assert "RESOURCE_EXHAUSTED" not in res.answer
            assert "429" not in res.answer

    svc.reset_quota_cooldown()


def test_adversarial_quota_case_fails_if_fake_grounded_answer_returned():
    """
    Phase C Requirement 3:
    The benchmark's adversarial quota case fails if any fake grounded answer
    or fabricated citations are returned on quota failure.
    """
    from app.services.evaluation.benchmark import evaluation_pipeline
    from app.models.schema import TutorQueryResponse

    # Simulate a buggy tutor that wrongly returned a fake grounded answer during quota exhaustion
    fake_answer = TutorQueryResponse(
        answer="Gradient descent updates parameters iteratively.",
        is_grounded=True,
        citations=[],
        is_error=False
    )
    with patch("app.services.evaluation.benchmark.grounded_tutor.answer_query", return_value=fake_answer):
        results = evaluation_pipeline.run_adversarial_suite(course_id="cs229", dry_run=True)
        assert results["adv_quota_error_handling"]["passed"] is False
        assert "Silently produced fake grounded answer" in results["adv_quota_error_handling"]["details"]


def test_adversarial_quota_case_passes_on_explicit_quota_error():
    """
    Phase C Requirement 3 & 4:
    The benchmark's adversarial quota case passes when the live Gemini quota error
    is properly handled with fail-closed behavior (5/5 PASS).
    """
    from app.services.evaluation.benchmark import evaluation_pipeline

    results = evaluation_pipeline.run_adversarial_suite(course_id="cs229", dry_run=True)
    assert results["adv_quota_error_handling"]["passed"] is True
    assert all(r["passed"] for r in results.values()), "All 5 adversarial scenarios must pass"


def test_normal_successful_live_generation_response():
    """
    Phase C Requirement 5:
    A normal successful live-generation response still produces grounded answers with citations.
    """
    tutor = GroundedTutorService()
    mock_retrieved = [{
        "id": "c1",
        "filename": "Lecture_01.pdf",
        "source_type": "pdf",
        "page_number": 2,
        "content": "Supervised learning maps inputs to outputs.",
        "hybrid_score": 0.88,
        "topic": "Supervised Learning",
        "concept": "Hypothesis"
    }]

    valid_llm_json = json.dumps({
        "answer": "Supervised learning learns a hypothesis function from training examples.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [1],
        "insufficient_evidence_reason": None
    })

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved), \
         patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True), \
         patch("app.services.tutor.grounded_tutor.gemini_service.generate_text", return_value=valid_llm_json):
        req = TutorQueryRequest(course_id="test_course", query="What is supervised learning?")
        res = tutor.answer_query(req)

        assert res.is_grounded is True
        assert res.is_error is False
        assert len(res.citations) == 1
        assert res.citations[0].source_file == "Lecture_01.pdf"
        assert res.citations[0].page_number == 2

