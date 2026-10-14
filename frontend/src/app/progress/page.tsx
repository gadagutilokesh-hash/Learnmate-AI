"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  LearnerProfile,
  Assessment,
  Citation,
  StudyPlanResponse,
  MasteryHistoryRecord
} from "@/lib/types";
import { SourceViewerModal } from "@/components/SourceViewerModal";
import {
  TrendingUp,
  Brain,
  AlertTriangle,
  Calendar,
  Layers,
  ArrowRight,
  Clock,
  BookOpen,
  CheckCircle2,
  RotateCcw,
  FileText,
  Sliders
} from "lucide-react";
import Link from "next/link";

export default function ProgressPage() {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [history, setHistory] = useState<MasteryHistoryRecord[]>([]);
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Study plan config
  const [targetExamDate, setTargetExamDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(30);
  const [planLoading, setPlanLoading] = useState(false);

  // Citation modal state
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [prof, assessList, histList] = await Promise.all([
          api.getLearnerProfile(),
          api.listAssessments(),
          api.getMasteryHistory()
        ]);
        setProfile(prof);
        setAssessments(assessList);
        setHistory(histList);
        if (prof.study_plan) {
          setStudyPlan(prof.study_plan);
          if (prof.study_plan.daily_study_minutes) {
            setDailyMinutes(prof.study_plan.daily_study_minutes);
          }
          if (prof.study_plan.target_exam_date) {
            setTargetExamDate(prof.study_plan.target_exam_date);
          }
        }
      } catch (e) {
        console.error("Error loading learner profile data:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleRecalculatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setPlanLoading(true);
    try {
      const plan = await api.createStudyPlan({
        target_exam_date: targetExamDate || undefined,
        daily_study_minutes: dailyMinutes
      });
      setStudyPlan(plan);
    } catch (err) {
      console.error("Failed to generate study plan:", err);
    } finally {
      setPlanLoading(false);
    }
  };

  if (loading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center min-h-[50vh] gap-3"
      >
        <div className="w-7 h-7 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
        <p className="text-[#71717A] text-xs">Loading Bayesian learner model and study plan...</p>
      </div>
    );
  }

  const overallMasteryPct = profile ? Math.round(profile.overall_mastery * 100) : 0;
  const isNewLearner = profile?.is_new_learner || (profile?.topics.length === 0);

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="pb-4 border-b border-[#262626]">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[#F5F5F5] flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#3B82F6]" aria-hidden="true" /> Student Progress & Bayesian Mastery Analytics
        </h1>
        <p className="text-xs md:text-sm text-[#A1A1AA] mt-1">
          Deterministic knowledge tracing tracking concept acquisition, spaced repetition intervals, and source-grounded study plans.
        </p>
      </div>

      {/* Empty State Banner for New Learner */}
      {isNewLearner && (
        <div className="p-5 rounded-md bg-[#121212] border border-[#262626] space-y-3">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-md bg-[#181818] border border-[#262626] text-[#3B82F6] shrink-0">
              <Brain className="w-5 h-5" aria-hidden="true" />
            </div>
            <div className="space-y-1 flex-1">
              <h2 className="text-sm md:text-base font-semibold text-[#F5F5F5]">
                Initial Calibration Needed
              </h2>
              <p className="text-xs text-[#A1A1AA] leading-relaxed">
                No previous performance data is assumed. LearnMate initializes your knowledge model using unassessed baseline priors (P(L0) = 0.15). Complete a diagnostic assessment to calibrate your concept mastery and generate a tailored study plan.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5 pt-1">
            <Link
              href="/assessments"
              className="px-3.5 py-1.5 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
            >
              Start Diagnostic Assessment <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
            <Link
              href="/tutor"
              className="px-3.5 py-1.5 rounded-md bg-[#181818] hover:bg-[#262626] text-[#F5F5F5] border border-[#262626] text-xs font-medium transition-colors"
            >
              Explore Grounded Tutor
            </Link>
          </div>
        </div>
      )}

      {/* Top Mastery Overview Card */}
      <div className="p-5 md:p-6 rounded-md bg-[#121212] border border-[#262626] flex flex-col md:flex-row md:items-center justify-between gap-5">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#3B82F6]">
            <Brain className="w-4 h-4" aria-hidden="true" /> Cognitive Learner State
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-[#F5F5F5]">
            Overall Curriculum Mastery: {overallMasteryPct}%
          </h2>
          <p className="text-xs text-[#A1A1AA] max-w-xl leading-relaxed">
            Updated via Bayesian Knowledge Tracing across {assessments.length} assessment sessions and grounded tutoring interactions.
            Distinguishes latent knowledge probability <span className="font-mono text-[#3B82F6]">P(L)</span> from observed quiz scores.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-[#080808] p-3.5 rounded-md border border-[#262626] shrink-0">
          <div className="text-center px-3 border-r border-[#262626]">
            <span className="text-xl md:text-2xl font-bold font-mono text-[#22C55E]">
              {profile?.strong_topics.length || 0}
            </span>
            <span className="text-[11px] text-[#71717A] block">Mastered</span>
          </div>
          <div className="text-center px-3 border-r border-[#262626]">
            <span className="text-xl md:text-2xl font-bold font-mono text-[#F59E0B]">
              {profile
                ? profile.topics.filter((t) => t.status === "in_progress").length
                : 0}
            </span>
            <span className="text-[11px] text-[#71717A] block">In Progress</span>
          </div>
          <div className="text-center px-3">
            <span className="text-xl md:text-2xl font-bold font-mono text-[#EF4444]">
              {profile?.weak_topics.length || 0}
            </span>
            <span className="text-[11px] text-[#71717A] block">Needs Work</span>
          </div>
        </div>
      </div>

      {/* Spaced Repetition Due Reviews Card */}
      {profile?.upcoming_reviews && profile.upcoming_reviews.length > 0 && (
        <div className="p-4 md:p-5 rounded-md bg-[#121212] border border-[#262626] space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[#F5F5F5] font-semibold text-xs md:text-sm">
              <RotateCcw className="w-4 h-4 text-[#F59E0B]" aria-hidden="true" />
              Spaced Repetition & Revision Schedule
            </div>
            <span className="text-[11px] text-[#71717A] font-mono">
              Intervals calibrated by retention history
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {profile.upcoming_reviews.map((rev) => {
              const isOverdue = rev.is_overdue;
              return (
                <div
                  key={rev.topic_name}
                  className={`p-3 rounded-md border flex flex-col justify-between gap-2 text-xs ${
                    isOverdue
                      ? "bg-[#EF4444]/10 border-[#EF4444]/30 text-[#EF4444]"
                      : "bg-[#080808] border-[#262626] text-[#A1A1AA]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-[#F5F5F5] truncate">{rev.topic_name}</span>
                    {isOverdue ? (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/30 uppercase">
                        Overdue ({rev.days_overdue}d)
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#181818] text-[#71717A] font-mono border border-[#262626]">
                        {rev.review_interval_days}d interval
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-[#71717A] font-mono pt-1 border-t border-[#262626]">
                    <span>Mastery: {Math.round(rev.mastery_score * 100)}%</span>
                    <span>Streak: {rev.consecutive_correct || 0}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Focus Areas Requiring Revision */}
      {profile?.weak_topics && profile.weak_topics.length > 0 && (
        <div className="p-4 rounded-md bg-[#EF4444]/10 border border-[#EF4444]/20 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[#EF4444] font-semibold text-xs md:text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" /> Focus Areas Requiring Revision ({profile.weak_topics.length})
            </span>
            <Link
              href="/assessments"
              className="text-xs font-semibold text-[#EF4444] hover:underline flex items-center gap-1"
            >
              Start Targeted Quiz <ArrowRight className="w-3 h-3" aria-hidden="true" />
            </Link>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {profile.weak_topics.map((w, idx) => (
              <span
                key={idx}
                className="px-2.5 py-1 rounded bg-[#080808] text-[#EF4444] text-xs font-medium border border-[#EF4444]/30"
              >
                {w}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Personalized Recommendations with Verified Citations */}
      {profile?.recommended_activities && profile.recommended_activities.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
              Source-Grounded Next Best Actions
            </h2>
            <span className="text-xs text-[#71717A] hidden sm:inline">
              Recommendations based on BKT mastery, prerequisites, and spaced intervals
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {profile.recommended_activities.map((act, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-md bg-[#121212] border border-[#262626] flex flex-col justify-between gap-2.5 text-xs hover:border-[#363636] transition-colors"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#181818] text-[#A1A1AA] border border-[#262626]">
                      {act.type.replace("_", " ")}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        act.priority === "high"
                          ? "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20"
                          : act.priority === "medium"
                          ? "bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20"
                          : "bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20"
                      }`}
                    >
                      {act.priority.toUpperCase()} PRIORITY
                    </span>
                  </div>
                  <h3 className="font-semibold text-[#F5F5F5] text-xs md:text-sm">{act.title}</h3>
                  <p className="text-[#A1A1AA] text-xs leading-relaxed">{act.description}</p>
                  {act.reason && (
                    <p className="text-[11px] text-[#71717A] italic bg-[#080808] p-2 rounded border border-[#262626]">
                      Rationale: {act.reason}
                    </p>
                  )}
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#262626] gap-2">
                  {act.source_citation ? (
                    <button
                      type="button"
                      onClick={() => setActiveCitation(act.source_citation || null)}
                      className="text-[#3B82F6] hover:text-[#60A5FA] text-xs font-medium flex items-center gap-1.5"
                    >
                      <BookOpen className="w-3.5 h-3.5" aria-hidden="true" /> View Verified Source
                    </button>
                  ) : (
                    <span className="text-[#71717A] text-[11px]">Curriculum Synthesis</span>
                  )}

                  <Link
                    href={act.action === "quiz" ? "/assessments" : act.action === "tutor" ? "/tutor" : "/courses"}
                    className="px-3 py-1.5 rounded bg-[#3B82F6] hover:bg-[#2563EB] text-white font-medium text-xs flex items-center gap-1 transition-colors"
                  >
                    Take Action <ArrowRight className="w-3 h-3" aria-hidden="true" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Personalized Study Plan Widget */}
      <div className="p-5 md:p-6 rounded-md bg-[#121212] border border-[#262626] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#262626] pb-3">
          <div>
            <h2 className="text-base font-semibold text-[#F5F5F5] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" />
              Personalized Time-Bounded Study Plan
            </h2>
            <p className="text-xs text-[#A1A1AA] mt-0.5">
              Constrained by daily availability and exam deadlines. Focuses on weak topics and upcoming spaced reviews.
            </p>
          </div>

          <form onSubmit={handleRecalculatePlan} className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-[#080808] px-2.5 py-1.5 rounded-md border border-[#262626] text-xs">
              <Clock className="w-3.5 h-3.5 text-[#71717A]" aria-hidden="true" />
              <label htmlFor="daily-study-select" className="sr-only">Daily Study Time</label>
              <select
                id="daily-study-select"
                aria-label="Daily Study Time"
                value={dailyMinutes}
                onChange={(e) => setDailyMinutes(Number(e.target.value))}
                className="bg-transparent text-[#F5F5F5] font-mono outline-none cursor-pointer"
              >
                <option value={15} className="bg-[#121212]">15 min/day</option>
                <option value={30} className="bg-[#121212]">30 min/day</option>
                <option value={45} className="bg-[#121212]">45 min/day</option>
                <option value={60} className="bg-[#121212]">60 min/day</option>
              </select>
            </div>

            <div className="flex items-center gap-1 bg-[#080808] px-2.5 py-1.5 rounded-md border border-[#262626] text-xs">
              <Calendar className="w-3.5 h-3.5 text-[#71717A]" aria-hidden="true" />
              <label htmlFor="exam-date-input" className="sr-only">Target Exam Date</label>
              <input
                id="exam-date-input"
                type="date"
                aria-label="Target Exam Date"
                value={targetExamDate}
                onChange={(e) => setTargetExamDate(e.target.value)}
                className="bg-transparent text-[#F5F5F5] font-mono outline-none text-xs"
              />
            </div>

            <button
              type="submit"
              disabled={planLoading}
              className="px-3 py-1.5 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-white font-medium text-xs flex items-center gap-1.5 transition-colors"
            >
              <Sliders className="w-3.5 h-3.5" aria-hidden="true" />
              {planLoading ? "Generating..." : "Recalibrate Plan"}
            </button>
          </form>
        </div>

        {studyPlan?.is_provisional && studyPlan.provisional_notice && (
          <div className="p-3 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/20 text-[#F59E0B] text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-[#F59E0B]" aria-hidden="true" />
            <span>{studyPlan.provisional_notice}</span>
          </div>
        )}

        {studyPlan?.schedule && studyPlan.schedule.length > 0 ? (
          <div className="space-y-2.5">
            {studyPlan.schedule.map((item, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-md bg-[#080808] border border-[#262626] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-start gap-3">
                  <div className="px-2.5 py-1.5 rounded bg-[#181818] border border-[#262626] text-[#3B82F6] font-mono text-center shrink-0">
                    <span className="block text-[10px] uppercase text-[#71717A]">Day</span>
                    <span className="text-base font-bold">+{item.day_offset}</span>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#F5F5F5]">{item.title}</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#181818] text-[#A1A1AA] border border-[#262626] uppercase">
                        {item.activity_type.replace("_", " ")}
                      </span>
                    </div>
                    <p className="text-[#A1A1AA] text-xs mt-1">{item.description}</p>
                    <p className="text-[11px] text-[#71717A] mt-0.5 font-mono">
                      Reason: {item.reason}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-center">
                  <span className="text-xs font-mono font-medium text-[#22C55E] bg-[#22C55E]/10 px-2 py-1 rounded border border-[#22C55E]/20">
                    {item.suggested_duration_minutes} mins
                  </span>
                  {item.source_citation && (
                    <button
                      type="button"
                      onClick={() => setActiveCitation(item.source_citation || null)}
                      className="p-1.5 rounded bg-[#181818] hover:bg-[#262626] text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors border border-[#262626]"
                      title="View Verified Source Passage"
                    >
                      <FileText className="w-4 h-4" aria-hidden="true" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center rounded-md bg-[#080808] border border-[#262626] text-[#71717A] text-xs">
            No study plan active. Set your daily availability or target exam date above to generate your customized plan.
          </div>
        )}
      </div>

      {/* Detailed BKT Mastery Parameters Table */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
          Topic Mastery & Bayesian Parameters
        </h2>

        <div className="overflow-x-auto rounded-md border border-[#262626] bg-[#121212]">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0B0B0B] text-[#71717A] font-semibold border-b border-[#262626]">
              <tr>
                <th className="p-3">Curriculum Topic</th>
                <th className="p-3">Mastery P(L)</th>
                <th className="p-3">P(Transit)</th>
                <th className="p-3">P(Guess)</th>
                <th className="p-3">P(Slip)</th>
                <th className="p-3">Attempts</th>
                <th className="p-3">Accuracy</th>
                <th className="p-3">Next Review</th>
                <th className="p-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#262626] font-mono text-[#A1A1AA]">
              {profile?.topics.map((t) => {
                const acc = t.attempts_count > 0 ? Math.round((t.correct_count / t.attempts_count) * 100) : 0;
                return (
                  <tr key={t.topic_name} className="hover:bg-[#181818] transition-colors">
                    <td className="p-3 font-sans font-medium text-[#F5F5F5]">{t.topic_name}</td>
                    <td className="p-3 font-bold text-[#22C55E]">
                      {Math.round(t.mastery_score * 100)}%
                    </td>
                    <td className="p-3 text-[#71717A]">{t.p_transit.toFixed(2)}</td>
                    <td className="p-3 text-[#71717A]">{t.p_guess.toFixed(2)}</td>
                    <td className="p-3 text-[#71717A]">{t.p_slip.toFixed(2)}</td>
                    <td className="p-3 text-[#A1A1AA]">{t.attempts_count}</td>
                    <td className="p-3 text-[#A1A1AA]">{acc}%</td>
                    <td className="p-3 text-[#71717A] text-[11px]">
                      {t.next_review_at ? new Date(t.next_review_at).toLocaleDateString() : "Pending"}
                    </td>
                    <td className="p-3 text-right font-sans">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                          t.status === "mastered"
                            ? "bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20"
                            : t.status === "in_progress"
                            ? "bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20"
                            : t.status === "unassessed"
                            ? "bg-[#181818] text-[#71717A] border border-[#262626]"
                            : "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20"
                        }`}
                      >
                        {t.status.replace("_", " ")}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Mastery Transitions & Audit Trail */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
          <Clock className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
          Mastery Progression & Audit Log ({history.length} Events)
        </h2>

        {history.length > 0 ? (
          <div className="overflow-x-auto rounded-md border border-[#262626] bg-[#121212]">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0B0B0B] text-[#71717A] font-semibold border-b border-[#262626]">
                <tr>
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Topic</th>
                  <th className="p-3">Result</th>
                  <th className="p-3">Score Delta</th>
                  <th className="p-3">Latent Mastery P(L)</th>
                  <th className="p-3">Observed Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626] font-mono text-[#A1A1AA]">
                {history.slice(0, 10).map((h) => {
                  const isGain = h.score_delta >= 0;
                  return (
                    <tr key={h.id} className="hover:bg-[#181818] transition-colors">
                      <td className="p-3 text-[#71717A] text-[11px]">
                        {new Date(h.recorded_at).toLocaleString()}
                      </td>
                      <td className="p-3 font-sans font-medium text-[#F5F5F5]">{h.topic_name}</td>
                      <td className="p-3">
                        {h.is_correct === true ? (
                          <span className="flex items-center gap-1 text-[#22C55E] font-sans">
                            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Correct
                          </span>
                        ) : h.is_correct === false ? (
                          <span className="flex items-center gap-1 text-[#EF4444] font-sans">
                            <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" /> Incorrect
                          </span>
                        ) : (
                          <span className="text-[#71717A] font-sans">Update</span>
                        )}
                      </td>
                      <td className={`p-3 font-bold ${isGain ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                        {isGain ? `+${h.score_delta.toFixed(4)}` : h.score_delta.toFixed(4)}
                      </td>
                      <td className="p-3 font-bold text-[#F5F5F5]">
                        {Math.round(h.mastery_score * 100)}%
                      </td>
                      <td className="p-3 text-[#71717A]">
                        {h.observed_score !== undefined && h.observed_score !== null
                          ? `${Math.round(h.observed_score * 100)}%`
                          : "N/A"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center rounded-md bg-[#121212] border border-[#262626] text-[#71717A] text-xs">
            No historical mastery transitions recorded yet. Complete quizzes to generate empirical audit logs.
          </div>
        )}
      </div>

      {/* Historical Assessment Sessions Log */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
          <Calendar className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
          Assessment Session History ({assessments.length})
        </h2>

        {assessments.length > 0 ? (
          <div className="space-y-2.5">
            {assessments.map((a) => (
              <div
                key={a.id}
                className="p-3.5 rounded-md bg-[#121212] border border-[#262626] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[#F5F5F5] text-xs md:text-sm">{a.title}</span>
                    <span className="px-2 py-0.5 rounded bg-[#181818] text-[#A1A1AA] border border-[#262626] text-[10px] font-mono">
                      {a.difficulty}
                    </span>
                  </div>
                  <span className="text-[#71717A] font-mono text-[11px] mt-0.5 block">
                    {new Date(a.created_at).toLocaleString()} &bull; {a.total_questions} Questions
                  </span>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <span className="text-[#71717A] block text-[10px]">Score</span>
                    <span className="font-mono font-medium text-sm md:text-base text-[#22C55E]">
                      {a.score !== null && a.score !== undefined ? `${Math.round(a.score * 100)}%` : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center rounded-md bg-[#121212] border border-[#262626] text-[#71717A] text-xs">
            No completed assessments yet. Complete a quiz to populate your historical timeline.
          </div>
        )}
      </div>

      {/* Source Citation Modal */}
      <SourceViewerModal
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
