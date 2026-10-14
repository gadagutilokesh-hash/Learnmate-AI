import React from "react";
import Link from "next/link";
import { BookOpen, AlertCircle, FileCheck, ShieldAlert, ArrowLeft } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description: "LearnMate AI Terms and Conditions: User agreements, acceptable use, academic integrity, and liability limitations."
};

export default function TermsPage() {
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
            Terms of Service
          </span>
          <span className="text-xs text-[#71717A]">Last updated: October 14, 2026</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#F5F5F5]">
          LearnMate AI Terms and Conditions
        </h1>
        <p className="text-sm text-[#A1A1AA] leading-relaxed max-w-3xl">
          These terms govern your access to and use of LearnMate AI, including course ingestion,
          grounded tutoring, adaptive assessments, and learner mastery analytics.
        </p>
      </div>

      {/* Legal Status Notice */}
      <div className="p-4 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 text-[#F59E0B] text-xs space-y-2">
        <div className="flex items-center gap-2 font-semibold text-[#F59E0B]">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Notice Regarding Commercial Terms and Legal Jurisdiction</span>
        </div>
        <p className="leading-relaxed text-[#A1A1AA]">
          These terms describe product rules and technical limitations for the LearnMate AI educational
          system. Formal dispute resolution clauses, governing law selection, and formal corporate
          entity information require final legal review prior to commercial software launch.
        </p>
      </div>

      {/* Section 1: Educational Scope and Disclaimers */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-[#3B82F6]" /> 1. Educational Scope and Warranty Disclaimer
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            LearnMate AI is designed as a study companion and adaptive assessment tool. The platform is
            provided on an &quot;as-is&quot; and &quot;as-available&quot; basis without warranties of any kind, whether
            express or implied.
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#71717A]">
            <li>
              <strong className="text-[#F5F5F5]">No Grade or Outcome Guarantees:</strong> LearnMate AI
              does not guarantee improved examination performance, course passing grades, or academic credit.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Grounded Citation Verification:</strong> While LearnMate AI
              applies strict retrieval thresholds and validates citation indices against indexed course chunks,
              students must verify critical formulas, definitions, and facts against original reference materials.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Model Limitations:</strong> Generative AI models may
              experience temporary service degradation, quota exhaustion, or parsing inconsistencies.
            </li>
          </ul>
        </div>
      </section>

      {/* Section 2: User Responsibilities and Acceptable Use */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-[#3B82F6]" /> 2. User Responsibilities and Content Rights
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            When uploading course files or submitting queries, you agree to comply with the following standards:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-[#71717A]">
            <li>
              <strong className="text-[#F5F5F5]">Copyright Compliance:</strong> You warrant that you have
              the necessary rights, permissions, or academic fair-use justification to upload course
              materials (PDFs, slide decks, lecture recordings) for personal study indexing.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">Prohibited Content:</strong> You may not upload malicious
              scripts, confidential personal data, or content that infringes upon third-party intellectual property.
            </li>
            <li>
              <strong className="text-[#F5F5F5]">System Integrity:</strong> You agree not to attempt to
              extract system API credentials, probe server vulnerabilities, or disrupt AI provider endpoints.
            </li>
          </ul>
        </div>
      </section>

      {/* Section 3: Assessment and Mastery Data */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5] flex items-center gap-2">
          <FileCheck className="w-5 h-5 text-[#3B82F6]" /> 3. Adaptive Assessment and Analytics
        </h2>
        <div className="space-y-3 text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          <p>
            LearnMate AI implements deterministic Bayesian Knowledge Tracing (BKT) to update topic mastery
            estimates upon quiz submission. These scores represent statistical estimates of concept familiarity
            and do not constitute an official academic credential or institutional evaluation.
          </p>
        </div>
      </section>

      {/* Section 4: Service Availability and Modifications */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-[#F5F5F5]">4. Service Availability</h2>
        <p className="text-xs md:text-sm text-[#A1A1AA] leading-relaxed">
          AI generation features depend on upstream provider availability (Google Gemini, Groq, NVIDIA).
          Operations may be temporarily throttled during provider quota exhaustion or upstream service outages.
          We reserve the right to modify or update application features as required for maintenance and security.
        </p>
      </section>

      {/* Section 5: Inquiries */}
      <section className="space-y-4 pt-4 border-t border-[#262626]">
        <h2 className="text-base font-semibold text-[#F5F5F5]">5. Questions Concerning Terms</h2>
        <p className="text-xs text-[#71717A] leading-relaxed">
          If you have questions regarding these terms, please contact the administrator via your designated
          repository or support contact channel.
        </p>
      </section>
    </div>
  );
}
