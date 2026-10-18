// MediaPipe Tasks runner shared by the Web Worker and the main-thread fallback.
// Only loaded on demand (dynamic import), and never in replay/mock mode, so the
// M1 dev loop and the tests do not touch MediaPipe at all.

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { ExtractionLevel } from "../metrics/ladder";
import { packHandPose, packHolistic } from "./packer";

/** Self-hosted assets (scripts/fetch_mediapipe_assets.py, Windows only). */
export const MEDIAPIPE_ASSETS = {
  wasm: "/mediapipe/wasm",
  holistic: "/mediapipe/holistic_landmarker.task",
  hand: "/mediapipe/hand_landmarker.task",
  pose: "/mediapipe/pose_landmarker_lite.task",
} as const;

export type Delegate = "GPU" | "CPU";

export interface Runner {
  detect(image: TexImageSource | ImageBitmap, tMs: number): WireFrame;
  close(): void;
  readonly delegate: Delegate;
}

/** Create L1 (Holistic) or L2 (Hand + Pose) on GPU, falling back to CPU. */
export async function createRunner(
  level: Exclude<ExtractionLevel, "L3">,
  spec: FeatureSpecWire,
  baseUrl: string,
  useModuleWasm: boolean,
): Promise<Runner> {
  const vision = await import("@mediapipe/tasks-vision");
  const fileset = await vision.FilesetResolver.forVisionTasks(
    new URL(MEDIAPIPE_ASSETS.wasm, baseUrl).href,
    useModuleWasm,
  );
  const asset = (path: string) => new URL(path, baseUrl).href;

  for (const delegate of ["GPU", "CPU"] as const) {
    try {
      if (level === "L1") {
        const holistic = await vision.HolisticLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: asset(MEDIAPIPE_ASSETS.holistic), delegate },
          runningMode: "VIDEO",
        });
        return {
          delegate,
          detect: (image, tMs) => packHolistic(holistic.detectForVideo(image, tMs), spec, tMs),
          close: () => holistic.close(),
        };
      }
      const hands = await vision.HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: asset(MEDIAPIPE_ASSETS.hand), delegate },
        runningMode: "VIDEO",
        numHands: 2,
      });
      const pose = await vision.PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: asset(MEDIAPIPE_ASSETS.pose), delegate },
        runningMode: "VIDEO",
        numPoses: 1,
      });
      return {
        delegate,
        detect: (image, tMs) =>
          packHandPose(
            { hands: hands.detectForVideo(image, tMs), pose: pose.detectForVideo(image, tMs) },
            spec,
            tMs,
          ),
        close: () => {
          hands.close();
          pose.close();
        },
      };
    } catch (error) {
      if (delegate === "CPU") throw error;
      // GPU delegate unavailable (e.g. no WebGL in a worker): retry on CPU.
    }
  }
  throw new Error("unreachable");
}
