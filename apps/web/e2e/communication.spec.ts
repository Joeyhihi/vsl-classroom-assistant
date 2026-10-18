import { expect, test } from "@playwright/test";

import { mockBackend, spokenTexts, stubSpeech } from "./helpers";

test.beforeEach(async ({ page }) => {
  await stubSpeech(page);
});

test("manual text → transcript → local vi-VN speech", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await expect(page.getByTestId("mock-badge")).toBeVisible();

  await page.getByLabel("Tin nhắn", { exact: true }).fill("Em xin phép ra ngoài");
  await page.getByRole("button", { name: "Gửi và đọc" }).click();

  const log = page.getByRole("log");
  await expect(log.getByText("Em xin phép ra ngoài")).toBeVisible();
  await expect(page.getByTestId("speaking-indicator")).toContainText("Đang phát");
  await expect(page.getByTestId("speaking-indicator")).toBeHidden();
  await expect(log.getByText("Đã đọc")).toBeVisible();
  // Only the local voice is used by default (ADR-010).
  expect(await spokenTexts(page)).toEqual(["Linh|Em xin phép ra ngoài"]);
});

test("backend offline: banner shown, manual text still works", async ({ page }) => {
  await mockBackend(page, "offline");
  await page.goto("/");

  await expect(page.getByTestId("connection-banner")).toContainText("Mất kết nối máy chủ");
  await page.getByLabel("Tin nhắn", { exact: true }).fill("Cảm ơn cô");
  await page.getByLabel("Tin nhắn", { exact: true }).press("Enter");
  await expect(page.getByRole("log").getByText("Cảm ơn cô")).toBeVisible();
});

test("settings: voice diagnostics and network voices off by default", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Cài đặt" }).click();

  await expect(page.getByTestId("voice-summary")).toHaveText("Giọng tiếng Việt: 1 cục bộ, 1 trực tuyến.");
  await expect(page.getByLabel("Giọng đọc tiếng Việt").locator("option")).toHaveCount(1);
  await expect(page.getByLabel("Cho phép giọng đọc trực tuyến (không khuyến khích)")).not.toBeChecked();
  await expect(page.getByText("Đã kết nối máy chủ")).toBeVisible();
});
