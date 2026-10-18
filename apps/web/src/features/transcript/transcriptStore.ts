import { useCallback, useReducer } from "react";

// Mirrors the TranscriptEntry contract in docs/API_CONTRACTS.md.
// In memory only; exported solely by explicit user action.
export type FeedbackVerdict = "correct" | "incorrect" | "unsure";

/** Where a sign entry came from, so the user can give feedback on it (FR-13). */
export interface PredictionOrigin {
  session_id: string;
  prediction_id: string;
  model_id: string;
}

export interface TranscriptEntry {
  id: string;
  created_at: string;
  source: "sign" | "manual" | "speech";
  speaker: "student" | "teacher";
  text: string;
  gloss_id?: string;
  icon?: string;
  confidence?: number;
  origin?: PredictionOrigin;
  feedback?: FeedbackVerdict;
  confirmed: boolean;
  spoken: boolean;
}

export const MAX_MESSAGE_LENGTH = 500;

/** NFC-normalise, collapse whitespace runs, trim, and cap the length. */
export function normalizeMessage(text: string): string {
  return text.normalize("NFC").replace(/[ \t]+/g, " ").trim().slice(0, MAX_MESSAGE_LENGTH);
}

export function createManualEntry(
  text: string,
  speaker: TranscriptEntry["speaker"],
  now: Date = new Date(),
): TranscriptEntry {
  return {
    id: crypto.randomUUID(),
    created_at: now.toISOString(),
    source: "manual",
    speaker,
    text: normalizeMessage(text),
    confirmed: true,
    spoken: false,
  };
}

/** A confirmed sign prediction (never added without the user's confirmation). */
export function createSignEntry(
  label: { gloss_id: string; text_vi: string; score: number; icon?: string },
  now: Date = new Date(),
  origin?: PredictionOrigin,
): TranscriptEntry {
  return {
    ...(origin ? { origin } : {}),
    ...(label.icon ? { icon: label.icon } : {}),
    id: crypto.randomUUID(),
    created_at: now.toISOString(),
    source: "sign",
    speaker: "student",
    text: normalizeMessage(label.text_vi),
    gloss_id: label.gloss_id,
    confidence: label.score,
    confirmed: true,
    spoken: false,
  };
}

type Action =
  | { type: "add"; entry: TranscriptEntry }
  | { type: "mark_spoken"; id: string }
  | { type: "mark_feedback"; id: string; verdict: FeedbackVerdict }
  | { type: "clear" };

export function transcriptReducer(state: TranscriptEntry[], action: Action): TranscriptEntry[] {
  switch (action.type) {
    case "add":
      return action.entry.text ? [...state, action.entry] : state;
    case "mark_spoken":
      return state.map((e) => (e.id === action.id ? { ...e, spoken: true } : e));
    case "mark_feedback":
      return state.map((e) => (e.id === action.id ? { ...e, feedback: action.verdict } : e));
    case "clear":
      return [];
  }
}

export function useTranscript() {
  const [entries, dispatch] = useReducer(transcriptReducer, []);
  return {
    entries,
    add: useCallback((entry: TranscriptEntry) => dispatch({ type: "add", entry }), []),
    markSpoken: useCallback((id: string) => dispatch({ type: "mark_spoken", id }), []),
    markFeedback: useCallback(
      (id: string, verdict: FeedbackVerdict) => dispatch({ type: "mark_feedback", id, verdict }),
      [],
    ),
    clear: useCallback(() => dispatch({ type: "clear" }), []),
  };
}

export function transcriptToText(
  entries: readonly TranscriptEntry[],
  speakerLabels: Record<TranscriptEntry["speaker"], string>,
): string {
  return entries
    .map((e) => `[${e.created_at}] ${speakerLabels[e.speaker]}: ${e.text}`)
    .join("\n");
}
