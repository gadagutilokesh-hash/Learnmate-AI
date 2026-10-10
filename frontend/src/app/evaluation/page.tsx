"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { EvaluationRun } from "@/lib/types";
import {
  BarChart3,
  Play,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles,
  Users,
  Target,
  FileCheck,
  RotateCw
} from "lucide-react";

export default function EvaluationPage() {
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [activeRun, setActiveRun] = useState<EvaluationRun | null>(null);
  const [running, setRunning] = useState(false);
  const [datasetType, setDatasetType] = useState("comprehensive");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRuns();
  }, []);

  async function loadRuns() {
    try {
      const pastRuns = await api.listEvaluationRuns();
      setRuns(pastRuns);
      if (pastRuns.length > 0) {
        setActiveRun(pastRuns[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunEvaluation() {
    setRunning(true);
    try {
      const newRun = await api.runEvaluation(undefined, datasetType);
      setActiveRun(newRun);
      await loadRuns();
    } catch (err: any) {
      alert(`Evaluation failed: ${err.message}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-indigo-400" /> RAG Evaluation & Learner Simulation Pipeline
          </h1>
          <p className="text-sm text-slate-400">
            Automated RAGAS retrieval & answer quality evaluation across 4 question categories, plus multi-session learner agent simulations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={datasetType}
            onChange={(e) => setDatasetType(e.target.value)}
            disabled={running}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
          >
            <option value="comprehensive">Comprehensive (All Categories)</option>
            <option value="grounded">Grounded Factual Only</option>
            <option value="multi_source">Multi-Source Synthesis</option>
            <option value="diagram">Multimodal Diagram & Vision</option>
            <option value="unsupported">Unsupported Negative Rejection</option>
          </select>

          <button
            onClick={handleRunEvaluation}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-all shadow-lg shadow-indigo-600/30 disabled:opacity-50 shrink-0"
          >
            {running ? (
              <>
                <Clock className="w-3.5 h-3.5 animate-spin" /> Running Benchmark & Simulation...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" /> Run Live Benchmark
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Benchmark Run Display */}
      {activeRun ? (
        <div className="space-y-8">
          {/* Run Header Info */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-semibold">
                  {activeRun.dataset_type}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {new Date(activeRun.timestamp).toLocaleString()}
                </span>
              </div>
              <h2 className="text-lg font-bold text-white mt-1">{activeRun.run_name}</h2>
              <span className="text-xs text-slate-400">
                Verified against {activeRun.total_eval_samples} standardized multimodal benchmark test cases.
              </span>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-400">Select Past Run:</span>
              <select
                value={activeRun.id}
                onChange={(e) => {
                  const found = runs.find((r) => r.id === e.target.value);
                  if (found) setActiveRun(found);
                }}
                className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
              >
                {runs.map((r, idx) => (
                  <option key={r.id} value={r.id}>
                    Run #{runs.length - idx} ({new Date(r.timestamp).toLocaleTimeString()})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* RAGAS Metrics Grid (ACTUAL MEASURED NUMBERS) */}
          <div>
            <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-400" /> Measured RAG Metrics
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Faithfulness</span>
                <div className="text-2xl font-bold font-mono text-emerald-400">
                  {(activeRun.metrics.faithfulness * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Claims supported by citations</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Answer Relevancy</span>
                <div className="text-2xl font-bold font-mono text-indigo-400">
                  {(activeRun.metrics.answer_relevancy * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Query-response semantic alignment</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Context Precision</span>
                <div className="text-2xl font-bold font-mono text-sky-400">
                  {(activeRun.metrics.context_precision * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Signal-to-noise ratio in top chunks</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Context Recall</span>
                <div className="text-2xl font-bold font-mono text-amber-400">
                  {(activeRun.metrics.context_recall * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Ground-truth concept recovery</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Unsupported Rejection</span>
                <div className="text-2xl font-bold font-mono text-emerald-400">
                  {(activeRun.metrics.unsupported_rejection_rate * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Zero hallucinations on off-topic</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Grounded Accuracy</span>
                <div className="text-2xl font-bold font-mono text-emerald-400">
                  {(activeRun.metrics.grounded_accuracy * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Factual answers with citations</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Citation Precision</span>
                <div className="text-2xl font-bold font-mono text-purple-400">
                  {(activeRun.metrics.citation_precision * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Page & slide metadata validity</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                <span className="text-slate-400 text-xs font-medium">Question Repetition</span>
                <div className="text-2xl font-bold font-mono text-slate-300">
                  {(activeRun.metrics.question_repetition_rate * 100).toFixed(1)}%
                </div>
                <p className="text-[11px] text-slate-500">Cross-quiz question overlap rate</p>
              </div>
            </div>
          </div>

          {/* Simulated Learner Trajectories (Beginner, Intermediate, Advanced) */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-400" />
              Simulated Learner Trajectories (3 Learning Sessions)
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(activeRun.simulation_results || {}).map(([persona, data]: any) => (
                <div
                  key={persona}
                  className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase font-bold tracking-wider text-indigo-400">
                      {persona} Student
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                        data.status === "mastered"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {data.status.replace("_", " ")}
                    </span>
                  </div>

                  <div className="flex items-baseline justify-between text-xs font-mono">
                    <span className="text-slate-400">Baseline Prior:</span>
                    <span className="text-slate-200">{(data.initial_mastery * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-baseline justify-between text-xs font-mono">
                    <span className="text-slate-400">Final Mastery:</span>
                    <span className="text-emerald-400 font-bold">{(data.final_mastery * 100).toFixed(0)}%</span>
                  </div>

                  {/* Visual Step-by-Step Trajectory */}
                  <div className="pt-2 border-t border-slate-800 space-y-1.5">
                    <span className="text-[11px] text-slate-500 font-medium block">
                      Session Progression:
                    </span>
                    <div className="flex items-center gap-1.5">
                      {data.mastery_trajectory.map((val: number, idx: number) => (
                        <div key={idx} className="flex-1 space-y-1 text-center">
                          <div
                            className="h-10 rounded bg-indigo-950 border border-indigo-500/30 flex items-end justify-center p-0.5"
                          >
                            <div
                              className="w-full bg-indigo-500 rounded-sm transition-all"
                              style={{ height: `${Math.max(10, Math.round(val * 100))}%` }}
                            />
                          </div>
                          <span className="text-[10px] font-mono text-slate-400">
                            {Math.round(val * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Benchmark Test Cases Detail Table */}
          <div className="space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-sky-400" />
              Standardized Test Case Executions ({activeRun.sample_evaluations?.length || 0})
            </h3>

            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                  <tr>
                    <th className="p-3.5">Category</th>
                    <th className="p-3.5">Evaluated Query</th>
                    <th className="p-3.5">Grounding</th>
                    <th className="p-3.5">Citations</th>
                    <th className="p-3.5">Faithfulness</th>
                    <th className="p-3.5">Concept Recall</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 text-slate-300">
                  {activeRun.sample_evaluations?.map((sample: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-800/50">
                      <td className="p-3.5 font-mono uppercase text-[10px] font-bold text-indigo-400">
                        {sample.category}
                      </td>
                      <td className="p-3.5 font-medium text-white max-w-xs truncate">
                        {sample.question}
                      </td>
                      <td className="p-3.5">
                        {sample.is_grounded ? (
                          <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Grounded
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center gap-1 font-semibold">
                            <AlertTriangle className="w-3.5 h-3.5" /> Rejected (Safe)
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 font-mono">{sample.citations_count}</td>
                      <td className="p-3.5 font-mono text-emerald-400">
                        {(sample.faithfulness * 100).toFixed(0)}%
                      </td>
                      <td className="p-3.5 font-mono text-sky-400">
                        {(sample.context_recall * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-16 text-center rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <BarChart3 className="w-12 h-12 text-indigo-400 mx-auto" />
          <h3 className="text-lg font-bold text-white">No Benchmark Evaluations Executed Yet</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Click &quot;Run Live Benchmark&quot; to execute real test cases measuring Faithfulness, Answer Relevancy, Context Precision, and simulated student sessions.
          </p>
          <button
            onClick={handleRunEvaluation}
            disabled={running}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors shadow-lg shadow-indigo-600/30"
          >
            Execute Benchmark Now
          </button>
        </div>
      )}
    </div>
  );
}
