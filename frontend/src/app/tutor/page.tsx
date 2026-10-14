"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Course, TutorResponse, Citation } from "@/lib/types";
import { CitationCard } from "@/components/CitationCard";
import { SourceViewerModal } from "@/components/SourceViewerModal";
import {
  MessageSquareQuote,
  Send,
  ShieldCheck,
  AlertTriangle,
  Bot,
  User,
  Info,
  Clock,
  RotateCcw
} from "lucide-react";

interface ChatMessage {
  id: string;
  sender: "user" | "tutor";
  text: string;
  isGrounded?: boolean;
  citations?: Citation[];
  unsupportedReason?: string;
  externalNotes?: string;
  followups?: string[];
  isError?: boolean;
  errorType?: string;
  retryAfter?: string;
  queryToRetry?: string;
  timestamp: string;
}

const INITIAL_WELCOME_MESSAGE: ChatMessage = {
  id: "msg_welcome",
  sender: "tutor",
  text: "Hello! I am LearnMate AI, your source-grounded academic tutor. Ask me any question regarding your uploaded textbooks, slide decks, or lecture recordings. Every factual claim will be strictly cited with verified page numbers, slide numbers, or video timestamps.",
  isGrounded: true,
  citations: [],
  timestamp: "Just now",
  followups: [
    "Why is feature normalization important before gradient descent?",
    "Compare batch vs stochastic gradient descent.",
    "What happens if a neural network lacks non-linear activation functions?"
  ]
};

let messageSequence = 0;
function createMessageId(prefix: string): string {
  messageSequence += 1;
  return `${prefix}_${messageSequence}`;
}

function getFormattedTime(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function TutorPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_WELCOME_MESSAGE]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listCourses().then((cList) => {
      setCourses(cList);
      if (cList.length > 0) {
        const courseWithDocs = cList.find((c) => c.documents_count > 0);
        setSelectedCourseId(courseWithDocs ? courseWithDocs.id : cList[0].id);
      }
    });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(queryText?: string) {
    const q = queryText || query;
    if (!q.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: createMessageId("user"),
      sender: "user",
      text: q.trim(),
      timestamp: getFormattedTime()
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setQuery("");

    if (!selectedCourseId) {
      const offlineMsg: ChatMessage = {
        id: createMessageId("err"),
        sender: "tutor",
        text: "The LearnMate AI backend service is currently offline or unreachable. Please connect your FastAPI backend via NEXT_PUBLIC_API_URL to ask questions and receive verified citations.",
        isGrounded: false,
        isError: true,
        errorType: "backend_offline",
        timestamp: getFormattedTime()
      };
      setMessages((prev) => [...prev, offlineMsg]);
      return;
    }

    setLoading(true);

    try {
      const res: TutorResponse = await api.askTutor(selectedCourseId, q.trim());
      const tutorMsg: ChatMessage = {
        id: createMessageId("tutor"),
        sender: "tutor",
        text: res.answer,
        isGrounded: res.is_grounded,
        citations: res.citations,
        unsupportedReason: res.unsupported_reason,
        externalNotes: res.external_context_notes,
        followups: res.suggested_followups,
        isError: res.is_error,
        errorType: res.error_type,
        retryAfter: res.retry_after,
        queryToRetry: q.trim(),
        timestamp: getFormattedTime()
      };
      setMessages((prev) => [...prev, tutorMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      const isQuota = msg.toLowerCase().includes("limit") || msg.toLowerCase().includes("quota") || msg.toLowerCase().includes("429");
      const isUnavailable = msg.toLowerCase().includes("503") || msg.toLowerCase().includes("demand") || msg.toLowerCase().includes("unavailable");
      const isOffline = msg.toLowerCase().includes("offline") || msg.toLowerCase().includes("unreachable");
      const friendlyMsg = isQuota
        ? "Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later."
        : isUnavailable
        ? "Live AI generation is temporarily unavailable due to high model demand. Please try again in a few moments."
        : isOffline
        ? "LearnMate AI backend service is currently offline or unreachable. Please check backend deployment or NEXT_PUBLIC_API_URL."
        : `AI Tutor service error: ${msg}`;
      const errorMsg: ChatMessage = {
        id: createMessageId("err"),
        sender: "tutor",
        text: friendlyMsg,
        isGrounded: false,
        isError: true,
        errorType: isQuota ? "quota_exceeded" : isUnavailable ? "service_unavailable" : isOffline ? "backend_offline" : "service_error",
        queryToRetry: q.trim(),
        timestamp: getFormattedTime()
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-4xl mx-auto space-y-3">
      {/* Top Banner / Course Context */}
      <div className="flex items-center justify-between px-4 py-2.5 rounded-md bg-[#121212] border border-[#262626] shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquareQuote className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" />
          <h1 className="text-xs md:text-sm font-semibold text-[#F5F5F5]">Grounded AI Tutor</h1>
          {courses.length > 0 ? (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-[#22C55E] px-2 py-0.5 rounded bg-[#22C55E]/10 border border-[#22C55E]/20">
              <ShieldCheck className="w-3 h-3" aria-hidden="true" /> Strict Grounding Active
            </span>
          ) : (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-[#F59E0B] px-2 py-0.5 rounded bg-[#F59E0B]/10 border border-[#F59E0B]/20">
              <AlertTriangle className="w-3 h-3" aria-hidden="true" /> Backend Offline
            </span>
          )}
        </div>

        {courses.length > 0 ? (
          <div className="flex items-center gap-2 text-xs">
            <label htmlFor="tutor-course-select" className="text-[#71717A] hidden md:inline">
              Course:
            </label>
            <select
              id="tutor-course-select"
              value={selectedCourseId}
              onChange={(e) => setSelectedCourseId(e.target.value)}
              className="px-2.5 py-1 rounded-md bg-[#080808] border border-[#262626] text-[#F5F5F5] text-xs focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] cursor-pointer font-medium"
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
          </div>
        ) : (
          <span className="text-xs text-[#71717A] font-mono">Backend Offline</span>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div
        role="log"
        aria-live="polite"
        className="flex-1 overflow-y-auto space-y-4 px-1 pr-2"
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-3 ${m.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {m.sender === "tutor" && (
              <div className="w-7 h-7 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] shrink-0 mt-1">
                <Bot className="w-4 h-4" aria-hidden="true" />
              </div>
            )}

            <div
              className={`max-w-2xl space-y-2.5 ${
                m.sender === "user"
                  ? "bg-[#181818] text-[#F5F5F5] border border-[#363636] p-3.5 rounded-md"
                  : "bg-[#121212] border border-[#262626] text-[#F5F5F5] p-4 rounded-md"
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center justify-between gap-4 text-[11px] text-[#71717A]">
                <span className="font-semibold text-[#A1A1AA]">
                  {m.sender === "user" ? "You" : "LearnMate AI Tutor"}
                </span>
                <span>{m.timestamp}</span>
              </div>

              {/* Service Error / Quota State Banner */}
              {m.sender === "tutor" && m.isError && (
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 text-[#F59E0B] text-xs">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-[#F59E0B] mt-0.5" aria-hidden="true" />
                    <div>
                      <strong className="font-semibold block text-[#F59E0B]">
                        {m.errorType === "quota_exceeded"
                          ? "AI Service Limit Reached"
                          : m.errorType === "service_unavailable"
                          ? "AI Service Temporarily Unavailable (High Demand)"
                          : "Service Notice"}
                      </strong>
                      <span className="text-xs text-[#A1A1AA]">{m.text}</span>
                      {m.retryAfter && (
                        <span className="block mt-1 text-[11px] text-[#F59E0B]">
                          Estimated availability: {m.retryAfter}
                        </span>
                      )}
                    </div>
                  </div>
                  {m.queryToRetry && (
                    <button
                      type="button"
                      onClick={() => handleSubmit(m.queryToRetry)}
                      disabled={loading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#F59E0B]/20 hover:bg-[#F59E0B]/30 text-[#F59E0B] border border-[#F59E0B]/30 text-xs font-medium transition-colors shrink-0 disabled:opacity-50"
                    >
                      <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" /> Retry Question
                    </button>
                  )}
                </div>
              )}

              {/* Unsupported Rejection Banner (Only when NOT an error) */}
              {m.sender === "tutor" && !m.isError && m.isGrounded === false && (
                <div className="flex items-start gap-2.5 p-3 rounded-md bg-[#EF4444]/10 border border-[#EF4444]/20 text-[#EF4444] text-xs">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-[#EF4444] mt-0.5" aria-hidden="true" />
                  <div>
                    <strong className="font-semibold block">Unsupported Question Rejection</strong>
                    <span className="text-[#A1A1AA]">
                      {m.unsupportedReason ||
                        "This question cannot be verified from the uploaded materials. LearnMate AI rejects ungrounded queries to prevent academic hallucinations."}
                    </span>
                  </div>
                </div>
              )}

              {/* Body Text */}
              {!m.isError && (
                <div className="text-xs md:text-sm leading-relaxed whitespace-pre-wrap font-sans text-[#F5F5F5]">
                  {m.text}
                </div>
              )}

              {/* Supplemental Context Note */}
              {m.externalNotes && (
                <div className="p-2.5 rounded-md bg-[#080808] border border-[#262626] text-xs text-[#A1A1AA] space-y-1">
                  <span className="font-semibold text-[#F5F5F5] flex items-center gap-1">
                    <Info className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" /> Supplemental Study Context
                  </span>
                  <p className="text-[#A1A1AA]">{m.externalNotes}</p>
                </div>
              )}

              {/* Citations Grid */}
              {m.citations && m.citations.length > 0 && (
                <div className="pt-2 border-t border-[#262626] space-y-2">
                  <div className="flex items-center justify-between text-xs text-[#71717A]">
                    <span className="font-medium text-[#F5F5F5]">
                      Exact Source Citations ({m.citations.length})
                    </span>
                    <span className="text-[11px] text-[#71717A]">Click to inspect source passage</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {m.citations.map((c, idx) => (
                      <CitationCard
                        key={idx}
                        citation={c}
                        index={idx}
                        onClick={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up Prompts */}
              {m.followups && m.followups.length > 0 && (
                <div className="pt-2 border-t border-[#262626] space-y-1.5">
                  <span className="text-[11px] font-semibold text-[#71717A] uppercase tracking-wider block">
                    Suggested Follow-ups
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {m.followups.map((f, fIdx) => (
                      <button
                        key={fIdx}
                        type="button"
                        onClick={() => handleSubmit(f)}
                        className="text-xs px-2.5 py-1 rounded bg-[#181818] hover:bg-[#262626] text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors border border-[#262626] text-left"
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {m.sender === "user" && (
              <div className="w-7 h-7 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#A1A1AA] shrink-0 mt-1">
                <User className="w-4 h-4" aria-hidden="true" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] shrink-0">
              <Bot className="w-4 h-4" aria-hidden="true" />
            </div>
            <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] text-xs text-[#A1A1AA] flex items-center gap-2">
              <Clock className="w-4 h-4 animate-spin text-[#3B82F6]" aria-hidden="true" />
              <span>Retrieving source-grounded excerpts and verifying citations...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Backend Offline Indicator */}
      {courses.length === 0 && (
        <div className="flex items-center gap-2 p-2.5 px-3 rounded-md bg-[#121212] border border-[#262626] text-xs text-[#A1A1AA] shrink-0">
          <div className="w-2 h-2 rounded-full bg-[#F59E0B] shrink-0" aria-hidden="true" />
          <span>Backend service offline. AI tutoring responses will activate once the backend is connected via <code className="text-[#3B82F6] font-mono text-[11px]">NEXT_PUBLIC_API_URL</code>.</span>
        </div>
      )}

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        className="relative shrink-0"
      >
        <label htmlFor="tutor-query-input" className="sr-only">
          Ask a question about your course materials
        </label>
        <textarea
          id="tutor-query-input"
          rows={2}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Ask a question grounded in your course materials... (Enter to send, Shift+Enter for newline)"
          className="w-full px-3.5 py-2.5 pr-12 rounded-md bg-[#121212] border border-[#262626] text-xs md:text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] resize-none"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          aria-label="Send question to tutor"
          className="absolute right-2.5 bottom-2.5 p-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white disabled:opacity-40 disabled:pointer-events-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
        >
          <Send className="w-4 h-4" aria-hidden="true" />
        </button>
      </form>

      {/* Clickable Citation Source Viewer Modal */}
      <SourceViewerModal
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
