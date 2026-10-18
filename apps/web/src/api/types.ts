// Hand-written mirror of services/ai-backend/src/vsl_backend/schemas/health.py.
// Replaced by generated contracts in Phase 3 (docs/API_CONTRACTS.md).
// Kept honest by src/api/types.test.ts, which validates the shared example
// services/ai-backend/tests/contract_examples/health.mock.json.

export type ComponentStatus = "ready" | "loading" | "unavailable" | "disabled" | "mock";

export interface ComponentHealth {
  status: ComponentStatus;
  detail: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  api_version: "v1";
  environment: "dev" | "prod";
  model_mode: "mock" | "template" | "onnx";
  components: {
    sign_model: ComponentHealth;
    stt: ComponentHealth;
    tts: ComponentHealth;
  };
}

const COMPONENT_STATUSES: readonly string[] = ["ready", "loading", "unavailable", "disabled", "mock"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isComponentHealth(value: unknown): value is ComponentHealth {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    COMPONENT_STATUSES.includes(value.status) &&
    (value.detail === null || typeof value.detail === "string")
  );
}

/** Runtime check of untrusted JSON from the backend. */
export function isHealthResponse(value: unknown): value is HealthResponse {
  if (!isRecord(value) || !isRecord(value.components)) return false;
  const { components } = value;
  return (
    (value.status === "ok" || value.status === "degraded") &&
    typeof value.version === "string" &&
    value.api_version === "v1" &&
    (value.environment === "dev" || value.environment === "prod") &&
    (value.model_mode === "mock" || value.model_mode === "template" || value.model_mode === "onnx") &&
    isComponentHealth(components.sign_model) &&
    isComponentHealth(components.stt) &&
    isComponentHealth(components.tts)
  );
}
