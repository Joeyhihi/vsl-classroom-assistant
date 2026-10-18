// Recognition UI state machine (docs/ARCHITECTURE.md §6). Pure reducer.
//
// Candidate policy: at most one pending candidate; a new prediction replaces it
// and the previous one moves to a short "skipped" list. Candidates never time
// out (WCAG 2.2.1); nothing is spoken without an explicit confirm.

import type {
  ModelInfo,
  PredictionMessage,
  ScoredLabelWire,
  SessionStarted,
  StatusMessage,
} from "../../api/generated/contracts";

export type Phase = "idle" | "connecting" | "running" | "paused" | "reconnecting" | "failed";

export interface RecognitionState {
  phase: Phase;
  serverState: StatusMessage["state"] | null;
  handsVisible: boolean;
  model: ModelInfo | null;
  extractionMode: SessionStarted["extraction_mode"] | null;
  candidate: PredictionMessage | null;
  skipped: PredictionMessage[];
  lastRejected: PredictionMessage | null;
  droppedFrames: number;
  failure: string | null; // error code or close code, for the UI message
  failureDetail: string | null; // e.g. the missing asset files
  reconnectAttempt: number;
}

export const MAX_SKIPPED = 3;

export const initialRecognitionState: RecognitionState = {
  phase: "idle",
  serverState: null,
  handsVisible: false,
  model: null,
  extractionMode: null,
  candidate: null,
  skipped: [],
  lastRejected: null,
  droppedFrames: 0,
  failure: null,
  failureDetail: null,
  reconnectAttempt: 0,
};

export type RecognitionAction =
  | { type: "start" }
  | { type: "session_started"; message: SessionStarted }
  | { type: "status"; message: StatusMessage }
  | { type: "prediction"; message: PredictionMessage }
  | { type: "resolve_candidate" } // confirmed or dismissed
  | { type: "paused" }
  | { type: "reconnecting"; attempt: number }
  | { type: "failed"; reason: string; detail?: string }
  | { type: "stopped" };

export function recognitionReducer(state: RecognitionState, action: RecognitionAction): RecognitionState {
  switch (action.type) {
    case "start":
      return { ...state, phase: "connecting", failure: null, failureDetail: null, serverState: null };
    case "session_started":
      return {
        ...state,
        phase: "running",
        model: action.message.model,
        extractionMode: action.message.extraction_mode,
        reconnectAttempt: 0,
      };
    case "status":
      return {
        ...state,
        serverState: action.message.state,
        handsVisible: action.message.hands_visible,
        droppedFrames: action.message.dropped_frames,
      };
    case "prediction": {
      const message = action.message;
      if (message.status === "rejected") return { ...state, lastRejected: message };
      const skipped = state.candidate ? [state.candidate, ...state.skipped].slice(0, MAX_SKIPPED) : state.skipped;
      return { ...state, candidate: message, skipped, lastRejected: null };
    }
    case "resolve_candidate":
      return { ...state, candidate: null };
    case "paused":
      return { ...state, phase: "paused", serverState: null };
    case "reconnecting":
      return { ...state, phase: "reconnecting", reconnectAttempt: action.attempt, serverState: null };
    case "failed":
      return { ...state, phase: "failed", failure: action.reason, failureDetail: action.detail ?? null, serverState: null };
    case "stopped":
      return { ...initialRecognitionState, skipped: state.skipped };
  }
}

/** Alternatives offered for an uncertain prediction (top 3, highest first). */
export function alternatives(prediction: PredictionMessage): ScoredLabelWire[] {
  return prediction.top.slice(0, 3);
}

/** Mock predictions are scripted: they must never be spoken (ADR-016). */
export function canSpeakPrediction(model: ModelInfo | null): boolean {
  return model !== null && model.kind !== "mock";
}
