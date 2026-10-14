from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models.schema import EvaluationRunRequest, EvaluationRunResponse
from app.services.evaluation.benchmark import evaluation_pipeline
from app.db.storage import storage
from app.core.auth import get_optional_user

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(
    req: EvaluationRunRequest,
    optional_user: Optional[dict] = Depends(get_optional_user)
):
    if req.course_id:
        user_id = optional_user["id"] if optional_user else None
        is_admin = (optional_user.get("role") == "admin") if optional_user else False
        if not storage.is_course_accessible(req.course_id, user_id=user_id, is_admin=is_admin):
            raise HTTPException(status_code=404, detail="Course not found")

    return evaluation_pipeline.run_evaluation(
        course_id=req.course_id,
        dataset_type=req.dataset_type,
        dry_run=req.dry_run
    )

@router.get("/runs", response_model=List[EvaluationRunResponse])
def list_evaluation_runs(limit: int = 10):
    runs = storage.list_evaluation_runs(limit=limit)
    return [EvaluationRunResponse(**r) for r in runs]

@router.get("/benchmark-cases")
def list_benchmark_cases(dataset_type: str = "comprehensive"):
    cases = evaluation_pipeline.get_benchmark_dataset(dataset_type)
    return {
        "dataset_version": "v2.0",
        "total_cases": len(cases),
        "cases": cases
    }
