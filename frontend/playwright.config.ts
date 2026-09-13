import { defineConfig, devices } from "@playwright/test";

/**
 * Drives the real running stack (docker compose up) — there is no webServer
 * entry here on purpose. These are end-to-end tests against live login,
 * RBAC, and the Sentinel proxy, not component tests; a mocked server would
 * defeat the point of the coverage (see e2e/README.md).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // shared demo/session-storage login state; keep it simple and deterministic
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: process.env.GUSIP_BASE_URL || "http://localhost:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
