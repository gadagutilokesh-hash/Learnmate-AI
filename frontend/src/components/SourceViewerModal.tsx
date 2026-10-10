"use client";

import React from "react";
import { Citation } from "@/lib/types";
import { X, FileText, Presentation, Video, ExternalLink, Bookmark } from "lucide-react";

interface SourceViewerModalProps {
  citation: Citation | null;
  onClose: () => void;
}

export function SourceViewerModal({ citation, onClose }: SourceViewerModalProps) {
  if (!citation) return null;

  const getSourceIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "pdf":
        return <FileText className="w-5 h-5 text-rose-400" />;
      case "pptx":
      case "ppt":
        return <Presentation className="w-5 h-5 text-amber-400" />;
      case "mp4":
      case "audio":
        return <Video className="w-5 h-5 text-sky-400" />;
      default:
        return <FileText className="w-5 h-5 text-indigo-400" />;
    }
  };

  const getLocationBadge = () => {
    if (citation.page_number) return `Page ${citation.page_number}`;
    if (citation.slide_number) return `Slide ${citation.slide_number}`;
    if (citation.start_timestamp) return `Timecode ${citation.start_timestamp} - ${citation.end_timestamp || ""}`;
    return "Document Section";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800 border border-slate-700">
              {getSourceIcon(citation.source_type)}
            </div>
            <div>
              <h3 className="font-semibold text-slate-100 text-sm md:text-base truncate max-w-md">
                {citation.source_file}
              </h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 font-medium border border-indigo-500/20">
                  {getLocationBadge()}
                </span>
                {citation.topic && (
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Bookmark className="w-3 h-3 text-slate-500" />
                    {citation.topic}
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Verified Source Passage
            </span>
            <div className="mt-2 p-4 rounded-lg bg-slate-950/80 border border-slate-800 text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-sans">
              {citation.excerpt}
            </div>
          </div>

          {citation.relevance_score !== undefined && citation.relevance_score !== null && (
            <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <span>Retrieval Relevance Confidence:</span>
              <span className="font-mono font-medium text-emerald-400">
                {(citation.relevance_score * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-6 py-3 border-t border-slate-800 bg-slate-950/40">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
          >
            Close Excerpt
          </button>
        </div>
      </div>
    </div>
  );
}
