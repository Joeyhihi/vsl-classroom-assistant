// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { isHealthResponse } from "./types";

// Shared with the backend tests: one example, validated by Pydantic and by this guard.
const EXAMPLE_PATH = fileURLToPath(
  new URL(
    "../../../../services/ai-backend/tests/contract_examples/health.mock.json",
    import.meta.url,
  ),
);

function loadExample(): Record<string, unknown> {
  return JSON.parse(readFileSync(EXAMPLE_PATH, "utf-8")) as Record<string, unknown>;
}

describe("isHealthResponse", () => {
  it("accepts the shared backend contract example", () => {
    expect(isHealthResponse(loadExample())).toBe(true);
  });

  it.each([
    ["unknown status", { status: "fine" }],
    ["wrong api version", { api_version: "v2" }],
    ["unknown model mode", { model_mode: "cloud" }],
    ["missing components", { components: undefined }],
  ])("rejects %s", (_label, patch) => {
    expect(isHealthResponse({ ...loadExample(), ...patch })).toBe(false);
  });

  it("rejects an unknown component status", () => {
    const example = loadExample();
    const components = example.components as Record<string, unknown>;
    const bad = { ...example, components: { ...components, stt: { status: "on", detail: null } } };
    expect(isHealthResponse(bad)).toBe(false);
  });
});
