import { test, expect } from "@playwright/test";
import { login } from "./fixtures";

test.describe("admin", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, "admin");
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
  });

  test("deactivating a user asks for confirmation and does nothing if dismissed", async ({ page }) => {
    // Regression check: this toggle used to fire the PATCH immediately, no
    // confirmation — unlike the matching "remove role" action beside it.
    const activePill = page.locator("button", { hasText: "Active" }).first();
    await expect(activePill).toBeVisible();

    let dialogMessage = "";
    page.once("dialog", (dialog) => {
      dialogMessage = dialog.message();
      void dialog.dismiss();
    });

    const [patchRequest] = await Promise.all([
      page
        .waitForRequest((req) => req.url().includes("/api/v1/admin/iam/users/") && req.method() === "PATCH", {
          timeout: 3000,
        })
        .catch(() => null),
      activePill.click(),
    ]);

    expect(dialogMessage).toMatch(/deactivate/i);
    expect(patchRequest).toBeNull(); // dismissing the confirm must not fire the request
    await expect(activePill).toHaveText(/Active/);
  });

  test("activating an inactive user does not require confirmation", async ({ page }) => {
    const inactivePill = page.locator("button", { hasText: "Disabled" }).first();
    test.skip((await inactivePill.count()) === 0, "no disabled demo user seeded to test against");

    let dialogFired = false;
    page.once("dialog", (dialog) => {
      dialogFired = true;
      void dialog.dismiss();
    });
    await inactivePill.click();
    await page.waitForTimeout(500);
    expect(dialogFired).toBe(false);
  });
});
