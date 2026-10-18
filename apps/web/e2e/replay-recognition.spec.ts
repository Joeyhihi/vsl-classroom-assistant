import { expect, test } from "@playwright/test";

import { spokenTexts, stubSpeech } from "./helpers";

// Full stack, no camera and no ML: synthetic replay → real WS → real backend
// (mock classifier, real utterance segmenter) → UI. The mock classifier scripts
// confident → uncertain → rejected, one per synthetic sign.

test.beforeEach(async ({ page }) => {
  await stubSpeech(page);
  await page.goto("/");
});

test("replay: handshake, segmentation, candidate policy, confirm without speech (mock)", async ({ page }) => {
  await expect(page.getByText("PHÁT LẠI TỔNG HỢP", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu nhận dạng" }).click();

  const status = page.getByTestId("recognition-status");
  await expect(status).toContainText(/Sẵn sàng|Đang ký|Đưa tay/);
  await expect(page.getByTestId("landmark-overlay")).toBeVisible();

  // First synthetic sign → confident candidate (mock label "Xin chào").
  const candidate = page.getByTestId("prediction-candidate");
  await expect(candidate).toContainText("Xin chào", { timeout: 15_000 });
  await expect(page.getByText("Chế độ mô phỏng: kết quả kịch bản không được đọc thành tiếng.")).toBeVisible();
  await candidate.getByRole("button", { name: "Xác nhận" }).click();
  await expect(page.getByRole("log").getByText("Xin chào")).toBeVisible();
  await expect(page.getByRole("log").getByText(/Ký hiệu/)).toBeVisible();
  expect(await spokenTexts(page)).toEqual([]); // scripted output is never spoken

  // Second sign → uncertain with alternatives.
  await expect(page.getByText("Bạn muốn nói gì?")).toBeVisible({ timeout: 15_000 });
  await expect(candidate.getByRole("button", { name: /^Chọn/ })).toHaveCount(3);
  await candidate.getByRole("button", { name: "Bỏ qua" }).click();

  // Third sign → rejected notice, no candidate text.
  await expect(page.getByTestId("prediction-rejected")).toBeVisible({ timeout: 15_000 });

  // Metrics were collected (replay fps ≈ 15; latency samples from 3 predictions).
  await page.getByRole("button", { name: "Cài đặt" }).click();
  const metrics = page.getByTestId("performance-metrics");
  await expect(metrics).toContainText(/1\d\.\d fps/);
  // Breakdown: processing (P3 criterion), the deliberate wait, and the total.
  for (const key of ["processing", "wait", "total"]) {
    await expect(page.getByTestId(`latency-${key}`)).toContainText("(n=3)");
  }
  const waitText = await page.getByTestId("latency-wait").textContent();
  expect(Number(/(\d+) ms/.exec(waitText ?? "")?.[1])).toBeGreaterThanOrEqual(600); // pause tolerance

  await page.getByRole("button", { name: "Giao tiếp" }).click();
  await page.getByRole("button", { name: "Dừng nhận dạng" }).click();
  await expect(page.getByRole("button", { name: "Bắt đầu nhận dạng" })).toBeVisible();
});

test("hidden tab pauses recognition visibly", async ({ page }) => {
  await page.getByRole("button", { name: "Bắt đầu nhận dạng" }).click();
  await expect(page.getByTestId("recognition-status")).toContainText(/Sẵn sàng|Đang ký|Đưa tay/);

  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
    document.dispatchEvent(new Event("visibilitychange"));
  });

  await expect(page.getByTestId("recognition-status")).toContainText("Tạm dừng");
  await expect(page.getByRole("button", { name: "Tiếp tục" })).toBeVisible();
});

test("recorder: session with SELF consent, synthetic take saved to DATA_ROOT", async ({ page }) => {
  await page.getByRole("button", { name: "Ghi mẫu" }).click();
  await expect(page.getByText("Từ vựng thử nghiệm của nhà phát triển")).toBeVisible();
  await expect(page.getByLabel("Mã đồng ý")).toBeDisabled(); // SELF only until B2
  await page.getByRole("button", { name: "Bắt đầu phiên ghi" }).click();
  await expect(page.getByTestId("session-active")).toContainText("Phiên đang mở: S");

  await page.getByLabel(/DEV_01/).check();
  await expect(page.getByLabel("Độ dài mỗi lượt").locator("option")).toHaveCount(2);
  await page.getByRole("button", { name: "Ghi một lượt (3 giây)" }).click();
  await expect(page.getByText("Chuẩn bị… 3")).toBeVisible();
  await expect(page.getByTestId("recording-banner")).toBeVisible({ timeout: 6000 });
  await expect(page.getByTestId("recorder-message")).toContainText("Đã lưu DEV_01", { timeout: 10_000 });
  await expect(page.getByTestId("take-count")).toHaveText("Đã ghi 1 lượt trong phiên này");
});

test("recorder: third-party consent is refused by the backend", async ({ request }) => {
  const response = await request.post("/api/v1/recordings/sessions", {
    data: {
      signer_id: "SGN-0001",
      consent_id: "C-1234",
      image_width: 640,
      image_height: 480,
      feature_spec_version: "fs-1",
      extractor_version: "synthetic",
      extractor_backend: "replay",
    },
  });
  expect(response.status()).toBe(403);
  expect((await response.json()).error.code).toBe("CONSENT_REQUIRED");
});

test("review: replay a recorded sample and accept it", async ({ page }) => {
  // Record one take first (each test has its own page).
  await page.getByRole("button", { name: "Ghi mẫu" }).click();
  await page.getByRole("button", { name: "Bắt đầu phiên ghi" }).click();
  await page.getByLabel(/REST_DESK/).check();
  await page.getByRole("button", { name: "Ghi một lượt (3 giây)" }).click();
  await expect(page.getByTestId("recorder-message")).toContainText("Đã lưu REST_DESK", { timeout: 10_000 });

  await page.getByRole("button", { name: "Duyệt mẫu" }).click();
  const list = page.getByTestId("review-list");
  await expect(list).toBeVisible();
  const before = await list.locator("li").count();
  await list.locator("li").filter({ hasText: "REST_DESK" }).first().getByRole("button", { name: /Xem lại/ }).click();
  await expect(page.getByTestId("review-current")).toBeVisible();
  await expect(page.getByTestId("landmark-overlay")).toBeVisible();
  await page.getByRole("button", { name: "Nhận", exact: true }).click();
  await expect(page.getByTestId("review-current")).toBeHidden();
  await expect.poll(async () => (await list.isVisible()) ? list.locator("li").count() : 0).toBe(before - 1);
});
