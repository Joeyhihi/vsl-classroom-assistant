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

// Zip end-of-central-directory signature "PK\x05\x06". MediaPipe .task files are
// zip archives with a few bytes BEFORE the zip header, so like any zip reader we
// look for this record at the end (22 bytes + up to 64 KiB comment), not "PK" at
// the start.
const EOCD = [0x50, 0x4b, 0x05, 0x06];
const EOCD_SEARCH = 22 + 0xffff;

export function isZip(bytes: Uint8Array): boolean {
  const stop = Math.max(0, bytes.length - EOCD_SEARCH);
  for (let i = bytes.length - 22; i >= stop; i--) {
    if (EOCD.every((b, k) => bytes[i + k] === b)) return true;
  }
  return false;
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
