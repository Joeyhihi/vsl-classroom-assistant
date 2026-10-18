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
