// Centralized typed API client. Handles the Bearer header and 401 -> logout.
// All paths are RELATIVE so the same build works behind the FastAPI static host
// in production and behind the Vite dev proxy in development.

import type {
  FeedbackRequest,
  HealthResponse,
  LoginResponse,
  RulesConfig,
  SignRequest,
  SignResponse,
  SubmissionError,
  SubmissionListItem,
  SubmissionResult,
  SuggestResponse,
  TrainingMetrics,
  VersionInfo,
} from "./types";

const TOKEN_KEY = "label_approval_token";
const ROLE_KEY = "label_approval_role";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

export function setSession(token: string, role: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

// Subscribers (the app shell) are notified when a 401 forces a logout.
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(fn: UnauthorizedHandler): void {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function handleUnauthorized(): void {
  clearSession();
  if (onUnauthorized) onUnauthorized();
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers || {}) },
  });

  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiError(401, "session expired — please log in again");
  }

  const body = await parseJson(res);
  if (!res.ok) {
    const message =
      (body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : null) ||
      (typeof body === "string" ? body : null) ||
      `request failed (${res.status})`;
    throw new ApiError(res.status, message, body);
  }
  return body as T;
}

// --- Auth -------------------------------------------------------------------

export async function login(password: string): Promise<LoginResponse> {
  // Bypass the shared request() so we can surface a clean 401 message.
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (res.status === 401) {
    throw new ApiError(401, "incorrect password");
  }
  const body = (await parseJson(res)) as LoginResponse;
  if (!res.ok) {
    throw new ApiError(res.status, "login failed", body);
  }
  return body;
}

// --- Submissions ------------------------------------------------------------

export interface CreateSubmissionResult {
  ok: true;
  result: SubmissionResult;
}
export interface CreateSubmissionFailure {
  ok: false;
  error: SubmissionError;
}

// Uploads the multipart form. A 422 is an expected business outcome
// (missing/unclassified/linkage mismatch), returned as { ok: false }.
export async function createSubmission(
  files: Record<string, File>,
): Promise<CreateSubmissionResult | CreateSubmissionFailure> {
  const form = new FormData();
  for (const [field, file] of Object.entries(files)) {
    form.append(field, file);
  }
  const res = await fetch("/api/submissions", {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });

  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiError(401, "session expired — please log in again");
  }

  const body = await parseJson(res);
  if (res.status === 422) {
    return { ok: false, error: body as SubmissionError };
  }
  if (!res.ok) {
    throw new ApiError(res.status, `upload failed (${res.status})`, body);
  }
  return { ok: true, result: body as SubmissionResult };
}

export function listSubmissions(): Promise<SubmissionListItem[]> {
  return request<SubmissionListItem[]>("/api/submissions");
}

export function getSubmission(id: string): Promise<SubmissionResult> {
  return request<SubmissionResult>(
    `/api/submissions/${encodeURIComponent(id)}`,
  );
}

export function sign(id: string, body: SignRequest): Promise<SignResponse> {
  return request<SignResponse>(
    `/api/submissions/${encodeURIComponent(id)}/sign`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

// The bundle endpoint requires the Bearer header, so it cannot be a plain <a>.
// Fetch it as a blob and return an object URL the caller can open / download.
export async function fetchBundleUrl(id: string): Promise<string> {
  const res = await fetch(
    `/api/submissions/${encodeURIComponent(id)}/bundle`,
    { headers: { ...authHeaders() } },
  );
  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiError(401, "session expired — please log in again");
  }
  if (!res.ok) {
    throw new ApiError(res.status, "bundle not available");
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// --- Training / feedback ----------------------------------------------------

// Same multipart shape as createSubmission, but the batch is tagged training (never signed)
// and kept out of the live History. A 422 mismatch is still an expected business outcome.
export async function createTrainingSubmission(
  files: Record<string, File>,
): Promise<CreateSubmissionResult | CreateSubmissionFailure> {
  const form = new FormData();
  for (const [field, file] of Object.entries(files)) form.append(field, file);
  const res = await fetch("/api/training/submissions", {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiError(401, "session expired — please log in again");
  }
  const body = await parseJson(res);
  if (res.status === 422) return { ok: false, error: body as SubmissionError };
  if (!res.ok) throw new ApiError(res.status, `upload failed (${res.status})`, body);
  return { ok: true, result: body as SubmissionResult };
}

export function listTrainingSubmissions(): Promise<SubmissionListItem[]> {
  return request<SubmissionListItem[]>("/api/training/submissions");
}

export function trainingMetrics(): Promise<TrainingMetrics> {
  return request<TrainingMetrics>("/api/training/metrics");
}

export function submitFeedback(
  id: string,
  body: FeedbackRequest,
): Promise<{ saved: number }> {
  return request<{ saved: number }>(
    `/api/submissions/${encodeURIComponent(id)}/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

// Draft reviewable rule changes from the accumulated feedback (Claude API on the server).
// Never applies anything — returns suggestions for a human to apply.
export function suggestRuleChanges(): Promise<SuggestResponse> {
  return request<SuggestResponse>("/api/training/suggest", { method: "POST" });
}

// --- Rules config -----------------------------------------------------------

export function getRules(): Promise<RulesConfig> {
  return request<RulesConfig>("/api/rules");
}

// Validates server-side; rejects with ApiError(400, <joined messages>) on bad input.
export function saveRules(
  rules: RulesConfig,
  reviewerName?: string,
): Promise<RulesConfig> {
  return request<RulesConfig>("/api/rules", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rules, reviewer_name: reviewerName }),
  });
}

// --- Health -----------------------------------------------------------------

export async function health(): Promise<HealthResponse> {
  // /healthz is unauthenticated; a degraded backend returns 503 with a body.
  const res = await fetch("/healthz");
  const body = (await parseJson(res)) as HealthResponse;
  return body;
}

// --- Version / changelog ----------------------------------------------------

export async function getVersion(): Promise<VersionInfo> {
  // /version is unauthenticated; powers the header "What's New" + footer badge.
  const res = await fetch("/version");
  return (await parseJson(res)) as VersionInfo;
}
