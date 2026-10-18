import { describe, expect, it, vi } from "vitest";

import { MediaPipeAssetError, isZip, loadMediaPipeAssets, modelsFor } from "./assets";

// Shaped like a real MediaPipe .task: leading zero bytes, local header, then the
// 22-byte end-of-central-directory record (verified against the upstream files).
const ZIP = new Uint8Array([
  0, 0, 0, 0, 0x50, 0x4b, 0x03, 0x04, 1, 2, 3,
  0x50, 0x4b, 0x05, 0x06, ...new Array<number>(18).fill(0),
]);
const HTML = new TextEncoder().encode("<!doctype html><html></html>");

type Files = Record<string, { status?: number; body?: Uint8Array<ArrayBuffer>; type?: string }>;

function fakeFetch(files: Files) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname.replace("/mediapipe/", "");
    // Simulates Vite's SPA fallback for anything not listed: 200 + index.html.
    const file = files[path] ?? { status: 200, body: HTML, type: "text/html" };
    return new Response(file.body ?? new Uint8Array(), {
      status: file.status ?? 200,
      headers: { "content-type": file.type ?? "application/octet-stream" },
    });
  }) as unknown as typeof fetch;
}

const WASM: Files = {
  "wasm/vision_wasm_module_internal.js": {},
  "wasm/vision_wasm_module_internal.wasm": {},
  "wasm/vision_wasm_internal.js": {},
  "wasm/vision_wasm_internal.wasm": {},
};

describe("loadMediaPipeAssets", () => {
  it("loads and validates the L1 model as a buffer", async () => {
    const assets = await loadMediaPipeAssets(
      "L1",
      "http://localhost:5173",
      fakeFetch({ ...WASM, "holistic_landmarker.task": { body: ZIP } }),
    );
    expect(assets.wasmBase).toBe("http://localhost:5173/mediapipe/wasm");
    expect(assets.models.holistic).toEqual(ZIP);
  });

  it("reports the SPA-fallback HTML page as a missing model (the Windows bug)", async () => {
    const promise = loadMediaPipeAssets("L1", "http://localhost:5173", fakeFetch(WASM));
    await expect(promise).rejects.toBeInstanceOf(MediaPipeAssetError);
    await expect(promise).rejects.toMatchObject({ missing: ["holistic_landmarker.task"] });
  });

  it("rejects 404s and non-zip content, listing every missing file", async () => {
    const promise = loadMediaPipeAssets(
      "L2",
      "http://localhost:5173",
      fakeFetch({
        "wasm/vision_wasm_internal.js": {},
        "hand_landmarker.task": { status: 404 },
        "pose_landmarker_lite.task": { body: new Uint8Array([1, 2, 3, 4]) },
      }),
    );
    await expect(promise).rejects.toMatchObject({
      missing: [
        "hand_landmarker.task",
        "pose_landmarker_lite.task",
        "wasm/vision_wasm_internal.wasm",
        "wasm/vision_wasm_module_internal.js",
        "wasm/vision_wasm_module_internal.wasm",
      ],
    });
  });

  it("knows which models each level needs", () => {
    expect(modelsFor("L1")).toEqual(["holistic"]);
    expect(modelsFor("L2")).toEqual(["hand", "pose"]);
    expect(isZip(ZIP)).toBe(true);
    expect(isZip(HTML)).toBe(false);
    // "PK" at the start is not enough, and leading bytes are allowed.
    expect(isZip(new Uint8Array([0x50, 0x4b, 0x03, 0x04, ...new Array<number>(30).fill(1)]))).toBe(false);
  });
});
