"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import { Course, DocumentItem, User } from "@/lib/types";
import { AuthModal } from "@/components/AuthModal";
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
  X,
  Lock,
  Trash2,
  Sparkles,
  Info,
  ShieldCheck,
  LogIn
} from "lucide-react";

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadTopic, setUploadTopic] = useState("Core Foundations");
  const [newCourseTitle, setNewCourseTitle] = useState("");
  const [newCourseDesc, setNewCourseDesc] = useState("");
  const [showNewCourseModal, setShowNewCourseModal] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Escape key handler for modal
  useEffect(() => {
    if (!showNewCourseModal) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowNewCourseModal(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showNewCourseModal]);

  const loadCourses = useCallback(async () => {
    try {
      const list = await api.listCourses();
      setCourses(list);
      setIsOnline(true);
      if (list.length > 0) {
        setSelectedCourseId((prev) => (list.some((c) => c.id === prev) ? prev : list[0].id));
      }
    } catch (e) {
      console.error("Failed to load courses:", e);
    }
  }, []);

  const loadDocuments = useCallback(async (cId: string) => {
    if (!cId) return;
    try {
      const docs = await api.listDocuments(cId);
      setDocuments(docs);
    } catch (e) {
      console.error("Failed to load documents:", e);
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    api.getHealth()
      .then(() => {
        if (isMounted) setIsOnline(true);
      })
      .catch(() => {
        if (isMounted) setIsOnline(false);
      });

    api.getMe()
      .then((me) => {
        if (isMounted) setUser(me);
      })
      .catch(() => {
        if (isMounted) setUser(null);
      });

    api.listCourses()
      .then((list) => {
        if (isMounted) {
          setCourses(list);
          if (list.length > 0) {
            setSelectedCourseId((prev) => (list.some((c) => c.id === prev) ? prev : list[0].id));
          }
        }
      })
      .catch((e) => console.error("Failed to load courses:", e));

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCourseId) return;
    let isMounted = true;
    api.listDocuments(selectedCourseId)
      .then((docs) => {
        if (isMounted) setDocuments(docs);
      })
      .catch((e) => {
        console.error("Failed to load documents:", e);
        if (isMounted) setDocuments([]);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedCourseId]);

  const selectedCourse = courses.find((c) => c.id === selectedCourseId);
  const isSelectedCourseDemo = Boolean(
    selectedCourse && (selectedCourse.is_demo || selectedCourse.visibility === "shared_demo")
  );

  const demoCourses = courses.filter((c) => c.is_demo || c.visibility === "shared_demo");
  const privateCourses = courses.filter((c) => !c.is_demo && c.visibility !== "shared_demo");

  async function processFile(file: File) {
    if (!selectedCourseId || uploading) return;
    setErrorMessage(null);

    // Guard: Prevent upload to shared demo course unless admin
    if (isSelectedCourseDemo && user?.role !== "admin") {
      setErrorMessage("The shared BEFA demo course is read-only. Please create or select a Private Course to upload documents.");
      return;
    }

    if (!user) {
      setAuthModalOpen(true);
      return;
    }

    setUploading(true);
    try {
      await api.uploadDocument(selectedCourseId, file, uploadTopic);
      await loadDocuments(selectedCourseId);
      await loadCourses();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Upload failed: ${msg}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      await processFile(file);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
  }

  async function handleRetry(docId: string) {
    try {
      await api.retryDocument(docId);
      await loadDocuments(selectedCourseId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Retry failed: ${msg}`);
    }
  }

  async function handleDeleteDocument(docId: string, filename: string) {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? This will remove all chunks and embeddings.`)) {
      return;
    }
    try {
      await api.deleteDocument(docId);
      await loadDocuments(selectedCourseId);
      await loadCourses();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Delete failed: ${msg}`);
    }
  }

  async function handleDeleteCourse(courseId: string, title: string) {
    if (!window.confirm(`Are you sure you want to delete the private course "${title}"? All course documents, embeddings, and records will be purged.`)) {
      return;
    }
    try {
      await api.deleteCourse(courseId);
      await loadCourses();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Failed to delete course: ${msg}`);
    }
  }

  async function handleCreateCourse(e: React.FormEvent) {
    e.preventDefault();
    if (!newCourseTitle.trim()) return;

    if (!user) {
      setAuthModalOpen(true);
      return;
    }

    try {
      const created = await api.createCourse(newCourseTitle.trim(), newCourseDesc.trim());
      setNewCourseTitle("");
      setNewCourseDesc("");
      setShowNewCourseModal(false);
      await loadCourses();
      setSelectedCourseId(created.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Failed to create course: ${msg}`);
    }
  }

  const getDocIcon = (type: string) => {
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

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium text-[#22C55E] px-2 py-0.5 rounded bg-[#22C55E]/10 border border-[#22C55E]/20">
            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Ingested & Grounded
          </span>
        );
      case "processing":
      case "pending":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium text-[#F59E0B] px-2 py-0.5 rounded bg-[#F59E0B]/10 border border-[#F59E0B]/20">
            <Clock className="w-3.5 h-3.5 animate-spin" aria-hidden="true" /> Indexing Chunks...
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium text-[#EF4444] px-2 py-0.5 rounded bg-[#EF4444]/10 border border-[#EF4444]/20">
            <AlertCircle className="w-3.5 h-3.5" aria-hidden="true" /> Processing Error
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header and Course Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#262626]">
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[#F5F5F5] flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#3B82F6]" aria-hidden="true" /> Course Knowledge Base Ingestion
          </h1>
          <p className="text-xs md:text-sm text-[#A1A1AA] mt-1">
            Access the shared read-only BEFA demo or manage your private courses with isolated retrieval.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            if (!user) {
              setAuthModalOpen(true);
            } else {
              setShowNewCourseModal(true);
            }
          }}
          className="flex items-center gap-2 px-3.5 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs md:text-sm font-medium transition-colors shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6] shadow-sm"
        >
          <Plus className="w-4 h-4" aria-hidden="true" /> Create Private Course
        </button>
      </div>

      {/* Global Error Banner */}
      {errorMessage && (
        <div className="p-3.5 rounded-lg bg-[#EF4444]/10 border border-[#EF4444]/30 text-[#EF4444] text-xs flex items-center justify-between gap-2 animate-in fade-in duration-150">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="p-1 rounded text-[#EF4444] hover:bg-[#EF4444]/20"
            aria-label="Dismiss message"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Section 1: Shared Demo Courses */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#3B82F6]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#F5F5F5]">
              Shared Demo Course (Public & Read-Only)
            </h2>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded bg-[#181818] border border-[#262626] text-[#A1A1AA]">
            No account required
          </span>
        </div>

        {/* Demo Course Cards / Selector */}
        {demoCourses.length === 0 ? (
          <div className="p-4 rounded-lg bg-[#121212] border border-[#262626] text-xs text-[#A1A1AA] flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0" />
            <span>
              {isOnline === false
                ? "Backend service is currently offline. Shared BEFA demo course will load once your backend server is deployed and connected."
                : "No shared demo courses available. Create a private course above to start uploading documents."}
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {demoCourses.map((c) => {
              const isSelected = selectedCourseId === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => setSelectedCourseId(c.id)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? "bg-[#181818] border-[#3B82F6] ring-1 ring-[#3B82F6]"
                      : "bg-[#121212] border-[#262626] hover:border-[#383838]"
                  }`}
                >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-[#080808] border border-[#262626] flex items-center justify-center text-[#3B82F6]">
                      <BookOpen className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <h3 className="font-medium text-xs md:text-sm text-[#F5F5F5]">{c.title}</h3>
                      <span className="text-[10px] text-[#71717A] uppercase font-mono">
                        Shared Demo &bull; Read-Only
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-[#3B82F6]/10 text-[#3B82F6] font-medium border border-[#3B82F6]/20">
                    {c.documents_count} Docs
                  </span>
                </div>
                {c.description && (
                  <p className="text-xs text-[#A1A1AA] mt-2 line-clamp-2">{c.description}</p>
                )}
              </div>
            );
          })}
        </div>
        )}
      </div>

      {/* Section 2: Private Workspaces (My Courses) */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-[#A1A1AA]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#F5F5F5]">
              My Private Workspaces (Isolated Storage)
            </h2>
          </div>
          {user ? (
            <span className="text-[11px] text-[#A1A1AA]">
              {privateCourses.length} Private Course{privateCourses.length === 1 ? "" : "s"}
            </span>
          ) : (
            <button
              onClick={() => setAuthModalOpen(true)}
              className="text-xs text-[#3B82F6] hover:underline flex items-center gap-1 focus:outline-none"
            >
              <LogIn className="w-3 h-3" /> Sign in to access
            </button>
          )}
        </div>

        {user ? (
          privateCourses.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {privateCourses.map((c) => {
                const isSelected = selectedCourseId === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedCourseId(c.id)}
                    className={`p-3.5 rounded-lg border cursor-pointer transition-all relative group ${
                      isSelected
                        ? "bg-[#181818] border-[#3B82F6] ring-1 ring-[#3B82F6]"
                        : "bg-[#121212] border-[#262626] hover:border-[#383838]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-[#080808] border border-[#262626] flex items-center justify-center text-[#22C55E]">
                          <ShieldCheck className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <h3 className="font-medium text-xs md:text-sm text-[#F5F5F5]">{c.title}</h3>
                          <span className="text-[10px] text-[#22C55E] uppercase font-mono">
                            Private Workspace
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] px-1.5 py-0.5 rounded bg-[#181818] text-[#A1A1AA] border border-[#262626]">
                          {c.documents_count} Docs
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteCourse(c.id, c.title);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded text-[#71717A] hover:text-[#EF4444] hover:bg-[#262626] transition-all"
                          title="Delete course"
                          aria-label={`Delete ${c.title}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    {c.description && (
                      <p className="text-xs text-[#A1A1AA] mt-2 line-clamp-2">{c.description}</p>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 rounded-lg bg-[#121212] border border-[#262626] text-center space-y-2">
              <p className="text-xs text-[#A1A1AA]">
                You have not created any private courses yet. Create one to upload your own textbooks and lecture slides.
              </p>
              <button
                type="button"
                onClick={() => setShowNewCourseModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1C1C1C] hover:bg-[#262626] border border-[#262626] text-xs font-medium text-[#F5F5F5] transition-colors"
              >
                <Plus className="w-3.5 h-3.5 text-[#3B82F6]" /> Create My First Course
              </button>
            </div>
          )
        ) : (
          <div className="p-5 rounded-lg bg-[#121212] border border-[#262626] flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="space-y-1 text-center sm:text-left">
              <h3 className="text-xs md:text-sm font-medium text-[#F5F5F5]">
                Private Workspaces Require an Account
              </h3>
              <p className="text-xs text-[#A1A1AA]">
                Sign in to create your own courses, upload confidential course files, and maintain private study records.
              </p>
            </div>
            <button
              onClick={() => setAuthModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-medium transition-colors shrink-0 shadow-sm"
            >
              <LogIn className="w-3.5 h-3.5" /> Sign In / Register
            </button>
          </div>
        )}
      </div>

      {/* Fallback when courses is empty */}
      {courses.length === 0 && (
        <div className="p-8 rounded-lg bg-[#121212] border border-[#262626] text-center space-y-3">
          <div className="w-10 h-10 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] mx-auto">
            {isOnline === false ? (
              <AlertCircle className="w-5 h-5 text-[#F59E0B]" aria-hidden="true" />
            ) : (
              <BookOpen className="w-5 h-5 text-[#3B82F6]" aria-hidden="true" />
            )}
          </div>
          <h3 className="text-sm font-semibold text-[#F5F5F5]">
            {isOnline === false ? "Backend Service Currently Offline" : "No Courses Indexed Yet"}
          </h3>
          <p className="text-xs text-[#A1A1AA] max-w-md mx-auto leading-relaxed">
            {isOnline === false
              ? "The frontend is running in standalone mode. Course knowledge base indexing and document ingestion will automatically activate once your FastAPI backend is running and connected via NEXT_PUBLIC_API_URL."
              : "No course materials have been uploaded yet. Click '+ Create Course' above to set up your first study workspace and start uploading lecture documents."}
          </p>
        </div>
      )}

      {/* Course Context & Ingestion Area */}
      {selectedCourse && (
        <div className="space-y-4 pt-2">
          {/* Active Course Banner */}
          <div className="p-4 rounded-lg bg-[#181818] border border-[#262626] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[#71717A] uppercase font-mono">
                  Currently Active Workspace:
                </span>
                <span
                  className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded font-mono ${
                    isSelectedCourseDemo
                      ? "bg-[#3B82F6]/10 text-[#3B82F6] border border-[#3B82F6]/30"
                      : "bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30"
                  }`}
                >
                  {isSelectedCourseDemo ? "Shared Demo (Read-Only)" : "Private Workspace"}
                </span>
              </div>
              <h2 className="text-base font-bold text-[#F5F5F5] mt-1">{selectedCourse.title}</h2>
            </div>
            <div className="text-xs text-[#A1A1AA] flex items-center gap-3">
              <span>{documents.length} Document{documents.length === 1 ? "" : "s"}</span>
              <span>&bull;</span>
              <span>{selectedCourse.topics_count} Topics</span>
            </div>
          </div>

          {/* Upload Dropzone OR Demo Read-Only Notice */}
          {isSelectedCourseDemo ? (
            <div className="p-6 rounded-lg bg-[#121212] border border-[#262626] flex items-start gap-3.5">
              <div className="w-9 h-9 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] shrink-0 mt-0.5">
                <Info className="w-4 h-4" />
              </div>
              <div className="space-y-1">
                <h3 className="text-xs md:text-sm font-semibold text-[#F5F5F5]">
                  Shared Demo Notes Are Read-Only
                </h3>
                <p className="text-xs text-[#A1A1AA] leading-relaxed">
                  This shared workspace includes official Business Economics &amp; Financial Analysis (BEFA) lecture materials. All visitors can query the grounded tutor, take adaptive quizzes, and view exact citations. To upload your own documents, select or create a Private Course above.
                </p>
                {!user && (
                  <button
                    onClick={() => setAuthModalOpen(true)}
                    className="inline-flex items-center gap-1.5 text-xs text-[#3B82F6] hover:underline font-medium mt-2"
                  >
                    <LogIn className="w-3.5 h-3.5" /> Sign in to create your own private course
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              className={`p-6 rounded-lg bg-[#121212] border-2 border-dashed transition-colors ${
                isDragOver ? "border-[#3B82F6] bg-[#181818]" : "border-[#262626] hover:border-[#383838]"
              }`}
            >
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] shrink-0">
                    <Upload className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#F5F5F5] text-sm md:text-base">
                      Upload Course Materials to Private Workspace
                    </h3>
                    <p className="text-xs text-[#A1A1AA] mt-0.5">
                      Supported formats: <strong className="text-[#F5F5F5]">PDF</strong>,{" "}
                      <strong className="text-[#F5F5F5]">PPTX</strong>,{" "}
                      <strong className="text-[#F5F5F5]">MP4</strong>
                    </p>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
                  <label htmlFor="upload-topic-input" className="sr-only">
                    Topic or chapter tag
                  </label>
                  <input
                    id="upload-topic-input"
                    type="text"
                    placeholder="Topic or chapter tag"
                    value={uploadTopic}
                    onChange={(e) => setUploadTopic(e.target.value)}
                    className="px-3 py-2 rounded-md bg-[#080808] border border-[#262626] text-xs text-[#F5F5F5] focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] w-full sm:w-48"
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
                    className={`flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-white font-medium text-xs md:text-sm cursor-pointer transition-colors w-full sm:w-auto shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6] ${
                      uploading ? "opacity-50 pointer-events-none" : ""
                    }`}
                  >
                    {uploading ? (
                      <>
                        <Clock className="w-4 h-4 animate-spin" aria-hidden="true" /> Ingesting Source File...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4" aria-hidden="true" /> Select File to Ingest
                      </>
                    )}
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Documents List */}
          <div className="space-y-3.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#71717A] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#71717A]" aria-hidden="true" />
                Ingested Documents ({documents.length})
              </h3>
              <button
                type="button"
                onClick={() => loadDocuments(selectedCourseId)}
                className="text-xs text-[#A1A1AA] hover:text-[#F5F5F5] flex items-center gap-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] rounded px-2 py-1 transition-colors"
              >
                <RotateCw className="w-3.5 h-3.5" aria-hidden="true" /> Refresh Status
              </button>
            </div>

            {documents.length > 0 ? (
              <div className="space-y-2.5">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3.5 rounded-md bg-[#121212] border border-[#262626] flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-md bg-[#181818] border border-[#262626] shrink-0">
                        {getDocIcon(doc.file_type)}
                      </div>
                      <div>
                        <h4 className="font-medium text-[#F5F5F5] text-xs md:text-sm truncate max-w-md">
                          {doc.filename}
                        </h4>
                        <div className="flex items-center gap-3 text-xs text-[#71717A] mt-1 font-mono">
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
                        {doc.ingestion_status === "failed" && doc.error_message && (
                          <div className="mt-2 text-xs text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/20 rounded px-2.5 py-1.5 max-w-xl">
                            <span className="font-semibold block text-[#EF4444]">
                              Processing Error
                            </span>
                            <span className="text-[#EF4444]/90">{doc.error_message}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {getStatusBadge(doc.ingestion_status)}
                      {doc.ingestion_status === "failed" && !isSelectedCourseDemo && (
                        <button
                          type="button"
                          onClick={() => handleRetry(doc.id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#181818] border border-[#262626] hover:bg-[#262626] text-xs font-medium text-[#F5F5F5] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
                        >
                          <RotateCw className="w-3.5 h-3.5" aria-hidden="true" /> Retry
                        </button>
                      )}
                      {!isSelectedCourseDemo && user && (
                        <button
                          type="button"
                          onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                          className="p-1.5 rounded text-[#71717A] hover:text-[#EF4444] hover:bg-[#181818] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[#EF4444]"
                          title="Delete document"
                          aria-label={`Delete ${doc.filename}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 rounded-md bg-[#121212] border border-[#262626] text-center space-y-1">
                <p className="text-xs text-[#A1A1AA]">
                  No documents found in this workspace. Upload your first lecture note or slide deck above.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* New Course Modal */}
      {showNewCourseModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-course-modal-title"
        >
          <div
            className="w-full max-w-md bg-[#121212] border border-[#262626] rounded-xl shadow-2xl p-6 relative"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowNewCourseModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-[#1C1C1C] transition-colors focus:outline-none"
              aria-label="Close dialog"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="mb-5">
              <h3 id="new-course-modal-title" className="text-base font-semibold text-[#F5F5F5] flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#3B82F6]" /> Create New Private Course
              </h3>
              <p className="text-xs text-[#A1A1AA] mt-1">
                Private courses are isolated to your account. Other students and visitors cannot view your documents or notes.
              </p>
            </div>

            <form onSubmit={handleCreateCourse} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5" htmlFor="course-title-input">
                  Course Title <span className="text-[#EF4444]">*</span>
                </label>
                <input
                  id="course-title-input"
                  type="text"
                  required
                  value={newCourseTitle}
                  onChange={(e) => setNewCourseTitle(e.target.value)}
                  placeholder="e.g. CS189: Introduction to Machine Learning"
                  className="w-full bg-[#181818] border border-[#262626] rounded-lg px-3 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:border-[#3B82F6] focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5" htmlFor="course-desc-input">
                  Description (optional)
                </label>
                <textarea
                  id="course-desc-input"
                  rows={3}
                  value={newCourseDesc}
                  onChange={(e) => setNewCourseDesc(e.target.value)}
                  placeholder="e.g. Core lecture slides and problem sets on optimization and deep learning."
                  className="w-full bg-[#181818] border border-[#262626] rounded-lg px-3 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:border-[#3B82F6] focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewCourseModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-[#181818] hover:bg-[#262626] text-xs font-medium text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors focus:outline-none"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newCourseTitle.trim()}
                  className="px-4 py-2 rounded-lg bg-[#3B82F6] hover:bg-[#2563EB] disabled:bg-[#1E3A8A] text-xs font-medium text-[#F5F5F5] transition-colors focus:outline-none shadow-sm"
                >
                  Create Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={(authenticatedUser) => {
          setUser(authenticatedUser);
          loadCourses();
        }}
      />
    </div>
  );
}
