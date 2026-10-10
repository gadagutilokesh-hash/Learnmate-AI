"use client";

import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Course, DocumentItem } from "@/lib/types";
import {
  Upload,
  FileText,
  Presentation,
  Video,
  CheckCircle2,
  AlertCircle,
  Clock,
  RotateCw,
  Plus,
  BookOpen,
  Layers,
  Sparkles
} from "lucide-react";

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadTopic, setUploadTopic] = useState("Core Foundations");
  const [newCourseTitle, setNewCourseTitle] = useState("");
  const [newCourseDesc, setNewCourseDesc] = useState("");
  const [showNewCourseModal, setShowNewCourseModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load courses
  useEffect(() => {
    loadCourses();
  }, []);

  async function loadCourses() {
    try {
      const list = await api.listCourses();
      setCourses(list);
      if (list.length > 0 && !selectedCourseId) {
        setSelectedCourseId(list[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Load documents for active course
  useEffect(() => {
    if (selectedCourseId) {
      loadDocuments(selectedCourseId);
    }
  }, [selectedCourseId]);

  async function loadDocuments(cId: string) {
    try {
      const docs = await api.listDocuments(cId);
      setDocuments(docs);
    } catch (e) {
      console.error(e);
    }
  }

  // Handle file upload
  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedCourseId) return;

    setUploading(true);
    try {
      await api.uploadDocument(selectedCourseId, file, uploadTopic);
      await loadDocuments(selectedCourseId);
      await loadCourses();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Handle Retry
  async function handleRetry(docId: string) {
    try {
      await api.retryDocument(docId);
      await loadDocuments(selectedCourseId);
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    }
  }

  // Handle Create Course
  async function handleCreateCourse(e: React.FormEvent) {
    e.preventDefault();
    if (!newCourseTitle.trim()) return;

    try {
      const created = await api.createCourse(newCourseTitle, newCourseDesc);
      setNewCourseTitle("");
      setNewCourseDesc("");
      setShowNewCourseModal(false);
      await loadCourses();
      setSelectedCourseId(created.id);
    } catch (err: any) {
      alert(`Failed to create course: ${err.message}`);
    }
  }

  const getDocIcon = (type: string) => {
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

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="flex items-center gap-1 text-xs font-medium text-emerald-400 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> Ingested & Grounded
          </span>
        );
      case "processing":
      case "pending":
        return (
          <span className="flex items-center gap-1 text-xs font-medium text-amber-400 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5 animate-spin" /> Chunking & Indexing...
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 text-xs font-medium text-rose-400 px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20">
            <AlertCircle className="w-3.5 h-3.5" /> Processing Error
          </span>
        );
      default:
        return null;
    }
  };

  const activeCourse = courses.find((c) => c.id === selectedCourseId);

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Header and Course Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-400" /> Course Knowledge Base Ingestion
          </h1>
          <p className="text-sm text-slate-400">
            Ingest textbooks (PDF), slide decks (PPTX), and lecture videos (MP4) with page-level provenance.
          </p>
        </div>

        <button
          onClick={() => setShowNewCourseModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors shadow-md shadow-indigo-600/20 shrink-0"
        >
          <Plus className="w-4 h-4" /> Create New Course
        </button>
      </div>

      {/* Course Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-slate-800">
        {courses.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelectedCourseId(c.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              selectedCourseId === c.id
                ? "bg-slate-800 text-white border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            {c.title}
          </button>
        ))}
      </div>

      {/* Upload Box */}
      <div className="p-6 rounded-2xl bg-slate-900 border border-dashed border-slate-700 hover:border-indigo-500/50 transition-colors">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
              <Upload className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">
                Upload Course Materials
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Supported formats: <strong className="text-slate-300">PDF</strong> (Text & Diagrams),{" "}
                <strong className="text-slate-300">PPTX</strong> (Slides & Tables),{" "}
                <strong className="text-slate-300">MP4</strong> (Transcripts & Timestamps)
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
            <input
              type="text"
              placeholder="Topic / Chapter tag"
              value={uploadTopic}
              onChange={(e) => setUploadTopic(e.target.value)}
              className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 w-full sm:w-48"
            />
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.pptx,.ppt,.mp4,.mp3,.wav"
              onChange={handleFileUpload}
              className="hidden"
              id="file-upload"
              disabled={uploading}
            />
            <label
              htmlFor="file-upload"
              className={`flex items-center justify-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm cursor-pointer transition-all w-full sm:w-auto shrink-0 ${
                uploading ? "opacity-50 pointer-events-none" : ""
              }`}
            >
              {uploading ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" /> Ingesting Multimodal Source...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" /> Select File to Ingest
                </>
              )}
            </label>
          </div>
        </div>
      </div>

      {/* Documents List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            Ingested Documents ({documents.length})
          </h2>
          <button
            onClick={() => loadDocuments(selectedCourseId)}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
          >
            <RotateCw className="w-3.5 h-3.5" /> Refresh Status
          </button>
        </div>

        {documents.length > 0 ? (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 shrink-0">
                    {getDocIcon(doc.file_type)}
                  </div>
                  <div>
                    <h4 className="font-semibold text-white text-sm truncate max-w-md">
                      {doc.filename}
                    </h4>
                    <div className="flex items-center gap-3 text-xs text-slate-400 mt-1 font-mono">
                      <span>Type: {doc.file_type.toUpperCase()}</span>
                      {doc.total_pages_or_slides && (
                        <span>
                          {doc.file_type === "pdf" ? "Pages" : "Slides"}: {doc.total_pages_or_slides}
                        </span>
                      )}
                      {doc.duration_seconds && (
                        <span>Duration: {Math.round(doc.duration_seconds)}s</span>
                      )}
                      <span>Chunks: {doc.chunks_count}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {getStatusBadge(doc.ingestion_status)}
                  {doc.ingestion_status === "failed" && (
                    <button
                      onClick={() => handleRetry(doc.id)}
                      className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-medium border border-rose-500/30 flex items-center gap-1 transition-colors"
                    >
                      <RotateCw className="w-3 h-3" /> Retry
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
            <BookOpen className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-sm">No documents uploaded for this course yet.</p>
            <p className="text-xs text-slate-500 mt-1">Upload a PDF textbook, PPTX slide deck, or MP4 video to start.</p>
          </div>
        )}
      </div>

      {/* New Course Modal */}
      {showNewCourseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <form
            onSubmit={handleCreateCourse}
            className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-xl p-6 shadow-2xl space-y-4"
          >
            <h3 className="text-lg font-bold text-white">Create New Course</h3>
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1">
                Course Title
              </label>
              <input
                type="text"
                required
                placeholder="e.g. CS231n: Deep Learning for Computer Vision"
                value={newCourseTitle}
                onChange={(e) => setNewCourseTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1">
                Description
              </label>
              <textarea
                rows={3}
                placeholder="Topics and curriculum goals..."
                value={newCourseDesc}
                onChange={(e) => setNewCourseDesc(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowNewCourseModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors"
              >
                Create Course
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
