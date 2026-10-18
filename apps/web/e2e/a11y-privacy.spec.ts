import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { mockBackend, stubSpeech } from "./helpers";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function expectAccessible(page: Page) {
  // Full rule set in a real browser, including colour contrast.
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  await mockBackend(page);
  await stubSpeech(page);
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe clean on every view (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    await expect(page.getByTestId("mock-badge")).toBeVisible();

    // Communication view with an active camera and a spoken transcript entry.
    await page.getByRole("button", { name: "Bật camera" }).click();
    await expect(page.getByTestId("camera-preview")).toBeVisible();
    await page.getByLabel("Tin nhắn", { exact: true }).fill("Xin chào");
    await page.getByRole("button", { name: "Gửi", exact: true }).click();
    await expectAccessible(page);

    await page.getByRole("button", { name: "Cài đặt" }).click();
    await expectAccessible(page);

    await page.getByRole("button", { name: "Quyền riêng tư" }).click();
    await expectAccessible(page);
  });
}

test("axe clean with the offline banner and a camera error", async ({ page }) => {
  await page.unrouteAll();
  await mockBackend(page, "offline");
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("x", "NotAllowedError"));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Bật camera" }).click();
  await expect(page.getByTestId("connection-banner")).toBeVisible();
  await expect(page.getByText("Chưa cho phép camera")).toBeVisible();
  await expectAccessible(page);
});

test("no network requests leave localhost (privacy)", async ({ page }) => {
  const external: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    const local = ["localhost", "127.0.0.1"].includes(url.hostname);
    if (!local && !["data:", "blob:"].includes(url.protocol)) external.push(request.url());
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Bật camera" }).click();
  await expect(page.getByTestId("camera-preview")).toBeVisible();
  await page.getByLabel("Tin nhắn", { exact: true }).fill("Kiểm tra");
  await page.getByRole("button", { name: "Gửi và đọc" }).click();
  await page.getByRole("button", { name: "Cài đặt" }).click();
  await page.getByRole("button", { name: "Quyền riêng tư" }).click();

  expect(external).toEqual([]);
});

test("missing MediaPipe assets are a 404, not the SPA fallback page", async ({ request }) => {
  // CI and the Mac never have the models; Vite used to answer index.html (HTTP 200).
  const response = await request.get("/mediapipe/holistic_landmarker.task");
  expect(response.status()).toBe(404);
  expect(await response.text()).toContain("bootstrap.py --with-models");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe clean on the recorder and review views (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    await page.getByRole("button", { name: "Ghi mẫu" }).click();
    await page.getByRole("button", { name: "Bắt đầu phiên ghi" }).click();
    await expect(page.getByTestId("session-active")).toBeVisible();
    await expectAccessible(page);

    await page.getByRole("button", { name: "Duyệt mẫu" }).click();
    await expect(page.getByRole("heading", { name: "Duyệt mẫu đã ghi" })).toBeVisible();
    await expectAccessible(page);
  });
}
