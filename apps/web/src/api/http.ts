import type {
  DiagnosticsResponse,
  FeatureSpecWire,
  FeedbackCreate,
  FeedbackCreated,
  RecorderConfig,
  ReviewCreate,
  SampleCreateContract,
  SampleFrames,
  SampleList,
  SampleSummary,
  SessionCreate,
  SessionCreated,
  VocabularyResponse,
} from "./generated/contracts";
import { isHealthResponse, type HealthResponse } from "./types";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "/api/v1";

const REQUEST_TIMEOUT_MS = 5000;

export type ApiFailure = "unreachable" | "invalid_response";

export class ApiError extends Error {
  readonly kind: ApiFailure;

  constructor(kind: ApiFailure, message: string) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/health`, { signal: combined });
  } catch (cause) {
    if (signal?.aborted) throw cause;
    throw new ApiError("unreachable", "Backend did not respond");
  }
  // The Vite proxy answers 5xx when the backend is down.
  if (response.status >= 500) {
    throw new ApiError("unreachable", `Backend unavailable (HTTP ${response.status})`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!isHealthResponse(body)) {
    throw new ApiError("invalid_response", "Unexpected health response");
  }
  return body;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  if (!response.ok) throw new ApiError("unreachable", `HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const fetchFeatureSpec = () => getJson<FeatureSpecWire>("/feature-spec");
export const fetchDiagnostics = () => getJson<DiagnosticsResponse>("/diagnostics");

// --- recorder (Phase 4) ------------------------------------------------------------

/** Error from the API's error envelope, with its code for the Vietnamese message map. */
export class ApiCallError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiCallError";
  }
}

async function sendJson<T>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    throw new ApiCallError("UNREACHABLE", "Backend did not respond");
  }
  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiCallError(error?.code ?? "INTERNAL", error?.message ?? `HTTP ${response.status}`);
  }
  return data as T;
}

export const fetchRecorderConfig = () => sendJson<RecorderConfig>("GET", "/recordings/config");
export const createRecordingSession = (body: SessionCreate) =>
  sendJson<SessionCreated>("POST", "/recordings/sessions", body);
export const uploadSample = (sessionId: string, body: SampleCreateContract) =>
  sendJson<SampleSummary>("POST", `/recordings/sessions/${encodeURIComponent(sessionId)}/samples`, body);
export const listSamples = (status?: string) =>
  sendJson<SampleList>("GET", `/recordings/samples${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const fetchSampleFrames = (sampleId: string) =>
  sendJson<SampleFrames>("GET", `/recordings/samples/${encodeURIComponent(sampleId)}/frames`);
export const reviewSample = (sampleId: string, body: ReviewCreate) =>
  sendJson<SampleSummary>("POST", `/recordings/samples/${encodeURIComponent(sampleId)}/review`, body);

// --- vocabulary and feedback (Phase 6) -----------------------------------------------

export const fetchVocabulary = () => sendJson<VocabularyResponse>("GET", "/vocabulary");
export const sendFeedback = (body: FeedbackCreate) => sendJson<FeedbackCreated>("POST", "/feedback", body);
export const deleteFeedback = () => sendJson<null>("DELETE", "/feedback");
