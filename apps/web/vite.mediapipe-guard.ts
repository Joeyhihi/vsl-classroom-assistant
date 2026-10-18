// Vite plugin: missing files under /mediapipe/ must be a real 404.
//
// Without this, Vite's SPA fallback answers with index.html (HTTP 200,
// text/html) and MediaPipe fails with "Unable to open zip archive", which hides
// the real problem: the assets were never fetched (scripts/bootstrap.py --with-models).

import { existsSync, statSync } from "node:fs";
import { join, normalize, sep } from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

export const MEDIAPIPE_PREFIX = "/mediapipe/";

type Next = () => void;

/** Middleware factory, exported for tests. `root` is the directory /mediapipe/ maps into. */
export function mediapipeGuard(root: string) {
  return (req: IncomingMessage, res: ServerResponse, next: Next) => {
    const path = (req.url ?? "").split("?")[0] ?? "";
    if (!path.startsWith(MEDIAPIPE_PREFIX)) return next();
    const file = normalize(join(root, decodeURIComponent(path)));
    const inside = file.startsWith(normalize(root) + sep);
    if (inside && existsSync(file) && statSync(file).isFile()) return next();
    res.statusCode = 404;
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.end(`MediaPipe asset not found: ${path}\nRun: uv run python scripts/bootstrap.py --with-models --pin\n`);
  };
}

export function mediapipeAssetsGuard(): Plugin {
  let publicDir = "";
  let outDir = "";
  return {
    name: "vsl-mediapipe-assets-guard",
    configResolved(config) {
      publicDir = config.publicDir;
      outDir = join(config.root, config.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use(mediapipeGuard(publicDir)); // dev: served from public/
    },
    configurePreviewServer(server) {
      server.middlewares.use(mediapipeGuard(outDir)); // preview: served from dist/
    },
  };
}
