// Landmark extractor: Web Worker first, main thread as fallback (P3 spike).
// The result of the spike (which mode actually runs) is reported in diagnostics.

import type { FeatureSpecWire, WireFrame } from "../../api/generated/contracts";
import type { ExtractionLevel } from "../metrics/ladder";
import { loadMediaPipeAssets, type MediaPipeAssets } from "./assets";
import type { WorkerRequest, WorkerResponse } from "./landmark.worker";

export type ExtractorMode = "worker" | "main";

export interface Extractor {
  readonly mode: ExtractorMode;
  readonly delegate: string;
  /** Resolves with a frame, or rejects; callers skip frames while one is in flight. */
  detect(video: HTMLVideoElement, tMs: number): Promise<WireFrame>;
  close(): void;
}

const WORKER_INIT_TIMEOUT_MS = 20_000;

async function createWorkerExtractor(
  level: Exclude<ExtractionLevel, "L3">,
  spec: FeatureSpecWire,
  assets: MediaPipeAssets,
): Promise<Extractor> {
  const worker = new Worker(new URL("./landmark.worker.ts", import.meta.url), { type: "module" });
  const send = (msg: WorkerRequest, transfer: Transferable[] = []) => worker.postMessage(msg, transfer);

  const delegate = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("worker init timeout")), WORKER_INIT_TIMEOUT_MS);
    worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      clearTimeout(timer);
      if (e.data.type === "ready") resolve(e.data.delegate);
      else reject(new Error(e.data.type === "error" ? e.data.message : "unexpected"));
    };
    worker.onerror = () => {
      clearTimeout(timer);
      reject(new Error("worker failed"));
    };
    // Model bytes are cloned (not transferred) so the main-thread fallback can reuse them.
    send({ type: "init", level, spec, assets });
  }).catch((error: unknown) => {
    worker.terminate();
    throw error;
  });

  let pending: { resolve: (f: WireFrame) => void; reject: (e: Error) => void } | null = null;
  worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
    const p = pending;
    pending = null;
    if (e.data.type === "result") p?.resolve(e.data.frame);
    else if (e.data.type === "error") p?.reject(new Error(e.data.message));
  };

  return {
    mode: "worker",
    delegate,
    async detect(video, tMs) {
      const bitmap = await createImageBitmap(video);
      return new Promise<WireFrame>((resolve, reject) => {
        pending = { resolve, reject };
        send({ type: "frame", bitmap, tMs }, [bitmap]);
      });
    },
    close() {
      send({ type: "close" });
      setTimeout(() => worker.terminate(), 500);
    },
  };
}

async function createMainThreadExtractor(
  level: Exclude<ExtractionLevel, "L3">,
  spec: FeatureSpecWire,
  assets: MediaPipeAssets,
): Promise<Extractor> {
  const { createRunner } = await import("./mediapipeRunner");
  const runner = await createRunner(level, spec, assets, false);
  return {
    mode: "main",
    delegate: runner.delegate,
    detect: async (video, tMs) => runner.detect(video, tMs),
    close: () => runner.close(),
  };
}

export async function createExtractor(
  level: Exclude<ExtractionLevel, "L3">,
  spec: FeatureSpecWire,
): Promise<Extractor> {
  // Missing/invalid assets throw MediaPipeAssetError here: no point trying either mode.
  const assets = await loadMediaPipeAssets(level);
  try {
    return await createWorkerExtractor(level, spec, assets);
  } catch (workerError) {
    // e.g. the WASM loader or GPU delegate is not usable inside a worker.
    console.warn("MediaPipe worker unavailable, using the main thread:", String(workerError));
    return createMainThreadExtractor(level, spec, assets);
  }
}
