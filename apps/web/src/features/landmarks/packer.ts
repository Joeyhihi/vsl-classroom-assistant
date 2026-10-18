// Packs MediaPipe results into wire frames using the server's feature spec
// (ADR-009: the browser never hard-codes landmark indices or shapes).

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";

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

export function packHolistic(result: HolisticLike, spec: FeatureSpecWire, tMs: number): WireFrame {
  const [poseN] = spec.shapes.pose as [number, number];
  const [handN] = spec.shapes.hand as [number, number];
  const face = result.faceLandmarks[0];
  const maxIndex = Math.max(...spec.face_indices);
  return {
    t_ms: Math.round(tMs * 10) / 10,
    pose: rows(result.poseLandmarks[0], poseN, true),
    // UNVERIFIED (P3 Windows calibration): MediaPipe Holistic "left" is the
    // signer's anatomical left when the frame is not mirrored.
    left_hand: rows(result.leftHandLandmarks[0], handN, false),
    right_hand: rows(result.rightHandLandmarks[0], handN, false),
    face:
      face && face.length > maxIndex
        ? spec.face_indices.map((i) => point(face[i] as LandmarkLike, false))
        : null,
  };
}

/**
 * MediaPipe hand "handedness" assumes a mirrored (selfie) image. Our frames are
 * unmirrored, so the label is swapped. UNVERIFIED until the P3 Windows test.
 */
export const HANDEDNESS_LABELS_ASSUME_MIRRORED = true;

export function packHandPose(result: HandPoseLike, spec: FeatureSpecWire, tMs: number): WireFrame {
  const [poseN] = spec.shapes.pose as [number, number];
  const [handN] = spec.shapes.hand as [number, number];
  let left: LandmarkLike[] | undefined;
  let right: LandmarkLike[] | undefined;
  result.hands.landmarks.forEach((landmarks, i) => {
    const label = result.hands.handedness[i]?.[0]?.categoryName;
    const isLeft = HANDEDNESS_LABELS_ASSUME_MIRRORED ? label === "Right" : label === "Left";
    if (isLeft) left ??= landmarks;
    else right ??= landmarks;
  });
  return {
    t_ms: Math.round(tMs * 10) / 10,
    pose: rows(result.pose.landmarks[0], poseN, true),
    left_hand: rows(left, handN, false),
    right_hand: rows(right, handN, false),
    face: null,
  };
}
