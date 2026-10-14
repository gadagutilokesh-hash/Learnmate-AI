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

  const getLoc = () => {
    if (citation.page_number) return `Page ${citation.page_number}`;
    if (citation.slide_number) return `Slide ${citation.slide_number}`;
    if (citation.start_timestamp) return `${citation.start_timestamp}`;
    return "Source";
  };

  return (
    <button
      type="button"
      onClick={() => onClick(citation)}
      aria-label={`View excerpt for citation ${index + 1} from ${citation.source_file}, ${getLoc()}`}
      className="group flex items-start gap-2.5 p-3 rounded-md bg-[#121212] hover:bg-[#181818] border border-[#262626] hover:border-[#363636] text-left transition-colors w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6]"
    >
      <div className="p-1.5 rounded-md bg-[#181818] border border-[#262626] shrink-0 mt-0.5">
        {getIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1.5">
          <span className="text-xs font-medium text-[#F5F5F5] truncate">
            [{index + 1}] {citation.source_file}
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#181818] text-[#A1A1AA] shrink-0 border border-[#262626] font-medium">
            {getLoc()}
          </span>
        </div>
        <p className="text-[11px] text-[#A1A1AA] line-clamp-2 mt-1 leading-relaxed">
          {citation.excerpt}
        </p>
      </div>
      <ExternalLink className="w-3.5 h-3.5 text-[#71717A] group-hover:text-[#F5F5F5] shrink-0 self-center transition-colors" aria-hidden="true" />
    </button>
  );
}
