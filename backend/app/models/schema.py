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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

# ==============================================================================
# Adaptive Assessments & Diagnosis
# ==============================================================================
class AssessmentGenerateRequest(BaseModel):
    course_id: str
    user_id: str = "student_default"
    topics: Optional[List[str]] = None
    difficulty: str = "adaptive"  # "beginner", "intermediate", "advanced", "adaptive"
    assessment_type: str = "adaptive_quiz"  # "diagnostic", "adaptive_quiz", "practice"
    question_count: int = 5

class AssessmentQuestion(BaseModel):
    id: str
    topic_name: str
    question_type: str  # "mcq", "short_answer", "numerical"
    prompt: str
    options: Optional[List[str]] = None  # For MCQ
    correct_answer: str
    explanation: str
    citation: Citation
    student_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    feedback: Optional[str] = None

class MisconceptionItem(BaseModel):
    topic_name: str
    misconception: str
    remediation_advice: str
    recommended_reading: Citation

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

class QuizSubmissionResponse(BaseModel):
    assessment_id: str
    score: float
    total_questions: int
    correct_count: int
    graded_questions: List[QuizGradedQuestion]
    mastery_updates: Dict[str, float]  # {topic_name: new_mastery}
    misconceptions: List[MisconceptionItem]
    recommended_next_steps: List[str]

# ==============================================================================
# Learner Model & Progress
# ==============================================================================
class TopicMastery(BaseModel):
    topic_name: str
    mastery_score: float  # 0.0 to 1.0
    p_transit: float = 0.15
    p_guess: float = 0.20
    p_slip: float = 0.10
    attempts_count: int = 0
    correct_count: int = 0
    status: str  # "needs_practice", "in_progress", "mastered"

class LearnerProfileResponse(BaseModel):
    user_id: str
    name: str
    overall_mastery: float
    topics: List[TopicMastery]
    weak_topics: List[str]
    strong_topics: List[str]
    recent_assessments: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_activities: List[Dict[str, Any]] = Field(default_factory=list)

# ==============================================================================
# Evaluation Suite
# ==============================================================================
class EvaluationRunRequest(BaseModel):
    course_id: Optional[str] = None
    dataset_type: str = "comprehensive"  # "grounded", "multi_source", "diagram", "unsupported", "comprehensive"
    num_test_cases: int = 10
    simulate_students: bool = True

class EvaluationMetrics(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    question_repetition_rate: float
    grounded_accuracy: float
    unsupported_rejection_rate: float
    citation_precision: float

class EvaluationRunResponse(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_name: str
    dataset_type: str
    total_eval_samples: int
    metrics: EvaluationMetrics
    simulation_results: Dict[str, Any]
    sample_evaluations: List[Dict[str, Any]]
