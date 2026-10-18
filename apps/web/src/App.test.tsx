import { act, fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi as vitest } from "vitest";

import { App } from "./App";
import type { HealthResponse } from "./api/types";
import { vi } from "./i18n/vi";
import { LOCAL_EN, LOCAL_VI, NETWORK_VI, installFakeSpeech, type FakeSpeech } from "./test/fakeSpeech";

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
  vitest.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.resolve(new Response(JSON.stringify(body), { status })),
  );
}

function mockFetchOffline() {
  vitest.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
}

const goTo = (label: string) => fireEvent.click(screen.getByRole("button", { name: label }));

function typeMessage(text: string) {
  fireEvent.change(screen.getByLabelText(vi.compose.label), { target: { value: text } });
}

async function expectNoAxeViolations(container: HTMLElement) {
  // jsdom cannot render, so colour contrast is checked in Playwright instead.
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations).toEqual([]);
}

let speech: FakeSpeech;

beforeEach(() => {
  speech = installFakeSpeech([LOCAL_EN, LOCAL_VI]);
});

afterEach(() => {
  speech.uninstall();
  Reflect.deleteProperty(navigator, "mediaDevices");
  localStorage.clear();
});

describe("App shell", () => {
  it("shows the MOCK badge and backend status in settings", async () => {
    mockFetchJson(health());
    render(<App />);

    expect(await screen.findByText(vi.mockBadge)).toBeInTheDocument();
    goTo(vi.nav.settings);
    expect(await screen.findByText(vi.backend.online)).toBeInTheDocument();
    expect(screen.getByText(vi.componentStatus.mock)).toBeInTheDocument();
  });

  it("shows the connection banner when the backend is unreachable", async () => {
    mockFetchOffline();
    render(<App />);

    expect(await screen.findByTestId("connection-banner")).toHaveTextContent(vi.connectionBanner.offline);
    expect(screen.queryByText(vi.mockBadge)).not.toBeInTheDocument();
  });

  it("flags an incompatible backend", async () => {
    mockFetchJson({ status: "ok", api_version: "v9" });
    render(<App />);

    expect(await screen.findByTestId("connection-banner")).toHaveTextContent(
      vi.connectionBanner.incompatible,
    );
  });
});

describe("manual text → transcript → speech", () => {
  it("works while the backend is offline (FR-9)", async () => {
    mockFetchOffline();
    render(<App />);
    await screen.findByTestId("connection-banner");

    typeMessage("Xin nhắc lại");
    fireEvent.click(screen.getByRole("button", { name: vi.compose.send }));

    const log = screen.getByRole("log");
    expect(within(log).getByText("Xin nhắc lại")).toBeInTheDocument();
    expect(within(log).getByText(vi.speakers.student)).toBeInTheDocument();
    expect(speech.spoken).toHaveLength(0);
  });

  it("sends on Enter but not on Shift+Enter, and ignores blank messages", async () => {
    mockFetchJson(health());
    render(<App />);
    const input = screen.getByLabelText(vi.compose.label);

    typeMessage("   ");
    expect(screen.getByRole("button", { name: vi.compose.send })).toBeDisabled();

    typeMessage("Dòng một");
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(within(screen.getByRole("log")).queryByText("Dòng một")).not.toBeInTheDocument();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(within(screen.getByRole("log")).getByText("Dòng một")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("speaks with the local Vietnamese voice and shows a visual indicator", async () => {
    mockFetchJson(health());
    render(<App />);

    fireEvent.click(screen.getByRole("radio", { name: vi.speakers.teacher }));
    typeMessage("Cả lớp mở sách trang 12");
    fireEvent.click(await screen.findByRole("button", { name: vi.compose.sendAndSpeak }));

    expect(speech.spoken).toHaveLength(1);
    expect(speech.spoken[0]?.voice).toBe(LOCAL_VI);
    expect(speech.spoken[0]?.text).toBe("Cả lớp mở sách trang 12");
    expect(screen.getByTestId("speaking-indicator")).toHaveTextContent(vi.tts.speaking);

    act(() => speech.finish());
    expect(screen.queryByTestId("speaking-indicator")).not.toBeInTheDocument();
    expect(within(screen.getByRole("log")).getByText(vi.transcript.spoken)).toBeInTheDocument();
  });

  it("refuses network-only voices by default and explains how to install one", async () => {
    speech.uninstall();
    speech = installFakeSpeech([LOCAL_EN, NETWORK_VI]);
    mockFetchJson(health());
    render(<App />);

    expect(await screen.findByText(vi.tts.noVoice)).toBeInTheDocument();
    typeMessage("Cảm ơn");
    expect(screen.getByRole("button", { name: vi.compose.sendAndSpeak })).toBeDisabled();
  });

  it("deletes local data from settings", async () => {
    mockFetchJson(health());
    render(<App />);
    typeMessage("Bí mật");
    fireEvent.click(screen.getByRole("button", { name: vi.compose.send }));

    goTo(vi.nav.settings);
    fireEvent.click(screen.getByRole("button", { name: vi.settings.deleteData }));
    fireEvent.click(screen.getByRole("button", { name: vi.settings.deleteConfirm }));
    expect(screen.getByText(vi.settings.deleted)).toBeInTheDocument();

    goTo(vi.nav.communicate);
    expect(within(screen.getByRole("log")).getByText(vi.transcript.empty)).toBeInTheDocument();
  });
});

describe("camera permission flows", () => {
  it.each([
    ["NotAllowedError", "denied"],
    ["NotFoundError", "unavailable"],
    ["NotReadableError", "in_use"],
  ] as const)("shows guidance for %s", async (name, failure) => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: () => Promise.reject(new DOMException("x", name)) },
      configurable: true,
    });
    mockFetchJson(health());
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: vi.camera.start }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(vi.camera.failure[failure]);
    expect(alert).toHaveTextContent(vi.camera.help[failure]);
    expect(within(alert).getByRole("button", { name: vi.camera.retry })).toBeInTheDocument();
    // Manual text remains usable while the camera is unavailable.
    expect(screen.getByLabelText(vi.compose.label)).toBeEnabled();
  });
});

describe("accessibility (axe, structure only)", () => {
  it.each([vi.nav.communicate, vi.nav.settings, vi.nav.privacy])("%s view", async (label) => {
    mockFetchJson(health());
    const { container } = render(<App />);
    await screen.findByText(vi.mockBadge);
    goTo(label);

    await expectNoAxeViolations(container);
  });
});
