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
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Mastered
        </span>
      );
    }
    if (topic.mastery_score >= 0.45) {
      return (
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
          In Progress
        </span>
      );
    }
    return (
      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
        Needs Practice
      </span>
    );
  };

  const getBarColor = () => {
    if (topic.mastery_score >= 0.75) return "bg-emerald-500";
    if (topic.mastery_score >= 0.45) return "bg-amber-500";
    return "bg-rose-500";
  };

  return (
    <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-slate-200 truncate">{topic.topic_name}</span>
        <div className="flex items-center gap-2 shrink-0">
          {getStatusBadge()}
          <span className="text-xs font-mono font-semibold text-slate-300">{percentage}%</span>
        </div>
      </div>

      <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getBarColor()}`}
          style={{ width: `${Math.max(5, percentage)}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 font-mono">
        <span>Attempts: {topic.attempts_count}</span>
        <span>Accuracy: {topic.attempts_count > 0 ? Math.round((topic.correct_count / topic.attempts_count) * 100) : 0}%</span>
      </div>
    </div>
  );
}
