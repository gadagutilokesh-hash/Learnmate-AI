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
  ShieldCheck
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
      aria-label="Application navigation"
      className={`relative flex flex-col border-r border-[#262626] bg-[#0B0B0B] transition-all duration-200 z-30 shrink-0 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-[#262626]">
        <Link
          href="/"
          className="flex items-center gap-2.5 overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6] rounded-md"
        >
          {/* Distinctive Geometric App Icon */}
          <div className="w-8 h-8 rounded-md bg-[#3B82F6] flex items-center justify-center text-white shrink-0">
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
              <path d="M6 6h10" />
              <path d="M6 10h10" />
            </svg>
          </div>
          {!collapsed && (
            <div className="leading-tight">
              <span className="font-semibold text-sm tracking-tight text-[#F5F5F5] block">
                LearnMate AI
              </span>
              <span className="text-[11px] text-[#71717A] font-normal block">
                Source-Grounded Study
              </span>
            </div>
          )}
        </Link>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md text-[#71717A] hover:text-[#F5F5F5] hover:bg-[#181818] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
          aria-label={collapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-2.5 py-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs md:text-sm font-medium transition-colors ${
                isActive
                  ? "bg-[#181818] text-[#F5F5F5] border border-[#363636]"
                  : "text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-[#121212]"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive ? "text-[#3B82F6]" : "text-[#71717A]"
                }`}
                aria-hidden="true"
              />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Grounding Assurance Indicator */}
      {!collapsed && (
        <div className="p-3 m-2.5 rounded-md bg-[#121212] border border-[#262626] text-xs space-y-1">
          <div className="flex items-center gap-1.5 font-medium text-[#F5F5F5]">
            <ShieldCheck className="w-3.5 h-3.5 text-[#22C55E]" aria-hidden="true" />
            <span>Strict Grounding</span>
          </div>
          <p className="text-[11px] text-[#71717A] leading-relaxed">
            Tutoring answers cite indexed textbooks, slides, and lecture media.
          </p>
        </div>
      )}
    </aside>
  );
}
