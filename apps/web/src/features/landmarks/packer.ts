// Packs MediaPipe results into wire frames using the server's feature spec
// (ADR-009: the browser never hard-codes landmark indices or shapes).

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { HandAssigner } from "./handAssigner";

export interface LandmarkLike {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

/** The subset of HolisticLandmarkerResult we read (L1). */
export interface HolisticLike {
  poseLandmarks: LandmarkLike[][];
  leftHandLandmarks: LandmarkLike[][];
  rightHandLandmarks: LandmarkLike[][];
  faceLandmarks: LandmarkLike[][];
}

/** HandLandmarker + PoseLandmarker results (L2, no face). */
export interface HandPoseLike {
  hands: { landmarks: LandmarkLike[][]; handedness: { categoryName: string }[][] };
  pose: { landmarks: LandmarkLike[][] };
}

const DECIMALS = 1e4;
const round = (v: number) => Math.round(v * DECIMALS) / DECIMALS;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

// Same ranges the server validates; clamping avoids dropping whole frames when a
// landmark sits just outside the image.
function point(lm: LandmarkLike, withVisibility: boolean): number[] {
  const xyz = [round(clamp(lm.x, -0.5, 1.5)), round(clamp(lm.y, -0.5, 1.5)), round(clamp(lm.z, -5, 5))];
  return withVisibility ? [...xyz, round(clamp(lm.visibility ?? 0, 0, 1))] : xyz;
}

function rows(list: LandmarkLike[] | undefined, n: number, withVisibility: boolean): number[][] | null {
  if (!list || list.length < n) return null;
  return list.slice(0, n).map((lm) => point(lm, withVisibility));
}

export function packHolistic(
  result: HolisticLike,
  spec: FeatureSpecWire,
  tMs: number,
  assigner: HandAssigner,
): WireFrame {
  const [poseN] = spec.shapes.pose as [number, number];
  const [handN] = spec.shapes.hand as [number, number];
  const face = result.faceLandmarks[0];
  const maxIndex = Math.max(...spec.face_indices);
  const pose = result.poseLandmarks[0];
  // Holistic's own left/right naming is not trusted: hands are re-assigned to the
  // pose wrists (see handAssigner.ts), which also stops left/right flicker.
  const detected = [
    { landmarks: result.leftHandLandmarks[0], label: "Left" },
    { landmarks: result.rightHandLandmarks[0], label: "Right" },
  ].filter((h): h is { landmarks: LandmarkLike[]; label: string } => !!h.landmarks && h.landmarks.length >= handN);
  const hands = assigner.assign(detected, pose);
  return {
    t_ms: Math.round(tMs * 10) / 10,
    pose: rows(pose, poseN, true),
    left_hand: rows(hands.left, handN, false),
    right_hand: rows(hands.right, handN, false),
    face:
      face && face.length > maxIndex
        ? spec.face_indices.map((i) => point(face[i] as LandmarkLike, false))
        : null,
  };
}

export function packHandPose(
  result: HandPoseLike,
  spec: FeatureSpecWire,
  tMs: number,
  assigner: HandAssigner,
): WireFrame {
  const [poseN] = spec.shapes.pose as [number, number];
  const [handN] = spec.shapes.hand as [number, number];
  const pose = result.pose.landmarks[0];
  const detected = result.hands.landmarks
    .map((landmarks, i) => ({ landmarks, label: result.hands.handedness[i]?.[0]?.categoryName }))
    .filter((h) => h.landmarks.length >= handN);
  const hands = assigner.assign(detected, pose);
  return {
    t_ms: Math.round(tMs * 10) / 10,
    pose: rows(pose, poseN, true),
    left_hand: rows(hands.left, handN, false),
    right_hand: rows(hands.right, handN, false),
    face: null,
  };
}
