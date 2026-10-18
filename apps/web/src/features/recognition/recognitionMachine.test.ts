import { describe, expect, it } from "vitest";

import type { ModelInfo, PredictionMessage, SessionStarted } from "../../api/generated/contracts";
import {
  MAX_SKIPPED,
  canSpeakPrediction,
  initialRecognitionState,
  recognitionReducer,
  type RecognitionAction,
  type RecognitionState,
} from "./recognitionMachine";

const MODEL: ModelInfo = {
  model_id: "mock",
  kind: "mock",
  vocabulary_version: "mock",
  feature_spec_version: "fs-1",
  developer_only: true,
};

function prediction(id: string, status: PredictionMessage["status"]): PredictionMessage {
  return {
    type: "prediction",
    prediction_id: id,
    model_id: "mock",
    status,
    utterance: { start_ms: 0, end_ms: 1000, n_frames: 15 },
    top: [{ gloss_id: "A", text_vi: `Chữ ${id}`, icon: "x", score: 0.9 }],
    timings: { hysteresis_ms: 600, inference_ms: 1 },
  };
}

const started: SessionStarted = {
  type: "session.started",
  session_id: "s",
  extraction_mode: "client",
  model: MODEL,
  feature_spec: { version: "fs-1", face_indices: [], shapes: { pose: [33, 4], hand: [21, 3], face: [0, 3] } },
  limits: { max_fps: 30, max_batch: 8, max_session_s: 7200 },
};

const run = (actions: RecognitionAction[], from: RecognitionState = initialRecognitionState) =>
  actions.reduce(recognitionReducer, from);

describe("recognitionReducer", () => {
  it("goes idle → connecting → running", () => {
    const state = run([{ type: "start" }, { type: "session_started", message: started }]);
    expect(state).toMatchObject({ phase: "running", model: MODEL, extractionMode: "client" });
  });

  it("a new prediction replaces the candidate and keeps a short skipped list", () => {
    const actions: RecognitionAction[] = ["1", "2", "3", "4", "5"].map((id) => ({
      type: "prediction",
      message: prediction(id, "confident"),
    }));
    const state = run(actions);
    expect(state.candidate?.prediction_id).toBe("5");
    expect(state.skipped.map((p) => p.prediction_id)).toEqual(["4", "3", "2"]);
    expect(state.skipped).toHaveLength(MAX_SKIPPED);
  });

  it("rejected predictions never replace a pending candidate", () => {
    const state = run([
      { type: "prediction", message: prediction("1", "uncertain") },
      { type: "prediction", message: prediction("2", "rejected") },
    ]);
    expect(state.candidate?.prediction_id).toBe("1");
    expect(state.lastRejected?.prediction_id).toBe("2");
  });

  it("resolving clears the candidate; stop resets but keeps skipped", () => {
    const state = run([
      { type: "prediction", message: prediction("1", "confident") },
      { type: "prediction", message: prediction("2", "confident") },
      { type: "resolve_candidate" },
    ]);
    expect(state.candidate).toBeNull();
    const stopped = recognitionReducer(state, { type: "stopped" });
    expect(stopped.phase).toBe("idle");
    expect(stopped.skipped).toHaveLength(1);
  });

  it("pause, reconnect and failure states", () => {
    expect(run([{ type: "paused" }]).phase).toBe("paused");
    expect(run([{ type: "reconnecting", attempt: 2 }])).toMatchObject({ phase: "reconnecting", reconnectAttempt: 2 });
    expect(run([{ type: "failed", reason: "MODEL_UNAVAILABLE" }])).toMatchObject({
      phase: "failed",
      failure: "MODEL_UNAVAILABLE",
    });
  });
});

describe("canSpeakPrediction", () => {
  it("never speaks scripted mock output", () => {
    expect(canSpeakPrediction(MODEL)).toBe(false);
    expect(canSpeakPrediction(null)).toBe(false);
    expect(canSpeakPrediction({ ...MODEL, kind: "template-dtw" })).toBe(true);
  });
});
