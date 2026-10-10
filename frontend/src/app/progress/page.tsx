"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { LearnerProfile, Assessment } from "@/lib/types";
import { MasteryBar } from "@/components/MasteryBar";
import {
  TrendingUp,
  Brain,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Layers,
  ArrowRight,
  BookOpen,
  Award
} from "lucide-react";
import Link from "next/link";

export default function ProgressPage() {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [prof, assessList] = await Promise.all([
          api.getLearnerProfile(),
          api.listAssessments()
        ]);
        setProfile(prof);
        setAssessments(assessList);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Loading Student Learner Model...</p>
      </div>
    );
  }

  const overallMasteryPct = profile ? Math.round(profile.overall_mastery * 100) : 0;

  return (
    <div className="space-y-8 max-w-5xl mx-auto animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-indigo-400" /> Student Progress & Bayesian Mastery Analytics
        </h1>
        <p className="text-sm text-slate-400">
          Deterministic knowledge tracing tracking concept acquisition, guess & slip parameters, and personalized remediation paths.
        </p>
      </div>

      {/* Top Mastery Overview Card */}
      <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-indigo-950/40 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            <Brain className="w-4 h-4" /> Cognitive Learner State
          </div>
          <h2 className="text-3xl font-extrabold text-white">
            Overall Curriculum Mastery: {overallMasteryPct}%
          </h2>
          <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
            Updated via Bayesian Knowledge Tracing across {assessments.length} assessment sessions and grounded tutoring interactions.
          </p>
        </div>

        <div className="flex items-center gap-4 bg-slate-950/80 p-4 rounded-xl border border-slate-800 shrink-0">
          <div className="text-center px-3 border-r border-slate-800">
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {profile?.strong_topics.length || 0}
            </span>
            <span className="text-[11px] text-slate-400 block">Mastered</span>
          </div>
          <div className="text-center px-3 border-r border-slate-800">
            <span className="text-2xl font-bold font-mono text-amber-400">
              {profile ? profile.topics.length - profile.strong_topics.length - profile.weak_topics.length : 0}
            </span>
            <span className="text-[11px] text-slate-400 block">In Progress</span>
          </div>
          <div className="text-center px-3">
            <span className="text-2xl font-bold font-mono text-rose-400">
              {profile?.weak_topics.length || 0}
            </span>
            <span className="text-[11px] text-slate-400 block">Weak Areas</span>
          </div>
        </div>
      </div>

      {/* Weak Areas Alert & Remediation */}
      {profile?.weak_topics && profile.weak_topics.length > 0 && (
        <div className="p-5 rounded-xl bg-rose-500/10 border border-rose-500/20 space-y-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" /> Focus Areas Requiring Revision ({profile.weak_topics.length})
            </span>
            <Link
              href="/assessments"
              className="text-xs font-semibold text-rose-300 hover:text-white flex items-center gap-1"
            >
              Start Targeted Quiz <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {profile.weak_topics.map((w, idx) => (
              <span
                key={idx}
                className="px-3 py-1 rounded-lg bg-slate-950 text-rose-300 text-xs font-medium border border-rose-500/30"
              >
                {w}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Detailed BKT Mastery Parameters Table */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-400" />
          Topic Mastery & Bayesian Parameters
        </h3>

        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
              <tr>
                <th className="p-3.5">Curriculum Topic</th>
                <th className="p-3.5">Mastery P(L)</th>
                <th className="p-3.5">P(Transit)</th>
                <th className="p-3.5">P(Guess)</th>
                <th className="p-3.5">P(Slip)</th>
                <th className="p-3.5">Attempts</th>
                <th className="p-3.5">Accuracy</th>
                <th className="p-3.5 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-mono text-slate-300">
              {profile?.topics.map((t) => {
                const acc = t.attempts_count > 0 ? Math.round((t.correct_count / t.attempts_count) * 100) : 0;
                return (
                  <tr key={t.topic_name} className="hover:bg-slate-800/50 transition-colors">
                    <td className="p-3.5 font-sans font-medium text-white">{t.topic_name}</td>
                    <td className="p-3.5 font-bold text-emerald-400">
                      {Math.round(t.mastery_score * 100)}%
                    </td>
                    <td className="p-3.5 text-slate-400">{t.p_transit.toFixed(2)}</td>
                    <td className="p-3.5 text-slate-400">{t.p_guess.toFixed(2)}</td>
                    <td className="p-3.5 text-slate-400">{t.p_slip.toFixed(2)}</td>
                    <td className="p-3.5 text-slate-300">{t.attempts_count}</td>
                    <td className="p-3.5 text-slate-300">{acc}%</td>
                    <td className="p-3.5 text-right font-sans">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                          t.status === "mastered"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : t.status === "in_progress"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
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

      {/* Historical Assessment Log */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Calendar className="w-5 h-5 text-indigo-400" />
          Assessment Session History ({assessments.length})
        </h3>

        {assessments.length > 0 ? (
          <div className="space-y-3">
            {assessments.map((a) => (
              <div
                key={a.id}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white text-sm">{a.title}</span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-mono">
                      {a.difficulty}
                    </span>
                  </div>
                  <span className="text-slate-500 font-mono text-[11px] mt-0.5 block">
                    {new Date(a.created_at).toLocaleString()} • {a.total_questions} Questions
                  </span>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <span className="text-slate-400 block text-[10px]">Score</span>
                    <span className="font-mono font-bold text-base text-emerald-400">
                      {a.score !== null && a.score !== undefined ? `${Math.round(a.score * 100)}%` : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-xs">
            No completed assessments yet. Complete a quiz to populate your historical timeline.
          </div>
        )}
      </div>
    </div>
  );
}
