import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { Page } from "@playwright/test";

// The same contract example the backend tests validate.
export const MOCK_HEALTH: unknown = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../services/ai-backend/tests/contract_examples/health.mock.json", import.meta.url),
    ),
    "utf-8",
  ),
);

/** Answer /api/v1/health without a running backend (keeps e2e RAM low). */
export async function mockBackend(page: Page, mode: "online" | "offline" = "online") {
  await page.route("**/api/v1/health", (route) =>
    mode === "online"
      ? route.fulfill({ json: MOCK_HEALTH })
      : route.fulfill({ status: 502, body: "Bad Gateway" }),
  );
}

/** Replace getUserMedia with one that fails with the given DOMException name. */
export async function failCameraWith(page: Page, errorName: string) {
  await page.addInitScript((name) => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("test", name));
  }, errorName);
}

/**
 * Deterministic speechSynthesis: one local vi-VN voice and one network voice.
 * Spoken texts are recorded on window.__spoken; utterances end after 300 ms.
 */
export async function stubSpeech(page: Page) {
  await page.addInitScript(() => {
    const voices = [
      { voiceURI: "Linh", name: "Linh", lang: "vi-VN", localService: true, default: false },
      { voiceURI: "Online VI", name: "Online VI", lang: "vi-VN", localService: false, default: false },
    ];
    const spoken: string[] = [];
    (window as unknown as { __spoken: string[] }).__spoken = spoken;
    const target = new EventTarget();
    // Chrome's real utterance rejects voices that are not genuine SpeechSynthesisVoice objects.
    class StubUtterance {
      voice: { name: string } | null = null;
      lang = "";
      rate = 1;
      onstart: ((e: Event) => void) | null = null;
      onend: ((e: Event) => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      constructor(public text: string) {}
    }
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: StubUtterance });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        getVoices: () => voices,
        speak: (u: SpeechSynthesisUtterance) => {
          spoken.push(`${u.voice?.name}|${u.text}`);
          u.onstart?.(new Event("start") as SpeechSynthesisEvent);
          setTimeout(() => u.onend?.(new Event("end") as SpeechSynthesisEvent), 300);
        },
        cancel: () => {},
        addEventListener: target.addEventListener.bind(target),
        removeEventListener: target.removeEventListener.bind(target),
      },
    });
  });
}

export async function spokenTexts(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken);
}
