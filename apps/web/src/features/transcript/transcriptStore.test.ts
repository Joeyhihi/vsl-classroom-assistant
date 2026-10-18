import { describe, expect, it } from "vitest";

import {
  MAX_MESSAGE_LENGTH,
  createManualEntry,
  normalizeMessage,
  transcriptReducer,
  transcriptToText,
} from "./transcriptStore";

describe("normalizeMessage", () => {
  it("composes Vietnamese to NFC, collapses spaces and trims", () => {
    const decomposed = "Xin chào   bạn ";
    expect(normalizeMessage(decomposed)).toBe("Xin chào bạn");
    expect(normalizeMessage(decomposed)).toBe("Xin chào bạn".normalize("NFC"));
  });

  it("caps the length", () => {
    expect(normalizeMessage("a".repeat(MAX_MESSAGE_LENGTH + 50))).toHaveLength(MAX_MESSAGE_LENGTH);
  });
});

describe("transcriptReducer", () => {
  const entry = createManualEntry("Cảm ơn", "student", new Date("2026-10-18T08:00:00Z"));

  it("creates a confirmed, unspoken manual entry", () => {
    expect(entry).toMatchObject({ source: "manual", speaker: "student", confirmed: true, spoken: false });
    expect(entry.created_at).toBe("2026-10-18T08:00:00.000Z");
  });

  it("adds entries, ignores empty ones, marks spoken and clears", () => {
    let state = transcriptReducer([], { type: "add", entry });
    state = transcriptReducer(state, { type: "add", entry: createManualEntry("   ", "teacher") });
    expect(state).toHaveLength(1);

    state = transcriptReducer(state, { type: "mark_spoken", id: entry.id });
    expect(state[0]?.spoken).toBe(true);

    expect(transcriptReducer(state, { type: "clear" })).toEqual([]);
  });

  it("exports readable text with speaker labels", () => {
    const text = transcriptToText([entry], { student: "Học sinh", teacher: "Giáo viên" });
    expect(text).toBe("[2026-10-18T08:00:00.000Z] Học sinh: Cảm ơn");
  });
});
