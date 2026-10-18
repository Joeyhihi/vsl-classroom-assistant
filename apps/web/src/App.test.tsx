import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi as vitest } from "vitest";

import { App } from "./App";
import type { HealthResponse } from "./api/types";
import { vi } from "./i18n/vi";

function health(overrides: Partial<HealthResponse> = {}): HealthResponse {
  return {
    status: "ok",
    version: "0.1.0",
    api_version: "v1",
    environment: "dev",
    model_mode: "mock",
    components: {
      sign_model: { status: "mock", detail: "scripted predictions (cycle)" },
      stt: { status: "disabled", detail: null },
      tts: { status: "disabled", detail: "browser speechSynthesis is used" },
    },
    ...overrides,
  };
}

function mockFetchJson(body: unknown, status = 200) {
  vitest
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(body), { status }));
}

describe("App", () => {
  it("shows connected status and the MOCK badge in mock mode", async () => {
    mockFetchJson(health());
    render(<App />);

    expect(await screen.findByText(vi.backend.online)).toBeInTheDocument();
    expect(screen.getByText(vi.mockBadge)).toBeInTheDocument();
    expect(screen.getByText(vi.componentStatus.mock)).toBeInTheDocument();
  });

  it("shows degraded status without the MOCK badge for a real model mode", async () => {
    mockFetchJson(
      health({
        status: "degraded",
        model_mode: "template",
        components: {
          ...health().components,
          sign_model: { status: "unavailable", detail: "not implemented until Phase 3" },
        },
      }),
    );
    render(<App />);

    expect(await screen.findByText(vi.backend.degraded)).toBeInTheDocument();
    expect(screen.queryByText(vi.mockBadge)).not.toBeInTheDocument();
  });

  it("shows the disconnected state when the backend is unreachable", async () => {
    vitest.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);

    expect(await screen.findByText(vi.backend.offline)).toBeInTheDocument();
    expect(screen.getByText(vi.backend.offlineHelp)).toBeInTheDocument();
  });

  it("flags an incompatible backend response", async () => {
    mockFetchJson({ status: "ok", api_version: "v9" });
    render(<App />);

    expect(await screen.findByText(vi.backend.incompatible)).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    mockFetchJson(health());
    const { container } = render(<App />);
    await screen.findByText(vi.backend.online);

    // jsdom cannot render, so colour contrast is checked in Playwright (Phase 2).
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
