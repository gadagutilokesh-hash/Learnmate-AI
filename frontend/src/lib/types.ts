export interface HealthStatus {
  status: string;
  app_name: string;
  gemini_configured: boolean;
  supabase_configured: boolean;
  storage_mode: string;
  timestamp: string;
}

export interface Course {
  id: string;
  title: string;
  description: string;
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
}

export interface AssessmentQuestion {
  id: string;
  topic_name: string;
  question_type: "mcq" | "short_answer" | "numerical";
  prompt: string;
  options?: string[];
  correct_answer: string;
  explanation: string;
  citation: Citation;
  student_answer?: string;
  is_correct?: boolean;
}

export interface MisconceptionItem {
  topic_name: string;
  misconception: string;
  remediation_advice: string;
  recommended_reading: Citation;
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
  }[];
  mastery_updates: Record<string, number>;
  misconceptions: MisconceptionItem[];
  recommended_next_steps: string[];
}

export interface TopicMastery {
  topic_name: string;
  mastery_score: number;
  p_transit: number;
  p_guess: number;
  p_slip: number;
  attempts_count: number;
  correct_count: number;
  status: "needs_practice" | "in_progress" | "mastered";
}

export interface LearnerProfile {
  user_id: string;
  name: string;
  overall_mastery: number;
  topics: TopicMastery[];
  weak_topics: string[];
  strong_topics: string[];
  recent_assessments: any[];
  recommended_activities: {
    type: string;
    priority: "high" | "medium" | "low";
    title: string;
    description: string;
    action: "tutor" | "quiz" | "course";
    topic: string;
  }[];
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
}

export interface EvaluationRun {
  id: string;
  timestamp: string;
  run_name: string;
  dataset_type: string;
  total_eval_samples: number;
  metrics: EvaluationMetrics;
  simulation_results: Record<string, {
    initial_mastery: number;
    final_mastery: number;
    mastery_trajectory: number[];
    sessions_completed: number;
    status: string;
  }>;
  sample_evaluations: any[];
}
