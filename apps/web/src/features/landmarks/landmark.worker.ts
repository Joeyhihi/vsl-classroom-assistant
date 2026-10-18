/// <reference lib="webworker" />
// Web Worker running MediaPipe off the main thread (P3 worker spike).
// Frames arrive as transferable ImageBitmaps; results go back as wire frames.

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { ExtractionLevel } from "../metrics/ladder";
import type { MediaPipeAssets } from "./assets";
import { createRunner, type Runner } from "./mediapipeRunner";

export type WorkerRequest =
  | { type: "init"; level: Exclude<ExtractionLevel, "L3">; spec: FeatureSpecWire; assets: MediaPipeAssets }
  | { type: "frame"; bitmap: ImageBitmap; tMs: number }
  | { type: "close" };

export type WorkerResponse =
  | { type: "ready"; delegate: string }
  | { type: "result"; frame: WireFrame }
  | { type: "error"; message: string };

let runner: Runner | null = null;
const post = (message: WorkerResponse) => self.postMessage(message);

self.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const msg = event.data;
  try {
    if (msg.type === "init") {
      // Module workers cannot importScripts(); use the ES-module WASM loader.
      runner = await createRunner(msg.level, msg.spec, msg.assets, true);
      post({ type: "ready", delegate: runner.delegate });
    } else if (msg.type === "frame") {
      if (!runner) throw new Error("not initialised");
      const frame = runner.detect(msg.bitmap, msg.tMs);
      msg.bitmap.close();
      post({ type: "result", frame });
    } else {
      runner?.close();
      runner = null;
      self.close();
    }
  } catch (error) {
    if (msg.type === "frame") msg.bitmap.close();
    // Name + message only (MediaPipe status text, no frame data).
    post({ type: "error", message: error instanceof Error ? `${error.name}: ${error.message}` : "error" });
  }
};
