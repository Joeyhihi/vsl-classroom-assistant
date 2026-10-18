import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi as vitest } from "vitest";

import type { PredictionMessage } from "../../api/generated/contracts";
import { initialRecognitionState, type RecognitionState } from "../../features/recognition/recognitionMachine";
import type { RecognitionController } from "../../features/recognition/useRecognitionSession";
import { vi } from "../../i18n/vi";
import { RecognitionPanel } from "./RecognitionPanel";

function prediction(status: PredictionMessage["status"]): PredictionMessage {
  return {
    type: "prediction",
    prediction_id: "p_1",
    model_id: "dev",
    status,
    utterance: { start_ms: 0, end_ms: 1000, n_frames: 15 },
    top: [
      { gloss_id: "A", text_vi: "Xin chào", icon: "wave", score: 0.62 },
      { gloss_id: "B", text_vi: "Cảm ơn", icon: "thanks", score: 0.25 },
      { gloss_id: "C", text_vi: "Xin nhắc lại", icon: "repeat", score: 0.08 },
    ],
    timings: { hysteresis_ms: 600, inference_ms: 2 },
  };
}

function controller(state: Partial<RecognitionState>, extra: Partial<RecognitionController> = {}): RecognitionController {
  return {
    state: { ...initialRecognitionState, ...state },
    metrics: {
      fps: null,
      latency: {
        total: { count: 0, p50: null, p95: null },
        wait: { count: 0, p50: null, p95: null },
        processing: { count: 0, p50: null, p95: null },
      },
      inferenceMs: null,
      sourceDetail: "-",
    },
    ladder: { kind: "measuring" },
    lastFrame: { current: null },
    start: vitest.fn(),
    stop: vitest.fn(),
    resolveCandidate: vitest.fn(),
    ...extra,
  };
}

const devModel = {
  model_id: "dev",
  kind: "template-dtw" as const,
  vocabulary_version: "dev-local",
  feature_spec_version: "fs-1",
  developer_only: true,
};

function renderPanel(c: RecognitionController, sourceKind: "camera" | "replay" = "camera") {
  const onConfirm = vitest.fn();
  const onAcceptL3 = vitest.fn();
  const view = render(<RecognitionPanel controller={c} sourceKind={sourceKind} onConfirm={onConfirm} onAcceptL3={onAcceptL3} />);
  return { ...view, onConfirm, onAcceptL3 };
}

describe("RecognitionPanel", () => {
  it("starts without passing the click event as a level", () => {
    const c = controller({});
    renderPanel(c);
    fireEvent.click(screen.getByRole("button", { name: vi.recognition.start }));
    expect(c.start).toHaveBeenCalledWith();
  });

  it("confident: large text, confirm sends the top label", () => {
    const c = controller({ phase: "running", model: devModel, candidate: prediction("confident") });
    const { onConfirm } = renderPanel(c);
    expect(screen.getByText("Xin chào")).toBeInTheDocument();
    expect(screen.getByText(vi.recognition.devModelBadge)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: vi.candidate.confirm }));
    expect(onConfirm.mock.calls[0]?.[0]).toMatchObject({ gloss_id: "A" });
  });

  it("uncertain: offers three alternatives and dismiss", () => {
    const c = controller({ phase: "running", candidate: prediction("uncertain") });
    const { onConfirm } = renderPanel(c);
    expect(screen.getByText(vi.candidate.uncertainPrompt)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: vi.candidate.choose("Cảm ơn") }));
    expect(onConfirm.mock.calls[0]?.[0]).toMatchObject({ gloss_id: "B" });
    fireEvent.click(screen.getByRole("button", { name: vi.candidate.dismiss }));
    expect(c.resolveCandidate).toHaveBeenCalled();
  });

  it("rejected: shows the sign-again notice, no text", () => {
    renderPanel(controller({ phase: "running", lastRejected: prediction("rejected") }));
    expect(screen.getByTestId("prediction-rejected")).toHaveTextContent(vi.candidate.rejected);
    expect(screen.queryByText("Xin chào")).not.toBeInTheDocument();
  });

  it("mock model: warns that speech is disabled", () => {
    renderPanel(controller({ phase: "running", model: { ...devModel, kind: "mock" }, candidate: prediction("confident") }));
    expect(screen.getByText(vi.candidate.mockNoSpeech)).toBeInTheDocument();
  });

  it.each([
    ["MODEL_UNAVAILABLE", "Nhận dạng ký hiệu không khả dụng."],
    ["EXTRACTOR_FAILED", vi.recognition.failure.EXTRACTOR_FAILED],
    ["CLOSE_4001", vi.recognition.failureGeneric],
  ])("failure %s is explained", (reason, text) => {
    renderPanel(controller({ phase: "failed", failure: reason }));
    expect(screen.getByTestId("recognition-status")).toHaveTextContent(text as string);
  });

  it("missing MediaPipe assets: says what to run and which files are missing", () => {
    renderPanel(
      controller({
        phase: "failed",
        failure: "MEDIAPIPE_ASSETS_MISSING",
        failureDetail: "holistic_landmarker.task",
      }),
    );
    expect(screen.getByTestId("recognition-status")).toHaveTextContent("bootstrap.py --with-models --pin");
    expect(screen.getByTestId("failure-detail")).toHaveTextContent("holistic_landmarker.task");
  });

  it("ladder offer calls onAcceptL3; replay badge is shown", () => {
    const c = controller(
      { phase: "running" },
      { ladder: { kind: "too_slow", fps: 9, next: { action: "offer", level: "L3" } } },
    );
    const { onAcceptL3 } = renderPanel(c, "replay");
    expect(screen.getByText(vi.recognition.replayBadge)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: vi.ladder.acceptL3 }));
    expect(onAcceptL3).toHaveBeenCalled();
  });

  it("paused shows resume", () => {
    renderPanel(controller({ phase: "paused" }));
    expect(screen.getByRole("button", { name: vi.recognition.resume })).toBeInTheDocument();
  });

  it("has no axe violations with an uncertain candidate", async () => {
    const { container } = renderPanel(controller({ phase: "running", candidate: prediction("uncertain") }));
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
