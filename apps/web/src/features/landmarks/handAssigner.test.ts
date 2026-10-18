import { describe, expect, it } from "vitest";

import { HandAssigner } from "./handAssigner";
import type { LandmarkLike } from "./packer";

const hand = (x: number, y = 0.5): LandmarkLike[] => Array.from({ length: 21 }, () => ({ x, y, z: 0 }));

function pose(leftX = 0.7, rightX = 0.3, visibility = 0.9): LandmarkLike[] {
  const p = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0, visibility }));
  p[15] = { x: leftX, y: 0.5, z: 0, visibility }; // signer's left wrist: image right (unmirrored)
  p[16] = { x: rightX, y: 0.5, z: 0, visibility };
  return p;
}

describe("HandAssigner", () => {
  it.each([
    ["Left", "Right"],
    ["Right", "Left"],
    [undefined, undefined],
  ])("two hands follow the pose wrists whatever the labels (%s/%s)", (la, lb) => {
    const { left, right } = new HandAssigner().assign(
      [
        { landmarks: hand(0.31), label: la },
        { landmarks: hand(0.69), label: lb },
      ],
      pose(),
    );
    expect(left?.[0]?.x).toBe(0.69);
    expect(right?.[0]?.x).toBe(0.31);
  });

  it("a fast right hand with a flickering label stays the right hand (Windows bug)", () => {
    const assigner = new HandAssigner();
    const sides = ["Right", "Right", "Left", "Right", "Left"].map((label, i) => {
      const x = 0.3 + i * 0.02;
      return assigner.assign([{ landmarks: hand(x), label }], pose(0.7, x)).right ? "right" : "left";
    });
    expect(sides).toEqual(["right", "right", "right", "right", "right"]);
  });

  it("bridges frames where the pose wrists are not visible using last positions", () => {
    const assigner = new HandAssigner();
    assigner.assign([{ landmarks: hand(0.3) }], pose());
    const { left, right } = assigner.assign([{ landmarks: hand(0.33), label: "Left" }], pose(0.7, 0.3, 0));
    expect(right).toBeDefined();
    expect(left).toBeUndefined();
  });

  it("falls back to the label, which names the signer's own hand", () => {
    const { left, right } = new HandAssigner().assign([{ landmarks: hand(0.5), label: "Left" }], undefined);
    expect(left).toBeDefined();
    expect(right).toBeUndefined();
  });

  it("without labels or geometry, uses image side (signer's left is on the image's right)", () => {
    const { left } = new HandAssigner().assign([{ landmarks: hand(0.8) }], undefined);
    expect(left).toBeDefined();
  });
});
