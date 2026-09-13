import { Page, expect } from "@playwright/test";

/** Demo credentials from README.md / backend/app/seed.py — PoC-only, not secrets. */
export const CREDENTIALS = {
  operator: { username: "operator", password: "GUSIP@ops2026" },
  investigator: { username: "investigator", password: "GUSIP@inv2026" },
  coordinator: { username: "coordinator", password: "GUSIP@coord2026" },
  admin: { username: "admin", password: "GUSIP@admin2026" },
} as const;

export type Role = keyof typeof CREDENTIALS;

export async function login(page: Page, role: Role): Promise<void> {
  const { username, password } = CREDENTIALS[role];
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL("/", { timeout: 15000 });
}

/**
 * Sign-out click triggers a client-side route change; wrap it in
 * expect_navigation-equivalent waiting so Playwright doesn't race the
 * button's own post-click stability check against the redirect.
 */
export async function logout(page: Page): Promise<void> {
  await Promise.all([page.waitForURL("**/login", { timeout: 15000 }), page.getByLabel("Sign out").click()]);
  await expect(page.locator('input[name="username"]')).toBeVisible();
}

export async function switchUser(page: Page, role: Role): Promise<void> {
  await logout(page);
  await login(page, role);
}
