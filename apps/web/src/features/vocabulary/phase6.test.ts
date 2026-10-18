import { describe, expect, it } from "vitest";

import type { SessionStarted } from "../../api/generated/contracts";
import { initialRecognitionState, recognitionReducer } from "../recognition/recognitionMachine";
import { createSignEntry, transcriptReducer } from "../transcript/transcriptStore";
import { DEFAULT_ICON, iconFor } from "./icons";

describe("icons", () => {
  it("maps known names and falls back to a hand", () => {
    expect(iconFor("wave")).toBe("👋");
    expect(iconFor("no-such-icon")).toBe(DEFAULT_ICON);
    expect(iconFor(undefined)).toBe(DEFAULT_ICON);
  });
});

describe("sign entries carry their prediction for feedback", () => {
  const origin = { session_id: "s1", prediction_id: "p1", model_id: "vsl-01" };

  it("keeps origin and icon, and records one verdict", () => {
    const entry = createSignEntry({ gloss_id: "DEV_01", text_vi: "Một", score: 0.9, icon: "wave" }, new Date(), origin);
    expect(entry.origin).toEqual(origin);
    expect(entry.icon).toBe("wave");

    const state = transcriptReducer([entry], { type: "mark_feedback", id: entry.id, verdict: "incorrect" });
    expect(state[0]?.feedback).toBe("incorrect");
  });

  it("has no origin when there was no session", () => {
    const entry = createSignEntry({ gloss_id: "DEV_01", text_vi: "Một", score: 0.9 });
    expect(entry.origin).toBeUndefined();
  });

  it("the recognition state remembers the session id", () => {
    const started = { type: "session.started", session_id: "abc", model: null, extraction_mode: "client" };
    const state = recognitionReducer(initialRecognitionState, {
      type: "session_started",
      message: started as unknown as SessionStarted,
    });
    expect(state.sessionId).toBe("abc");
    expect(recognitionReducer(state, { type: "stopped" }).sessionId).toBeNull();
  });
});
