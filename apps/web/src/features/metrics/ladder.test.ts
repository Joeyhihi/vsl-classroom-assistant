import { describe, expect, it } from "vitest";

import { LadderMonitor, isExtractionLevel, nextStep } from "./ladder";

const CONFIG = { minFps: 15, warmupMs: 3000, windowMs: 5000 };

describe("ladder", () => {
  it("L1 switches automatically, L2 only offers L3, L3 is the end", () => {
    expect(nextStep("L1")).toEqual({ action: "auto_switch", level: "L2" });
    expect(nextStep("L2")).toEqual({ action: "offer", level: "L3" });
    expect(nextStep("L3")).toEqual({ action: "unsupported" });
  });

  it("ignores the warm-up period", () => {
    const monitor = new LadderMonitor("L1", 0, CONFIG);
    expect(monitor.observe(2000, 5)).toEqual({ kind: "measuring" });
  });

  it("needs fps below the threshold for the whole window", () => {
    const monitor = new LadderMonitor("L1", 0, CONFIG);
    expect(monitor.observe(3000, 10).kind).toBe("measuring");
    expect(monitor.observe(7000, 10).kind).toBe("measuring");
    expect(monitor.observe(8000, 10)).toEqual({
      kind: "too_slow",
      fps: 10,
      next: { action: "auto_switch", level: "L2" },
    });
  });

  it("a good reading resets the slow window", () => {
    const monitor = new LadderMonitor("L2", 0, CONFIG);
    monitor.observe(3000, 10);
    expect(monitor.observe(6000, 20)).toEqual({ kind: "ok" });
    expect(monitor.observe(8000, 10).kind).toBe("measuring");
  });

  it("validates stored levels", () => {
    expect(["L1", "L2", "L3"].every(isExtractionLevel)).toBe(true);
    expect(isExtractionLevel("L4")).toBe(false);
  });
});
