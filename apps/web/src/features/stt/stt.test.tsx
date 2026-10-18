import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi as vitest } from "vitest";

import { SubtitlePanel } from "../../components/speech/SubtitlePanel";
import { vi } from "../../i18n/vi";
import { createSpeechEntry } from "../transcript/transcriptStore";
import type { PushToTalkController, PushToTalkState } from "./usePushToTalk";
import { concatChunks, encodeWav, MAX_RECORDING_S, resampleLinear, STT_SAMPLE_RATE, toUploadWav } from "./wav";

describe("wav", () => {
  it("writes a 16 kHz mono 16-bit PCM header", () => {
    const view = new DataView(encodeWav(new Float32Array([0, 1, -1, 0.5])));
    const tag = (o: number) => String.fromCharCode(...[0, 1, 2, 3].map((i) => view.getUint8(o + i)));
    expect(tag(0)).toBe("RIFF");
    expect(tag(8)).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(STT_SAMPLE_RATE);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getUint32(40, true)).toBe(8);
    expect([view.getInt16(46, true), view.getInt16(48, true)]).toEqual([32767, -32768]);
  });

  it("resamples 48 kHz to 16 kHz", () => {
    const out = resampleLinear(new Float32Array(48_000).fill(0.25), 48_000, 16_000);
    expect(out.length).toBe(16_000);
    expect(out[100]).toBeCloseTo(0.25);
  });

  it("concatenates chunks and caps uploads at 30 s", () => {
    expect(Array.from(concatChunks([new Float32Array([1, 2]), new Float32Array([3])]))).toEqual([1, 2, 3]);
    const long = Array.from({ length: 40 }, () => new Float32Array(STT_SAMPLE_RATE));
    expect(toUploadWav(long, STT_SAMPLE_RATE).size).toBe(44 + MAX_RECORDING_S * STT_SAMPLE_RATE * 2);
  });

  it("speech entries are teacher messages from speech", () => {
    const entry = createSpeechEntry("  Xin chào  các em ");
    expect(entry).toMatchObject({ source: "speech", speaker: "teacher", text: "Xin chào các em", confirmed: true });
  });
});

function controller(state: PushToTalkState, lastText: string | null = null): PushToTalkController {
  return { state, lastText, press: vitest.fn(), release: vitest.fn() };
}

describe("SubtitlePanel", () => {
  const ready = { status: "ready" as const, detail: "model=small" };

  it("press and release on pointer and keyboard", async () => {
    const ptt = controller({ kind: "idle" });
    const { container } = render(<SubtitlePanel health={ready} ptt={ptt} />);
    const button = screen.getByRole("button", { name: /Giữ để nói/ });
    fireEvent.pointerDown(button);
    fireEvent.pointerUp(button);
    fireEvent.keyDown(button, { key: " " });
    fireEvent.keyUp(button, { key: " " });
    expect(ptt.press).toHaveBeenCalledTimes(2);
    expect(ptt.release).toHaveBeenCalledTimes(2);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("shows listening, the last subtitle and errors", () => {
    const { rerender } = render(<SubtitlePanel health={ready} ptt={controller({ kind: "listening" }, "Mở sách")} />);
    expect(screen.getAllByText(vi.stt.listening).length).toBeGreaterThan(0);
    expect(screen.getByTestId("subtitle-text")).toHaveTextContent("Mở sách");

    rerender(<SubtitlePanel health={ready} ptt={controller({ kind: "error", code: "MIC_DENIED" })} />);
    expect(screen.getByText(vi.stt.errors.MIC_DENIED as string)).toBeInTheDocument();
    rerender(<SubtitlePanel health={ready} ptt={controller({ kind: "error", code: "STT_UNAVAILABLE" })} />);
    expect(screen.getByText(/Chuyển giọng nói thành chữ không khả dụng/)).toBeInTheDocument();
  });

  it("is disabled with the reason when STT is unavailable", () => {
    render(
      <SubtitlePanel health={{ status: "unavailable", detail: "faster-whisper is not installed" }} ptt={controller({ kind: "idle" })} />,
    );
    expect(screen.getByRole("button", { name: /Giữ để nói/ })).toBeDisabled();
    expect(screen.getByText(/faster-whisper is not installed/)).toBeInTheDocument();
  });
});
