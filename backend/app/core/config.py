from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    APP_NAME: str = "LearnMate AI Backend"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

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

    # Storage paths
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    UPLOADS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")

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

settings = Settings()
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
