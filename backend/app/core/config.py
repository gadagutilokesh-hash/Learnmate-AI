from pydantic_settings import BaseSettings
from pydantic import model_validator, field_validator
from typing import List, Optional, Any
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    APP_NAME: str = "LearnMate AI Backend"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://learnmate-ai-peach.vercel.app"
    ]

    # Multi-provider AI configuration
    AI_PROVIDER: str = "gemini"  # "gemini" | "groq" | "nvidia"

    # Authentication & Session Security
    AUTH_SECRET_KEY: str = "learnmate-secret-auth-key-2026-phase-prod"
    SESSION_EXPIRE_HOURS: int = 72
    ADMIN_EMAIL: str = "admin@learnmate.ai"
    ADMIN_INITIAL_PASSWORD: str = "Admin@LearnMate2026"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Gemini AI configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_MULTIMODAL_MODEL: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768

    # GroqCloud configuration (https://console.groq.com/)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # NVIDIA Nemotron configuration (https://build.nvidia.com/)
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/llama-3.1-nemotron-70b-instruct"

    # Supabase / DB configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    # Storage paths and serverless ephemeral controls
    DATA_DIR: Optional[str] = None
    UPLOADS_DIR: Optional[str] = None
    ALLOW_EPHEMERAL_STORAGE: bool = False

    # Retrieval settings
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    HYBRID_ALPHA: float = 0.5
    TOP_K_RETRIEVAL: int = 5
    MIN_RELEVANCE_SCORE: float = 0.35

    # Bayesian Knowledge Tracing (BKT) Parameters
    BKT_DEFAULT_PRIOR: float = 0.15
    BKT_DEFAULT_TRANSIT: float = 0.15
    BKT_DEFAULT_GUESS: float = 0.20
    BKT_DEFAULT_SLIP: float = 0.10

    # Spaced Repetition Parameters
    SPACED_REPETITION_DEFAULT_INTERVAL_DAYS: float = 1.0
    SPACED_REPETITION_MAX_INTERVAL_DAYS: float = 30.0

    model_config = {
        "env_file": (
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
            ".env"
        ),
        "extra": "allow"
    }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            origins = [o.strip() for o in v.split(",") if o.strip()]
        elif isinstance(v, (list, tuple, set)):
            origins = [str(o).strip() for o in v if str(o).strip()]
        else:
            origins = [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "https://learnmate-ai-peach.vercel.app"
            ]
        if "https://learnmate-ai-peach.vercel.app" not in origins:
            origins.append("https://learnmate-ai-peach.vercel.app")
        return origins

    @model_validator(mode="after")
    def resolve_storage_paths(self) -> "Settings":
        """
        Dynamically configures storage paths based on environment.
        In serverless or read-only deployments (such as Vercel / AWS Lambda),
        default to an ephemeral temporary directory (/tmp) so the application
        never attempts to create directories or write files in the read-only deployment tree.
        CRITICAL: Never execute os.makedirs() or disk operations during Settings validation!
        """
        if self.DATA_DIR is None:
            if self.is_serverless:
                self.DATA_DIR = os.path.join(tempfile.gettempdir(), "learnmate_data")
            else:
                self.DATA_DIR = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "data"
                )

        if self.UPLOADS_DIR is None:
            if self.is_serverless:
                self.UPLOADS_DIR = os.path.join(tempfile.gettempdir(), "learnmate_uploads")
            else:
                self.UPLOADS_DIR = os.path.join(self.DATA_DIR, "uploads")

        return self

    @property
    def is_production(self) -> bool:
        env = (self.ENVIRONMENT or "").lower().strip()
        vercel_env = os.environ.get("VERCEL_ENV", "").lower().strip()
        return env == "production" or vercel_env == "production"

    @property
    def is_serverless(self) -> bool:
        return bool(
            os.environ.get("VERCEL") == "1"
            or "AWS_LAMBDA_FUNCTION_NAME" in os.environ
            or os.environ.get("VERCEL_ENV")
            or os.environ.get("IS_SERVERLESS", "").lower() in ("1", "true", "yes")
        )

    @property
    def has_persistent_storage(self) -> bool:
        return bool(self.DATABASE_URL or (self.SUPABASE_URL and self.SUPABASE_KEY))

    @property
    def storage_mode(self) -> str:
        if self.has_persistent_storage:
            return "supabase"
        if self.is_serverless or self.ALLOW_EPHEMERAL_STORAGE:
            return "local_ephemeral"
        return "local_embedded"

settings = Settings()

def ensure_storage_dirs() -> None:
    """
    Ensures that data and upload directories exist.
    Must ONLY be invoked at runtime (e.g., during startup/lifespan or explicit request processing),
    and NEVER during module import.
    """
    try:
        if settings.DATA_DIR:
            os.makedirs(settings.DATA_DIR, exist_ok=True)
        if settings.UPLOADS_DIR:
            os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create storage directories ({settings.DATA_DIR}, {settings.UPLOADS_DIR}): {e}")
        raise
