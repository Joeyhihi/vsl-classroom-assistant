import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const BACKEND_PORT = 8765; // separate from a developer backend on 8000
const isCI = !!process.env.CI;

// Locally we drive the installed Google Chrome (no extra browser download on
// the 8 GB Mac); CI installs Playwright's Chromium. Override with PW_CHANNEL.
const channel = process.env.PW_CHANNEL ?? (isCI ? undefined : "chrome");

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1, // keep memory low on the M1
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["list"]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    channel,
    baseURL: `http://localhost:${PORT}`,
    locale: "vi-VN",
    trace: "retain-on-failure",
    permissions: ["camera"],
    launchOptions: {
      // Synthetic test-pattern camera: no real camera and no real person.
      args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
    },
  },
  webServer: [
    {
      // Real backend in mock mode (no ML libraries) for the replay end-to-end test.
      command: `uv run python scripts/run_backend.py --mock --port ${BACKEND_PORT}`,
      cwd: "../..",
      url: `http://127.0.0.1:${BACKEND_PORT}/api/v1/health`,
      env: { VSL_ALLOWED_ORIGINS: `http://localhost:${PORT}`, VSL_ENV: "dev" },
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
    {
      // Production build in replay mode with the recorder; /api is proxied to the backend.
      command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
      url: `http://localhost:${PORT}`,
      env: { VSL_PORT: String(BACKEND_PORT), VITE_LANDMARK_SOURCE: "replay", VITE_ENABLE_RECORDER: "true" },
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
  ],
});
