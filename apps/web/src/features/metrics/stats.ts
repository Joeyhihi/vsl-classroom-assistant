// Rolling performance metrics for the P3 benchmark (docs/AI_ML_STRATEGY.md §5).

export function percentile(values: readonly number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index] ?? null;
}

/** Frames per second over a sliding time window of processed-frame timestamps. */
export class FpsMeter {
  private readonly times: number[] = [];

  constructor(private readonly windowMs = 5000) {}

  tick(nowMs: number) {
    this.times.push(nowMs);
    while (this.times.length > 0 && nowMs - (this.times[0] as number) > this.windowMs) this.times.shift();
  }

  /** Mean fps over the window; null until at least two frames were seen. */
  fps(nowMs: number): number | null {
    const recent = this.times.filter((t) => nowMs - t <= this.windowMs);
    if (recent.length < 2) return null;
    const span = (recent[recent.length - 1] as number) - (recent[0] as number);
    return span > 0 ? ((recent.length - 1) * 1000) / span : null;
  }

  reset() {
    this.times.length = 0;
  }
}

/** Bounded sample list with p50/p95 (e.g. "hands at rest → prediction rendered"). */
export class SampleStats {
  private readonly samples: number[] = [];

  constructor(private readonly capacity = 200) {}

  add(value: number) {
    this.samples.push(value);
    if (this.samples.length > this.capacity) this.samples.shift();
  }

  summary() {
    return {
      count: this.samples.length,
      p50: percentile(this.samples, 50),
      p95: percentile(this.samples, 95),
    };
  }

  reset() {
    this.samples.length = 0;
  }
}
