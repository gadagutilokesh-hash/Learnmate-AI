"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, BookOpen, FileText } from "lucide-react";

export function Footer() {
  const pathname = usePathname();

  // On the tutor page, avoid unnecessary footer content that steals vertical chat height
  if (pathname === "/tutor") {
    return (
      <footer className="border-t border-[#262626] bg-[#0B0B0B] py-2 px-4 text-center text-[11px] text-[#71717A]">
        <span>LearnMate AI &bull; Strict Source Grounding &bull; </span>
        <Link href="/privacy" className="hover:text-[#F5F5F5] transition-colors ml-1">
          Privacy
        </Link>
        <span className="mx-1">&bull;</span>
        <Link href="/terms" className="hover:text-[#F5F5F5] transition-colors">
          Terms
        </Link>
      </footer>
    );
  }

  return (
    <footer className="border-t border-[#262626] bg-[#0B0B0B] text-[#A1A1AA] mt-auto">
      <div className="max-w-7xl mx-auto px-6 py-8 md:py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand & Provenance statement */}
          <div className="space-y-3 md:col-span-2">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-md bg-[#3B82F6] flex items-center justify-center text-white">
                <BookOpen className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-[#F5F5F5] tracking-tight">
                LearnMate AI
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] text-[#22C55E] bg-[#22C55E]/10 border border-[#22C55E]/20 px-2 py-0.5 rounded">
                <ShieldCheck className="w-3 h-3" /> Grounded RAG
              </span>
            </div>
            <p className="text-xs text-[#A1A1AA] max-w-md leading-relaxed">
              Source-grounded educational platform. Tutoring responses and assessment questions
              are retrieved directly from uploaded textbooks, slides, and lecture media with verified citations.
            </p>
          </div>

          {/* Navigation Links */}
          <div className="space-y-2.5 text-xs">
            <span className="font-semibold text-[#F5F5F5] block uppercase tracking-wider text-[11px]">
              Workspace
            </span>
            <ul className="space-y-1.5">
              <li>
                <Link href="/" className="hover:text-[#F5F5F5] transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link href="/courses" className="hover:text-[#F5F5F5] transition-colors">
                  Course Ingestion
                </Link>
              </li>
              <li>
                <Link href="/tutor" className="hover:text-[#F5F5F5] transition-colors">
                  Grounded AI Tutor
                </Link>
              </li>
              <li>
                <Link href="/assessments" className="hover:text-[#F5F5F5] transition-colors">
                  Adaptive Quizzes
                </Link>
              </li>
              <li>
                <Link href="/progress" className="hover:text-[#F5F5F5] transition-colors">
                  Mastery Analytics
                </Link>
              </li>
              <li>
                <Link href="/evaluation" className="hover:text-[#F5F5F5] transition-colors">
                  Evaluation Benchmark
                </Link>
              </li>
            </ul>
          </div>

          {/* Compliance & Legal Links */}
          <div className="space-y-2.5 text-xs">
            <span className="font-semibold text-[#F5F5F5] block uppercase tracking-wider text-[11px]">
              Compliance & Legal
            </span>
            <ul className="space-y-1.5">
              <li>
                <Link href="/privacy" className="hover:text-[#F5F5F5] transition-colors flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" /> Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-[#F5F5F5] transition-colors flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" /> Terms and Conditions
                </Link>
              </li>
            </ul>
            <p className="text-[11px] text-[#71717A] pt-2 leading-relaxed">
              Data handling notice: Content submitted for queries is processed strictly by configured AI provider endpoints (Google, Groq, or NVIDIA).
            </p>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-6 mt-6 border-t border-[#262626] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#71717A]">
          <span>&copy; 2026 LearnMate AI. All rights reserved.</span>
          <div className="flex items-center gap-4 text-xs">
            <Link href="/privacy" className="hover:text-[#F5F5F5] transition-colors">
              Privacy
            </Link>
            <span>&bull;</span>
            <Link href="/terms" className="hover:text-[#F5F5F5] transition-colors">
              Terms
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
