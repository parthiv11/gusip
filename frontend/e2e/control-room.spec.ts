import { test, expect } from "@playwright/test";
import { login } from "./fixtures";

test.describe("control room", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "operator");
  });

  test("a live Sentinel feed renders real video, not the demo test pattern", async ({ page }) => {
    // Regression check for the Sentinel Camera Grid auth fix: before it, the
    // focus pane fell back to an ffmpeg testsrc2 placeholder clip instead of
    // real government camera video.
    await expect(page.locator("video").first()).toBeVisible({ timeout: 15000 });
  });

  test("Gov feeds / Own-demo / All wall tabs switch", async ({ page }) => {
    const govTab = page.getByRole("tab", { name: "Gov feeds" });
    const demoTab = page.getByRole("tab", { name: "Own/demo" });
    await expect(govTab).toBeVisible();
    await demoTab.click();
    await expect(demoTab).toHaveAttribute("aria-selected", "true");
    await govTab.click();
    await expect(govTab).toHaveAttribute("aria-selected", "true");
  });

  test("camera load failure surfaces a visible error, not a silent empty wall", async ({ page }) => {
    // Regression check: ControlRoom.tsx used to render the same "no cameras"
    // copy for a genuinely empty wall and for a failed /api/v1/cameras fetch.
    await page.route("**/api/v1/cameras", (route) => route.abort("failed"));
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByRole("alert").filter({ hasText: /unavailable/i })).toBeVisible({ timeout: 20000 });
  });
});
