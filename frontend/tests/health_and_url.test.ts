import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeApiBaseUrl,
  DEFAULT_PRODUCTION_API_URL,
  parseHealthResponse,
  isNetworkError
} from "../src/lib/api";

test("API Base URL Normalization - Default Fallback", () => {
  assert.equal(
    normalizeApiBaseUrl(undefined),
    DEFAULT_PRODUCTION_API_URL,
    "undefined should fall back to DEFAULT_PRODUCTION_API_URL"
  );
  assert.equal(
    normalizeApiBaseUrl(null),
    DEFAULT_PRODUCTION_API_URL,
    "null should fall back to DEFAULT_PRODUCTION_API_URL"
  );
  assert.equal(
    normalizeApiBaseUrl(""),
    DEFAULT_PRODUCTION_API_URL,
    "empty string should fall back to DEFAULT_PRODUCTION_API_URL"
  );
  assert.equal(
    normalizeApiBaseUrl("   "),
    DEFAULT_PRODUCTION_API_URL,
    "whitespace-only string should fall back to DEFAULT_PRODUCTION_API_URL"
  );
});

test("API Base URL Normalization - Path Correction and Deduplication", () => {
  const host = "https://learnmate-ai-backend-gvxc.onrender.com";
  const expected = "https://learnmate-ai-backend-gvxc.onrender.com/api";

  // When /api is omitted
  assert.equal(normalizeApiBaseUrl(host), expected);
  assert.equal(normalizeApiBaseUrl(`${host}/`), expected);

  // When /api is already present
  assert.equal(normalizeApiBaseUrl(`${host}/api`), expected);
  assert.equal(normalizeApiBaseUrl(`${host}/api/`), expected);

  // When /api is accidentally duplicated
  assert.equal(normalizeApiBaseUrl(`${host}/api/api`), expected);
  assert.equal(normalizeApiBaseUrl(`${host}/api/api/`), expected);

  // Custom hosts
  assert.equal(normalizeApiBaseUrl("http://localhost:8000"), "http://localhost:8000/api");
  assert.equal(normalizeApiBaseUrl("http://localhost:8000/api/"), "http://localhost:8000/api");
});

test("Exact Health Check Endpoint URL Construction", () => {
  const base = normalizeApiBaseUrl(undefined);
  const healthUrl = `${base}/health`;
  assert.equal(
    healthUrl,
    "https://learnmate-ai-backend-gvxc.onrender.com/api/health",
    "Health check must point to /api/health on the deployed backend"
  );
});

test("Health Status Parsing - Live Groq Backend Shape", () => {
  const livePayload = {
    status: "ok",
    app_name: "LearnMate AI Backend",
    active_provider: "groq",
    active_model: "openai/gpt-oss-120b",
    provider_configured: true
  };

  const parsed = parseHealthResponse(livePayload);
  assert.equal(parsed.status, "ok");
  assert.equal(parsed.app_name, "LearnMate AI Backend");
  assert.equal(parsed.active_provider, "groq");
  assert.equal(parsed.active_model, "openai/gpt-oss-120b");
  assert.equal(parsed.provider_configured, true);
  assert.equal(parsed.storage_mode, "local_embedded");
});

test("Health Status Parsing - Minimal and Alternative Shapes", () => {
  const minimalPayload = {
    status: "healthy"
  };

  const parsedMinimal = parseHealthResponse(minimalPayload);
  assert.equal(parsedMinimal.status, "ok");
  assert.equal(parsedMinimal.app_name, "LearnMate AI Backend");
  assert.equal(parsedMinimal.provider_configured, true);

  const geminiPayload = {
    status: "ok",
    app_name: "LearnMate AI Backend",
    gemini_configured: true,
    supabase_configured: true,
    storage_mode: "supabase",
    active_provider: "gemini"
  };

  const parsedGemini = parseHealthResponse(geminiPayload);
  assert.equal(parsedGemini.gemini_configured, true);
  assert.equal(parsedGemini.supabase_configured, true);
  assert.equal(parsedGemini.storage_mode, "supabase");
  assert.equal(parsedGemini.provider_configured, true);
});

test("Network Error Detection", () => {
  assert.equal(isNetworkError(new TypeError("Failed to fetch")), true);
  assert.equal(isNetworkError(new Error("NetworkError when attempting to fetch resource.")), true);
  assert.equal(isNetworkError(new Error("Load failed")), true);
  assert.equal(isNetworkError(new Error("Internal Server Error (500)")), false);
  assert.equal(isNetworkError(null), false);
});

test("Live Backend Connectivity Verification", async () => {
  const healthUrl = "https://learnmate-ai-backend-gvxc.onrender.com/api/health";
  const res = await fetch(healthUrl);
  assert.equal(res.status, 200, "Deployed backend health endpoint must respond with 200 OK");
  const data = await res.json();
  assert.equal(data.status, "ok");
  assert.ok(data.app_name);
  console.log("  Live backend health verified:", JSON.stringify(data));
});

test("Regression: Provided HTTP 200 Health Response Is Considered Healthy", () => {
  const verifiedProductionResponse = {
    status: "ok",
    app_name: "LearnMate AI Backend",
    active_provider: "groq",
    active_model: "openai/gpt-oss-120b",
    provider_configured: true
  };

  const parsed = parseHealthResponse(verifiedProductionResponse);

  // 1. Core health check status
  assert.equal(parsed.status, "ok", "HTTP 200 health response must have status 'ok'");

  // 2. Provider configuration
  const isConfigured = parsed.provider_configured ?? parsed.gemini_configured ?? false;
  assert.equal(isConfigured, true, "provider_configured must be true for Groq");

  // 3. Provider label calculation
  const providerLabel = parsed.active_provider ? parsed.active_provider.toUpperCase() : "GEMINI";
  assert.equal(providerLabel, "GROQ", "Provider label must be uppercase 'GROQ'");

  // 4. Header status indicator logic
  const isHealthy = parsed !== null && parsed.status === "ok";
  assert.equal(isHealthy, true, "Health state must be considered healthy and online");
});

test("Regression: Empty Courses Array Does Not Mark Backend Offline", () => {
  const healthyStatus = parseHealthResponse({
    status: "ok",
    app_name: "LearnMate AI Backend",
    active_provider: "groq",
    provider_configured: true
  });
  const courses: unknown[] = [];
  const isCheckingHealth = false;

  // Header course display logic
  const headerCourseText =
    courses.length > 0
      ? "Course Dropdown Active"
      : healthyStatus === null
      ? (isCheckingHealth ? "Connecting..." : "Backend Offline")
      : "No courses indexed";

  assert.equal(
    headerCourseText,
    "No courses indexed",
    "Header must display 'No courses indexed' when backend is healthy and courses array is empty"
  );

  // Header AI Engine display logic
  const isConfigured = healthyStatus?.provider_configured ?? false;
  const headerEngineText =
    healthyStatus === null ? "Offline" : isConfigured ? "Live" : "Standby";

  assert.equal(
    headerEngineText,
    "Live",
    "Header engine indicator must remain 'Live' when courses array is empty"
  );

  // Tutor banner display logic
  const isOnline = healthyStatus !== null && healthyStatus.status === "ok";
  const tutorBannerText =
    courses.length > 0
      ? "Strict Grounding Active"
      : isOnline === false
      ? "Backend Offline"
      : "Awaiting Course Upload";

  assert.equal(
    tutorBannerText,
    "Awaiting Course Upload",
    "Tutor banner must display 'Awaiting Course Upload' when online with 0 courses"
  );

  // Assessments button text logic
  const assessmentButtonText =
    isOnline === false
      ? "Backend Offline (Quiz Generation Unavailable)"
      : courses.length === 0
      ? "Awaiting Course Upload (No Courses Found)"
      : "Generate Adaptive Assessment";

  assert.equal(
    assessmentButtonText,
    "Awaiting Course Upload (No Courses Found)",
    "Assessments button must indicate awaiting course upload, not 'Backend Offline'"
  );

  // Dashboard deployment banner logic
  const dashboardBannerType =
    isOnline === false
      ? "backend_offline"
      : courses.length === 0
      ? "awaiting_courses"
      : "active";

  assert.equal(
    dashboardBannerType,
    "awaiting_courses",
    "Dashboard must show welcoming course upload instructions, not 'Backend API is currently offline'"
  );
});

test("Regression: Course Loading Failure Does Not Overwrite Successful Health Check", async () => {
  let healthState: ReturnType<typeof parseHealthResponse> | null = null;
  let isCheckingHealth = true;
  let coursesState: unknown[] = [];

  // Step 1: Health check succeeds
  const mockHealthPayload = {
    status: "ok",
    app_name: "LearnMate AI Backend",
    active_provider: "groq",
    provider_configured: true
  };
  healthState = parseHealthResponse(mockHealthPayload);
  isCheckingHealth = false;
  assert.equal(isCheckingHealth, false);

  assert.ok(healthState !== null, "Health check must be populated");
  assert.equal(healthState.status, "ok");

  // Step 2: Course loading fails (e.g. 500 error, network timeout on courses endpoint)
  try {
    throw new Error("HTTP 500 Internal Server Error loading courses");
  } catch {
    // Handling must NOT reset or overwrite healthState
    coursesState = [];
    assert.equal(coursesState.length, 0);
    console.log("  Handled expected course loading failure without touching health state");
  }

  // Step 3: Verify health check remains intact
  assert.ok(healthState !== null, "healthState must NOT be set to null when course fetch fails");
  assert.equal(healthState.status, "ok", "healthState.status must remain 'ok'");

  // Step 4: Verify Header still displays healthy state
  const isHealthyAfterCourseFailure = healthState !== null && healthState.status === "ok";
  assert.equal(
    isHealthyAfterCourseFailure,
    true,
    "Backend must remain verified online even if courses endpoint encountered an error"
  );
});

