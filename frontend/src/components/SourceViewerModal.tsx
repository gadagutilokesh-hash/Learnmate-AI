"use client";

import React, { useEffect } from "react";
import { Citation } from "@/lib/types";
import { X, FileText, Presentation, Video, Bookmark } from "lucide-react";

interface SourceViewerModalProps {
  citation: Citation | null;
  onClose: () => void;
}

export function SourceViewerModal({ citation, onClose }: SourceViewerModalProps) {
  useEffect(() => {
    if (!citation) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [citation, onClose]);

  if (!citation) return null;

  const getSourceIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "pdf":
        return <FileText className="w-4 h-4 text-[#EF4444]" aria-hidden="true" />;
      case "pptx":
      case "ppt":
        return <Presentation className="w-4 h-4 text-[#F59E0B]" aria-hidden="true" />;
      case "mp4":
      case "audio":
        return <Video className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" />;
      default:
        return <FileText className="w-4 h-4 text-[#3B82F6]" aria-hidden="true" />;
    }
  };

  const getLocationBadge = () => {
    if (citation.page_number) return `Page ${citation.page_number}`;
    if (citation.slide_number) return `Slide ${citation.slide_number}`;
    if (citation.start_timestamp) return `Timecode ${citation.start_timestamp} - ${citation.end_timestamp || ""}`;
    return "Document Section";
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4"
    >
      <div className="relative w-full max-w-2xl bg-[#121212] border border-[#363636] rounded-md shadow-2xl overflow-hidden animate-in fade-in duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#262626] bg-[#0B0B0B]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-md bg-[#181818] border border-[#262626]">
              {getSourceIcon(citation.source_type)}
            </div>
            <div>
              <h3 id="source-modal-title" className="font-medium text-[#F5F5F5] text-sm md:text-base truncate max-w-md">
                {citation.source_file}
              </h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs px-2 py-0.5 rounded bg-[#181818] text-[#A1A1AA] font-medium border border-[#262626]">
                  {getLocationBadge()}
                </span>
                {citation.topic && (
                  <span className="text-xs text-[#71717A] flex items-center gap-1">
                    <Bookmark className="w-3 h-3 text-[#71717A]" aria-hidden="true" />
                    {citation.topic}
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close excerpt viewer"
            className="p-1.5 rounded-md text-[#71717A] hover:text-[#F5F5F5] hover:bg-[#181818] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[#A1A1AA]">
              Verified Source Passage
            </span>
            <div className="mt-2 p-3.5 rounded-md bg-[#080808] border border-[#262626] text-[#F5F5F5] text-xs md:text-sm leading-relaxed whitespace-pre-wrap font-sans">
              {citation.excerpt}
            </div>
          </div>

          {citation.relevance_score !== undefined && citation.relevance_score !== null && (
            <div className="flex items-center justify-between text-xs text-[#71717A] pt-2 border-t border-[#262626]">
              <span>Retrieval Relevance Score:</span>
              <span className="font-mono font-medium text-[#22C55E]">
                {(citation.relevance_score * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-5 py-3 border-t border-[#262626] bg-[#0B0B0B]">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-[#F5F5F5] bg-[#181818] hover:bg-[#262626] border border-[#262626] rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
          >
            Close Excerpt
          </button>
        </div>
      </div>
    </div>
  );
}
