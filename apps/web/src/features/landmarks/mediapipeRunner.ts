// MediaPipe Tasks runner shared by the Web Worker and the main-thread fallback.
// Only loaded on demand (dynamic import), and never in replay/mock mode, so the
// M1 dev loop and the tests do not touch MediaPipe at all.

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { ExtractionLevel } from "../metrics/ladder";
import type { MediaPipeAssets } from "./assets";
import { packHandPose, packHolistic } from "./packer";

export type Delegate = "GPU" | "CPU";

export interface Runner {
  detect(image: TexImageSource | ImageBitmap, tMs: number): WireFrame;
  close(): void;
  readonly delegate: Delegate;
}

/**
 * Create L1 (Holistic) or L2 (Hand + Pose) on GPU, falling back to CPU.
 * Models arrive as validated buffers (see assets.ts); only the WASM runtime is
 * loaded by URL.
 */
export async function createRunner(
  level: Exclude<ExtractionLevel, "L3">,
  spec: FeatureSpecWire,
  assets: MediaPipeAssets,
  useModuleWasm: boolean,
): Promise<Runner> {
  const vision = await import("@mediapipe/tasks-vision");
  const fileset = await vision.FilesetResolver.forVisionTasks(assets.wasmBase, useModuleWasm);
  const model = (name: keyof MediaPipeAssets["models"]) => {
    const bytes = assets.models[name];
    if (!bytes) throw new Error(`model ${name} not loaded`);
    return bytes;
  };

  for (const delegate of ["GPU", "CPU"] as const) {
    try {
      if (level === "L1") {
        const holistic = await vision.HolisticLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetBuffer: model("holistic"), delegate },
          runningMode: "VIDEO",
        });
        return {
          delegate,
          detect: (image, tMs) => packHolistic(holistic.detectForVideo(image, tMs), spec, tMs),
          close: () => holistic.close(),
        };
      }
      const hands = await vision.HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetBuffer: model("hand"), delegate },
        runningMode: "VIDEO",
        numHands: 2,
      });
      const pose = await vision.PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetBuffer: model("pose"), delegate },
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
