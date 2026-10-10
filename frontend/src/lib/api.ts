import {
  HealthStatus, Course, DocumentItem, TutorResponse, Assessment,
  QuizSubmissionResult, LearnerProfile, EvaluationRun
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {})
    }
  });
  if (!res.ok) {
    let errMessage = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      errMessage = err.detail || err.message || errMessage;
    } catch (_) {}
    throw new Error(errMessage);
  }
  return res.json();
}

export const api = {
  // Health
  getHealth: (): Promise<HealthStatus> => fetchJson(`${API_BASE_URL}/health`),

  // Courses
  listCourses: (): Promise<Course[]> => fetchJson(`${API_BASE_URL}/courses`),
  getCourse: (courseId: string): Promise<Course> => fetchJson(`${API_BASE_URL}/courses/${courseId}`),
  createCourse: (title: string, description: string): Promise<Course> =>
    fetchJson(`${API_BASE_URL}/courses`, {
      method: "POST",
      body: JSON.stringify({ title, description })
    }),

  // Documents & Ingestion
  listDocuments: (courseId: string): Promise<DocumentItem[]> =>
    fetchJson(`${API_BASE_URL}/courses/${courseId}/documents`),
  getDocument: (documentId: string): Promise<DocumentItem> =>
    fetchJson(`${API_BASE_URL}/documents/${documentId}`),
  uploadDocument: async (courseId: string, file: File, topic: string = "General Foundations"): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("topic", topic);
    const res = await fetch(`${API_BASE_URL}/courses/${courseId}/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      let errMessage = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        errMessage = err.detail || errMessage;
      } catch (_) {}
      throw new Error(errMessage);
    }
    return res.json();
  },
  retryDocument: (documentId: string): Promise<DocumentItem> =>
    fetchJson(`${API_BASE_URL}/documents/${documentId}/retry`, { method: "POST" }),

  // Grounded Tutor
  askTutor: (courseId: string, query: string, topK: number = 5): Promise<TutorResponse> =>
    fetchJson(`${API_BASE_URL}/tutor/query`, {
      method: "POST",
      body: JSON.stringify({ course_id: courseId, query, top_k: topK })
    }),

  // Adaptive Assessments
  generateAssessment: (params: {
    courseId: string;
    userId?: string;
    topics?: string[];
    difficulty?: string;
    assessmentType?: string;
    questionCount?: number;
  }): Promise<Assessment> =>
    fetchJson(`${API_BASE_URL}/assessments/generate`, {
      method: "POST",
      body: JSON.stringify({
        course_id: params.courseId,
        user_id: params.userId || "student_default",
        topics: params.topics,
        difficulty: params.difficulty || "adaptive",
        assessment_type: params.assessmentType || "adaptive_quiz",
        question_count: params.questionCount || 5
      })
    }),
  getAssessment: (assessmentId: string): Promise<Assessment> =>
    fetchJson(`${API_BASE_URL}/assessments/${assessmentId}`),
  listAssessments: (userId: string = "student_default"): Promise<Assessment[]> =>
    fetchJson(`${API_BASE_URL}/assessments?user_id=${userId}`),
  submitQuiz: (assessmentId: string, answers: { question_id: string; student_answer: string }[], userId: string = "student_default"): Promise<QuizSubmissionResult> =>
    fetchJson(`${API_BASE_URL}/assessments/submit`, {
      method: "POST",
      body: JSON.stringify({
        assessment_id: assessmentId,
        user_id: userId,
        answers
      })
    }),

  // Learner Model
  getLearnerProfile: (userId: string = "student_default"): Promise<LearnerProfile> =>
    fetchJson(`${API_BASE_URL}/learner/profile?user_id=${userId}`),

  // Evaluation
  runEvaluation: (courseId?: string, datasetType: string = "comprehensive"): Promise<EvaluationRun> =>
    fetchJson(`${API_BASE_URL}/evaluation/run`, {
      method: "POST",
      body: JSON.stringify({ course_id: courseId, dataset_type: datasetType })
    }),
  listEvaluationRuns: (): Promise<EvaluationRun[]> =>
    fetchJson(`${API_BASE_URL}/evaluation/runs`)
};
