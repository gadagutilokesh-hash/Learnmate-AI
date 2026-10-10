"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { HealthStatus, Course } from "@/lib/types";
import { Cpu, Database, CheckCircle2, AlertCircle, BookOpen, User } from "lucide-react";

export function Header() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [activeCourseId, setActiveCourseId] = useState<string>("");

  useEffect(() => {
    api.getHealth()
      .then(setHealth)
      .catch((err) => console.warn("Backend not reached yet:", err));

    api.listCourses()
      .then((cList) => {
        setCourses(cList);
        if (cList.length > 0) {
          setActiveCourseId(cList[0].id);
        }
      })
      .catch((err) => console.warn("Could not list courses:", err));
  }, []);

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Active Course Selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-sm">
          <BookOpen className="w-4 h-4 text-indigo-400" />
          <span className="text-slate-400 text-xs hidden sm:inline">Active Course:</span>
          {courses.length > 0 ? (
            <select
              value={activeCourseId}
              onChange={(e) => setActiveCourseId(e.target.value)}
              className="bg-transparent text-slate-200 text-xs sm:text-sm font-medium focus:outline-none cursor-pointer"
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id} className="bg-slate-900 text-slate-200">
                  {c.title}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-slate-400 text-xs font-mono">Loading courses...</span>
          )}
        </div>
      </div>

      {/* System Status Indicators */}
      <div className="flex items-center gap-3">
        {/* Gemini Engine Status */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-slate-400">Gemini 2.0:</span>
          {health?.gemini_configured ? (
            <span className="text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3 h-3" /> Live
            </span>
          ) : (
            <span className="text-amber-400 flex items-center gap-1 font-medium">
              Simulation Mode
            </span>
          )}
        </div>

        {/* Database Engine Status */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
          <Database className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-slate-400">DB:</span>
          <span className="text-sky-300 font-mono font-medium">
            {health?.storage_mode === "supabase" ? "Supabase pgvector" : "Local Embedded"}
          </span>
        </div>

        {/* User Profile avatar */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 font-medium text-xs">
            <User className="w-4 h-4" />
          </div>
          <span className="text-xs font-medium text-slate-300 hidden sm:inline">Student</span>
        </div>
      </div>
    </header>
  );
}
