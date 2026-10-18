import { describe, expect, it } from "vitest";

import { FpsMeter, SampleStats, percentile } from "./stats";

describe("percentile", () => {
  it("uses nearest-rank", () => {
    const values = Array.from({ length: 100 }, (_, i) => i + 1);
    expect(percentile(values, 50)).toBe(50);
    expect(percentile(values, 95)).toBe(95);
    expect(percentile([], 50)).toBeNull();
  });
});

describe("FpsMeter", () => {
  it("measures frames per second inside the window", () => {
    const meter = new FpsMeter(5000);
    for (let i = 0; i <= 20; i++) meter.tick(i * 50); // 20 fps for 1 s
    expect(meter.fps(1000)).toBeCloseTo(20);
  });

  it("forgets frames older than the window", () => {
    const meter = new FpsMeter(1000);
    for (let i = 0; i <= 30; i++) meter.tick(i * 33);
    meter.tick(5000);
    expect(meter.fps(5000)).toBeNull();
  });
});

describe("SampleStats", () => {
  it("keeps a bounded window", () => {
    const stats = new SampleStats(3);
    [10, 20, 30, 1000].forEach((v) => stats.add(v));
    expect(stats.summary()).toEqual({ count: 3, p50: 30, p95: 1000 });
  });
});
