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
  ArrowRight,
  FileCheck,
  ChevronDown,
  ChevronUp,
  Layers
} from "lucide-react";

export default function DashboardPage() {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [recentAssessments, setRecentAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDetailedMastery, setShowDetailedMastery] = useState(false);

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
        if (courseList.length > 0) {
          setSelectedCourseId(courseList[0].id);
        }
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
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center min-h-[50vh] gap-3"
      >
        <div className="w-7 h-7 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
        <p className="text-[#71717A] text-xs">Loading learner data...</p>
      </div>
    );
  }

  const overallMasteryPct = profile ? Math.round(profile.overall_mastery * 100) : 0;
  const activeCourse = courses.find((c) => c.id === selectedCourseId) || courses[0];

  // Deduplicate and limit recommendations to top 3
  const rawActivities = profile?.recommended_activities || [];
  const uniqueActivities = rawActivities.filter(
    (act, index, self) => index === self.findIndex((a) => a.title === act.title && a.topic === act.topic)
  ).slice(0, 3);

  // Determine top priority action for Continue Learning
  const topActivity = uniqueActivities[0];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* A. Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#262626]">
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[#F5F5F5]">
            Learning Dashboard
          </h1>
          <p className="text-xs md:text-sm text-[#A1A1AA] mt-1">
            Track your course progress, continue study sessions, and review recent assessments.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {courses.length > 0 && (
            <label htmlFor="dashboard-course-selector" className="sr-only">
              Current course
            </label>
          )}
          {courses.length > 0 && (
            <select
              id="dashboard-course-selector"
              value={selectedCourseId}
              onChange={(e) => setSelectedCourseId(e.target.value)}
              className="px-3 py-2 rounded-md bg-[#121212] border border-[#262626] text-xs text-[#F5F5F5] font-medium focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] cursor-pointer"
            >
              {courses.map((c) => {
                const isDemo = c.is_demo || c.visibility === "shared_demo";
                return (
                  <option key={c.id} value={c.id}>
                    {isDemo ? `[Demo] ${c.title}` : `[Private] ${c.title}`}
                  </option>
                );
              })}
            </select>
          )}

          <Link
            href="/tutor"
            className="flex items-center gap-2 px-3.5 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white font-medium text-xs md:text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
          >
            <MessageSquareQuote className="w-4 h-4" aria-hidden="true" /> Ask Grounded Tutor
          </Link>
        </div>
      </div>

      {/* Standalone Deployment Status Banner (Visible when backend has not connected yet) */}
      {courses.length === 0 && (
        <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-[#A1A1AA]">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-[#F59E0B] shrink-0" aria-hidden="true" />
            <span>
              <strong className="text-[#F5F5F5] font-medium">Standalone Frontend Deployment:</strong> Backend API is currently offline. AI tutoring, live assessments, and course ingestion will activate automatically once your FastAPI backend server is deployed and connected via <code className="text-[#3B82F6] font-mono text-[11px]">NEXT_PUBLIC_API_URL</code>.
            </span>
          </div>
        </div>
      )}

      {/* B. Learning Overview */}
      <section aria-labelledby="overview-heading" className="space-y-3">
        <h2 id="overview-heading" className="text-xs uppercase tracking-wider font-semibold text-[#71717A]">
          Learning Overview
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* 1. Overall Mastery */}
          <div className="p-4 rounded-md bg-[#121212] border border-[#262626] space-y-2">
            <div className="flex items-center justify-between text-[#A1A1AA] text-xs">
              <span>Overall Mastery</span>
              <TrendingUp className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-[#F5F5F5]">{overallMasteryPct}%</span>
              <span className="text-xs text-[#71717A]">Bayesian Score</span>
            </div>
            <div
              role="progressbar"
              aria-label="Overall topic mastery percentage"
              aria-valuenow={overallMasteryPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="w-full h-1.5 rounded bg-[#181818] overflow-hidden"
            >
              <div
                className="h-full rounded bg-[#3B82F6] transition-all duration-300"
                style={{ width: `${overallMasteryPct}%` }}
              />
            </div>
          </div>

          {/* 2. Active Courses */}
          <div className="p-4 rounded-md bg-[#121212] border border-[#262626] space-y-2">
            <div className="flex items-center justify-between text-[#A1A1AA] text-xs">
              <span>Active Courses</span>
              <BookOpen className="w-4 h-4 text-[#A1A1AA]" aria-hidden="true" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-[#F5F5F5]">{courses.length}</span>
              <span className="text-xs text-[#71717A]">
                ({activeCourse?.documents_count || 0} Files Ingested)
              </span>
            </div>
            <p className="text-xs text-[#71717A] truncate">
              {activeCourse ? activeCourse.title : "No active course"}
            </p>
          </div>

          {/* 3. Completed Assessments */}
          <div className="p-4 rounded-md bg-[#121212] border border-[#262626] space-y-2">
            <div className="flex items-center justify-between text-[#A1A1AA] text-xs">
              <span>Assessments Completed</span>
              <FileCheck className="w-4 h-4 text-[#22C55E]" aria-hidden="true" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-[#F5F5F5]">{recentAssessments.length}</span>
              <span className="text-xs text-[#71717A]">Sessions Graded</span>
            </div>
            <p className="text-xs text-[#71717A]">
              Calibrated by deterministic scoring
            </p>
          </div>
        </div>
      </section>

      {/* C. Continue Learning */}
      <section aria-labelledby="continue-heading" className="space-y-3">
        <h2 id="continue-heading" className="text-xs uppercase tracking-wider font-semibold text-[#71717A]">
          Continue Learning
        </h2>
        <div className="p-5 rounded-md bg-[#121212] border border-[#262626] flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#181818] text-[#3B82F6] border border-[#262626] font-medium">
                {activeCourse ? activeCourse.title : "Getting Started"}
              </span>
              {topActivity?.topic && (
                <span className="text-xs text-[#71717A]">Topic: {topActivity.topic}</span>
              )}
            </div>
            <h3 className="text-sm md:text-base font-semibold text-[#F5F5F5]">
              {topActivity?.title || "Ask questions or take a practice quiz"}
            </h3>
            <p className="text-xs text-[#A1A1AA] max-w-2xl leading-relaxed">
              {topActivity?.description ||
                "Consult the grounded AI tutor with verified citations from your uploaded textbooks and lecture materials."}
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Link
              href="/tutor"
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-[#181818] hover:bg-[#262626] text-[#F5F5F5] border border-[#262626] text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
            >
              <MessageSquareQuote className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" />
              Open Tutor
            </Link>
            <Link
              href="/assessments"
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
            >
              <GraduationCap className="w-3.5 h-3.5" aria-hidden="true" />
              Practice Quiz
            </Link>
          </div>
        </div>
      </section>

      {/* D. Recommended Next Activities */}
      <section aria-labelledby="recommendations-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="recommendations-heading" className="text-xs uppercase tracking-wider font-semibold text-[#71717A]">
            Recommended Next Activities
          </h2>
          <Link
            href="/progress"
            className="text-xs text-[#3B82F6] hover:text-[#60A5FA] font-medium flex items-center gap-1"
          >
            Study Plan <ArrowRight className="w-3 h-3" aria-hidden="true" />
          </Link>
        </div>

        {uniqueActivities.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {uniqueActivities.map((act, idx) => (
              <div
                key={idx}
                className="p-4 rounded-md bg-[#121212] border border-[#262626] hover:border-[#363636] transition-colors flex flex-col justify-between space-y-3"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded ${
                        act.priority === "high"
                          ? "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20"
                          : "bg-[#3B82F6]/10 text-[#3B82F6] border border-[#3B82F6]/20"
                      }`}
                    >
                      {act.priority} Priority
                    </span>
                    <span className="text-[11px] font-mono text-[#71717A] truncate max-w-[120px]">
                      {act.topic}
                    </span>
                  </div>
                  <h3 className="text-xs font-semibold text-[#F5F5F5]">{act.title}</h3>
                  <p className="text-[11px] text-[#A1A1AA] leading-relaxed line-clamp-2">
                    {act.description}
                  </p>
                </div>

                <div className="pt-2 border-t border-[#181818]">
                  <Link
                    href={act.action === "quiz" ? "/assessments" : "/tutor"}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-[#3B82F6] hover:text-[#60A5FA] transition-colors"
                  >
                    Start Activity <ArrowRight className="w-3 h-3" aria-hidden="true" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center rounded-md bg-[#121212] border border-[#262626] text-[#71717A] text-xs">
            No recommended activities. Select a course to start studying.
          </div>
        )}
      </section>

      {/* E. Recent Assessment Results */}
      <section aria-labelledby="assessments-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="assessments-heading" className="text-xs uppercase tracking-wider font-semibold text-[#71717A]">
            Recent Assessment Results
          </h2>
          <Link
            href="/assessments"
            className="text-xs text-[#3B82F6] hover:text-[#60A5FA] font-medium flex items-center gap-1"
          >
            All Quizzes <ArrowRight className="w-3 h-3" aria-hidden="true" />
          </Link>
        </div>

        {recentAssessments.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {recentAssessments.slice(0, 3).map((a) => (
              <div
                key={a.id}
                className="p-3.5 rounded-md bg-[#121212] border border-[#262626] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#181818] text-[#A1A1AA] border border-[#262626] capitalize">
                    {a.difficulty}
                  </span>
                  <span className="text-[11px] text-[#71717A] font-mono">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="text-xs font-medium text-[#F5F5F5] truncate">{a.title}</h3>
                <div className="flex items-center justify-between text-xs pt-2 border-t border-[#181818]">
                  <span className="text-[#71717A]">Questions: {a.total_questions}</span>
                  <span className="font-mono font-medium text-[#22C55E]">
                    {a.score !== null && a.score !== undefined ? `${Math.round(a.score * 100)}%` : "Ungraded"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center rounded-md bg-[#121212] border border-[#262626] text-[#71717A] text-xs">
            No quiz attempts recorded. Start an adaptive assessment to calibrate your learner model.
          </div>
        )}
      </section>

      {/* F. Expandable Topic Mastery Breakdown (Secondary / Low Visual Noise) */}
      <section aria-labelledby="topic-mastery-heading" className="pt-2 border-t border-[#262626]">
        <button
          type="button"
          onClick={() => setShowDetailedMastery(!showDetailedMastery)}
          className="w-full flex items-center justify-between p-3 rounded-md bg-[#121212] hover:bg-[#181818] border border-[#262626] transition-colors text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
        >
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
            <span id="topic-mastery-heading" className="text-xs font-semibold text-[#F5F5F5]">
              Topic-Level Mastery Details ({profile?.topics.length || 0} topics)
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#71717A]">
            <span>{showDetailedMastery ? "Hide Details" : "Show Details"}</span>
            {showDetailedMastery ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showDetailedMastery && (
          <div className="mt-3.5 space-y-3 animate-in fade-in duration-150">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {profile?.topics.map((t) => (
                <MasteryBar key={t.topic_name} topic={t} />
              ))}
            </div>
            <div className="flex justify-end pt-1">
              <Link
                href="/progress"
                className="text-xs text-[#3B82F6] hover:text-[#60A5FA] font-medium flex items-center gap-1"
              >
                Open Full Analytics & Study Plan <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </Link>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
