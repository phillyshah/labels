// E2E: full submission flow through the deployed UI.
//
// Logs in, uploads the four sample PDFs, clicks Go, waits for the scorecard, asserts the amber
// APPROVE_WITH_FLAGS verdict, acknowledges both flags, signs & releases, and confirms a bundle
// and history row are produced.
//
// Run: npx playwright test tests/e2e/test_submission_flow.spec.ts
// Requires the stack running (locally or staging) and a seeded reviewer login.
//
// Env: E2E_BASE_URL, E2E_REVIEWER_EMAIL, E2E_REVIEWER_PASSWORD

import { test, expect } from "@playwright/test";
import path from "path";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const SAMPLES = path.resolve(__dirname, "../../reference-documents/samples");

const FILES = {
  label: path.join(SAMPLES, "1__V11022719_label.pdf"),
  batchCoc: path.join(SAMPLES, "1__V11022719_COC.pdf"),
  sterileCoc: path.join(SAMPLES, "M26-179_COC.pdf"),
  sterileLotRecord: path.join(SAMPLES, "Sterile_Lot_Record_M26-179.pdf"),
};

test.beforeEach(async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.getByLabel(/email/i).fill(process.env.E2E_REVIEWER_EMAIL ?? "reviewer@maxxortho.net");
  await page.getByLabel(/password/i).fill(process.env.E2E_REVIEWER_PASSWORD ?? "test-password");
  await page.getByRole("button", { name: /log in|sign in/i }).click();
  await expect(page).toHaveURL(/.*(review|dashboard|new).*/);
});

test("V11022719 submission resolves to APPROVE_WITH_FLAGS and can be signed", async ({ page }) => {
  await page.goto(`${BASE}/new`);

  await page.getByTestId("upload-label").setInputFiles(FILES.label);
  await page.getByTestId("upload-batch-coc").setInputFiles(FILES.batchCoc);
  await page.getByTestId("upload-sterile-coc").setInputFiles(FILES.sterileCoc);
  await page.getByTestId("upload-sterile-lot-record").setInputFiles(FILES.sterileLotRecord);

  await page.getByRole("button", { name: /^go$/i }).click();

  // Wait for processing to complete and the verdict banner to appear.
  const banner = page.getByTestId("verdict-banner");
  await expect(banner).toBeVisible({ timeout: 45_000 });
  await expect(banner).toContainText(/approve with flags/i);

  // Identity summary reflects the parsed batch.
  await expect(page.getByTestId("identity-summary")).toContainText("MTUUX400-K");
  await expect(page.getByTestId("identity-summary")).toContainText("V11022719");

  // Scorecard rows.
  await expect(page.getByTestId("check-row-A")).toContainText(/pass/i);
  await expect(page.getByTestId("check-row-B")).toContainText(/pass/i);
  await expect(page.getByTestId("check-row-G")).toContainText(/flag/i);

  // DEFERRED panel is present (machine did not verify D/E/F).
  await expect(page.getByTestId("deferred-panel")).toContainText(/not machine-verified/i);

  // Sign & Release is disabled until both flags acknowledged.
  const signBtn = page.getByRole("button", { name: /sign.*release/i });
  await expect(signBtn).toBeDisabled();

  // Acknowledge each flag.
  for (const flag of await page.getByTestId(/flag-ack-/).all()) {
    await flag.click();
  }
  await expect(signBtn).toBeEnabled();

  await signBtn.click();

  // Confirmation + bundle link + history row.
  await expect(page.getByTestId("release-confirmation")).toBeVisible();
  await expect(page.getByRole("link", { name: /approval bundle|download/i })).toBeVisible();

  await page.goto(`${BASE}/history`);
  await expect(page.getByText("V11022719").first()).toBeVisible();
  await expect(page.getByText(/released/i).first()).toBeVisible();
});

test("missing a required document blocks the run with a clear message", async ({ page }) => {
  await page.goto(`${BASE}/new`);
  await page.getByTestId("upload-label").setInputFiles(FILES.label);
  await page.getByTestId("upload-batch-coc").setInputFiles(FILES.batchCoc);
  // intentionally omit sterile CoC + sterile lot record
  await page.getByRole("button", { name: /^go$/i }).click();
  await expect(page.getByTestId("error-message")).toContainText(/required|missing/i);
});
