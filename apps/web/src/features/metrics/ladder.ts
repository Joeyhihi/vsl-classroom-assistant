// Extraction fallback ladder (ADR-002): pure decision logic, unit-tested.
//
//   L1 browser Holistic → L2 browser Hand+Pose (480p, no face) → L3 server extraction
//
// L1 → L2 is automatic, L2 → L3 is only offered (the user must confirm), and
// switching happens at session boundaries, never mid-utterance.

export type ExtractionLevel = "L1" | "L2" | "L3";

export interface LadderConfig {
  minFps: number;
  warmupMs: number;
  windowMs: number;
}

export const DEFAULT_LADDER: LadderConfig = { minFps: 15, warmupMs: 3000, windowMs: 5000 };

export type LadderVerdict =
  | { kind: "measuring" }
  | { kind: "ok" }
  | { kind: "too_slow"; fps: number; next: LadderNext };

export type LadderNext =
  | { action: "auto_switch"; level: "L2" }
  | { action: "offer"; level: "L3" }
  | { action: "unsupported" };

export function nextStep(level: ExtractionLevel): LadderNext {
  if (level === "L1") return { action: "auto_switch", level: "L2" };
  if (level === "L2") return { action: "offer", level: "L3" };
  return { action: "unsupported" };
}

/**
 * Tracks how long fps has stayed below the threshold. Feed it one fps reading
 * per second (or per frame) after the session started.
 */
export class LadderMonitor {
  private slowSince: number | null = null;

  constructor(
    private readonly level: ExtractionLevel,
    private readonly startedAt: number,
    private readonly config: LadderConfig = DEFAULT_LADDER,
  ) {}

  observe(nowMs: number, fps: number | null): LadderVerdict {
    if (nowMs - this.startedAt < this.config.warmupMs || fps === null) return { kind: "measuring" };
    if (fps >= this.config.minFps) {
      this.slowSince = null;
      return { kind: "ok" };
    }
    this.slowSince ??= nowMs;
    if (nowMs - this.slowSince >= this.config.windowMs) {
      return { kind: "too_slow", fps, next: nextStep(this.level) };
    }
    return { kind: "measuring" };
  }
}

const LEVELS: readonly string[] = ["L1", "L2", "L3"];
export const isExtractionLevel = (v: unknown): v is ExtractionLevel =>
  typeof v === "string" && LEVELS.includes(v);
