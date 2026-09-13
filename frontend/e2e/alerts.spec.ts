import { test, expect } from "@playwright/test";
import { login } from "./fixtures";

test.describe("alerts evidence images", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "operator");
  });

  test("an alert with no snapshot shows the labeled placeholder, not a stock photo", async ({ page }) => {
    // Regression check: this used to fall back to a hardcoded stock photo
    // (/assets/alert_fortuner.jpg) that could be mistaken for real evidence.
    await page.route("**/api/v1/alerts*", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      if (Array.isArray(body) && body.length > 0) {
        body[0].snapshot_url = null;
      }
      await route.fulfill({ response, json: body });
    });
    await page.goto("/alerts", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("No image").first()).toBeVisible({ timeout: 10000 });
    expect(await page.locator('img[src*="alert_fortuner"]').count()).toBe(0);
  });

  test("an alert whose snapshot file 404s falls back to the same placeholder", async ({ page }) => {
    // Regression check: a present-but-broken snapshot_url used to render a
    // bare broken-image icon instead of the placeholder.
    const brokenUrl = "/api/v1/evidence/snapshots/e2e-test-missing.enc";
    await page.route("**/api/v1/alerts*", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      if (Array.isArray(body) && body.length > 0) {
        body[0].snapshot_url = brokenUrl;
      }
      await route.fulfill({ response, json: body });
    });
    await page.route(`**${brokenUrl}`, (route) => route.fulfill({ status: 404, body: "not found" }));

    await page.goto("/alerts", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("No image").first()).toBeVisible({ timeout: 10000 });
  });
});
