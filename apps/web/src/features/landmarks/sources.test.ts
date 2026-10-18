import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import { ReplayLandmarkSource, binaryFrame, type ReplayFile } from "./sources";

const frame = (t: number): WireFrame => ({ t_ms: t, pose: null, left_hand: null, right_hand: null, face: null });

const SPEC: FeatureSpecWire = { version: "fs-1", face_indices: [], shapes: { pose: [33, 4], hand: [21, 3], face: [0, 3] } };

const REPLAY: ReplayFile = {
  format: "vsl-replay-v1",
  synthetic: true,
  feature_spec_version: "fs-1",
  fps: 10,
  image_width: 640,
  image_height: 480,
  frames: [frame(0), frame(100), frame(200)],
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("ReplayLandmarkSource", () => {
  it("plays in real time and loops with strictly increasing t_ms", async () => {
    let now = 500; // the session clock is already running when the source starts
    const source = new ReplayLandmarkSource(REPLAY);
    const seen: number[] = [];
    await source.start(
      { onFrame: (f) => seen.push(f.t_ms), onBinary: () => undefined, onProcessed: () => undefined },
      SPEC,
      () => now,
    );
    for (let i = 0; i < 30; i++) {
      now += 100;
      vi.advanceTimersByTime(100);
    }
    source.stop();
    // Timestamps are on the session clock (offset 500), with a 1 s loop gap.
    expect(seen.slice(0, 4)).toEqual([500, 600, 700, 1700]);
    expect(seen.every((t, i) => i === 0 || t > (seen[i - 1] as number))).toBe(true);
  });
});

describe("binaryFrame", () => {
  it("writes the 16-byte little-endian header before the JPEG", () => {
    const jpeg = new Uint8Array([0xff, 0xd8, 0x01]).buffer;
    const view = new DataView(binaryFrame(1234.6, 640, 480, jpeg));
    expect(view.byteLength).toBe(19);
    expect(view.getBigUint64(0, true)).toBe(1235n);
    expect(view.getUint16(8, true)).toBe(640);
    expect(view.getUint16(10, true)).toBe(480);
    expect(view.getUint8(16)).toBe(0xff);
  });
});
