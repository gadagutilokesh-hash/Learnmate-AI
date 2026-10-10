"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LearnerProfile, Course, Assessment } from "@/lib/types";
import { MasteryBar } from "@/components/MasteryBar";
import {
  BookOpen,
  GraduationCap,
  MessageSquareQuote,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  FileCheck
} from "lucide-react";

export default function DashboardPage() {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [recentAssessments, setRecentAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [profData, courseList, assessList] = await Promise.all([
          api.getLearnerProfile(),
          api.listCourses(),
          api.listAssessments()
        ]);
        setProfile(profData);
        setCourses(courseList);
        setRecentAssessments(assessList);
      } catch (e) {
        console.error("Dashboard data load error:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Loading LearnMate AI learner model & courses...</p>
      </div>
    );
  }

  const overallMasteryPct = profile ? Math.round(profile.overall_mastery * 100) : 0;
  const activeCourse = courses[0];

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Top Banner / Welcome */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/20 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Track D: Personalized Tutoring & Adaptive Learning
            </span>
            <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
              <ShieldCheck className="w-3.5 h-3.5" /> 100% Grounded
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
            Welcome back to LearnMate AI
          </h1>
          <p className="text-sm text-slate-400 max-w-2xl">
            Your source-grounded study companion. Ingest lecture notes, textbooks, and video transcripts; query with verified citations; and track concept mastery with Bayesian Knowledge Tracing.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link
            href="/tutor"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-all shadow-md shadow-indigo-600/30"
          >
            <MessageSquareQuote className="w-4 h-4" /> Ask Grounded Tutor
          </Link>
          <Link
            href="/assessments"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-sm border border-slate-700 transition-all"
          >
            <GraduationCap className="w-4 h-4" /> Adaptive Quiz
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overall Mastery Gauge */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Overall Mastery</span>
            <TrendingUp className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">{overallMasteryPct}%</span>
            <span className="text-xs text-slate-400">Bayesian Knowledge Score</span>
          </div>
          <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-700"
              style={{ width: `${overallMasteryPct}%` }}
            />
          </div>
        </div>

        {/* Uploaded Courses & Docs */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Enrolled Courses</span>
            <BookOpen className="w-4 h-4 text-sky-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">{courses.length}</span>
            <span className="text-xs text-slate-400">
              ({activeCourse?.documents_count || 0} Ingested Docs)
            </span>
          </div>
          <p className="text-xs text-slate-400 truncate">
            {activeCourse ? activeCourse.title : "No active course"}
          </p>
        </div>

        {/* Mastery Breakdown Stats */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Mastered Concepts</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-emerald-400">
              {profile?.strong_topics.length || 0}
            </span>
            <span className="text-xs text-slate-400">
              of {profile?.topics.length || 0} Curriculum Topics
            </span>
          </div>
          <p className="text-xs text-slate-400">
            {profile?.weak_topics.length || 0} topics currently require review
          </p>
        </div>

        {/* Completed Quizzes */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Assessments Completed</span>
            <FileCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">
              {recentAssessments.length}
            </span>
            <span className="text-xs text-slate-400">Adaptive Sessions</span>
          </div>
          <p className="text-xs text-slate-400">
            Average accuracy tracked deterministically
          </p>
        </div>
      </div>

      {/* Main Grid: Topic Mastery vs Next Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column (2 Cols): Topic Mastery Breakdown */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-400" />
              Topic-Level Mastery (Bayesian Knowledge Tracing)
            </h2>
            <Link
              href="/progress"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
            >
              Detailed Analytics <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {profile?.topics.map((t) => (
              <MasteryBar key={t.topic_name} topic={t} />
            ))}
          </div>

          {(!profile?.topics || profile.topics.length === 0) && (
            <div className="p-8 text-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-sm">
              No topic mastery estimates yet. Upload materials or take a diagnostic quiz.
            </div>
          )}
        </div>

        {/* Right Column: Recommended Next Activities */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            Recommended Next Activities
          </h2>

          <div className="space-y-3">
            {profile?.recommended_activities.map((act, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${
                      act.priority === "high"
                        ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        : "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                    }`}
                  >
                    {act.priority} Priority
                  </span>
                  <span className="text-xs font-mono text-slate-500">{act.topic}</span>
                </div>
                <h4 className="text-sm font-semibold text-slate-200">{act.title}</h4>
                <p className="text-xs text-slate-400 leading-relaxed">{act.description}</p>
                <div className="pt-1">
                  <Link
                    href={act.action === "quiz" ? "/assessments" : "/tutor"}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Launch Activity <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Assessment Results */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <GraduationCap className="w-5 h-5 text-purple-400" />
            Recent Assessment Results
          </h2>
          <Link
            href="/assessments"
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
          >
            Take New Quiz <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {recentAssessments.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recentAssessments.map((a) => (
              <div
                key={a.id}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {a.difficulty}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-white truncate">{a.title}</h4>
                <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/80">
                  <span className="text-slate-400">Questions: {a.total_questions}</span>
                  <span className="font-mono font-bold text-emerald-400">
                    {a.score !== null && a.score !== undefined ? `${Math.round(a.score * 100)}%` : "Not taken"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-sm">
            No quiz attempts yet. Start your first adaptive assessment to calibrate your learner model.
          </div>
        )}
      </div>
    </div>
  );
}
