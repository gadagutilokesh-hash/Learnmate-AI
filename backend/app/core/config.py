from pydantic_settings import BaseSettings
from pydantic import model_validator, field_validator
from typing import List, Optional, Any
import os
import tempfile
import logging
import uuid

logger = logging.getLogger(__name__)

def is_path_in_source_tree(target_path: Optional[str]) -> bool:
    """Checks whether a given filesystem path is located inside the application source tree."""
    if not target_path:
        return False
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_dir = os.path.dirname(backend_dir)
        abs_target = os.path.abspath(target_path)

        for root in (backend_dir, project_dir):
            try:
                common = os.path.commonpath([abs_target, root])
                if common == root:
                    return True
            except (ValueError, OSError):
                continue
        return False
    except (ValueError, OSError):
        return False

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

    @property
    def is_production(self) -> bool:
        env = (self.ENVIRONMENT or "").lower().strip()
        vercel_env = os.environ.get("VERCEL_ENV", "").lower().strip()
        return env == "production" or vercel_env == "production"

    @property
    def is_render(self) -> bool:
        return bool(
            os.environ.get("RENDER") in ("true", "1")
            or os.environ.get("RENDER_SERVICE_ID")
            or os.environ.get("RENDER_INSTANCE_ID")
        )

    @property
    def is_serverless(self) -> bool:
        return bool(
            os.environ.get("VERCEL") == "1"
            or "AWS_LAMBDA_FUNCTION_NAME" in os.environ
            or os.environ.get("VERCEL_ENV")
            or os.environ.get("IS_SERVERLESS", "").lower() in ("1", "true", "yes")
        )

    @model_validator(mode="after")
    def resolve_storage_paths(self) -> "Settings":
        """
        Dynamically and deterministically configures storage paths based on environment.
        1. If DATA_DIR is explicitly configured, use it.
        2. In serverless environments (Vercel / AWS Lambda), default to ephemeral /tmp.
        3. If a persistent disk is mounted (e.g. /var/data or /data exists), use that mount path.
        4. Otherwise (local development or container without persistent disk), default to backend/data.
        CRITICAL: Never execute os.makedirs() or disk operations during Settings validation!
        """
        if self.DATA_DIR is not None:
            self.DATA_DIR = os.path.abspath(os.path.expanduser(self.DATA_DIR))
        else:
            if self.is_serverless:
                self.DATA_DIR = os.path.join(tempfile.gettempdir(), "learnmate_data")
            elif os.path.isdir("/var/data"):
                # Render persistent disk mounted at standard /var/data mount path
                self.DATA_DIR = "/var/data"
            elif os.path.isdir("/data") and not is_path_in_source_tree("/data"):
                # Alternative standard persistent disk mount path
                self.DATA_DIR = "/data"
            else:
                # Default to project data directory
                self.DATA_DIR = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data"
                )

        if self.UPLOADS_DIR is not None:
            self.UPLOADS_DIR = os.path.abspath(os.path.expanduser(self.UPLOADS_DIR))
        else:
            if self.is_serverless:
                self.UPLOADS_DIR = os.path.join(tempfile.gettempdir(), "learnmate_uploads")
            else:
                self.UPLOADS_DIR = os.path.join(self.DATA_DIR, "uploads")

        return self

    @property
    def has_persistent_disk(self) -> bool:
        """True if storage is located on a persistent host outside the source tree (not serverless /tmp)."""
        if self.is_serverless or not self.DATA_DIR:
            return False
        # Ephemeral temp directory is not persistent disk
        temp_dir = tempfile.gettempdir()
        try:
            if os.path.commonpath([os.path.abspath(self.DATA_DIR), os.path.abspath(temp_dir)]) == os.path.abspath(temp_dir):
                return False
        except (ValueError, OSError):
            pass
        # In production or on Render, persistent disk must reside outside source tree
        if (self.is_production or self.is_render) and is_path_in_source_tree(self.DATA_DIR):
            return False
        return True

    @property
    def has_persistent_storage(self) -> bool:
        return bool(
            self.DATABASE_URL
            or (self.SUPABASE_URL and self.SUPABASE_KEY)
            or (self.has_persistent_disk and not self.is_serverless)
        )

    @property
    def storage_mode(self) -> str:
        if self.DATABASE_URL or (self.SUPABASE_URL and self.SUPABASE_KEY):
            return "supabase"
        if self.is_serverless or self.ALLOW_EPHEMERAL_STORAGE:
            return "local_ephemeral"
        return "local_embedded"

settings = Settings()

def ensure_storage_dirs() -> None:
    """
    Ensures that data and upload directories exist and are writable.
    Must ONLY be invoked at runtime (e.g., during startup/lifespan or explicit request processing),
    and NEVER during module import.
    """
    for dir_path, label in [(settings.DATA_DIR, "Data directory"), (settings.UPLOADS_DIR, "Uploads directory")]:
        if not dir_path:
            continue
        try:
            os.makedirs(dir_path, exist_ok=True)
            test_probe = os.path.join(dir_path, f".write_probe_{uuid.uuid4().hex}")
            with open(test_probe, "w") as f:
                f.write("probe")
            os.remove(test_probe)
        except OSError as e:
            logger.error(f"Could not create or write to {label} ({dir_path}): {e}")
            raise RuntimeError(
                f"{label} '{dir_path}' could not be created or is not writable: {e}. "
                "If running on Render with a persistent disk, ensure the disk is mounted at the configured path."
            ) from e
