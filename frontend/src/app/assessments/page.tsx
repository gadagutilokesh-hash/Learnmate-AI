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
  ArrowRight,
  RotateCcw,
  Check,
  FileText,
  Clock,
  Layers,
  HelpCircle
} from "lucide-react";

export default function AssessmentsPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [difficulty, setDifficulty] = useState("adaptive");
  const [assessmentType, setAssessmentType] = useState("adaptive_quiz");
  const [questionCount, setQuestionCount] = useState(4);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Active Quiz State
  const [activeQuiz, setActiveQuiz] = useState<Assessment | null>(null);
  const [studentAnswers, setStudentAnswers] = useState<Record<string, string>>({});
  const [submissionResult, setSubmissionResult] = useState<QuizSubmissionResult | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    api.listCourses().then((cList) => {
      setCourses(cList);
      if (cList.length > 0) {
        setSelectedCourseId(cList[0].id);
      }
    });
  }, []);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCourseId) return;

    setGenerating(true);
    setSubmissionResult(null);
    setStudentAnswers({});

    try {
      const assessment = await api.generateAssessment({
        courseId: selectedCourseId,
        difficulty,
        assessmentType,
        questionCount
      });
      setActiveQuiz(assessment);
    } catch (err: any) {
      alert(`Assessment generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  }

  async function handleSubmitQuiz() {
    if (!activeQuiz) return;

    setSubmitting(true);
    try {
      const answersList = activeQuiz.questions.map((q) => ({
        question_id: q.id,
        student_answer: studentAnswers[q.id] || ""
      }));

      const res = await api.submitQuiz(activeQuiz.id, answersList);
      setSubmissionResult(res);
    } catch (err: any) {
      alert(`Submission failed: ${err.message}`);
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
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <GraduationCap className="w-6 h-6 text-indigo-400" /> Adaptive Assessments & Misconception Diagnosis
        </h1>
        <p className="text-sm text-slate-400">
          Curriculum-grounded quizzes spanning MCQs, short-answer, and numerical problems with diagnostic cognitive error analysis.
        </p>
      </div>

      {/* Mode 1: Assessment Generator Configurator (When no quiz is active) */}
      {!activeQuiz && !submissionResult && (
        <form
          onSubmit={handleGenerate}
          className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-6 shadow-xl"
        >
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" /> Configure Assessment
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Course */}
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                Target Course Knowledge Base
              </label>
              <select
                value={selectedCourseId}
                onChange={(e) => setSelectedCourseId(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>

            {/* Assessment Type */}
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                Assessment Type
              </label>
              <select
                value={assessmentType}
                onChange={(e) => setAssessmentType(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="adaptive_quiz">Adaptive Mastery Quiz</option>
                <option value="diagnostic">Diagnostic Assessment (Baseline Calibrator)</option>
                <option value="practice">Targeted Practice Quiz</option>
              </select>
            </div>

            {/* Difficulty */}
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                Difficulty Tier
              </label>
              <div className="grid grid-cols-4 gap-2">
                {["beginner", "intermediate", "advanced", "adaptive"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDifficulty(d)}
                    className={`py-2 text-xs font-medium rounded-lg capitalize border transition-all ${
                      difficulty === d
                        ? "bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30"
                        : "bg-slate-950 text-slate-400 border-slate-800 hover:text-white"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Count */}
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                Question Count ({questionCount} problems)
              </label>
              <input
                type="range"
                min={3}
                max={10}
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-slate-500 mt-1">
                <span>3 Questions (Quick)</span>
                <span>10 Questions (Comprehensive)</span>
              </div>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              disabled={generating}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-all shadow-lg shadow-indigo-600/25 disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" /> Synthesizing Grounded Problems...
                </>
              ) : (
                <>
                  <GraduationCap className="w-4 h-4" /> Generate Adaptive Assessment
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Mode 2: Interactive Quiz Runner (Taking Quiz) */}
      {activeQuiz && !submissionResult && (
        <div className="space-y-6">
          <div className="flex items-center justify-between p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div>
              <span className="text-[11px] font-mono font-medium text-indigo-400 uppercase tracking-wider">
                {activeQuiz.assessment_type.replace("_", " ")} • {activeQuiz.difficulty}
              </span>
              <h2 className="text-lg font-bold text-white">{activeQuiz.title}</h2>
            </div>
            <button
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-slate-800"
            >
              Cancel
            </button>
          </div>

          {/* Question List */}
          <div className="space-y-6">
            {activeQuiz.questions.map((q, idx) => (
              <div
                key={q.id}
                className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-indigo-400">
                    Question {idx + 1} of {activeQuiz.questions.length}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-medium">
                      {q.topic_name}
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {q.question_type.toUpperCase()}
                    </span>
                  </div>
                </div>

                <p className="text-sm md:text-base font-medium text-slate-100 leading-relaxed">
                  {q.prompt}
                </p>

                {/* Multiple Choice Options */}
                {q.question_type === "mcq" && q.options && (
                  <div className="space-y-2 pt-1">
                    {q.options.map((opt, oIdx) => {
                      const isSelected = studentAnswers[q.id] === opt;
                      return (
                        <button
                          key={oIdx}
                          type="button"
                          onClick={() => handleOptionSelect(q.id, opt)}
                          className={`w-full text-left p-3.5 rounded-xl border text-sm transition-all flex items-center justify-between ${
                            isSelected
                              ? "bg-indigo-600/20 border-indigo-500 text-white shadow-sm"
                              : "bg-slate-950/70 border-slate-800 text-slate-300 hover:bg-slate-800"
                          }`}
                        >
                          <span>{opt}</span>
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                              isSelected
                                ? "border-indigo-400 bg-indigo-500 text-white"
                                : "border-slate-600"
                            }`}
                          >
                            {isSelected && <Check className="w-2.5 h-2.5" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Short Answer or Numerical */}
                {q.question_type !== "mcq" && (
                  <div className="pt-1">
                    <input
                      type="text"
                      placeholder={q.question_type === "numerical" ? "Enter numeric value (e.g. 1.5)" : "Enter concise answer..."}
                      value={studentAnswers[q.id] || ""}
                      onChange={(e) => setStudentAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                )}

                {/* Provenance Tag */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
                  <span>Source Material: {q.citation.source_file}</span>
                  <button
                    type="button"
                    onClick={() => setActiveCitation(q.citation)}
                    className="text-indigo-400 hover:text-indigo-300 text-xs font-medium"
                  >
                    View Source Context
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-4">
            <button
              onClick={handleSubmitQuiz}
              disabled={submitting}
              className="flex items-center gap-2 px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-all shadow-xl shadow-indigo-600/30 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" /> Evaluating Responses & Diagnosing Misconceptions...
                </>
              ) : (
                <>
                  Submit Assessment & Diagnose Errors <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Mode 3: Graded Assessment Results & Misconception Diagnosis Report */}
      {submissionResult && (
        <div className="space-y-8 animate-in fade-in duration-300">
          {/* Score Header Card */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs uppercase font-mono tracking-wider text-slate-400 font-semibold">
                  Diagnostic Performance Report
                </span>
                <h2 className="text-2xl font-bold text-white mt-0.5">
                  Assessment Completed: {Math.round(submissionResult.score * 100)}% Score
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Answered {submissionResult.correct_count} of {submissionResult.total_questions} questions correctly. Bayesian Knowledge Tracing parameters calibrated.
                </p>
              </div>

              <button
                onClick={handleReset}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shrink-0 transition-colors shadow-md shadow-indigo-600/30"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Take Another Assessment
              </button>
            </div>

            {/* Mastery Updates Grid */}
            <div className="pt-3 border-t border-slate-800">
              <span className="text-xs font-semibold text-slate-300 block mb-2">
                Bayesian Knowledge Mastery Updates:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(submissionResult.mastery_updates).map(([topic, newM]) => (
                  <div
                    key={topic}
                    className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs flex items-center justify-between"
                  >
                    <span className="text-slate-300 truncate max-w-[150px]">{topic}</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {Math.round(newM * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Misconception Diagnosis & Remediation Box (CRITICAL REQUIREMENT) */}
          {submissionResult.misconceptions && submissionResult.misconceptions.length > 0 && (
            <div className="p-6 rounded-2xl bg-amber-500/10 border border-amber-500/20 space-y-4">
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-base">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <span>Identified Cognitive Misconceptions ({submissionResult.misconceptions.length})</span>
              </div>
              <p className="text-xs text-amber-200/80">
                LearnMate AI analyzed your incorrect answers to identify conceptual confusions and provide exact reading citations:
              </p>

              <div className="space-y-3">
                {submissionResult.misconceptions.map((m, mIdx) => (
                  <div
                    key={mIdx}
                    className="p-4 rounded-xl bg-slate-950/90 border border-amber-500/20 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-400 uppercase tracking-wide">
                        {m.topic_name}
                      </span>
                      <button
                        onClick={() => setActiveCitation(m.recommended_reading)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                      >
                        <BookOpen className="w-3.5 h-3.5" /> Read Source Excerpt
                      </button>
                    </div>
                    <p className="text-sm font-medium text-slate-200">
                      <strong className="text-rose-400">Likely Misconception:</strong> {m.misconception}
                    </p>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      <strong className="text-emerald-400">Recommended Remediation:</strong> {m.remediation_advice}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Question Review Breakdown */}
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-400" /> Question-by-Question Breakdown
            </h3>

            <div className="space-y-4">
              {submissionResult.graded_questions.map((gq, gIdx) => (
                <div
                  key={gq.question_id}
                  className={`p-5 rounded-2xl border space-y-3 ${
                    gq.is_correct
                      ? "bg-slate-900 border-emerald-500/30"
                      : "bg-slate-900 border-rose-500/30"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-bold text-slate-400">Question {gIdx + 1}</span>
                    <span
                      className={`flex items-center gap-1 font-semibold px-2.5 py-0.5 rounded-full ${
                        gq.is_correct
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      }`}
                    >
                      {gq.is_correct ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" /> Correct
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5" /> Incorrect
                        </>
                      )}
                    </span>
                  </div>

                  <p className="text-sm font-semibold text-slate-100">{gq.prompt}</p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                    <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px] uppercase font-bold">Your Answer:</span>
                      <span className={gq.is_correct ? "text-emerald-300 font-medium" : "text-rose-300 font-medium"}>
                        {gq.student_answer || "(No response)"}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px] uppercase font-bold">Correct Answer:</span>
                      <span className="text-emerald-300 font-medium">{gq.correct_answer}</span>
                    </div>
                  </div>

                  {/* Explanation with Citation */}
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-300 space-y-1.5">
                    <span className="font-semibold text-indigo-300 block">Explanation:</span>
                    <p className="leading-relaxed">{gq.explanation}</p>
                    <div className="pt-1 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Source: {gq.citation.source_file}</span>
                      <button
                        onClick={() => setActiveCitation(gq.citation)}
                        className="text-indigo-400 hover:text-indigo-300 font-medium"
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
