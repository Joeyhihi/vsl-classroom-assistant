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

test("recorder: one synthetic take, landmarks only", async ({ page }) => {
  await page.getByRole("button", { name: "Ghi mẫu" }).click();
  await page.getByLabel("Mã ký hiệu (ví dụ DEV_01)").fill("DEV_01");
  await page.getByLabel("Chữ hiển thị").fill("Thử nghiệm");
  await page.getByRole("button", { name: "Ghi một lượt (3 giây)" }).click();

  await expect(page.getByText("Chuẩn bị… 3")).toBeVisible();
  await expect(page.getByTestId("recording-banner")).toBeVisible({ timeout: 6000 });
  await expect(page.getByTestId("take-count")).toHaveText("Đã ghi 1 lượt", { timeout: 8000 });

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Tải tệp ghi (.json)" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("recording-DEV_01.json");
  const body = JSON.parse(await (await file.createReadStream()).toArray().then((c) => Buffer.concat(c).toString("utf-8")));
  expect(body.format).toBe("vsl-recording-v1");
  expect(body.developer_own_data).toBe(true);
  expect(body.takes[0].frames.length).toBeGreaterThan(30); // ~3 s at 15 fps
  expect(Object.keys(body.takes[0].frames[0]).sort()).toEqual(["face", "left_hand", "pose", "right_hand", "t_ms"]);
});
