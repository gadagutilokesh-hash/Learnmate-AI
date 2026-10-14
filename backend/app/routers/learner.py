from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from app.models.schema import (
    LearnerProfileResponse, MasteryHistoryRecord,
    StudyPlanRequest, StudyPlanResponse
)
from app.services.learner.mastery_model import mastery_service
from app.db.storage import storage
from app.core.auth import get_optional_user

router = APIRouter(prefix="/learner", tags=["Learner Model"])

@router.get("/profile", response_model=LearnerProfileResponse)
def get_learner_profile(
    user_id: str = "student_default",
    course_id: Optional[str] = None,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    effective_user_id = optional_user["id"] if optional_user else user_id
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    if course_id and not storage.is_course_accessible(course_id, user_id=effective_user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    return mastery_service.get_learner_profile(user_id=effective_user_id, course_id=course_id)

@router.get("/history", response_model=List[MasteryHistoryRecord])
def get_mastery_history(
    user_id: str = "student_default",
    topic_name: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    effective_user_id = optional_user["id"] if optional_user else user_id
    raw_history = storage.list_mastery_history(user_id=effective_user_id, topic_name=topic_name, limit=limit)
    return [MasteryHistoryRecord(**h) for h in raw_history]

@router.post("/study-plan", response_model=StudyPlanResponse)
def create_study_plan(
    req: StudyPlanRequest,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    effective_user_id = optional_user["id"] if optional_user else req.user_id
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    if req.course_id and not storage.is_course_accessible(req.course_id, user_id=effective_user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    req.user_id = effective_user_id
    return mastery_service.generate_study_plan(req)

@router.get("/study-plan", response_model=StudyPlanResponse)
def get_study_plan(
    user_id: str = "student_default",
    course_id: Optional[str] = None,
    target_exam_date: Optional[str] = None,
    daily_study_minutes: int = Query(default=30, ge=15, le=180),
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    effective_user_id = optional_user["id"] if optional_user else user_id
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    if course_id and not storage.is_course_accessible(course_id, user_id=effective_user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    req = StudyPlanRequest(
        user_id=effective_user_id,
        course_id=course_id,
        target_exam_date=target_exam_date,
        daily_study_minutes=daily_study_minutes
    )
    return mastery_service.generate_study_plan(req)

@router.get("/prerequisites", response_model=List[Dict[str, Any]])
def get_prerequisites(
    course_id: Optional[str] = None,
    topic_name: Optional[str] = None,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    effective_user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    if course_id and not storage.is_course_accessible(course_id, user_id=effective_user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    return storage.get_topic_prerequisites(course_id=course_id, topic_name=topic_name)
