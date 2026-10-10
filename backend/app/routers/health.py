from fastapi import APIRouter
from app.models.schema import HealthResponse
from app.core.config import settings
from app.core.gemini import gemini_service

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", response_model=HealthResponse)
def get_health():
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        gemini_configured=gemini_service.is_configured(),
        supabase_configured=bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        storage_mode="supabase" if (settings.SUPABASE_URL and settings.SUPABASE_KEY) else "local_embedded"
    )
