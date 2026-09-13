import { test, expect } from "@playwright/test";
import { login, logout, CREDENTIALS } from "./fixtures";

test.describe("authentication & RBAC", () => {
  test("unauthenticated API access is rejected", async ({ request, baseURL }) => {
    const res = await request.get(`${baseURL}/api/v1/cameras`);
    expect(res.status()).toBe(401);
  });

  test("operator can log in and lands on the control room", async ({ page }) => {
    await login(page, "operator");
    await expect(page.getByText("SOC Operator")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Gov feeds" })).toBeVisible();
  });

  test("each seeded role can log in", async ({ page }) => {
    for (const role of Object.keys(CREDENTIALS) as (keyof typeof CREDENTIALS)[]) {
      await page.goto("/login", { waitUntil: "domcontentloaded" });
      await page.fill('input[name="username"]', CREDENTIALS[role].username);
      await page.fill('input[name="password"]', CREDENTIALS[role].password);
      await page.click('button[type="submit"]');
      await page.waitForURL("/", { timeout: 15000 });
      await logout(page);
    }
  });

  test("operator is denied super-admin-only endpoints (403, not a silent empty state)", async ({ page }) => {
    await login(page, "operator");
    const res = await page.request.get("/api/v1/admin/stats");
    expect(res.status()).toBe(403);
  });

  test("admin can reach super-admin-only endpoints", async ({ page }) => {
    await login(page, "admin");
    const res = await page.request.get("/api/v1/admin/stats");
    expect(res.ok()).toBeTruthy();
  });

  test("sign out clears the session — a protected page redirects back to login", async ({ page }) => {
    await login(page, "operator");
    await logout(page);
    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/login$/);
  });
});
