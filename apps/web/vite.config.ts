/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend binds to 127.0.0.1 only; the dev/preview servers proxy /api to it
// so the browser talks to a single origin (docs/ARCHITECTURE.md).
const backend = {
  "/api": { target: "http://127.0.0.1:8000", ws: true },
};

export default defineConfig({
  plugins: [react()],
  envDir: "../..", // share the repository-root .env (only VITE_* is exposed)
  server: { host: "localhost", port: 5173, strictPort: true, proxy: backend },
  preview: { host: "localhost", port: 5173, strictPort: true, proxy: backend },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
