import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import health, auth, courses, ingestion, tutor, assessment, learner, evaluation
from app.db.storage import storage
from app.core.gemini import gemini_service
from app.core.auth import hash_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("LearnMateAI")

from contextlib import asynccontextmanager

def validate_storage_configuration(cfg=None):
    """
    Validates storage configuration at application startup.
    In a serverless production environment (such as Vercel), local SQLite database files and
    local upload directories are ephemeral (/tmp) and cannot be shared across serverless function instances.
    Persistent learner accounts, courses, embeddings, and assessments require persistent storage.

    In a container production environment (such as Render), persistent disks (mounted e.g. at /var/data)
    preserve SQLite databases across restarts and redeployments. If no persistent disk is configured,
    the application logs an explicit warning that SQLite data and uploads will not survive restarts/redeployments.
    """
    s = cfg or settings
    if s.is_production:
        if s.is_serverless:
            if not s.has_persistent_storage and not s.ALLOW_EPHEMERAL_STORAGE:
                error_msg = (
                    "Production startup aborted: Required persistent storage is not configured.\n"
                    "LearnMate AI currently uses SQLite and local file storage. "
                    "In a serverless production environment (such as Vercel), local files and SQLite databases "
                    "are ephemeral (/tmp) and cannot be shared across serverless function instances.\n"
                    "User accounts, courses, embeddings, assessments, and uploaded documents will not persist.\n"
                    "Action required:\n"
                    "  1. Configure a persistent external database (set SUPABASE_URL and SUPABASE_KEY, or DATABASE_URL).\n"
                    "  2. Configure cloud object storage (e.g., AWS S3, Supabase Storage, Cloudflare R2) for uploads.\n"
                    "  3. To bypass this check strictly for temporary preview or testing on Vercel, set the environment variable:\n"
                    "     ALLOW_EPHEMERAL_STORAGE=true\n"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)
            elif not s.has_persistent_storage and s.ALLOW_EPHEMERAL_STORAGE:
                logger.warning(
                    "⚠️ RUNNING WITH EPHEMERAL STORAGE IN PRODUCTION/SERVERLESS: "
                    "ALLOW_EPHEMERAL_STORAGE=true is active. SQLite database (%s) and uploads (%s) "
                    "are stored in temporary storage (/tmp). Data WILL NOT persist across serverless instances, "
                    "cold starts, or new deployments. Do not use this for real learner accounts or production persistence.",
                    s.DATA_DIR,
                    s.UPLOADS_DIR
                )
        else:
            # Container production (Render, Docker, etc.)
            if not s.has_persistent_storage:
                db_target = os.path.join(s.DATA_DIR, "learnmate.db") if s.DATA_DIR else "unknown"
                logger.warning(
                    "⚠️ RENDER / CONTAINER PERSISTENCE NOTICE: No persistent disk detected or configured. "
                    "SQLite database (%s) and uploads (%s) are using container storage. "
                    "Data and uploaded files will not survive service restarts, redeployments, or instance rebuilds. "
                    "To persist data across deployments on Render, attach a persistent disk (mounted at /var/data) "
                    "or set DATA_DIR to your disk mount path, or configure SUPABASE_URL / DATABASE_URL.",
                    db_target,
                    s.UPLOADS_DIR
                )
            else:
                logger.info(
                    "Persistent storage verified for production. Data dir: %s | Uploads dir: %s",
                    s.DATA_DIR,
                    s.UPLOADS_DIR
                )
    else:
        logger.info(
            f"Storage mode: {s.storage_mode} | Environment: {s.ENVIRONMENT} | "
            f"Data dir: {s.DATA_DIR} | Uploads dir: {s.UPLOADS_DIR}"
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Validate storage configuration
    validate_storage_configuration()

    # 2. Ensure storage directories exist at runtime for local/ephemeral execution
    from app.core.config import ensure_storage_dirs
    try:
        ensure_storage_dirs()
    except Exception as e:
        logger.error(f"Failed to ensure storage directories: {e}")
        if settings.is_production and not settings.ALLOW_EPHEMERAL_STORAGE:
            raise

    # 3. Explicitly initialize storage database schema
    try:
        storage._init_db()
    except Exception as e:
        logger.critical(f"Failed to initialize storage database: {e}")
        if settings.is_production and not settings.ALLOW_EPHEMERAL_STORAGE:
            raise

    # 4. Startup AI Provider Check
    from app.core.ai_provider import get_ai_provider
    try:
        provider = get_ai_provider()
        logger.info(
            f"Active AI Provider: '{provider.provider_name}' | Model: '{provider.model_name}' | "
            f"Configured: {provider.is_configured()}"
        )
    except Exception as e:
        logger.error(f"Startup AI provider configuration error: {e}")

    # 4. Bootstrap initial admin if not yet created
    try:
        if settings.ADMIN_EMAIL and settings.ADMIN_INITIAL_PASSWORD:
            admin_pwd_hash = hash_password(settings.ADMIN_INITIAL_PASSWORD)
            admin_id = storage.bootstrap_admin_user(
                email=settings.ADMIN_EMAIL,
                password_hash=admin_pwd_hash,
                full_name="System Administrator"
            )
            if admin_id:
                logger.info(f"Initial administrator account bootstrapped successfully: {settings.ADMIN_EMAIL}")
    except Exception as e:
        logger.error(f"Admin bootstrap error: {e}")

    try:
        startup_seed_demo_data()
    except Exception as e:
        logger.error(f"Startup demo data seeding error: {e}")

    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="LearnMate AI: Source-grounded multimodal study companion for Track D: Personalized Tutoring & Adaptive Learning",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
# Explicitly ensure frontend production origin is always permitted
cors_origins = list(settings.CORS_ORIGINS) if settings.CORS_ORIGINS else [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://learnmate-ai-peach.vercel.app"
]
if "https://learnmate-ai-peach.vercel.app" not in cors_origins:
    cors_origins.append("https://learnmate-ai-peach.vercel.app")

if settings.ENVIRONMENT.lower() == "production":
    logger.info(f"Production CORS strictly restricted to origins: {cors_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https:\/\/learnmate-ai.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    # Development mode: permit local frontend and preview origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://learnmate-ai-peach.vercel.app", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API Routers
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(ingestion.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")
app.include_router(assessment.router, prefix="/api")
app.include_router(learner.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")

@app.get("/health")
def root_health():
    """Alias for /api/health to support cloud platforms requesting root /health."""
    return health.get_health()

@app.get("/")
def root():
    return {
        "message": "Welcome to LearnMate AI API",
        "documentation": "/docs",
        "health": "/api/health",
        "gemini_ready": gemini_service.is_configured(),
        "storage_mode": settings.storage_mode
    }

def startup_seed_demo_data():
    """
    Seeds a high-quality demonstration course on Machine Learning Foundations if database is empty.
    This guarantees that the UI has immediate rich content with exact slide, page, and timestamp citations!
    """
    existing_courses = storage.list_courses()
    if not existing_courses:
        logger.info("Seeding initial demonstration course: 'CS229: Machine Learning & Deep Learning'...")
        course = storage.create_course(
            title="CS229: Machine Learning & Deep Learning",
            description="Comprehensive course covering supervised learning, gradient descent, neural networks, and multimodal architectures."
        )
        c_id = course["id"]

        # Seed Documents
        doc1 = storage.create_document(
            course_id=c_id,
            filename="Lecture_01_Supervised_Learning_Foundations.pdf",
            file_type="pdf",
            file_path=os.path.join(settings.UPLOADS_DIR, "Lecture_01.pdf")
        )
        storage.update_document(doc1["id"], status="completed", total_pages_or_slides=14)

        doc2 = storage.create_document(
            course_id=c_id,
            filename="Lecture_02_Optimization_and_Gradient_Descent.pptx",
            file_type="pptx",
            file_path=os.path.join(settings.UPLOADS_DIR, "Lecture_02.pptx")
        )
        storage.update_document(doc2["id"], status="completed", total_pages_or_slides=22)

        doc3 = storage.create_document(
            course_id=c_id,
            filename="Lecture_03_Neural_Network_Architectures.mp4",
            file_type="mp4",
            file_path=os.path.join(settings.UPLOADS_DIR, "Lecture_03.mp4")
        )
        storage.update_document(doc3["id"], status="completed", duration_seconds=900.0)

        # Seed Rich Grounded Chunks with exact provenance
        chunks = [
            {
                "document_id": doc1["id"],
                "course_id": c_id,
                "chunk_index": 0,
                "content": "Supervised learning formalizes the problem where the learner is provided with training examples consisting of input vectors and corresponding output targets. The goal is to estimate a hypothesis function h that generalizes accurately to unseen test instances.",
                "chunk_type": "text",
                "source_type": "pdf",
                "page_number": 2,
                "topic": "Supervised Learning",
                "concept": "Hypothesis Mapping",
                "embedding": gemini_service.get_embedding("Supervised learning hypothesis mapping input vectors targets"),
                "metadata": {"chapter": "Introduction"}
            },
            {
                "document_id": doc1["id"],
                "course_id": c_id,
                "chunk_index": 1,
                "content": "Feature normalization and standardization (z-score scaling) rescale data to zero mean and unit variance. This prevents gradient explosions, ensures isotropic loss contours, and drastically accelerates convergence in iterative optimization.",
                "chunk_type": "text",
                "source_type": "pdf",
                "page_number": 5,
                "topic": "Data Preprocessing",
                "concept": "Feature Normalization",
                "embedding": gemini_service.get_embedding("Feature normalization standardization z-score scaling gradient explosions"),
                "metadata": {"formula": "z = (x - mu) / sigma"}
            },
            {
                "document_id": doc1["id"],
                "course_id": c_id,
                "chunk_index": 2,
                "content": "[Diagram/Figure on Page 8]: Loss surface contour comparison showing elongated elliptical valleys for unnormalized features versus circular concentric contours for normalized features, illustrating how gradient vectors point directly towards the global minimum after standardization.",
                "chunk_type": "diagram",
                "source_type": "pdf",
                "page_number": 8,
                "topic": "Optimization Dynamics",
                "concept": "Loss Surface Geometry",
                "embedding": gemini_service.get_embedding("Diagram loss surface contour comparison unnormalized features concentric contours"),
                "metadata": {"figure": "Figure 1.3"}
            },
            {
                "document_id": doc2["id"],
                "course_id": c_id,
                "chunk_index": 0,
                "content": "Slide 4: Gradient Descent Update Rule. The parameter theta is updated iteratively according to theta := theta - alpha * grad(J(theta)), where alpha represents the learning rate. Setting alpha too large causes oscillations and divergence; setting alpha too small causes painfully slow convergence.",
                "chunk_type": "text",
                "source_type": "pptx",
                "slide_number": 4,
                "topic": "Gradient Descent",
                "concept": "Learning Rate Dynamics",
                "embedding": gemini_service.get_embedding("Gradient Descent update rule theta learning rate alpha divergence"),
                "metadata": {"slide_title": "Update Rule"}
            },
            {
                "document_id": doc2["id"],
                "course_id": c_id,
                "chunk_index": 1,
                "content": "Slide 11 Table: Comparison of Batch, Mini-batch, and Stochastic Gradient Descent. Batch computes full dataset gradients (exact but computationally intensive O(N)). Stochastic computes single sample updates (high variance, noisy). Mini-batch (typical size 32-256) balances vectorization efficiency with stochastic regularizing noise.",
                "chunk_type": "table",
                "source_type": "pptx",
                "slide_number": 11,
                "topic": "Optimization Algorithms",
                "concept": "Batch vs Stochastic",
                "embedding": gemini_service.get_embedding("Batch Mini-batch Stochastic Gradient Descent comparison table vectorization efficiency"),
                "metadata": {"table_name": "SGD Variants"}
            },
            {
                "document_id": doc3["id"],
                "course_id": c_id,
                "chunk_index": 0,
                "content": "Video Transcript [03:15 - 06:40]: In this lecture segment, Professor highlights that activation functions must introduce non-linearity. Without non-linear activations like ReLU or GELU, multiple stacked linear layers collapse mathematically into a single matrix multiplication, completely eliminating deep expressive capacity.",
                "chunk_type": "transcript",
                "source_type": "mp4",
                "start_timestamp": "03:15",
                "end_timestamp": "06:40",
                "topic": "Neural Network Architectures",
                "concept": "Activation Functions",
                "embedding": gemini_service.get_embedding("Activation functions non-linearity ReLU stacked linear layers deep expressive capacity"),
                "metadata": {"video_title": "Lecture 03 Video Recording"}
            },
            {
                "document_id": doc3["id"],
                "course_id": c_id,
                "chunk_index": 1,
                "content": "Video Transcript [08:20 - 11:45]: Addressing common student confusion around overfitting: Regularization techniques such as weight decay (L2 penalty) and dropout penalize complex hypothesis spaces. Always measure generalization error against a completely isolated validation split rather than training error.",
                "chunk_type": "transcript",
                "source_type": "mp4",
                "start_timestamp": "08:20",
                "end_timestamp": "11:45",
                "topic": "Generalization & Regularization",
                "concept": "L2 Regularization and Dropout",
                "embedding": gemini_service.get_embedding("Overfitting Regularization weight decay L2 penalty dropout validation split"),
                "metadata": {"video_title": "Lecture 03 Video Recording"}
            }
        ]

        storage.save_chunks(chunks)

        # Seed initial topic mastery for default student
        user_id = "student_default"
        storage.save_topic_mastery(user_id, "Supervised Learning", mastery_score=0.72, attempts_delta=4, correct_delta=3)
        storage.save_topic_mastery(user_id, "Data Preprocessing", mastery_score=0.85, attempts_delta=5, correct_delta=4)
        storage.save_topic_mastery(user_id, "Optimization Dynamics", mastery_score=0.42, attempts_delta=3, correct_delta=1)
        storage.save_topic_mastery(user_id, "Gradient Descent", mastery_score=0.60, attempts_delta=4, correct_delta=2)
        storage.save_topic_mastery(user_id, "Neural Network Architectures", mastery_score=0.35, attempts_delta=2, correct_delta=0)
        storage.save_topic_mastery(user_id, "Generalization & Regularization", mastery_score=0.50, attempts_delta=2, correct_delta=1)

        logger.info("Demo course and knowledge base seeded successfully.")
