import { expect, test } from "@playwright/test";

import { failCameraWith, mockBackend, stubSpeech } from "./helpers";

test.beforeEach(async ({ page }) => {
  await mockBackend(page);
  await stubSpeech(page);
});

test("fake camera: preview, mirrored, selector, stop", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Bật camera" }).click();

  const video = page.getByTestId("camera-preview");
  await expect(video).toBeVisible();
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.videoWidth), { timeout: 10_000 })
    .toBeGreaterThan(0);
  await expect(video).toHaveCSS("transform", "matrix(-1, 0, 0, 1, 0, 0)");
  await expect(page.getByText("Camera đang bật").first()).toBeVisible();

  const selector = page.getByLabel("Chọn camera");
  await expect(selector).toBeVisible();
  expect(await selector.locator("option").count()).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Tắt camera" }).click();
  await expect(video).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Bật camera" })).toBeVisible();
});

const failures = [
  { error: "NotAllowedError", title: "Chưa cho phép camera" },
  { error: "NotFoundError", title: "Không tìm thấy camera" },
  { error: "NotReadableError", title: "Camera đang được ứng dụng khác dùng" },
];

for (const { error, title } of failures) {
  test(`camera failure ${error} shows guidance and keeps manual text usable`, async ({ page }) => {
    await failCameraWith(page, error);
    await page.goto("/");
    await page.getByRole("button", { name: "Bật camera" }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toContainText(title);
    await expect(alert.getByRole("button", { name: "Thử lại" })).toBeVisible();
    await expect(page.getByLabel("Tin nhắn", { exact: true })).toBeEditable();
  });
}
