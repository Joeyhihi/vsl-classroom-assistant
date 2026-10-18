import { describe, expect, it } from "vitest";

import type { FeatureSpecWire } from "../../api/generated/contracts";
import { HandAssigner } from "./handAssigner";
import { packHandPose, packHolistic, type LandmarkLike } from "./packer";

const SPEC: FeatureSpecWire = {
  version: "fs-1",
  face_indices: [1, 4, 7],
  shapes: { pose: [33, 4], hand: [21, 3], face: [3, 3] },
};

const lms = (n: number, x = 0.5): LandmarkLike[] =>
  Array.from({ length: n }, (_, i) => ({ x, y: 0.4 + i * 1e-3, z: -0.01, visibility: 0.9 }));

/** Pose with the signer's left wrist (15) on the image's right, right wrist (16) on the left. */
function poseWithWrists(): LandmarkLike[] {
  const pose = lms(33);
  pose[15] = { x: 0.7, y: 0.5, z: 0, visibility: 0.9 };
  pose[16] = { x: 0.3, y: 0.5, z: 0, visibility: 0.9 };
  return pose;
}

describe("packHolistic", () => {
  it("uses shapes and face indices from the server spec", () => {
    const face = lms(478).map((p, i) => ({ ...p, x: i / 1000 }));
    const frame = packHolistic(
      { poseLandmarks: [poseWithWrists()], leftHandLandmarks: [], rightHandLandmarks: [lms(21, 0.3)], faceLandmarks: [face] },
      SPEC,
      123.456,
      new HandAssigner(),
    );
    expect(frame.t_ms).toBe(123.5);
    expect(frame.pose).toHaveLength(33);
    expect(frame.pose?.[0]).toEqual([0.5, 0.4, -0.01, 0.9]);
    expect(frame.right_hand?.[0]?.[0]).toBe(0.3); // matched to the right pose wrist
    expect(frame.left_hand).toBeNull();
    expect(frame.right_hand?.[0]).toHaveLength(3);
    expect(frame.face?.map((p) => p[0])).toEqual([0.001, 0.004, 0.007]);
  });

  it("re-assigns Holistic's hands to the pose wrists", () => {
    // Holistic reported the hand at the signer's right wrist as "left".
    const frame = packHolistic(
      { poseLandmarks: [poseWithWrists()], leftHandLandmarks: [lms(21, 0.31)], rightHandLandmarks: [], faceLandmarks: [] },
      SPEC,
      0,
      new HandAssigner(),
    );
    expect(frame.left_hand).toBeNull();
    expect(frame.right_hand?.[0]?.[0]).toBe(0.31);
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
      new HandAssigner(),
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
      new HandAssigner(),
    );
    expect([frame.pose, frame.left_hand, frame.face]).toEqual([null, null, null]);
  });
});

describe("packHandPose (L2)", () => {
  it("uses the signer's own labels when no pose is visible, and has no face (verified on Windows)", () => {
    const left = lms(21, 0.7);
    const right = lms(21, 0.3);
    const frame = packHandPose(
      {
        hands: {
          landmarks: [left, right],
          handedness: [[{ categoryName: "Left" }], [{ categoryName: "Right" }]],
        },
        pose: { landmarks: [] },
      },
      SPEC,
      10,
      new HandAssigner(),
    );
    expect(frame.left_hand?.[0]?.[0]).toBe(0.7);
    expect(frame.right_hand?.[0]?.[0]).toBe(0.3);
    expect(frame.face).toBeNull();
  });
});
