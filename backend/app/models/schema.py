from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

# ==============================================================================
# Health & Status
# ==============================================================================
class HealthResponse(BaseModel):
    status: str
    app_name: str
    gemini_configured: bool
    supabase_configured: bool
    storage_mode: str  # "supabase" or "local_embedded"
    gemini_model: Optional[str] = None
    gemini_embedding_model: Optional[str] = None
    gemini_live_verified: Optional[bool] = None
    active_provider: Optional[str] = "gemini"
    active_model: Optional[str] = None
    provider_configured: Optional[bool] = False
    provider_capabilities: Optional[Dict[str, bool]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==============================================================================
# User Accounts & Authentication
# ==============================================================================
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str = "user"  # "admin" | "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: str
    password: str

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ==============================================================================
# Course & Document Ingestion
# ==============================================================================
class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = ""

class CourseResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = ""
    owner_id: Optional[str] = None
    visibility: str = "private"  # "shared_demo" | "private"
    is_demo: bool = False
    documents_count: int = 0
    topics_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Citation(BaseModel):
    source_file: str
    source_type: str  # "pdf", "pptx", "mp4", "audio"
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    excerpt: str
    relevance_score: Optional[float] = None
    topic: Optional[str] = None
    concept: Optional[str] = None

class DocumentChunk(BaseModel):
    id: str
    document_id: str
    course_id: str
    chunk_index: int
    content: str
    chunk_type: str = "text"  # "text", "table", "diagram", "transcript"
    source_type: str  # "pdf", "pptx", "mp4"
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    topic: Optional[str] = None
    concept: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentResponse(BaseModel):
    id: str
    course_id: str
    filename: str
    file_type: str
    ingestion_status: str  # "pending", "processing", "completed", "failed"
    error_message: Optional[str] = None
    total_pages_or_slides: Optional[int] = None
    duration_seconds: Optional[float] = None
    chunks_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==============================================================================
# Grounded AI Tutor
# ==============================================================================
class TutorQueryRequest(BaseModel):
    course_id: str
    query: str
    chat_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    top_k: int = 5
    strict_grounding: bool = True

class TutorQueryResponse(BaseModel):
    answer: str
    is_grounded: bool
    citations: List[Citation] = Field(default_factory=list)
    unsupported_reason: Optional[str] = None
    external_context_notes: Optional[str] = None
    suggested_followups: List[str] = Field(default_factory=list)
    is_error: bool = False
    error_type: Optional[str] = None
    retry_after: Optional[str] = None

# ==============================================================================
# Adaptive Assessments & Diagnosis
# ==============================================================================
class AssessmentGenerateRequest(BaseModel):
    course_id: str
    user_id: str = "student_default"
    topics: Optional[List[str]] = None
    concepts: Optional[List[str]] = None
    difficulty: str = "adaptive"  # "beginner", "intermediate", "advanced", "adaptive", "mixed"
    assessment_type: str = "adaptive_quiz"  # "diagnostic", "adaptive_quiz", "practice"
    question_count: int = 5
    question_type: Optional[str] = "mixed"  # "mixed", "mcq", "short_answer", "numerical"
    allow_revision: bool = False

class AssessmentQuestion(BaseModel):
    id: str
    topic_name: str
    concept: Optional[str] = None
    question_type: str  # "mcq", "short_answer", "numerical"
    prompt: str
    options: Optional[List[str]] = None  # For MCQ
    correct_answer: str
    explanation: str
    citation: Citation
    difficulty: Optional[str] = "medium"
    numerical_tolerance: Optional[float] = None
    numerical_unit: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    fingerprint: Optional[str] = None
    student_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    feedback: Optional[str] = None

class MisconceptionItem(BaseModel):
    topic_name: str
    misconception: str
    remediation_advice: str
    recommended_reading: Citation
    observed_mistake: Optional[str] = None

class AssessmentResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    title: str
    assessment_type: str
    difficulty: str
    total_questions: int
    score: Optional[float] = None
    status: str
    questions: List[AssessmentQuestion]
    misconceptions: List[MisconceptionItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class QuizSubmissionItem(BaseModel):
    question_id: str
    student_answer: str

class QuizSubmissionRequest(BaseModel):
    assessment_id: str
    user_id: str = "student_default"
    answers: List[QuizSubmissionItem]

class QuizGradedQuestion(BaseModel):
    question_id: str
    prompt: str
    student_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str
    citation: Citation
    partial_score: Optional[float] = None
    grading_method: Optional[str] = None
    feedback: Optional[str] = None

class QuizSubmissionResponse(BaseModel):
    assessment_id: str
    score: float
    total_questions: int
    correct_count: int
    graded_questions: List[QuizGradedQuestion]
    mastery_updates: Dict[str, float]  # {topic_name: new_mastery}
    misconceptions: List[MisconceptionItem]
    recommended_next_steps: List[str]
    topic_performance: Optional[Dict[str, Dict[str, Any]]] = None
    weak_concepts: Optional[List[str]] = None
    completed_at: Optional[datetime] = None

# ==============================================================================
# Learner Model & Progress
# ==============================================================================
class TopicMastery(BaseModel):
    topic_name: str
    mastery_score: float  # 0.0 to 1.0 (Latent BKT belief P(L))
    p_transit: float = 0.15
    p_guess: float = 0.20
    p_slip: float = 0.10
    attempts_count: int = 0
    correct_count: int = 0
    status: str  # "needs_practice", "in_progress", "mastered", "unassessed"
    last_attempt_at: Optional[str] = None
    next_review_at: Optional[str] = None
    review_interval_days: Optional[float] = 1.0
    consecutive_correct: Optional[int] = 0
    repetition_count: Optional[int] = 0
    is_overdue: Optional[bool] = False
    days_overdue: Optional[float] = 0.0
    overdue_reason: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)

class MasteryHistoryRecord(BaseModel):
    id: str
    user_id: str
    topic_name: str
    assessment_id: Optional[str] = None
    mastery_score: float
    previous_score: float
    is_correct: Optional[bool] = None
    score_delta: float
    observed_score: Optional[float] = None
    p_transit: float
    p_guess: float
    p_slip: float
    recorded_at: str

class RecommendedActivity(BaseModel):
    id: str
    type: str  # "review_source", "practice_quiz", "prerequisite_study", "spaced_revision", "challenge_assessment"
    priority: str  # "urgent", "high", "medium", "normal"
    title: str
    description: str
    action: str  # "tutor", "quiz"
    topic: str
    reason: str
    citation: Optional[Citation] = None
    source_citation: Optional[Citation] = None

class StudyPlanItem(BaseModel):
    day_number: int = 1
    day_offset: Optional[int] = None
    date: str = ""  # YYYY-MM-DD
    suggested_date: Optional[str] = None
    topic_name: str = ""
    topic: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    activity_type: str = "concept_review"
    suggested_duration_minutes: int = 30
    reason: str = ""
    citation: Optional[Citation] = None
    source_citation: Optional[Citation] = None
    priority: str = "normal"

class StudyPlanRequest(BaseModel):
    user_id: str = "student_default"
    course_id: Optional[str] = None
    target_exam_date: Optional[str] = None
    daily_study_minutes: int = 30

class StudyPlanResponse(BaseModel):
    user_id: str
    is_provisional: bool
    target_exam_date: Optional[str] = None
    daily_study_minutes: int
    total_days: int
    total_study_hours: float
    items: List[StudyPlanItem] = Field(default_factory=list)
    schedule: List[StudyPlanItem] = Field(default_factory=list)
    provisional_notice: Optional[str] = None
    weak_topics_addressed: List[str] = Field(default_factory=list)
    overdue_topics_scheduled: List[str] = Field(default_factory=list)
    notes: str = ""

class LearnerProfileResponse(BaseModel):
    user_id: str
    name: str
    overall_mastery: float
    is_new_learner: bool = False
    topics: List[TopicMastery]
    weak_topics: List[str]
    strong_topics: List[str]
    upcoming_reviews: List[TopicMastery] = Field(default_factory=list)
    recent_assessments: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[MasteryHistoryRecord] = Field(default_factory=list)
    recommended_activities: List[RecommendedActivity] = Field(default_factory=list)
    study_plan: Optional[StudyPlanResponse] = None

# ==============================================================================
# Evaluation Suite
# ==============================================================================
class EvaluationRunRequest(BaseModel):
    course_id: Optional[str] = None
    dataset_type: str = "comprehensive"  # "grounded", "multi_source", "diagram", "unsupported", "comprehensive"
    num_test_cases: int = 12
    simulate_students: bool = True
    dry_run: bool = False
    benchmark_version: str = "v2.0"

class EvaluationMetrics(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    question_repetition_rate: float
    grounded_accuracy: float
    unsupported_rejection_rate: float
    citation_precision: float
    recall_at_k: Optional[float] = None
    precision_at_k: Optional[float] = None
    mrr: Optional[float] = None
    citation_source_accuracy: Optional[float] = None
    citation_location_accuracy: Optional[float] = None
    metric_breakdowns: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

class EvaluationRunResponse(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_name: str
    dataset_type: str
    dataset_version: str = "v2.0"
    is_dry_run: bool = True
    evaluation_mode: str = "dry_run"
    total_eval_samples: int = 12
    metrics: EvaluationMetrics
    simulation_results: Dict[str, Any] = Field(default_factory=dict)
    learner_evaluations: Optional[Dict[str, Any]] = Field(default_factory=dict)
    adversarial_results: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sample_evaluations: List[Dict[str, Any]] = Field(default_factory=list)
