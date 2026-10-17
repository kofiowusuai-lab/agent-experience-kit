import { test, expect, Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

async function login(page: Page, role: "reviewer" | "viewer" = "reviewer") {
  const key = process.env[role === "reviewer" ? "AEK_E2E_REVIEWER_KEY" : "AEK_E2E_VIEWER_KEY"];
  if (!key) throw new Error("Set demo reviewer/viewer environment keys before running browser checks");
  await page.goto("/");
  await page.getByLabel("Access key").fill(key);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A clear view of reported work." })).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
}

test("inspect evidence, record a review and inspect failure patterns", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await login(page);
  await expect(page.getByText("SYNTHETIC DEMO", { exact: true })).toBeVisible();
  if (process.env.AEK_SCREENSHOT_DIR) {
    mkdirSync(process.env.AEK_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: join(process.env.AEK_SCREENSHOT_DIR, `${testInfo.project.name}-overview.png`), fullPage: true });
  }
  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page.locator("tbody tr").first()).toContainText("failed");
  await page.getByRole("button", { name: /^Open / }).first().click();
  await expect(page.getByRole("heading", { name: "Acceptance & evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Audit trail & automated QA" })).toBeVisible();
  await page.locator(".step summary").first().click();
  await expect(page.getByRole("heading", { name: "Reported artifact hashes" }).first()).toBeVisible();
  await page.getByLabel("Outcome", { exact: true }).selectOption("needs_changes");
  const note = `Synthetic browser review (${testInfo.project.name}): repair the failed acceptance check.`;
  await page.getByLabel("Review note").fill(note);
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(page.getByLabel("Review note")).toHaveValue(note);
  await page.getByRole("button", { name: "Record review", exact: true }).click();
  await expect(page.getByText("Review recorded.", { exact: true })).toBeVisible();
  await expect(page.getByText(note, { exact: true }).first()).toBeVisible();
  if (process.env.AEK_SCREENSHOT_DIR)
    await page.screenshot({ path: join(process.env.AEK_SCREENSHOT_DIR, `${testInfo.project.name}-run.png`), fullPage: true });
  await page.getByRole("button", { name: "Reviews", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Reviews", exact: true })).toBeVisible();
  await expect(page.getByText(note, { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Failure patterns", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Failure patterns", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByText("external failure", { exact: true }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("server filters, empty results and error recovery", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Fleet", exact: true }).click();
  await page.getByRole("combobox", { name: "Team", exact: true }).selectOption({ label: "Product engineering" });
  await page.getByLabel("Filter by status").selectOption("completed");
  await expect(page.locator("tbody tr").first()).toContainText("Product engineering");
  await page.getByLabel("Search runs or agents").fill("no-such-synthetic-run");
  await expect(page.locator("tbody tr")).toHaveCount(0);
  await page.route("**/api/runs?*", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic temporary outage" }) }));
  await page.getByLabel("Search runs or agents").fill("");
  await expect(page.getByText("Synthetic temporary outage", { exact: true })).toBeVisible();
  await page.unroute("**/api/runs?*");
  await page.getByRole("button", { name: /Retry/ }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
});

test("viewer cannot record reviews and session credentials stay out of browser storage", async ({ page, context }) => {
  await login(page, "viewer");
  await page.getByRole("button", { name: /^Open / }).first().click();
  await expect(page.getByText(/Viewer access is read only/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Record review", exact: true })).toHaveCount(0);
  const cookies = await context.cookies();
  const session = cookies.find(cookie => cookie.name === "aek_session");
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Strict");
  const stored = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }));
  expect(stored).toEqual({ local: 0, session: 0 });
  const width = await page.evaluate(() => ({ body: document.documentElement.scrollWidth, viewport: innerWidth }));
  expect(width.body).toBeLessThanOrEqual(width.viewport + 1);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Access key")).toBeVisible();
});
