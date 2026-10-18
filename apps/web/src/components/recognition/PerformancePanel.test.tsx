import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi as vitest } from "vitest";

import { initialRecognitionState } from "../../features/recognition/recognitionMachine";
import type { RecognitionController } from "../../features/recognition/useRecognitionSession";
import { vi } from "../../i18n/vi";
import { PerformancePanel } from "./PerformancePanel";

const summary = (p50: number, p95: number, count = 4) => ({ count, p50, p95 });

function controller(extra: Partial<RecognitionController> = {}): RecognitionController {
  return {
    state: { ...initialRecognitionState, phase: "running" },
    metrics: {
      fps: 17,
      latency: { total: summary(900, 1700), wait: summary(600, 1500), processing: summary(300, 420) },
      closeReasons: { rest: 2, still: 1, max_duration: 1 },
      inferenceMs: 1.4,
      sourceDetail: "L1 worker/GPU",
    },
    ladder: { kind: "measuring" },
    lastFrame: { current: null },
    start: vitest.fn(),
    stop: vitest.fn(),
    resolveCandidate: vitest.fn(),
    ...extra,
  };
}

describe("PerformancePanel", () => {
  it("shows the latency breakdown and how signs ended", () => {
    render(<PerformancePanel controller={controller()} level="L1" onLevelChange={vitest.fn()} />);
    expect(screen.getByTestId("latency-processing")).toHaveTextContent("300 ms / 420 ms (n=4)");
    expect(screen.getByTestId("latency-wait")).toHaveTextContent("600 ms / 1500 ms");
    expect(screen.getByTestId("close-reasons")).toHaveTextContent("hạ tay 2 · giữ yên 1 · quá dài 1");
    expect(screen.getByText("L1 worker/GPU")).toBeInTheDocument();
  });

  it("explains an automatic level change right where the level is chosen", () => {
    const c = controller({ ladder: { kind: "too_slow", fps: 12.3, next: { action: "auto_switch", level: "L2" } } });
    render(<PerformancePanel controller={c} level="L2" onLevelChange={vitest.fn()} />);
    expect(screen.getByTestId("settings-ladder-notice")).toHaveTextContent(vi.ladder.autoSwitch(12.3));
  });
});
