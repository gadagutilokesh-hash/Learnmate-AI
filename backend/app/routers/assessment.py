from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from app.models.schema import (
    AssessmentGenerateRequest, AssessmentResponse, QuizSubmissionRequest,
    QuizSubmissionResponse
)
from app.services.assessment.generator import assessment_service
from app.db.storage import storage
from app.core.auth import get_optional_user
from app.core.gemini import (
    GeminiQuotaExceededError, is_gemini_quota_error,
    GeminiServiceUnavailableError, is_gemini_transient_error,
    get_friendly_quota_message, get_friendly_service_unavailable_message,
    extract_gemini_retry_delay, sanitize_error
)

router = APIRouter(prefix="/assessments", tags=["Assessments"])

@router.post("/generate", response_model=AssessmentResponse)
def generate_assessment(
    req: AssessmentGenerateRequest,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    # Check course authorization
    course = storage.get_course(req.course_id)
    if course and not storage.is_course_accessible(course["id"], user_id=user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    # If user is authenticated, strictly bind user_id to session user
    if optional_user:
        req.user_id = optional_user["id"]

    try:
        return assessment_service.generate_assessment(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GeminiQuotaExceededError as e:
        headers = {}
        if e.retry_delay_seconds:
            headers["Retry-After"] = str(int(e.retry_delay_seconds))
        raise HTTPException(status_code=429, detail=e.message, headers=headers or None)
    except GeminiServiceUnavailableError as e:
        headers = {}
        if getattr(e, "retry_delay_seconds", None):
            headers["Retry-After"] = str(int(e.retry_delay_seconds))
        raise HTTPException(status_code=503, detail=e.message, headers=headers or None)
    except RuntimeError as e:
        if is_gemini_quota_error(e):
            delay_sec, human = extract_gemini_retry_delay(e)
            friendly = get_friendly_quota_message(e, retry_after_human=human)
            headers = {}
            if delay_sec:
                headers["Retry-After"] = str(int(delay_sec))
            raise HTTPException(status_code=429, detail=friendly, headers=headers or None)
        if is_gemini_transient_error(e):
            delay_sec, human = extract_gemini_retry_delay(e)
            friendly = get_friendly_service_unavailable_message(e, retry_after_human=human)
            headers = {}
            if delay_sec:
                headers["Retry-After"] = str(int(delay_sec))
            raise HTTPException(status_code=503, detail=friendly, headers=headers or None)
        raise HTTPException(status_code=502, detail=sanitize_error(e))

@router.post("/{assessment_id}/start", response_model=AssessmentResponse)
def start_assessment(
    assessment_id: str,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    assessment = storage.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Verify ownership
    if optional_user:
        if assessment.get("user_id") != optional_user["id"] and optional_user.get("role") != "admin":
            raise HTTPException(status_code=404, detail="Assessment not found")

    res = storage.start_assessment(assessment_id)
    return AssessmentResponse(**res)

@router.post("/submit", response_model=QuizSubmissionResponse)
def submit_quiz(
    req: QuizSubmissionRequest,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    assessment = storage.get_assessment(req.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if optional_user:
        if assessment.get("user_id") != optional_user["id"] and optional_user.get("role") != "admin":
            raise HTTPException(status_code=404, detail="Assessment not found")
        req.user_id = optional_user["id"]

    try:
        return assessment_service.grade_and_diagnose(req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: str,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    assessment = storage.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if optional_user:
        if assessment.get("user_id") != optional_user["id"] and optional_user.get("role") != "admin":
            raise HTTPException(status_code=404, detail="Assessment not found")

    return AssessmentResponse(**assessment)

@router.get("/{assessment_id}/answers", response_model=List[Dict[str, Any]])
def get_assessment_answers(
    assessment_id: str,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    assessment = storage.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if optional_user:
        if assessment.get("user_id") != optional_user["id"] and optional_user.get("role") != "admin":
            raise HTTPException(status_code=404, detail="Assessment not found")

    return storage.get_assessment_answers(assessment_id)

@router.get("", response_model=List[AssessmentResponse])
def list_assessments(
    user_id: str = "student_default",
    limit: int = 10,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    target_user_id = optional_user["id"] if optional_user else user_id
    assessments = storage.list_assessments(user_id=target_user_id, limit=limit)
    return [AssessmentResponse(**a) for a in assessments]
