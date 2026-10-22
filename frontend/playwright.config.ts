import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  expect: { timeout: 10000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: "../reports/react-playwright", open: "never" }],
    ["json", { outputFile: "../reports/react-playwright.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:8502",
    browserName: "chromium",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "..\\.venv\\Scripts\\python.exe ..\\tests\\web_test_server.py",
    url: "http://127.0.0.1:8502/api/health",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
