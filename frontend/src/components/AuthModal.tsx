"use client";

import React, { useState, useEffect, useSyncExternalStore } from "react";
import { api, isBackendConfigured } from "@/lib/api";
import { User } from "@/lib/types";
import { X, Lock, Mail, User as UserIcon, Loader2, AlertCircle, BookOpen } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: User) => void;
  initialMode?: "login" | "register";
}

const emptySubscribe = () => () => {};

export function AuthModal({ isOpen, onClose, onSuccess, initialMode = "login" }: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isClient = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const backendConfigured = isClient ? isBackendConfigured() : true;

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError(null);

    if (!isBackendConfigured()) {
      setError(
        "Account services are temporarily unavailable because the backend server has not been deployed yet. Please configure NEXT_PUBLIC_API_URL once your FastAPI backend is online."
      );
      return;
    }

    setLoading(true);

    try {
      if (mode === "login") {
        const res = await api.login(email, password);
        onSuccess(res.user);
        onClose();
      } else {
        const res = await api.register(email, password, fullName || undefined);
        onSuccess(res.user);
        onClose();
      }
    } catch (err: unknown) {
      const rawMsg = err instanceof Error ? err.message : String(err);
      let friendlyMsg = rawMsg;
      if (rawMsg.toLowerCase().includes("not found") || rawMsg.includes("404")) {
        friendlyMsg =
          "Account service is currently unavailable. The backend authentication endpoint was not found (HTTP 404). Please ensure your FastAPI backend is deployed and NEXT_PUBLIC_API_URL is configured.";
      } else if (
        rawMsg.toLowerCase().includes("failed to fetch") ||
        rawMsg.toLowerCase().includes("offline") ||
        rawMsg.toLowerCase().includes("networkerror")
      ) {
        friendlyMsg =
          "Unable to reach the LearnMate AI backend server. The service is currently offline or unreachable.";
      }
      setError(friendlyMsg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div
        className="w-full max-w-md bg-[#121212] border border-[#262626] rounded-xl shadow-2xl p-6 relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-[#A1A1AA] hover:text-[#F5F5F5] hover:bg-[#1C1C1C] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6]"
          aria-label="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6]">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h2 id="auth-modal-title" className="text-lg font-semibold text-[#F5F5F5]">
                {mode === "login" ? "Sign In to LearnMate AI" : "Create Your Account"}
              </h2>
              <p className="text-xs text-[#A1A1AA]">
                {mode === "login"
                  ? "Access your private workspaces and saved courses."
                  : "Start creating your own private, isolated courses."}
              </p>
            </div>
          </div>

          {/* Shared Demo Callout Banner */}
          <div className="p-2.5 rounded-lg bg-[#181818] border border-[#262626] text-[11px] text-[#A1A1AA] flex items-start gap-2 mt-3">
            <BookOpen className="w-3.5 h-3.5 text-[#3B82F6] shrink-0 mt-0.5" />
            <span>
              <strong className="text-[#F5F5F5]">Visitor Notice:</strong> The shared BEFA demo course is completely free and requires no account. Sign in only if you wish to upload personal documents and create private courses.
            </span>
          </div>

          {/* Backend Offline Callout Banner */}
          {!backendConfigured && (
            <div className="p-2.5 rounded-lg bg-[#F59E0B]/10 border border-[#F59E0B]/30 text-[#F59E0B] text-xs flex items-start gap-2 mt-3">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[#F59E0B]" />
              <div>
                <strong className="block font-semibold text-[#F59E0B]">
                  Account Services Standby
                </strong>
                <p className="text-[#A1A1AA] mt-0.5 leading-relaxed text-[11px]">
                  The FastAPI backend has not been deployed yet. Account creation and private workspaces will activate once your backend is online.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-[#EF4444]/10 border border-[#EF4444]/30 text-[#EF4444] text-xs flex items-center gap-2 animate-in fade-in duration-150">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5" htmlFor="full-name">
                Full Name (optional)
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-[#71717A] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="full-name"
                  type="text"
                  disabled={loading}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Jane Doe"
                  className="w-full bg-[#181818] border border-[#262626] rounded-lg pl-9 pr-3 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:border-[#3B82F6] focus-visible:ring-1 focus-visible:ring-[#3B82F6] disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5" htmlFor="email-input">
              Email Address <span className="text-[#EF4444]">*</span>
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-[#71717A] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="email-input"
                type="email"
                required
                disabled={loading}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@university.edu"
                className="w-full bg-[#181818] border border-[#262626] rounded-lg pl-9 pr-3 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:border-[#3B82F6] focus-visible:ring-1 focus-visible:ring-[#3B82F6] disabled:opacity-50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5" htmlFor="password-input">
              Password <span className="text-[#EF4444]">*</span>
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#71717A] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="password-input"
                type="password"
                required
                minLength={8}
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? "Minimum 8 characters" : "Enter your password"}
                className="w-full bg-[#181818] border border-[#262626] rounded-lg pl-9 pr-3 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus-visible:border-[#3B82F6] focus-visible:ring-1 focus-visible:ring-[#3B82F6] disabled:opacity-50"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !backendConfigured}
            className="w-full py-2.5 px-4 bg-[#3B82F6] hover:bg-[#2563EB] disabled:bg-[#181818] disabled:text-[#71717A] disabled:border disabled:border-[#262626] disabled:cursor-not-allowed text-[#F5F5F5] font-medium text-xs rounded-lg transition-colors flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6] mt-2 shadow-sm"
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>{mode === "login" ? "Authenticating..." : "Creating Account..."}</span>
              </>
            ) : !backendConfigured ? (
              <span>{mode === "login" ? "Sign In (Backend Offline)" : "Create Account (Backend Offline)"}</span>
            ) : (
              <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
            )}
          </button>
        </form>

        {/* Mode Switcher */}
        <div className="mt-5 pt-4 border-t border-[#262626] text-center text-xs text-[#A1A1AA]">
          {mode === "login" ? (
            <p>
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
                className="text-[#3B82F6] hover:underline font-medium focus:outline-none"
              >
                Create one now
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                className="text-[#3B82F6] hover:underline font-medium focus:outline-none"
              >
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
