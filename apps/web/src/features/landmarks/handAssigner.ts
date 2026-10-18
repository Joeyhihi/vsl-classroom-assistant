// Decides which detected hand is the signer's left and which is the right.
//
// MediaPipe's per-hand "Left"/"Right" label comes from a classifier that flips
// under motion blur (seen on Windows: a fast right hand briefly became the left).
// Hands are therefore matched to the pose wrists (pose 15 = left, 16 = right,
// anatomical), falling back to last frame's hand positions, and only then to the
// label. Mirrored by vsl_features/handedness.py for L3. Stateful: one per source.

import type { LandmarkLike } from "./packer";

export interface DetectedHand {
  landmarks: LandmarkLike[];
  /** Model label, if any: "Left"/"Right" as reported by MediaPipe. */
  label?: string;
}

export interface AssignedHands {
  left: LandmarkLike[] | undefined;
  right: LandmarkLike[] | undefined;
}

type Point = { x: number; y: number };

const POSE_LEFT_WRIST = 15;
const POSE_RIGHT_WRIST = 16;
const MIN_WRIST_VISIBILITY = 0.3;
/** Previous-frame positions older than this many frames are forgotten. */
const MAX_STALE_FRAMES = 5;

/**
 * Verified on Windows (P3, L2 HandLandmarker): on unmirrored frames the label
 * already names the signer's own hand. Only used when no geometry is available.
 */
export const HANDEDNESS_LABELS_ASSUME_MIRRORED = false;

const dist = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

function labelSide(label: string | undefined): "left" | "right" | null {
  if (label !== "Left" && label !== "Right") return null;
  const isLeft = HANDEDNESS_LABELS_ASSUME_MIRRORED ? label === "Right" : label === "Left";
  return isLeft ? "left" : "right";
}

export class HandAssigner {
  private prev: { left: Point | null; right: Point | null } = { left: null, right: null };
  private staleness = { left: 0, right: 0 };

  assign(hands: readonly DetectedHand[], pose: readonly LandmarkLike[] | undefined): AssignedHands {
    const anchors = this.anchors(pose);
    const wrists = hands.map((h) => h.landmarks[0] as Point);
    let left: LandmarkLike[] | undefined;
    let right: LandmarkLike[] | undefined;

    if (hands.length >= 2) {
      const [a, b] = hands as [DetectedHand, DetectedHand];
      const [wa, wb] = wrists as [Point, Point];
      let aIsLeft: boolean;
      if (anchors.left && anchors.right) {
        const keep = dist(wa, anchors.left) + dist(wb, anchors.right);
        const swap = dist(wa, anchors.right) + dist(wb, anchors.left);
        aIsLeft = keep <= swap;
      } else {
        // No geometry: trust labels if they disagree, else image position
        // (on an unmirrored frame the signer's left hand is on the image's right).
        const sa = labelSide(a.label);
        const sb = labelSide(b.label);
        aIsLeft = sa && sb && sa !== sb ? sa === "left" : wa.x > wb.x;
      }
      [left, right] = aIsLeft ? [a.landmarks, b.landmarks] : [b.landmarks, a.landmarks];
    } else if (hands.length === 1) {
      const hand = hands[0] as DetectedHand;
      const wrist = wrists[0] as Point;
      let side: "left" | "right" | null = null;
      if (anchors.left && anchors.right) side = dist(wrist, anchors.left) <= dist(wrist, anchors.right) ? "left" : "right";
      else if (anchors.left || anchors.right) side = anchors.left ? "left" : "right";
      side ??= labelSide(hand.label) ?? (wrist.x > 0.5 ? "left" : "right");
      if (side === "left") left = hand.landmarks;
      else right = hand.landmarks;
    }

    this.remember(left, right);
    return { left, right };
  }

  /** Pose wrists when visible, otherwise last known hand positions. */
  private anchors(pose: readonly LandmarkLike[] | undefined): { left: Point | null; right: Point | null } {
    const wrist = (i: number): Point | null => {
      const p = pose?.[i];
      return p && (p.visibility ?? 1) >= MIN_WRIST_VISIBILITY ? p : null;
    };
    return {
      left: wrist(POSE_LEFT_WRIST) ?? this.prev.left,
      right: wrist(POSE_RIGHT_WRIST) ?? this.prev.right,
    };
  }

  private remember(left: LandmarkLike[] | undefined, right: LandmarkLike[] | undefined) {
    for (const [side, hand] of [
      ["left", left],
      ["right", right],
    ] as const) {
      if (hand) {
        this.prev[side] = hand[0] as Point;
        this.staleness[side] = 0;
      } else if (++this.staleness[side] > MAX_STALE_FRAMES) {
        this.prev[side] = null;
      }
    }
  }
}
