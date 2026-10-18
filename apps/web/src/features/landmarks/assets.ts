// Loads and validates MediaPipe assets on the main thread before any task is
// created. The model bytes are then passed to MediaPipe as buffers, so the worker
// never resolves model paths itself, and a missing file becomes a clear error
// instead of "Unable to open zip archive".

import type { ExtractionLevel } from "../metrics/ladder";

export const MEDIAPIPE_BASE = "/mediapipe";

export const MODEL_FILES = {
  holistic: "holistic_landmarker.task",
  hand: "hand_landmarker.task",
  pose: "pose_landmarker_lite.task",
} as const;

// Worker uses the ES-module loader; the main-thread fallback uses the classic one.
export const WASM_FILES = [
  "wasm/vision_wasm_module_internal.js",
  "wasm/vision_wasm_module_internal.wasm",
  "wasm/vision_wasm_internal.js",
  "wasm/vision_wasm_internal.wasm",
] as const;

export type ModelName = keyof typeof MODEL_FILES;

export interface MediaPipeAssets {
  wasmBase: string; // absolute URL of the wasm directory
  models: Partial<Record<ModelName, Uint8Array>>;
}

export class MediaPipeAssetError extends Error {
  constructor(readonly missing: string[]) {
    super(`MediaPipe assets missing or invalid: ${missing.join(", ")}`);
    this.name = "MediaPipeAssetError";
  }
}

export const modelsFor = (level: Exclude<ExtractionLevel, "L3">): ModelName[] =>
  level === "L1" ? ["holistic"] : ["hand", "pose"];

const ZIP_MAGIC = [0x50, 0x4b, 0x03, 0x04]; // .task files are zip archives

export function isZip(bytes: Uint8Array): boolean {
  return ZIP_MAGIC.every((b, i) => bytes[i] === b);
}

const isHtml = (response: Response) => (response.headers.get("content-type") ?? "").includes("text/html");

export async function loadMediaPipeAssets(
  level: Exclude<ExtractionLevel, "L3">,
  origin: string = window.location.origin,
  fetchImpl: typeof fetch = fetch,
): Promise<MediaPipeAssets> {
  const url = (file: string) => new URL(`${MEDIAPIPE_BASE}/${file}`, origin).href;
  const missing: string[] = [];

  const wasmChecks = WASM_FILES.map(async (file) => {
    const response = await fetchImpl(url(file), { method: "HEAD" }).catch(() => null);
    if (!response?.ok || isHtml(response)) missing.push(file);
  });

  const models: MediaPipeAssets["models"] = {};
  const modelLoads = modelsFor(level).map(async (name) => {
    const file = MODEL_FILES[name];
    const response = await fetchImpl(url(file)).catch(() => null);
    const bytes = response?.ok && !isHtml(response) ? new Uint8Array(await response.arrayBuffer()) : null;
    if (bytes && isZip(bytes)) models[name] = bytes;
    else missing.push(file);
  });

  await Promise.all([...wasmChecks, ...modelLoads]);
  if (missing.length > 0) throw new MediaPipeAssetError(missing.sort());
  return { wasmBase: url("wasm"), models };
}
