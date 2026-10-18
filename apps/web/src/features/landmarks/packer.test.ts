import { describe, expect, it } from "vitest";

import type { FeatureSpecWire } from "../../api/generated/contracts";
import { packHandPose, packHolistic, type LandmarkLike } from "./packer";

const SPEC: FeatureSpecWire = {
  version: "fs-1",
  face_indices: [1, 4, 7],
  shapes: { pose: [33, 4], hand: [21, 3], face: [3, 3] },
};

const lms = (n: number, x = 0.5): LandmarkLike[] =>
  Array.from({ length: n }, (_, i) => ({ x, y: 0.4 + i * 1e-3, z: -0.01, visibility: 0.9 }));

describe("packHolistic", () => {
  it("uses shapes and face indices from the server spec", () => {
    const face = lms(478).map((p, i) => ({ ...p, x: i / 1000 }));
    const frame = packHolistic(
      { poseLandmarks: [lms(33)], leftHandLandmarks: [], rightHandLandmarks: [lms(21)], faceLandmarks: [face] },
      SPEC,
      123.456,
    );
    expect(frame.t_ms).toBe(123.5);
    expect(frame.pose).toHaveLength(33);
    expect(frame.pose?.[0]).toEqual([0.5, 0.4, -0.01, 0.9]);
    expect(frame.left_hand).toBeNull();
    expect(frame.right_hand?.[0]).toHaveLength(3);
    expect(frame.face?.map((p) => p[0])).toEqual([0.001, 0.004, 0.007]);
  });

  it("clamps to the ranges the server validates and rounds to 4 decimals", () => {
    const frame = packHolistic(
      {
        poseLandmarks: [lms(33, -2)],
        leftHandLandmarks: [lms(21, 1.234567)],
        rightHandLandmarks: [],
        faceLandmarks: [],
      },
      SPEC,
      0,
    );
    expect(frame.pose?.[0]?.[0]).toBe(-0.5);
    expect(frame.left_hand?.[0]?.[0]).toBe(1.2346);
    expect(frame.face).toBeNull();
  });

  it("drops incomplete parts instead of sending wrong shapes", () => {
    const frame = packHolistic(
      { poseLandmarks: [lms(20)], leftHandLandmarks: [lms(10)], rightHandLandmarks: [], faceLandmarks: [lms(5)] },
      SPEC,
      0,
    );
    expect([frame.pose, frame.left_hand, frame.face]).toEqual([null, null, null]);
  });
});

describe("packHandPose (L2)", () => {
  it("swaps mirrored handedness labels and has no face", () => {
    const left = lms(21, 0.7);
    const right = lms(21, 0.3);
    const frame = packHandPose(
      {
        hands: {
          landmarks: [left, right],
          handedness: [[{ categoryName: "Right" }], [{ categoryName: "Left" }]],
        },
        pose: { landmarks: [lms(33)] },
      },
      SPEC,
      10,
    );
    expect(frame.left_hand?.[0]?.[0]).toBe(0.7);
    expect(frame.right_hand?.[0]?.[0]).toBe(0.3);
    expect(frame.face).toBeNull();
  });
});
