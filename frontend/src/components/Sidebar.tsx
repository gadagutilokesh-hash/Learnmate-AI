"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BookOpen,
  MessageSquareQuote,
  GraduationCap,
  TrendingUp,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Layers
} from "lucide-react";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/courses", label: "Course Ingestion", icon: BookOpen },
    { href: "/tutor", label: "Grounded AI Tutor", icon: MessageSquareQuote },
    { href: "/assessments", label: "Adaptive Quizzes", icon: GraduationCap },
    { href: "/progress", label: "Student Progress", icon: TrendingUp },
    { href: "/evaluation", label: "RAG Evaluation", icon: BarChart3 }
  ];

  return (
    <aside
      className={`relative flex flex-col border-r border-slate-800 bg-slate-950/95 transition-all duration-200 z-30 ${
        collapsed ? "w-20" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between px-4 py-5 border-b border-slate-800/80">
        <Link href="/" className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 text-white font-bold shadow-lg shadow-indigo-500/20 shrink-0">
            <Sparkles className="w-5 h-5 text-indigo-100" />
          </div>
          {!collapsed && (
            <div>
              <span className="font-bold text-base tracking-tight text-white block">
                LearnMate AI
              </span>
              <span className="text-[10px] text-indigo-400 font-medium tracking-wide uppercase block">
                Track D • Multimodal 2026
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/25"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Track & Grounding Assurance Pill */}
      {!collapsed && (
        <div className="p-4 m-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs space-y-1.5">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Source-Grounded</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Zero citation hallucinations. Verified against PDF pages, slides & transcripts.
          </p>
        </div>
      )}
    </aside>
  );
}
