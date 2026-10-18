// @vitest-environment node
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { mediapipeGuard } from "./vite.mediapipe-guard";

function run(root: string, url: string) {
  const next = vi.fn();
  const res = { statusCode: 200, setHeader: vi.fn(), end: vi.fn() };
  mediapipeGuard(root)({ url } as IncomingMessage, res as unknown as ServerResponse, next);
  return { next, res };
}

const root = mkdtempSync(join(tmpdir(), "mp-guard-"));
mkdirSync(join(root, "mediapipe", "wasm"), { recursive: true });
writeFileSync(join(root, "mediapipe", "holistic_landmarker.task"), "PK\x03\x04");

describe("mediapipeGuard", () => {
  it("passes existing assets through to the static server", () => {
    expect(run(root, "/mediapipe/holistic_landmarker.task?v=1").next).toHaveBeenCalled();
  });

  it("returns 404 instead of the SPA fallback for missing assets", () => {
    const { next, res } = run(root, "/mediapipe/hand_landmarker.task");
    expect(next).not.toHaveBeenCalled();
    expect(res.statusCode).toBe(404);
    expect(String(res.end.mock.calls[0]?.[0])).toContain("bootstrap.py --with-models");
  });

  it("does not allow escaping the directory", () => {
    expect(run(root, "/mediapipe/../../etc/passwd").res.statusCode).toBe(404);
    expect(run(root, "/mediapipe/wasm").res.statusCode).toBe(404); // directory, not a file
  });

  it("ignores other paths", () => {
    expect(run(root, "/api/v1/health").next).toHaveBeenCalled();
    expect(run(root, "/").next).toHaveBeenCalled();
  });
});
