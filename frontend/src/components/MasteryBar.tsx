"use client";

import React from "react";
import { TopicMastery } from "@/lib/types";

interface MasteryBarProps {
  topic: TopicMastery;
}

export function MasteryBar({ topic }: MasteryBarProps) {
  const percentage = Math.round(topic.mastery_score * 100);

  const getStatusBadge = () => {
    if (topic.mastery_score >= 0.75) {
      return (
        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20">
          Mastered
        </span>
      );
    }
    if (topic.mastery_score >= 0.45) {
      return (
        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/20">
          In Progress
        </span>
      );
    }
    return (
      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20">
        Needs Practice
      </span>
    );
  };

  const getBarColor = () => {
    if (topic.mastery_score >= 0.75) return "bg-[#22C55E]";
    if (topic.mastery_score >= 0.45) return "bg-[#F59E0B]";
    return "bg-[#EF4444]";
  };

  return (
    <div className="p-3.5 rounded-md bg-[#121212] border border-[#262626] hover:border-[#363636] transition-colors">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs md:text-sm font-medium text-[#F5F5F5] truncate">{topic.topic_name}</span>
        <div className="flex items-center gap-2 shrink-0">
          {getStatusBadge()}
          <span className="text-xs font-mono font-medium text-[#F5F5F5]">{percentage}%</span>
        </div>
      </div>

      <div
        role="progressbar"
        aria-label={`${topic.topic_name} mastery`}
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        className="w-full h-1.5 rounded bg-[#181818] overflow-hidden"
      >
        <div
          className={`h-full rounded transition-all duration-300 ${getBarColor()}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
