"use client";

import React from "react";
import { Citation } from "@/lib/types";
import { FileText, Presentation, Video, ExternalLink } from "lucide-react";

interface CitationCardProps {
  citation: Citation;
  index: number;
  onClick: (citation: Citation) => void;
}

export function CitationCard({ citation, index, onClick }: CitationCardProps) {
  const getIcon = () => {
    switch (citation.source_type?.toLowerCase()) {
      case "pdf":
        return <FileText className="w-4 h-4 text-rose-400" />;
      case "pptx":
      case "ppt":
        return <Presentation className="w-4 h-4 text-amber-400" />;
      case "mp4":
      case "audio":
        return <Video className="w-4 h-4 text-sky-400" />;
      default:
        return <FileText className="w-4 h-4 text-indigo-400" />;
    }
  };

  const getLoc = () => {
    if (citation.page_number) return `P. ${citation.page_number}`;
    if (citation.slide_number) return `Slide ${citation.slide_number}`;
    if (citation.start_timestamp) return `${citation.start_timestamp}`;
    return "Source";
  };

  return (
    <button
      onClick={() => onClick(citation)}
      className="group flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-indigo-500/50 text-left transition-all duration-150 w-full max-w-sm"
    >
      <div className="p-1.5 rounded-md bg-slate-800/80 group-hover:bg-slate-700/80 border border-slate-700/50 shrink-0">
        {getIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1">
          <span className="text-xs font-semibold text-slate-200 truncate">
            [{index + 1}] {citation.source_file}
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 shrink-0 border border-indigo-500/30">
            {getLoc()}
          </span>
        </div>
        <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5 leading-snug">
          {citation.excerpt}
        </p>
      </div>
      <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 shrink-0 self-center transition-colors" />
    </button>
  );
}
