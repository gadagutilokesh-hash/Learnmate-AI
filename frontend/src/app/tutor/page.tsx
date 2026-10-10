"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Course, TutorResponse, Citation } from "@/lib/types";
import { CitationCard } from "@/components/CitationCard";
import { SourceViewerModal } from "@/components/SourceViewerModal";
import {
  MessageSquareQuote,
  Send,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  Bot,
  User,
  Info,
  Clock,
  BookOpen
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
  timestamp: string;
}

export default function TutorPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listCourses().then((cList) => {
      setCourses(cList);
      if (cList.length > 0) {
        setSelectedCourseId(cList[0].id);
      }
    });
  }, []);

  useEffect(() => {
    // Initial welcome message
    setMessages([
      {
        id: "msg_welcome",
        sender: "tutor",
        text: "Hello! I am LearnMate AI, your source-grounded academic tutor. Ask me any question about your uploaded textbooks, slide decks, or lecture recordings. Every claim I make will be strictly cited with verified page numbers, slide numbers, or video timestamps.",
        isGrounded: true,
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        followups: [
          "Why is feature normalization important before gradient descent?",
          "Compare batch vs stochastic gradient descent.",
          "What happens if a neural network lacks non-linear activation functions?"
        ]
      }
    ]);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(queryText?: string) {
    const q = queryText || query;
    if (!q.trim() || !selectedCourseId || loading) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: "user",
      text: q.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setQuery("");
    setLoading(true);

    try {
      const res: TutorResponse = await api.askTutor(selectedCourseId, q.trim());
      const tutorMsg: ChatMessage = {
        id: `tutor_${Date.now()}`,
        sender: "tutor",
        text: res.answer,
        isGrounded: res.is_grounded,
        citations: res.citations,
        unsupportedReason: res.unsupported_reason,
        externalNotes: res.external_context_notes,
        followups: res.suggested_followups,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      };
      setMessages((prev) => [...prev, tutorMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: "tutor",
        text: `Error connecting to AI Tutor: ${err.message}`,
        isGrounded: false,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-5xl mx-auto space-y-4">
      {/* Top Banner / Course Context */}
      <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900 border border-slate-800">
        <div className="flex items-center gap-2">
          <MessageSquareQuote className="w-5 h-5 text-indigo-400" />
          <h1 className="text-base font-bold text-white">Grounded AI Tutor</h1>
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <ShieldCheck className="w-3 h-3" /> Strict Grounding Enabled
          </span>
        </div>

        {courses.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 hidden md:inline">Grounding Course:</span>
            <select
              value={selectedCourseId}
              onChange={(e) => setSelectedCourseId(e.target.value)}
              className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none"
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-6 px-1 pr-2">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-3 ${m.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {m.sender === "tutor" && (
              <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-1">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-3xl space-y-3 ${
                m.sender === "user"
                  ? "bg-indigo-600 text-white p-4 rounded-2xl rounded-tr-none shadow-md"
                  : "bg-slate-900 border border-slate-800 text-slate-200 p-5 rounded-2xl rounded-tl-none shadow-lg"
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center justify-between gap-4 text-[11px] opacity-75">
                <span className="font-semibold">
                  {m.sender === "user" ? "You" : "LearnMate AI Tutor"}
                </span>
                <span>{m.timestamp}</span>
              </div>

              {/* Unsupported Rejection Banner */}
              {m.sender === "tutor" && m.isGrounded === false && (
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                  <div>
                    <strong className="font-semibold block">Unsupported Question Rejection</strong>
                    <span>
                      {m.unsupportedReason ||
                        "This question cannot be verified from the uploaded materials. LearnMate AI rejects ungrounded queries to prevent academic hallucinations."}
                    </span>
                  </div>
                </div>
              )}

              {/* Body Text */}
              <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                {m.text}
              </div>

              {/* Supplemental Context Note */}
              {m.externalNotes && (
                <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-400 space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center gap-1">
                    <Info className="w-3.5 h-3.5 text-sky-400" /> Supplemental Study Context
                  </span>
                  <p>{m.externalNotes}</p>
                </div>
              )}

              {/* Citations Grid */}
              {m.citations && m.citations.length > 0 && (
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-semibold text-indigo-300">
                      Exact Source Citations ({m.citations.length})
                    </span>
                    <span className="text-[11px] text-slate-500">Click to view source excerpt</span>
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
                <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Suggested Follow-ups
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {m.followups.map((f, fIdx) => (
                      <button
                        key={fIdx}
                        onClick={() => handleSubmit(f)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/60 text-left"
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {m.sender === "user" && (
              <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <Clock className="w-4 h-4 animate-spin text-indigo-400" />
              <span>Retrieving source-grounded excerpts and verifying citations...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        className="relative"
      >
        <textarea
          rows={2}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Ask a question grounded in your course materials... (Enter to send, Shift+Enter for new line)"
          className="w-full px-4 py-3 pr-14 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none shadow-lg"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="absolute right-3 bottom-3 p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:pointer-events-none transition-colors shadow-md shadow-indigo-600/30"
          title="Send query"
        >
          <Send className="w-4 h-4" />
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
