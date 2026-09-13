import { test, expect, Page } from "@playwright/test";
import { login } from "./fixtures";

/** The table groups cameras by city with a CityGroupRow header interspersed
 * in <tbody> — filter to rows that actually have an Actions button, not the
 * group headers. */
function cameraRow(page: Page) {
  return page.locator("tbody tr").filter({ has: page.getByTitle("Actions") });
}

test.describe("camera registry", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "operator");
    await page.goto("/cameras", { waitUntil: "domcontentloaded" });
  });

  test("lists cameras", async ({ page }) => {
    await expect(page.locator("table")).toBeVisible();
    await expect(cameraRow(page).first()).toBeVisible();
  });

  test('"View live feed" navigates to the control room with that camera selected', async ({ page }) => {
    // Regression check: this action used to only close the menu and do nothing.
    const row = cameraRow(page).first();
    const code = (await row.locator("td").first().textContent())?.trim();
    await row.getByTitle("Actions").click();
    await page.getByRole("menuitem", { name: "View live feed" }).click();
    // ControlRoom consumes and strips the ?camera= param almost immediately,
    // so assert on the end state (back at "/", that camera focused) rather
    // than the transient URL, which a poll can miss.
    await page.waitForURL((url) => url.pathname === "/", { timeout: 10000 });
    if (code) {
      await expect(page.getByText(code).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test("row action menu closes on Escape (keyboard accessible)", async ({ page }) => {
    const row = cameraRow(page).first();
    const trigger = row.getByTitle("Actions");
    await trigger.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
