"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Course, Assessment, QuizSubmissionResult, Citation } from "@/lib/types";
import { SourceViewerModal } from "@/components/SourceViewerModal";
import {
  GraduationCap,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  BookOpen,
  RotateCcw,
  Check,
  Clock,
  Layers,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  Sliders,
  Target
} from "lucide-react";

export default function AssessmentsPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [availableTopics, setAvailableTopics] = useState<string[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string>("");
  const [selectedQuestionType, setSelectedQuestionType] = useState<string>("mixed");
  const [difficulty, setDifficulty] = useState("adaptive");
  const [assessmentType, setAssessmentType] = useState("adaptive_quiz");
  const [questionCount, setQuestionCount] = useState(4);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [generationError, setGenerationError] = useState<{ message: string; isQuota: boolean; isUnavailable?: boolean } | null>(null);

  // Active Quiz State
  const [activeQuiz, setActiveQuiz] = useState<Assessment | null>(null);
  const [studentAnswers, setStudentAnswers] = useState<Record<string, string>>({});
  const [submissionResult, setSubmissionResult] = useState<QuizSubmissionResult | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  // Fetch courses on mount
  useEffect(() => {
    api.listCourses().then((cList) => {
      setCourses(cList);
      if (cList.length > 0) {
        setSelectedCourseId(cList[0].id);
      }
    });
  }, []);

  // Fetch topics when course changes
  useEffect(() => {
    if (selectedCourseId) {
      api.getCourseTopics(selectedCourseId)
        .then((tList) => {
          setAvailableTopics(tList || []);
          setSelectedTopic("");
        })
        .catch(() => setAvailableTopics([]));
    }
  }, [selectedCourseId]);

  async function handleGenerate(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!selectedCourseId) return;

    setGenerating(true);
    setGenerationError(null);
    setSubmissionResult(null);
    setStudentAnswers({});
    setActiveQuestionIndex(0);

    try {
      const assessment = await api.generateAssessment({
        courseId: selectedCourseId,
        topics: selectedTopic ? [selectedTopic] : undefined,
        difficulty,
        assessmentType,
        questionCount,
        questionType: selectedQuestionType
      });
      setActiveQuiz(assessment);

      // Trigger start event to record when assessment begins
      api.startAssessment(assessment.id).catch(() => {});
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      const isQuota = msg.toLowerCase().includes("limit") || msg.toLowerCase().includes("quota") || msg.toLowerCase().includes("429");
      const isUnavailable = msg.toLowerCase().includes("503") || msg.toLowerCase().includes("demand") || msg.toLowerCase().includes("unavailable");
      const cleanMsg = isQuota
        ? "Assessment generation is temporarily throttled because the AI service has reached its usage limit. Please try again later."
        : isUnavailable
        ? "AI service is currently under high demand. Please retry in a few moments."
        : msg;
      setGenerationError({
        message: cleanMsg,
        isQuota,
        isUnavailable
      });
    } finally {
      setGenerating(false);
    }
  }

  async function handleSubmitQuiz() {
    if (!activeQuiz || submitting) return;

    setSubmitting(true);
    try {
      const answersList = activeQuiz.questions.map((q) => ({
        question_id: q.id,
        student_answer: studentAnswers[q.id] || ""
      }));

      const res = await api.submitQuiz(activeQuiz.id, answersList);
      setSubmissionResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Submission failed: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  function handleOptionSelect(qId: string, option: string) {
    setStudentAnswers((prev) => ({ ...prev, [qId]: option }));
  }

  function handleReset() {
    setActiveQuiz(null);
    setSubmissionResult(null);
    setStudentAnswers({});
    setActiveQuestionIndex(0);
    setGenerationError(null);
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-[#262626]">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[#F5F5F5] flex items-center gap-2">
          <GraduationCap className="w-5 h-5 text-[#3B82F6]" aria-hidden="true" /> Adaptive Quizzes & Misconception Diagnosis
        </h1>
        <p className="text-xs md:text-sm text-[#A1A1AA] mt-1">
          Source-grounded quizzes across MCQs, short answers, and numerical problems with Bayesian Knowledge Tracing.
        </p>
      </div>

      {/* Generation Error State Banner */}
      {generationError && (
        <div className="p-3.5 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 text-[#F59E0B] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0 text-[#F59E0B] mt-0.5" aria-hidden="true" />
            <div>
              <strong className="font-semibold block text-[#F59E0B] text-xs">
                {generationError.isQuota
                  ? "AI Service Limit Reached"
                  : generationError.isUnavailable
                  ? "AI Service Temporarily Unavailable (High Demand)"
                  : "Generation Notice"}
              </strong>
              <p className="text-xs text-[#A1A1AA] mt-0.5 leading-relaxed">
                {generationError.message}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
            <button
              type="button"
              onClick={() => handleGenerate()}
              disabled={generating}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#F59E0B]/20 hover:bg-[#F59E0B]/30 text-[#F59E0B] border border-[#F59E0B]/30 text-xs font-medium transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-3 h-3" aria-hidden="true" /> Try Again
            </button>
            <button
              type="button"
              onClick={() => setGenerationError(null)}
              className="p-1.5 rounded text-[#71717A] hover:text-[#F5F5F5] hover:bg-[#181818] transition-colors"
              aria-label="Dismiss notice"
            >
              <XCircle className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      {/* Backend Offline Notice */}
      {courses.length === 0 && (
        <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] text-xs flex items-center gap-2.5 text-[#A1A1AA]">
          <div className="w-2 h-2 rounded-full bg-[#F59E0B] shrink-0" aria-hidden="true" />
          <span>
            <strong className="text-[#F5F5F5] font-medium">Backend Offline:</strong> Adaptive quiz generation and concept diagnosis require an active FastAPI backend server. Configure <code className="text-[#3B82F6] font-mono text-[11px]">NEXT_PUBLIC_API_URL</code> to connect.
          </span>
        </div>
      )}

      {/* Mode 1: Assessment Generator Configurator */}
      {!activeQuiz && !submissionResult && (
        <form
          onSubmit={handleGenerate}
          className="p-5 md:p-6 rounded-md bg-[#121212] border border-[#262626] space-y-5"
        >
          <div className="flex items-center justify-between border-b border-[#262626] pb-3">
            <h2 className="text-sm md:text-base font-semibold text-[#F5F5F5] flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" /> Configure Assessment
            </h2>
            <span className="text-xs text-[#71717A] font-mono flex items-center gap-1">
              <Target className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" /> Bayesian Grounded Engine
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Course */}
            <div>
              <label htmlFor="quiz-course-select" className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Target Course Knowledge Base
              </label>
              <select
                id="quiz-course-select"
                value={selectedCourseId}
                onChange={(e) => setSelectedCourseId(e.target.value)}
                disabled={courses.length === 0}
                className="w-full px-3 py-2 rounded-md bg-[#080808] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] disabled:opacity-60"
              >
                {courses.length === 0 ? (
                  <option value="">Backend offline &bull; No courses indexed</option>
                ) : (
                  courses.map((c) => {
                    const isDemo = c.is_demo || c.visibility === "shared_demo";
                    return (
                      <option key={c.id} value={c.id}>
                        {isDemo ? `[Demo] ${c.title}` : `[Private] ${c.title}`}
                      </option>
                    );
                  })
                )}
              </select>
            </div>

            {/* Topic Filter */}
            <div>
              <label htmlFor="quiz-topic-select" className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Target Topic (Optional Focus)
              </label>
              <select
                id="quiz-topic-select"
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
                className="w-full px-3 py-2 rounded-md bg-[#080808] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
              >
                <option value="">All Course Topics (Comprehensive & Adaptive)</option>
                {availableTopics.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            {/* Assessment Type */}
            <div>
              <label htmlFor="quiz-type-select" className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Assessment Type
              </label>
              <select
                id="quiz-type-select"
                value={assessmentType}
                onChange={(e) => setAssessmentType(e.target.value)}
                className="w-full px-3 py-2 rounded-md bg-[#080808] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
              >
                <option value="adaptive_quiz">Adaptive Mastery Quiz (Prioritizes Weak Topics)</option>
                <option value="diagnostic">Diagnostic Assessment (Baseline Across All Topics)</option>
                <option value="practice">Targeted Practice Quiz</option>
              </select>
            </div>

            {/* Question Type Selection */}
            <div>
              <label htmlFor="quiz-format-select" className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Question Type Format
              </label>
              <select
                id="quiz-format-select"
                value={selectedQuestionType}
                onChange={(e) => setSelectedQuestionType(e.target.value)}
                className="w-full px-3 py-2 rounded-md bg-[#080808] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
              >
                <option value="mixed">Mixed (MCQ, Short Answer, Numerical)</option>
                <option value="mcq">Multiple Choice (MCQ Only)</option>
                <option value="short_answer">Short Answer (Rubric Semantic Grading)</option>
                <option value="numerical">Numerical Problems (Calculation & Tolerance)</option>
              </select>
            </div>

            {/* Difficulty */}
            <div>
              <span className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Difficulty Tier
              </span>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { id: "beginner", label: "Easy" },
                  { id: "intermediate", label: "Medium" },
                  { id: "advanced", label: "Hard" },
                  { id: "adaptive", label: "Adaptive" }
                ].map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setDifficulty(d.id)}
                    className={`py-1.5 text-xs font-medium rounded-md border transition-colors ${
                      difficulty === d.id
                        ? "bg-[#3B82F6] text-white border-[#3B82F6]"
                        : "bg-[#080808] text-[#A1A1AA] border-[#262626] hover:text-[#F5F5F5] hover:bg-[#181818]"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Count */}
            <div>
              <label htmlFor="quiz-count-slider" className="text-xs font-medium text-[#A1A1AA] block mb-1">
                Question Count ({questionCount} problems)
              </label>
              <input
                id="quiz-count-slider"
                type="range"
                min={2}
                max={10}
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value))}
                className="w-full accent-[#3B82F6] cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-[#71717A] mt-0.5">
                <span>2 Problems (Quick)</span>
                <span>10 Problems (Exhaustive)</span>
              </div>
            </div>
          </div>

          <div className="pt-3 flex justify-end border-t border-[#262626]">
            <button
              type="submit"
              disabled={generating || courses.length === 0}
              className="flex items-center gap-2 px-5 py-2.5 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs md:text-sm font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
            >
              {generating ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" aria-hidden="true" /> Generating Grounded Questions...
                </>
              ) : courses.length === 0 ? (
                <>
                  <AlertTriangle className="w-4 h-4 text-[#F59E0B]" aria-hidden="true" /> Backend Offline (Quiz Generation Unavailable)
                </>
              ) : (
                <>
                  <GraduationCap className="w-4 h-4" aria-hidden="true" /> Generate Adaptive Assessment
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Mode 2: Interactive Quiz Runner */}
      {activeQuiz && !submissionResult && (
        <div className="space-y-4">
          {/* Quiz Status Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-md bg-[#121212] border border-[#262626]">
            <div>
              <span className="text-[11px] font-mono font-medium text-[#3B82F6] uppercase tracking-wider">
                {activeQuiz.assessment_type.replace("_", " ")} &bull; {activeQuiz.difficulty}
              </span>
              <h2 className="text-base font-semibold text-[#F5F5F5] mt-0.5">{activeQuiz.title}</h2>
            </div>

            {/* Question Jump Navigation */}
            <div className="flex items-center gap-1.5 overflow-x-auto py-1">
              {activeQuiz.questions.map((q, idx) => {
                const isAnswered = Boolean(studentAnswers[q.id]);
                const isCurrent = idx === activeQuestionIndex;
                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => setActiveQuestionIndex(idx)}
                    aria-label={`Jump to question ${idx + 1}`}
                    className={`w-7 h-7 rounded text-xs font-mono font-bold transition-colors flex items-center justify-center shrink-0 border ${
                      isCurrent
                        ? "bg-[#3B82F6] text-white border-[#3B82F6]"
                        : isAnswered
                        ? "bg-[#22C55E]/10 border-[#22C55E]/40 text-[#22C55E]"
                        : "bg-[#080808] border-[#262626] text-[#71717A] hover:text-[#F5F5F5]"
                    }`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded text-xs font-medium text-[#A1A1AA] hover:text-[#F5F5F5] bg-[#181818] border border-[#262626] shrink-0 self-end sm:self-auto transition-colors"
            >
              Cancel
            </button>
          </div>

          {/* Active Question Card */}
          {activeQuiz.questions.length > 0 && (() => {
            const q = activeQuiz.questions[activeQuestionIndex];
            const isLastQuestion = activeQuestionIndex === activeQuiz.questions.length - 1;
            const isFirstQuestion = activeQuestionIndex === 0;

            return (
              <div
                key={q.id}
                className="p-5 md:p-6 rounded-md bg-[#121212] border border-[#262626] space-y-4"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-[#3B82F6]">
                    Question {activeQuestionIndex + 1} of {activeQuiz.questions.length}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded bg-[#181818] text-[#A1A1AA] border border-[#262626] font-medium">
                      {q.topic_name}
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#181818] text-[#71717A] border border-[#262626] uppercase">
                      {q.question_type.replace("_", " ")}
                    </span>
                  </div>
                </div>

                <p className="text-sm md:text-base font-medium text-[#F5F5F5] leading-relaxed">
                  {q.prompt}
                </p>

                {/* Multiple Choice Options */}
                {q.question_type === "mcq" && q.options && (
                  <div className="space-y-2 pt-1" role="radiogroup" aria-label="Multiple choice options">
                    {q.options.map((opt, oIdx) => {
                      const isSelected = studentAnswers[q.id] === opt;
                      return (
                        <button
                          key={oIdx}
                          type="button"
                          role="radio"
                          aria-checked={isSelected}
                          onClick={() => handleOptionSelect(q.id, opt)}
                          className={`w-full text-left p-3 rounded-md border text-xs md:text-sm transition-colors flex items-center justify-between ${
                            isSelected
                              ? "bg-[#181818] border-[#3B82F6] text-[#F5F5F5]"
                              : "bg-[#080808] border-[#262626] text-[#A1A1AA] hover:bg-[#181818] hover:text-[#F5F5F5]"
                          }`}
                        >
                          <span>{opt}</span>
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                              isSelected
                                ? "border-[#3B82F6] bg-[#3B82F6] text-white"
                                : "border-[#363636]"
                            }`}
                          >
                            {isSelected && <Check className="w-2.5 h-2.5" aria-hidden="true" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Short Answer or Numerical Input */}
                {q.question_type !== "mcq" && (
                  <div className="space-y-1.5 pt-1">
                    <label htmlFor={`question-input-${q.id}`} className="sr-only">
                      Your answer
                    </label>
                    <input
                      id={`question-input-${q.id}`}
                      type="text"
                      placeholder={
                        q.question_type === "numerical"
                          ? `Enter numeric answer${q.numerical_unit ? ` (in ${q.numerical_unit})` : ""}, e.g. 1.5`
                          : "Type your concise explanation covering core principles..."
                      }
                      value={studentAnswers[q.id] || ""}
                      onChange={(e) => setStudentAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      className="w-full px-3.5 py-2.5 rounded-md bg-[#080808] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] font-mono"
                    />
                    {q.question_type === "numerical" && (
                      <p className="text-[11px] text-[#71717A] flex items-center gap-1">
                        <HelpCircle className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" />
                        Evaluated within tolerance (&plusmn;{(q.numerical_tolerance || 0.01) * 100}%).
                      </p>
                    )}
                  </div>
                )}

                {/* Provenance Tag */}
                <div className="pt-2.5 border-t border-[#262626] flex items-center justify-between text-xs text-[#71717A]">
                  <span className="truncate max-w-[70%]">
                    Grounding: {q.citation.source_file}
                    {q.citation.page_number ? ` (Page ${q.citation.page_number})` : ""}
                    {q.citation.slide_number ? ` (Slide ${q.citation.slide_number})` : ""}
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveCitation(q.citation)}
                    className="text-[#3B82F6] hover:text-[#60A5FA] text-xs font-medium shrink-0 flex items-center gap-1"
                  >
                    <BookOpen className="w-3.5 h-3.5" aria-hidden="true" /> Source Context
                  </button>
                </div>

                {/* Navigation Buttons */}
                <div className="flex items-center justify-between pt-3 border-t border-[#262626]">
                  <button
                    type="button"
                    onClick={() => setActiveQuestionIndex((prev) => Math.max(0, prev - 1))}
                    disabled={isFirstQuestion}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium text-[#A1A1AA] bg-[#181818] border border-[#262626] hover:text-[#F5F5F5] disabled:opacity-40 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" aria-hidden="true" /> Previous
                  </button>

                  {!isLastQuestion ? (
                    <button
                      type="button"
                      onClick={() => setActiveQuestionIndex((prev) => Math.min(activeQuiz.questions.length - 1, prev + 1))}
                      className="flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-medium text-white bg-[#3B82F6] hover:bg-[#2563EB] transition-colors"
                    >
                      Next <ChevronRight className="w-4 h-4" aria-hidden="true" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={handleSubmitQuiz}
                      disabled={submitting}
                      className="flex items-center gap-2 px-5 py-2 rounded-md bg-[#22C55E] hover:bg-[#16A34A] text-white font-medium text-xs transition-colors disabled:opacity-50"
                    >
                      {submitting ? (
                        <>
                          <Clock className="w-3.5 h-3.5 animate-spin" aria-hidden="true" /> Evaluating...
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Submit Assessment
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Mode 3: Graded Assessment Results & Misconception Diagnosis Report */}
      {submissionResult && (
        <div className="space-y-6 animate-in fade-in duration-150">
          {/* Score Header Card */}
          <div className="p-5 md:p-6 rounded-md bg-[#121212] border border-[#262626] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs uppercase font-mono tracking-wider text-[#71717A] font-semibold">
                  Diagnostic Performance Report
                </span>
                <h2 className="text-xl md:text-2xl font-bold text-[#F5F5F5] mt-0.5">
                  Assessment Completed: {Math.round(submissionResult.score * 100)}% Score
                </h2>
                <p className="text-xs text-[#A1A1AA] mt-1">
                  Answered {submissionResult.correct_count} of {submissionResult.total_questions} questions correctly. Bayesian Knowledge Tracing parameters calibrated.
                </p>
              </div>

              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-2 px-4 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-medium shrink-0 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" /> Take Another Assessment
              </button>
            </div>

            {/* Topic Performance Breakdown */}
            {submissionResult.topic_performance && Object.keys(submissionResult.topic_performance).length > 0 && (
              <div className="pt-3 border-t border-[#262626]">
                <span className="text-xs font-medium text-[#A1A1AA] block mb-2 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" /> Topic Performance Breakdown:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {Object.entries(submissionResult.topic_performance).map(([topic, stat]) => (
                    <div
                      key={topic}
                      className="p-3 rounded-md bg-[#080808] border border-[#262626] space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[#F5F5F5] font-medium truncate max-w-[140px]">{topic}</span>
                        <span className="font-mono font-semibold text-[#3B82F6]">
                          {stat.correct}/{stat.total}
                        </span>
                      </div>
                      <div className="w-full bg-[#181818] h-1.5 rounded overflow-hidden">
                        <div
                          className={`h-full ${
                            stat.percentage >= 0.75
                              ? "bg-[#22C55E]"
                              : stat.percentage >= 0.50
                              ? "bg-[#F59E0B]"
                              : "bg-[#EF4444]"
                          }`}
                          style={{ width: `${Math.round(stat.percentage * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* BKT Mastery Updates Grid */}
            <div className="pt-3 border-t border-[#262626]">
              <span className="text-xs font-medium text-[#A1A1AA] block mb-2 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-[#22C55E]" aria-hidden="true" /> Calibrated Bayesian Knowledge Mastery (BKT):
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(submissionResult.mastery_updates).map(([topic, newM]) => (
                  <div
                    key={topic}
                    className="p-2.5 rounded-md bg-[#080808] border border-[#262626] text-xs flex items-center justify-between"
                  >
                    <span className="text-[#A1A1AA] truncate max-w-[150px]">{topic}</span>
                    <span className="font-mono font-medium text-[#22C55E]">
                      {Math.round(newM * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Misconception Diagnosis & Remediation Box */}
          {submissionResult.misconceptions && submissionResult.misconceptions.length > 0 && (
            <div className="p-5 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 space-y-3">
              <div className="flex items-center gap-2 text-[#F59E0B] font-semibold text-sm md:text-base">
                <AlertTriangle className="w-4 h-4 shrink-0 text-[#F59E0B]" aria-hidden="true" />
                <span>Identified Cognitive Misconceptions ({submissionResult.misconceptions.length})</span>
              </div>
              <p className="text-xs text-[#A1A1AA] leading-relaxed">
                Cognitive analysis distinguishing observed student errors from inferred conceptual misconceptions:
              </p>

              <div className="space-y-2.5">
                {submissionResult.misconceptions.map((m, mIdx) => (
                  <div
                    key={mIdx}
                    className="p-3.5 rounded-md bg-[#080808] border border-[#262626] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-[#F59E0B] uppercase tracking-wide">
                        {m.topic_name}
                      </span>
                      <button
                        type="button"
                        onClick={() => setActiveCitation(m.recommended_reading)}
                        className="text-xs text-[#3B82F6] hover:text-[#60A5FA] font-medium flex items-center gap-1"
                      >
                        <BookOpen className="w-3.5 h-3.5" aria-hidden="true" /> Read Source Excerpt
                      </button>
                    </div>

                    {m.observed_mistake && (
                      <p className="text-xs text-[#A1A1AA]">
                        <strong className="text-[#F5F5F5]">Observed Mistake:</strong> {m.observed_mistake}
                      </p>
                    )}

                    <p className="text-xs md:text-sm font-medium text-[#F5F5F5]">
                      <strong className="text-[#EF4444]">Inferred Misconception:</strong> {m.misconception}
                    </p>
                    <p className="text-xs text-[#A1A1AA] leading-relaxed">
                      <strong className="text-[#22C55E]">Recommended Remediation:</strong> {m.remediation_advice}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Question Review Breakdown */}
          <div className="space-y-3.5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#71717A]" aria-hidden="true" /> Question Breakdown
            </h3>

            <div className="space-y-3">
              {submissionResult.graded_questions.map((gq, gIdx) => (
                <div
                  key={gq.question_id}
                  className={`p-4 rounded-md bg-[#121212] border space-y-2.5 ${
                    gq.is_correct
                      ? "border-[#22C55E]/30"
                      : "border-[#EF4444]/30"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-medium text-[#71717A]">Question {gIdx + 1}</span>
                    <div className="flex items-center gap-2">
                      {gq.grading_method && (
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#181818] text-[#71717A] border border-[#262626]">
                          {gq.grading_method}
                        </span>
                      )}
                      <span
                        className={`flex items-center gap-1 font-semibold px-2 py-0.5 rounded ${
                          gq.is_correct
                            ? "bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20"
                            : "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20"
                        }`}
                      >
                        {gq.is_correct ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Correct
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3.5 h-3.5" aria-hidden="true" /> Incorrect
                          </>
                        )}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs md:text-sm font-medium text-[#F5F5F5]">{gq.prompt}</p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                    <div className="p-2.5 rounded bg-[#080808] border border-[#262626]">
                      <span className="text-[#71717A] block text-[10px] uppercase font-semibold">Your Answer:</span>
                      <span className={gq.is_correct ? "text-[#22C55E] font-medium" : "text-[#EF4444] font-medium"}>
                        {gq.student_answer || "(No response)"}
                      </span>
                    </div>
                    <div className="p-2.5 rounded bg-[#080808] border border-[#262626]">
                      <span className="text-[#71717A] block text-[10px] uppercase font-semibold">Correct Answer:</span>
                      <span className="text-[#22C55E] font-medium">{gq.correct_answer}</span>
                    </div>
                  </div>

                  {/* Feedback & Explanation with Citation */}
                  <div className="p-3 rounded bg-[#080808] border border-[#262626] text-xs text-[#A1A1AA] space-y-1.5">
                    {gq.feedback && (
                      <p className="text-[#F5F5F5] font-medium">
                        <strong className="text-[#3B82F6]">Feedback: </strong> {gq.feedback}
                      </p>
                    )}
                    <p className="leading-relaxed text-[#A1A1AA]">{gq.explanation}</p>
                    <div className="pt-1.5 flex items-center justify-between text-[11px] text-[#71717A] border-t border-[#262626]">
                      <span>
                        Source: {gq.citation.source_file}
                        {gq.citation.page_number ? ` (p. ${gq.citation.page_number})` : ""}
                        {gq.citation.slide_number ? ` (slide ${gq.citation.slide_number})` : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => setActiveCitation(gq.citation)}
                        className="text-[#3B82F6] hover:text-[#60A5FA] font-medium"
                      >
                        Inspect Citation Excerpt
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Source Excerpt Modal */}
      <SourceViewerModal
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
