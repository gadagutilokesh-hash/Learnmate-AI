import React from "react";
import Link from "next/link";
import { ShieldCheck, AlertCircle, Database, Server, Lock, ArrowLeft } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "LearnMate AI Privacy Policy: Transparent disclosure of data handling, AI processing, storage, and retention."
};

export default function PrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Back button */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#71717A] hover:text-[#F5F5F5] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to Workspace
        </Link>
      </div>

      {/* Header */}
      <div className="border-b border-[#262626] pb-6 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-[#181818] text-[#3B82F6] border border-[#262626]">
            Privacy Policy
          </span>
          <span className="text-xs text-[#71717A]">Last updated: October 14, 2026</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#F5F5F5]">
          LearnMate AI Privacy Policy
        </h1>
        <p className="text-sm text-[#A1A1AA] leading-relaxed max-w-3xl">
          This policy discloses how LearnMate AI collects, stores, processes, and transmits data
          when you interact with course ingestion, grounded tutoring, adaptive quizzes, and mastery tracking.
        </p>
      </div>

      {/* Important Legal Flag Banner */}
      <div className="p-4 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 text-[#F59E0B] text-xs space-y-2">
        <div className="flex items-center gap-2 font-semibold text-[#F59E0B]">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Notice Regarding Corporate Entity and Jurisdiction Status</span>
        </div>
        <p className="leading-relaxed text-[#A1A1AA]">
          This document represents the technical and operational privacy practices of the LearnMate AI
          application codebase. Formal operating entity registration, corporate mailing address,
          designated Data Protection Officer (DPO), and specific governing jurisdiction are pending
          corporate finalization prior to public commercial launch.
        </p>
      </div>

      {/* Section 1: Data We Collect and Process */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <Database className="w-5 h-5 text-[#3B82F6]" /> 1. Information Collected and Processed
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            When using LearnMate AI, the following categories of information are processed by the system:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#71717A]">
            <li>
              <strong className="text-[#F5F5F5]">Uploaded Course Materials:</strong> PDF textbooks,
              PPTX presentation slides, MP4 lecture video recordings, and associated audio files that
              you submit for indexing.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Extracted Educational Content:</strong> Text segments,
              slide notes, tables, diagram descriptions, and video transcript timestamps extracted from
              your uploaded files.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">User Inquiries and Chat History:</strong> Questions
              submitted to the Grounded AI Tutor and associated conversation exchanges.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Assessment Responses and Mastery Data:</strong> Answers
              submitted to adaptive quizzes, grading records, Bayesian Knowledge Tracing topic mastery
              parameters, and generated study schedules.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">System Identifiers:</strong> Learner profile IDs (such
              as local session keys) used to maintain concept mastery states.
            </li>
          </ul>
        </div>
      </section>

      {/* Section 2: External AI Providers */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <Server className="w-5 h-5 text-[#3B82F6]" /> 2. Transmission to External AI Providers
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            LearnMate AI uses external AI providers to generate text, synthesize assessments, and compute
            semantic vector embeddings. Depending on your system configuration (the AI_PROVIDER environment setting),
            your course excerpts and queries are transmitted to one or more of the following services:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
            <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] space-y-1">
              <span className="font-semibold text-[#F5F5F5] text-xs block">Google Gemini</span>
              <p className="text-[11px] text-[#71717A]">
                Used for multimodal text generation, diagram analysis, and 768-dimensional semantic embeddings.
              </p>
            </div>
            <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] space-y-1">
              <span className="font-semibold text-[#F5F5F5] text-xs block">GroqCloud</span>
              <p className="text-[11px] text-[#71717A]">
                Used for accelerated LLM inference when AI_PROVIDER is set to groq.
              </p>
            </div>
            <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] space-y-1">
              <span className="font-semibold text-[#F5F5F5] text-xs block">NVIDIA NIM</span>
              <p className="text-[11px] text-[#71717A]">
                Used for Nemotron model inference when AI_PROVIDER is set to nvidia.
              </p>
            </div>
          </div>
          <p className="text-xs text-[#71717A] pt-1">
            We do not claim that data sent to third-party model providers is exempt from their respective
            terms of service. Please review Google, Groq, and NVIDIA privacy terms regarding enterprise API data processing.
          </p>
        </div>
      </section>

      {/* Section 3: Storage, Retention and Deletion */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <Lock className="w-5 h-5 text-[#3B82F6]" /> 3. Storage, Retention, and Security Controls
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            The technical implementation stores data as follows:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#71717A]">
            <li>
              <strong className="text-[#F5F5F5]">Local Filesystem Storage:</strong> Uploaded source files
              are saved in the server data/uploads directory.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Database Storage:</strong> Chunk text, document metadata,
              embeddings, and quiz responses are stored in SQLite (or Supabase PostgreSQL when configured).
            </li>
            <li>
              <strong className="text-[#F5F5F5]">API Key Isolation:</strong> Provider credentials (Gemini,
              Groq, NVIDIA) are stored solely on the server in environment variables. Client bundles and
              frontend responses never receive private keys.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Sanitized Error Logging:</strong> Backend logging scrub
              routines automatically redact authorization headers, bearer tokens, and API key patterns.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Deletion Notice:</strong> Automated time-based deletion
              is not currently implemented. Uploaded materials and student records persist in storage until
              manually removed or re-initialized by the administrator.
            </li>
          </ul>
        </div>
      </section>

      {/* Section 4: Cookies and Tracking */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-[#3B82F6]" /> 4. Cookies, Analytics, and Advertising
        </h2>
        <div className="space-y-2 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            LearnMate AI does not use marketing cookies, tracking pixels, third-party analytics scripts,
            or behavioral advertising networks. The application uses client-side state solely for essential
            navigation, active course selection, and quiz progression.
          </p>
        </div>
      </section>

      {/* Section 5: Inquiries and Contact */}
      <section className="space-y-4 pt-4 border-t border-[#262626]">
        <h2 className="text-base font-semibold text-[#F5F5F5]">5. Privacy Inquiries</h2>
        <p className="text-xs text-[#71717A] leading-relaxed">
          For questions regarding data handling practices or to report a privacy concern, please contact
          the system administrator or project team through your designated project repository or deployment channel.
        </p>
      </section>
    </div>
  );
}
