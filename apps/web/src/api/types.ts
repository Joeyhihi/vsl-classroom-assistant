// Runtime guard for the health response. Types come from the generated contracts
// (scripts/gen_contracts.py); src/api/types.test.ts validates the shared example
// services/ai-backend/tests/contract_examples/health.mock.json.

import type { ComponentHealth, HealthResponse } from "./generated/contracts";

export type { ComponentHealth, HealthResponse };

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
