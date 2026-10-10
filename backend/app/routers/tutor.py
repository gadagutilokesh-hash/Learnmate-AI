from fastapi import APIRouter
from app.models.schema import TutorQueryRequest, TutorQueryResponse
from app.services.tutor.grounded_tutor import grounded_tutor

router = APIRouter(prefix="/tutor", tags=["Grounded Tutor"])

@router.post("/query", response_model=TutorQueryResponse)
def answer_tutor_query(req: TutorQueryRequest):
    return grounded_tutor.answer_query(req)
