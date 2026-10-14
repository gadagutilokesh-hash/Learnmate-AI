import {
  HealthStatus, Course, DocumentItem, TutorResponse, Assessment,
  QuizSubmissionResult, LearnerProfile, EvaluationRun,
  MasteryHistoryRecord, StudyPlanResponse, SampleEvaluation,
  User, AuthTokenResponse
} from "./types";

const rawBaseUrl = (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL)
  ? process.env.NEXT_PUBLIC_API_URL.trim()
  : "http://localhost:8000/api";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export const BACKEND_OFFLINE_NOTICE =
  "LearnMate AI backend service is currently offline or unreachable. Please verify that your backend server is deployed and NEXT_PUBLIC_API_URL is configured.";

export function isNetworkError(err: unknown): boolean {
  if (!err) return false;
  if (err instanceof TypeError) return true;
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    return msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("network error") || msg.includes("load failed");
  }
  return false;
}

export function isBackendConfigured(): boolean {
  if (typeof window === "undefined") {
    return Boolean(process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim() !== "");
  }
  const isLocalHost =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "[::1]";

  if (!isLocalHost) {
    const url = getApiBaseUrl().toLowerCase();
    // On remote domain, if API_BASE_URL points to localhost or is relative, it is unconfigured
    if (!process.env.NEXT_PUBLIC_API_URL || url.includes("localhost") || url.includes("127.0.0.1")) {
      return false;
    }
    if (url.startsWith("/") || url === window.location.origin.toLowerCase() + "/api") {
      return false;
    }
  }
  return true;
}

const TOKEN_KEY = "learnmate_auth_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options?.headers as Record<string, string> || {})
  };

  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      credentials: "include",
      headers
    });
  } catch (err: unknown) {
    if (isNetworkError(err)) {
      throw new Error(BACKEND_OFFLINE_NOTICE);
    }
    throw err instanceof Error ? err : new Error(String(err));
  }

  if (!res.ok) {
    let errMessage = `HTTP ${res.status}`;
    if (res.status === 404) {
      if (url.includes("/auth/")) {
        errMessage =
          "Authentication service is temporarily unavailable. The backend account endpoint was not found (HTTP 404). Please ensure your FastAPI backend is deployed and NEXT_PUBLIC_API_URL is configured.";
      } else {
        errMessage =
          "Backend service endpoint was not found (HTTP 404). Please verify that your FastAPI backend is deployed and NEXT_PUBLIC_API_URL is configured correctly.";
      }
    } else if (res.status === 502 || res.status === 503 || res.status === 504) {
      errMessage = `LearnMate AI backend is temporarily unavailable (HTTP ${res.status}). The service may be starting up or under maintenance.`;
    } else {
      try {
        const err = await res.json();
        errMessage = err.detail || err.message || errMessage;
      } catch {
        // Ignore JSON parse failure, use fallback status text
      }
    }
    throw new Error(errMessage);
  }
  return res.json();
}

export const api = {
  // Authentication
  register: async (email: string, password: string, fullName?: string): Promise<AuthTokenResponse> => {
    if (!isBackendConfigured()) {
      throw new Error(
        "Account registration is temporarily unavailable. The backend service has not been deployed yet. Please configure NEXT_PUBLIC_API_URL once your FastAPI backend is online."
      );
    }
    const res = await fetchJson<AuthTokenResponse>(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName })
    });
    if (res?.access_token) {
      setStoredToken(res.access_token);
    }
    return res;
  },

  login: async (email: string, password: string): Promise<AuthTokenResponse> => {
    if (!isBackendConfigured()) {
      throw new Error(
        "Sign in is temporarily unavailable. The backend service has not been deployed yet. Please configure NEXT_PUBLIC_API_URL once your FastAPI backend is online."
      );
    }
    const res = await fetchJson<AuthTokenResponse>(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    if (res?.access_token) {
      setStoredToken(res.access_token);
    }
    return res;
  },

  logout: async (): Promise<void> => {
    try {
      await fetchJson(`${API_BASE_URL}/auth/logout`, { method: "POST" });
    } catch {
      // Continue cleanup on network failure
    } finally {
      clearStoredToken();
    }
  },

  getMe: (): Promise<User> => fetchJson(`${API_BASE_URL}/auth/me`),

  // Health
  getHealth: (): Promise<HealthStatus> => fetchJson(`${API_BASE_URL}/health`),

  // Courses
  listCourses: (): Promise<Course[]> => fetchJson(`${API_BASE_URL}/courses`),
  getCourse: (courseId: string): Promise<Course> => fetchJson(`${API_BASE_URL}/courses/${courseId}`),
  getCourseTopics: (courseId: string): Promise<string[]> => fetchJson(`${API_BASE_URL}/courses/${courseId}/topics`),
  createCourse: (title: string, description: string): Promise<Course> =>
    fetchJson(`${API_BASE_URL}/courses`, {
      method: "POST",
      body: JSON.stringify({ title, description })
    }),
  deleteCourse: (courseId: string): Promise<{ deleted: boolean; course_id: string }> =>
    fetchJson(`${API_BASE_URL}/courses/${courseId}`, { method: "DELETE" }),

  // Documents & Ingestion
  listDocuments: (courseId: string): Promise<DocumentItem[]> =>
    fetchJson(`${API_BASE_URL}/courses/${courseId}/documents`),
  getDocument: (documentId: string): Promise<DocumentItem> =>
    fetchJson(`${API_BASE_URL}/documents/${documentId}`),
  deleteDocument: (documentId: string): Promise<{ deleted: boolean; document_id: string }> =>
    fetchJson(`${API_BASE_URL}/documents/${documentId}`, { method: "DELETE" }),
  uploadDocument: async (courseId: string, file: File, topic: string = "General Foundations"): Promise<DocumentItem> => {
    const token = getStoredToken();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("topic", topic);

    const headers: Record<string, string> = {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };

    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/courses/${courseId}/upload`, {
        method: "POST",
        credentials: "include",
        headers,
        body: formData
      });
    } catch (err: unknown) {
      if (isNetworkError(err)) {
        throw new Error(
          "LearnMate AI backend service is currently offline or unreachable. Document upload cannot be processed right now."
        );
      }
      throw err instanceof Error ? err : new Error(String(err));
    }

    if (!res.ok) {
      let errMessage = `HTTP ${res.status}`;
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        errMessage = `LearnMate AI backend is temporarily unavailable (HTTP ${res.status}). Document upload cannot be processed right now.`;
      } else {
        try {
          const err = await res.json();
          errMessage = err.detail || err.message || errMessage;
        } catch {
          // Ignore JSON parse failure
        }
      }
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
    questionType?: string;
    allowRevision?: boolean;
  }): Promise<Assessment> =>
    fetchJson(`${API_BASE_URL}/assessments/generate`, {
      method: "POST",
      body: JSON.stringify({
        course_id: params.courseId,
        user_id: params.userId || "student_default",
        topics: params.topics,
        difficulty: params.difficulty || "adaptive",
        assessment_type: params.assessmentType || "adaptive_quiz",
        question_count: params.questionCount || 5,
        question_type: params.questionType || "mixed",
        allow_revision: params.allowRevision || false
      })
    }),
  startAssessment: (assessmentId: string): Promise<Assessment> =>
    fetchJson(`${API_BASE_URL}/assessments/${assessmentId}/start`, { method: "POST" }),
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

  // Learner Model & Personalization
  getLearnerProfile: (userId: string = "student_default", courseId?: string): Promise<LearnerProfile> => {
    const url = courseId
      ? `${API_BASE_URL}/learner/profile?user_id=${encodeURIComponent(userId)}&course_id=${encodeURIComponent(courseId)}`
      : `${API_BASE_URL}/learner/profile?user_id=${encodeURIComponent(userId)}`;
    return fetchJson(url);
  },
  getMasteryHistory: (userId: string = "student_default", topicName?: string): Promise<MasteryHistoryRecord[]> => {
    const url = topicName
      ? `${API_BASE_URL}/learner/history?user_id=${encodeURIComponent(userId)}&topic_name=${encodeURIComponent(topicName)}`
      : `${API_BASE_URL}/learner/history?user_id=${encodeURIComponent(userId)}`;
    return fetchJson(url);
  },
  getStudyPlan: (userId: string = "student_default", courseId?: string, targetExamDate?: string, dailyMinutes: number = 30): Promise<StudyPlanResponse> => {
    const params = new URLSearchParams({ user_id: userId, daily_study_minutes: String(dailyMinutes) });
    if (courseId) params.append("course_id", courseId);
    if (targetExamDate) params.append("target_exam_date", targetExamDate);
    return fetchJson(`${API_BASE_URL}/learner/study-plan?${params.toString()}`);
  },
  createStudyPlan: (req: { user_id?: string; course_id?: string; target_exam_date?: string; daily_study_minutes?: number }): Promise<StudyPlanResponse> =>
    fetchJson(`${API_BASE_URL}/learner/study-plan`, {
      method: "POST",
      body: JSON.stringify(req)
    }),
  getPrerequisites: (): Promise<Record<string, string[]>> =>
    fetchJson(`${API_BASE_URL}/learner/prerequisites`),

  // Evaluation
  runEvaluation: (courseId?: string, datasetType: string = "comprehensive", dryRun: boolean = true): Promise<EvaluationRun> =>
    fetchJson(`${API_BASE_URL}/evaluation/run`, {
      method: "POST",
      body: JSON.stringify({ course_id: courseId, dataset_type: datasetType, dry_run: dryRun })
    }),
  listEvaluationRuns: (): Promise<EvaluationRun[]> =>
    fetchJson(`${API_BASE_URL}/evaluation/runs`),
  getBenchmarkCases: (datasetType: string = "comprehensive"): Promise<{ dataset_version: string; total_cases: number; cases: SampleEvaluation[] }> =>
    fetchJson(`${API_BASE_URL}/evaluation/benchmark-cases?dataset_type=${encodeURIComponent(datasetType)}`)
};
