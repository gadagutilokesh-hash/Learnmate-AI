export interface HealthStatus {
  status: string;
  app_name: string;
  gemini_configured: boolean;
  active_provider?: string;
  active_model?: string;
  provider_configured?: boolean;
  supabase_configured: boolean;
  storage_mode: string;
  timestamp: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Course {
  id: string;
  title: string;
  description: string;
  owner_id?: string | null;
  visibility?: "shared_demo" | "private" | string;
  is_demo?: boolean;
  documents_count: number;
  topics_count: number;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  course_id: string;
  filename: string;
  file_type: "pdf" | "pptx" | "ppt" | "mp4" | "audio";
  ingestion_status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
  total_pages_or_slides?: number;
  duration_seconds?: number;
  chunks_count: number;
  created_at: string;
}

export interface Citation {
  source_file: string;
  source_type: string;
  page_number?: number;
  slide_number?: number;
  start_timestamp?: string;
  end_timestamp?: string;
  excerpt: string;
  relevance_score?: number;
  topic?: string;
  concept?: string;
}

export interface TutorResponse {
  answer: string;
  is_grounded: boolean;
  citations: Citation[];
  unsupported_reason?: string;
  external_context_notes?: string;
  suggested_followups: string[];
  is_error?: boolean;
  error_type?: string;
  retry_after?: string;
}

export interface AssessmentQuestion {
  id: string;
  topic_name: string;
  concept?: string;
  question_type: "mcq" | "short_answer" | "numerical";
  prompt: string;
  options?: string[];
  correct_answer: string;
  explanation: string;
  citation: Citation;
  difficulty?: string;
  numerical_tolerance?: number;
  numerical_unit?: string;
  student_answer?: string;
  is_correct?: boolean;
}

export interface MisconceptionItem {
  topic_name: string;
  misconception: string;
  remediation_advice: string;
  recommended_reading: Citation;
  observed_mistake?: string;
}

export interface Assessment {
  id: string;
  course_id: string;
  user_id: string;
  title: string;
  assessment_type: "diagnostic" | "adaptive_quiz" | "practice";
  difficulty: "beginner" | "intermediate" | "advanced" | "adaptive";
  total_questions: number;
  score?: number;
  status: "generated" | "in_progress" | "completed";
  questions: AssessmentQuestion[];
  misconceptions: MisconceptionItem[];
  created_at: string;
}

export interface QuizSubmissionResult {
  assessment_id: string;
  score: number;
  total_questions: number;
  correct_count: number;
  graded_questions: {
    question_id: string;
    prompt: string;
    student_answer: string;
    correct_answer: string;
    is_correct: boolean;
    explanation: string;
    citation: Citation;
    partial_score?: number;
    grading_method?: string;
    feedback?: string;
  }[];
  mastery_updates: Record<string, number>;
  misconceptions: MisconceptionItem[];
  recommended_next_steps: string[];
  topic_performance?: Record<string, {
    correct: number;
    total: number;
    percentage: number;
    current_mastery?: number;
  }>;
  weak_concepts?: string[];
}

export interface TopicMastery {
  topic_name: string;
  mastery_score: number;
  p_transit: number;
  p_guess: number;
  p_slip: number;
  attempts_count: number;
  correct_count: number;
  status: "needs_practice" | "in_progress" | "mastered" | "unassessed";
  last_attempt_at?: string;
  next_review_at?: string;
  review_interval_days?: number;
  consecutive_correct?: number;
  repetition_count?: number;
  is_overdue?: boolean;
  days_overdue?: number;
  prerequisites?: string[];
}

export interface MasteryHistoryRecord {
  id: string;
  user_id: string;
  topic_name: string;
  assessment_id?: string;
  mastery_score: number;
  previous_score: number;
  is_correct?: boolean;
  score_delta: number;
  observed_score?: number;
  p_transit: number;
  p_guess: number;
  p_slip: number;
  recorded_at: string;
}

export interface RecommendedActivity {
  type: string;
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  action: "tutor" | "quiz" | "course";
  topic: string;
  reason?: string;
  source_citation?: Citation;
}

export interface StudyPlanItem {
  day_offset: number;
  suggested_date: string;
  topic: string;
  suggested_duration_minutes: number;
  activity_type: "review" | "diagnostic" | "quiz" | "practice" | "concept_review";
  title: string;
  description: string;
  reason: string;
  source_citation?: Citation;
}

export interface StudyPlanResponse {
  user_id: string;
  course_id?: string;
  target_exam_date?: string;
  daily_study_minutes: number;
  total_estimated_days: number;
  is_provisional: boolean;
  provisional_notice?: string;
  schedule: StudyPlanItem[];
  generated_at: string;
}

export interface LearnerProfile {
  user_id: string;
  name: string;
  overall_mastery: number;
  is_new_learner?: boolean;
  topics: TopicMastery[];
  weak_topics: string[];
  strong_topics: string[];
  recent_assessments: Assessment[];
  recommended_activities: RecommendedActivity[];
  upcoming_reviews?: TopicMastery[];
  history?: MasteryHistoryRecord[];
  study_plan?: StudyPlanResponse | null;
}

export interface MetricBreakdown {
  numerator: number;
  denominator: number;
  num_cases: number;
  description: string;
}

export interface LearnerProfileRegression {
  profile_name: string;
  passed: boolean;
  expected_behavior: string;
  actual_behavior: string;
  details: string;
}

export interface AdversarialScenarioResult {
  scenario: string;
  passed: boolean;
  details: string;
}

export interface SampleEvaluation {
  id?: string;
  category: string;
  question: string;
  is_supported: boolean;
  should_abstain?: boolean;
  is_grounded: boolean;
  retrieval_hit?: boolean;
  first_rank?: number;
  expected_document?: string;
  expected_location?: Record<string, string | number>;
  citations_count: number;
  citations?: Citation[];
  answer_preview: string;
  faithfulness: number;
  context_recall: number;
  abstention_correct?: boolean;
}

export interface EvaluationMetrics {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  question_repetition_rate: number;
  grounded_accuracy: number;
  unsupported_rejection_rate: number;
  citation_precision: number;
  recall_at_k?: number;
  precision_at_k?: number;
  mrr?: number;
  citation_source_accuracy?: number;
  citation_location_accuracy?: number;
  metric_breakdowns?: Record<string, MetricBreakdown>;
}

export interface EvaluationRun {
  id: string;
  timestamp: string;
  run_name: string;
  dataset_type: string;
  dataset_version?: string;
  is_dry_run?: boolean;
  evaluation_mode?: "dry_run" | "live" | string;
  total_eval_samples: number;
  metrics: EvaluationMetrics;
  simulation_results: Record<string, {
    initial_mastery: number;
    final_mastery: number;
    mastery_trajectory: number[];
    sessions_completed: number;
    status: string;
  }>;
  learner_evaluations?: Record<string, LearnerProfileRegression>;
  adversarial_results?: Record<string, AdversarialScenarioResult>;
  sample_evaluations: SampleEvaluation[];
}
