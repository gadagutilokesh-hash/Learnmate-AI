import pytest
import time
import uuid
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.gemini import (
    GeminiService, GeminiQuotaExceededError, GeminiServiceUnavailableError,
    is_gemini_quota_error, is_gemini_transient_error,
    get_friendly_service_unavailable_message, extract_gemini_retry_delay,
    sanitize_error
)
from app.db.storage import storage
from app.routers.ingestion import process_document_task
from app.services.tutor.grounded_tutor import grounded_tutor
from app.models.schema import TutorQueryRequest, AssessmentGenerateRequest

client = TestClient(app)


# ==============================================================================
# 1. Transient 503 Detection & Differentiation
# ==============================================================================
def test_is_gemini_transient_error_detects_503_signatures():
    """Verify 503, SERVICE_UNAVAILABLE, and model overload signatures are detected."""
    assert is_gemini_transient_error(Exception("503 Service Unavailable"))
    assert is_gemini_transient_error(Exception("SERVICE_UNAVAILABLE"))
    assert is_gemini_transient_error(Exception("This model is currently experiencing high demand. Spikes in demand are usually temporary."))
    assert is_gemini_transient_error(Exception("The model is overloaded. Please try again later."))
    assert is_gemini_transient_error(GeminiServiceUnavailableError())

    # HTTP status code inspection
    err_code = Exception("Provider error")
    err_code.status_code = 503
    assert is_gemini_transient_error(err_code)


def test_429_quota_error_is_never_treated_as_transient_503():
    """
    Requirement 4: Do not retry 429 quota-exhaustion errors as if they were
    ordinary 503 overload errors.
    """
    err_429 = Exception("429 RESOURCE_EXHAUSTED: Rate limit exceeded")
    assert is_gemini_quota_error(err_429)
    assert not is_gemini_transient_error(err_429)

    quota_custom = GeminiQuotaExceededError("Usage limit reached")
    assert not is_gemini_transient_error(quota_custom)


# ==============================================================================
# 2. Retry Logic: 503 Followed by Success & Exhaustion
# ==============================================================================
def test_503_followed_by_success():
    """
    Requirement 9: A 503 followed by success.
    Verify exponential backoff retries transient 503 and returns successfully.
    """
    svc = GeminiService()
    svc._client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Diagram illustrates backpropagation flow through layers."

    # First attempt raises 503; second attempt succeeds
    err_503 = Exception("503 Service Unavailable: Model is currently experiencing high demand.")
    svc._client.models.generate_content.side_effect = [err_503, mock_resp]

    with patch("time.sleep") as mock_sleep, \
         patch.object(svc, "is_configured", return_value=True):
        result = svc.generate_multimodal_description(
            image_bytes=b"fake_image_bytes",
            mime_type="image/png",
            prompt="Explain this diagram."
        )

        assert result == "Diagram illustrates backpropagation flow through layers."
        assert svc._client.models.generate_content.call_count == 2
        assert mock_sleep.call_count == 1  # Slept once before retry


def test_repeated_503_exhausts_retry_limit():
    """
    Requirement 9: Repeated 503 responses exhausting the retry limit.
    Verify bounded retries (max 3 retries = 4 attempts total) and raises GeminiServiceUnavailableError.
    """
    svc = GeminiService()
    svc._client = MagicMock()
    err_503 = Exception("503 Service Unavailable: High demand.")
    svc._client.models.generate_content.side_effect = err_503

    with patch("time.sleep") as mock_sleep, \
         patch.object(svc, "is_configured", return_value=True):
        with pytest.raises(GeminiServiceUnavailableError) as exc_info:
            svc.generate_multimodal_description(
                image_bytes=b"fake_image_bytes",
                mime_type="image/png"
            )

        assert "temporarily unavailable due to high model demand" in str(exc_info.value)
        # 1 initial attempt + 3 retries = 4 total calls
        assert svc._client.models.generate_content.call_count == 4
        assert mock_sleep.call_count == 3


def test_429_quota_error_does_not_enter_503_retry_loop():
    """
    Requirement 9: A 429 quota error that does not enter the 503 retry loop.
    Verify immediate abort with cooldown set.
    """
    svc = GeminiService()
    svc._client = MagicMock()
    err_429 = Exception("429 RESOURCE_EXHAUSTED: Daily request quota exceeded.")
    svc._client.models.generate_content.side_effect = err_429

    with patch("time.sleep") as mock_sleep, \
         patch.object(svc, "is_configured", return_value=True):
        with pytest.raises(GeminiQuotaExceededError) as exc_info:
            svc.generate_text("Explain gradient descent.")

        assert "reached its current usage limit" in str(exc_info.value)
        # Quota error must abort immediately on 1st attempt with NO retries
        assert svc._client.models.generate_content.call_count == 1
        assert mock_sleep.call_count == 0
        assert svc.is_quota_exhausted()


def test_unrelated_exception_does_not_retry():
    """
    Requirement 9: An unrelated exception (e.g. 403 Forbidden).
    Verify immediate abort with RuntimeError and zero retries.
    """
    svc = GeminiService()
    svc._client = MagicMock()
    err_403 = Exception("403 Forbidden: The caller does not have permission")
    svc._client.models.generate_content.side_effect = err_403

    with patch("time.sleep") as mock_sleep, \
         patch.object(svc, "is_configured", return_value=True):
        with pytest.raises(RuntimeError) as exc_info:
            svc.generate_text("Explain gradient descent.")

        assert "Gemini live generation failed" in str(exc_info.value)
        assert svc._client.models.generate_content.call_count == 1
        assert mock_sleep.call_count == 0


# ==============================================================================
# 3. Sanitized Error Messaging & Credential Redaction
# ==============================================================================
def test_sanitized_service_unavailable_redacts_credentials_and_urls():
    """
    Requirement 7: Do not expose raw provider payloads, secrets, or stack traces.
    """
    raw_error = Exception(
        "503 Service Unavailable at https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5?key=AIzaSyD1234567890123456789012345678901 "
        "Bearer secret_token_xyz: High demand"
    )
    sanitized = sanitize_error(raw_error)
    assert "AIza" not in sanitized
    assert "secret_token" not in sanitized
    assert "generativelanguage.googleapis.com" not in sanitized
    assert "temporarily unavailable due to high model demand" in sanitized


def test_service_unavailable_message_with_provider_retry_delay():
    """
    Requirement 4: Respect provider retry metadata when available.
    """
    err = Exception("503 Service Unavailable: retry in 2m")
    msg = get_friendly_service_unavailable_message(err)
    assert "temporarily unavailable due to high model demand" in msg
    assert "in about 2 minutes" in msg


# ==============================================================================
# 4. Course Ingestion: Persistence, Safe Retry, and No Duplicate Chunks
# ==============================================================================
def test_document_persistence_and_safe_retry_after_ai_fails():
    """
    Requirement 6 & 9:
    - Uploaded document is persisted before AI processing.
    - AI failure records clear failed status without marking complete.
    - Safe retry succeeds after AI service recovers.
    """
    course = storage.create_course(f"Ingestion Hardening Test {uuid.uuid4().hex[:6]}")
    course_id = course["id"]

    # Create dummy PDF file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Chapter 1: Foundations of Deep Learning.\nGradient descent iteratively optimizes model parameters.")
        temp_file_path = f.name

    try:
        # Create document record
        doc = storage.create_document(
            course_id=course_id,
            filename="lecture1.txt",
            file_type="pdf",
            file_path=temp_file_path
        )
        doc_id = doc["id"]

        # Step 1: Document is persisted in DB immediately
        persisted = storage.get_document(doc_id)
        assert persisted is not None
        assert persisted["ingestion_status"] == "pending"

        # Step 2: Simulate failure during AI processing (e.g. 503 Service Unavailable)
        with patch("app.routers.ingestion.pdf_parser.parse", side_effect=GeminiServiceUnavailableError("High demand")):
            process_document_task(doc_id, temp_file_path, "pdf", course_id, "General")

        failed_doc = storage.get_document(doc_id)
        assert failed_doc["ingestion_status"] == "failed"
        assert "temporarily unavailable due to high model demand" in failed_doc["error_message"]
        # Must NOT be marked completed
        assert failed_doc["chunks_count"] == 0

        # Step 3: Service recovers, retry processing succeeds
        mock_chunk = MagicMock()
        mock_chunk.content = "Gradient descent minimizes empirical risk through gradient steps."
        mock_chunk.chunk_type = "text"
        mock_chunk.source_type = "pdf"
        mock_chunk.page_number = 1
        mock_chunk.slide_number = None
        mock_chunk.start_timestamp = None
        mock_chunk.end_timestamp = None
        mock_chunk.topic = "Optimization"
        mock_chunk.concept = "Gradient Descent"
        mock_chunk.metadata = {}

        with patch("app.routers.ingestion.pdf_parser.parse", return_value=([mock_chunk], 1)), \
             patch("app.core.gemini.gemini_service.get_embedding", return_value=[0.1] * 768):
            process_document_task(doc_id, temp_file_path, "pdf", course_id, "Optimization")

        completed_doc = storage.get_document(doc_id)
        assert completed_doc["ingestion_status"] == "completed"
        assert completed_doc["error_message"] is None
        assert completed_doc["chunks_count"] == 1

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        storage.delete_course(course_id)


def test_no_duplicate_document_chunks_or_embeddings_on_resume():
    """
    Requirement 6 & 9:
    Ensure transient AI failures do not create duplicate documents, chunks,
    or embeddings when processing resumes.
    """
    course = storage.create_course(f"Idempotency Test {uuid.uuid4().hex[:6]}")
    course_id = course["id"]
    try:
        doc = storage.create_document(course_id, "slides.pdf", "pdf", "/tmp/slides.pdf")
        doc_id = doc["id"]

        mock_chunk = MagicMock()
        mock_chunk.content = "Slide 1 Content"
        mock_chunk.chunk_type = "text"
        mock_chunk.source_type = "pdf"
        mock_chunk.page_number = 1
        mock_chunk.slide_number = None
        mock_chunk.start_timestamp = None
        mock_chunk.end_timestamp = None
        mock_chunk.topic = "Basics"
        mock_chunk.concept = "Intro"
        mock_chunk.metadata = {}

        with patch("app.routers.ingestion.pdf_parser.parse", return_value=([mock_chunk], 1)), \
             patch("app.core.gemini.gemini_service.get_embedding", return_value=[0.05] * 768):

            # Run 1: Successful processing
            process_document_task(doc_id, "/tmp/slides.pdf", "pdf", course_id, "Basics")
            doc_after_1 = storage.get_document(doc_id)
            assert doc_after_1["chunks_count"] == 1

            # Run 2: Resume / Retry processing on the same document
            process_document_task(doc_id, "/tmp/slides.pdf", "pdf", course_id, "Basics")
            doc_after_2 = storage.get_document(doc_id)

            # Must still be exactly 1 chunk, NOT 2 chunks!
            assert doc_after_2["chunks_count"] == 1
    finally:
        storage.delete_course(course_id)


# ==============================================================================
# 5. Live Tutor & Assessment Flows Under 503 Errors
# ==============================================================================
def test_grounded_tutor_handles_503_without_fake_answer():
    """
    Requirement 5: Ensure a failed call does not silently produce fabricated content.
    Requirement 8: Distinguish temporary service unavailability from quota exhaustion.
    """
    with patch("app.core.gemini.gemini_service.generate_text", side_effect=GeminiServiceUnavailableError("Model overloaded")):
        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="", query="Explain backpropagation.", top_k=2)
        )

        assert not res.is_grounded, "Must not claim grounded when 503 fails"
        assert len(res.citations) == 0, "Must not produce fake citations on 503 error"
        assert res.is_error is True
        assert res.error_type == "service_unavailable"
        assert "temporarily unavailable due to high model demand" in res.answer


def test_assessment_router_503_service_unavailable_response():
    """
    Requirement 7 & 8: Assessment generation returns HTTP 503 on model overload.
    """
    with patch("app.services.assessment.generator.assessment_service.generate_assessment",
               side_effect=GeminiServiceUnavailableError("Model overloaded")):
        response = client.post("/api/assessments/generate", json={
            "course_id": "test_course",
            "assessment_type": "adaptive_quiz",
            "question_count": 3
        })
        assert response.status_code == 503
        data = response.json()
        assert "temporarily unavailable due to high model demand" in data["detail"]
