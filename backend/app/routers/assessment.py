from fastapi import APIRouter, HTTPException
from typing import List, Optional
from app.models.schema import (
    AssessmentGenerateRequest, AssessmentResponse, QuizSubmissionRequest,
    QuizSubmissionResponse
)
from app.services.assessment.generator import assessment_service
from app.db.storage import storage

router = APIRouter(prefix="/assessments", tags=["Assessments"])

@router.post("/generate", response_model=AssessmentResponse)
def generate_assessment(req: AssessmentGenerateRequest):
    return assessment_service.generate_assessment(req)

@router.post("/submit", response_model=QuizSubmissionResponse)
def submit_quiz(req: QuizSubmissionRequest):
    try:
        return assessment_service.grade_and_diagnose(req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: str):
    assessment = storage.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return AssessmentResponse(**assessment)

@router.get("", response_model=List[AssessmentResponse])
def list_assessments(user_id: str = "student_default", limit: int = 10):
    assessments = storage.list_assessments(user_id=user_id, limit=limit)
    return [AssessmentResponse(**a) for a in assessments]
