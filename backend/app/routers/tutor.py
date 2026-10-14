from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.models.schema import TutorQueryRequest, TutorQueryResponse
from app.services.tutor.grounded_tutor import grounded_tutor
from app.db.storage import storage
from app.core.auth import get_optional_user

router = APIRouter(prefix="/tutor", tags=["Grounded Tutor"])

@router.post("/query", response_model=TutorQueryResponse)
def answer_tutor_query(
    req: TutorQueryRequest,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    if not req.course_id:
        raise HTTPException(status_code=400, detail="A valid course_id is required")

    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False

    # Check course authorization: visitors can access shared_demo courses,
    # authenticated users can access shared_demo and their own courses.
    if not storage.is_course_accessible(req.course_id, user_id=user_id, is_admin=is_admin):
        # Prevent IDOR: reject without revealing course existence
        raise HTTPException(status_code=404, detail="Course not found")

    return grounded_tutor.answer_query(req)
