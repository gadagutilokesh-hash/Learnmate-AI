from fastapi import APIRouter
from typing import List
from app.models.schema import EvaluationRunRequest, EvaluationRunResponse
from app.services.evaluation.benchmark import evaluation_pipeline
from app.db.storage import storage

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(req: EvaluationRunRequest):
    return evaluation_pipeline.run_evaluation(
        course_id=req.course_id,
        dataset_type=req.dataset_type
    )

@router.get("/runs", response_model=List[EvaluationRunResponse])
def list_evaluation_runs(limit: int = 10):
    runs = storage.list_evaluation_runs(limit=limit)
    return [EvaluationRunResponse(**r) for r in runs]
