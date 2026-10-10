from fastapi import APIRouter
from app.models.schema import LearnerProfileResponse
from app.services.learner.mastery_model import mastery_service

router = APIRouter(prefix="/learner", tags=["Learner Model"])

@router.get("/profile", response_model=LearnerProfileResponse)
def get_learner_profile(user_id: str = "student_default"):
    return mastery_service.get_learner_profile(user_id=user_id)
