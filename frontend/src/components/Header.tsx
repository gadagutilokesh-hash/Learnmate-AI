"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { HealthStatus, Course, User } from "@/lib/types";
import { AuthModal } from "./AuthModal";
import {
  Cpu, Database, CheckCircle2, BookOpen,
  User as UserIcon, AlertCircle, LogIn, LogOut, ShieldCheck
} from "lucide-react";

export function Header() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(true);
  const [courses, setCourses] = useState<Course[]>([]);
  const [activeCourseId, setActiveCourseId] = useState<string>("");
  const [user, setUser] = useState<User | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const loadCourses = useCallback(async () => {
    try {
      const cList = await api.listCourses();
      setCourses(cList);
      if (cList.length > 0) {
        setActiveCourseId((prev) => (cList.some((c) => c.id === prev) ? prev : cList[0].id));
      }
    } catch (err) {
      console.warn("Could not list courses:", err);
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
      setIsCheckingHealth(false);
      return h;
    } catch (err) {
      console.warn("[Header] Backend health check failed:", err);
      setHealth(null);
      setIsCheckingHealth(false);
      return null;
    }
  }, []);

  const coursesRef = React.useRef(courses);
  useEffect(() => {
    coursesRef.current = courses;
  }, [courses]);

  useEffect(() => {
    let isMounted = true;
    let retryTimer: NodeJS.Timeout | null = null;
    let pollInterval: NodeJS.Timeout | null = null;

    const performInitialCheck = async () => {
      const initialHealth = await checkHealth();
      if (!isMounted) return;

      if (!initialHealth) {
        // First attempt failed (possible Render cold start). Schedule a quick retry in 3.5s
        retryTimer = setTimeout(async () => {
          if (!isMounted) return;
          const retryHealth = await checkHealth();
          if (retryHealth) {
            loadCourses();
          }
        }, 3500);
      }
    };

    performInitialCheck();

    // Background health polling every 30s to detect server recovery / maintain connection
    pollInterval = setInterval(() => {
      if (isMounted) {
        checkHealth().then((h) => {
          if (h && coursesRef.current.length === 0) {
            loadCourses();
          }
        });
      }
    }, 30000);

    api.getMe()
      .then((me) => {
        if (isMounted) setUser(me);
      })
      .catch(() => {
        if (isMounted) setUser(null);
      });

    api.listCourses()
      .then((cList) => {
        if (isMounted) {
          setCourses(cList);
          if (cList.length > 0) {
            setActiveCourseId((prev) => (cList.some((c) => c.id === prev) ? prev : cList[0].id));
          }
        }
      })
      .catch((err) => console.warn("Could not list courses:", err));

    return () => {
      isMounted = false;
      if (retryTimer) clearTimeout(retryTimer);
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [checkHealth, loadCourses]);

  const handleAuthSuccess = (authenticatedUser: User) => {
    setUser(authenticatedUser);
    loadCourses();
  };

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    loadCourses();
  };

  const providerLabel = health?.active_provider
    ? health.active_provider.toUpperCase()
    : "GEMINI";

  const isConfigured = health?.provider_configured ?? health?.gemini_configured ?? false;

  return (
    <>
      <header className="h-14 border-b border-[#262626] bg-[#0B0B0B]/95 backdrop-blur-sm px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20">
        {/* Active Course Selector with Accessible Association */}
        <div className="flex items-center gap-2">
          <label
            htmlFor="active-course-dropdown"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-[#121212] border border-[#262626] text-xs font-medium text-[#A1A1AA]"
          >
            <BookOpen className="w-3.5 h-3.5 text-[#3B82F6] shrink-0" aria-hidden="true" />
            <span className="hidden sm:inline text-[#71717A]">Course:</span>
            {courses.length > 0 ? (
              <select
                id="active-course-dropdown"
                value={activeCourseId}
                onChange={(e) => setActiveCourseId(e.target.value)}
                className="bg-transparent text-[#F5F5F5] font-medium focus:outline-none focus-visible:ring-1 focus-visible:ring-[#3B82F6] cursor-pointer ml-1 max-w-[200px] sm:max-w-[280px] truncate"
              >
                {courses.map((c) => {
                  const isDemo = c.is_demo || c.visibility === "shared_demo";
                  return (
                    <option key={c.id} value={c.id} className="bg-[#121212] text-[#F5F5F5]">
                      {isDemo ? `[Demo] ${c.title}` : `[Private] ${c.title}`}
                    </option>
                  );
                })}
              </select>
            ) : (
              <span className="text-[#71717A] text-[11px] ml-1">
                {health === null ? (isCheckingHealth ? "Connecting..." : "Backend Offline") : "No courses indexed"}
              </span>
            )}
          </label>
        </div>

        {/* System Status Indicators & Auth Actions */}
        <div className="flex items-center gap-2 text-xs">
          {/* Dynamic AI Engine Indicator */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#121212] border border-[#262626] text-[#A1A1AA]">
            <Cpu className="w-3.5 h-3.5 text-[#3B82F6]" aria-hidden="true" />
            <span className="text-[#71717A] text-[11px]">{health ? `${providerLabel}:` : "Backend:"}</span>
            {isCheckingHealth && !health ? (
              <span className="text-[#A1A1AA] flex items-center gap-1 font-medium text-[11px]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6] animate-pulse" /> Connecting...
              </span>
            ) : health === null ? (
              <span className="text-[#71717A] flex items-center gap-1 font-medium text-[11px]">
                <AlertCircle className="w-3 h-3 text-[#F59E0B]" aria-hidden="true" /> Offline
              </span>
            ) : isConfigured ? (
              <span className="text-[#22C55E] flex items-center gap-1 font-medium text-[11px]">
                <CheckCircle2 className="w-3 h-3" aria-hidden="true" /> Live
              </span>
            ) : (
              <span className="text-[#F59E0B] flex items-center gap-1 font-medium text-[11px]">
                <AlertCircle className="w-3 h-3" aria-hidden="true" /> Standby
              </span>
            )}
          </div>

          {/* Database Index Indicator */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#121212] border border-[#262626] text-[#A1A1AA]">
            <Database className="w-3.5 h-3.5 text-[#71717A]" aria-hidden="true" />
            <span className="text-[#71717A] text-[11px]">Index:</span>
            <span className="text-[#F5F5F5] font-mono text-[11px]">
              {health === null ? (isCheckingHealth ? "Connecting..." : "Offline") : health?.storage_mode === "supabase" ? "Supabase pgvector" : "Local Vector DB"}
            </span>
          </div>

          {/* User Account / Auth Section */}
          <div className="flex items-center gap-2 pl-2 border-l border-[#262626]">
            {user ? (
              <div className="flex items-center gap-2">
                <div
                  className="w-7 h-7 rounded-md bg-[#181818] border border-[#262626] flex items-center justify-center text-[#3B82F6] font-medium text-xs"
                  title={user.email}
                >
                  <UserIcon className="w-3.5 h-3.5" aria-hidden="true" />
                </div>
                <div className="hidden sm:flex flex-col text-left">
                  <span className="text-xs font-medium text-[#F5F5F5] leading-none max-w-[120px] truncate">
                    {user.full_name || user.email.split("@")[0]}
                  </span>
                  {user.role === "admin" && (
                    <span className="text-[10px] text-[#3B82F6] flex items-center gap-0.5 leading-none mt-0.5">
                      <ShieldCheck className="w-2.5 h-2.5" /> Admin
                    </span>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1.5 rounded-md text-[#71717A] hover:text-[#EF4444] hover:bg-[#181818] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[#EF4444]"
                  title="Sign Out"
                  aria-label="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAuthModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#3B82F6] hover:bg-[#2563EB] text-[#F5F5F5] font-medium text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B82F6] shadow-sm"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
      />
    </>
  );
}
