from fastapi import APIRouter
from app.models.schema import HealthResponse
from app.core.config import settings
from app.core.gemini import gemini_service
from app.core.ai_provider import get_ai_provider

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", response_model=HealthResponse)
def get_health():
    is_gemini_cfg = gemini_service.is_gemini_configured()
    try:
        provider = get_ai_provider()
        provider_name = provider.provider_name
        provider_model = provider.model_name
        provider_cfg = provider.is_configured()
        provider_caps = provider.get_capabilities()
    except Exception:
        provider_name = getattr(settings, "AI_PROVIDER", "gemini")
        provider_model = None
        provider_cfg = False
        provider_caps = None

    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        gemini_configured=is_gemini_cfg,
        gemini_model=gemini_service.model_name if is_gemini_cfg else None,
        gemini_embedding_model=gemini_service.embedding_model_name if is_gemini_cfg else None,
        gemini_live_verified=gemini_service._verified_live,
        supabase_configured=bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        storage_mode=settings.storage_mode,
        active_provider=provider_name,
        active_model=provider_model,
        provider_configured=provider_cfg,
        provider_capabilities=provider_caps
    )

@router.get("/verify-gemini")
def verify_gemini_connection():
    """
    Explicit diagnostic endpoint to verify live Gemini connectivity without exposing secrets.
    """
    return gemini_service.test_connectivity()

@router.get("/verify-provider")
def verify_provider_connection():
    """
    Explicit diagnostic endpoint to verify configured active AI provider connectivity without exposing secrets.
    """
    return get_ai_provider().test_connectivity()
