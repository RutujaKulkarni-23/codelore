import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const localAppData = process.env.LOCALAPPDATA || "";
const chromePath = path.join(
  localAppData,
  "ms-playwright",
  "chromium-1208",
  "chrome-win64",
  "chrome.exe"
);

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    headless: true,
    launchOptions: {
      executablePath: chromePath,
    },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          executablePath: chromePath,
        },
      },
    },
  ],
  webServer: [
    {
      command: `"${path.resolve(__dirname, "../.venv/Scripts/python.exe")}" -m uvicorn server.app:app --port 8000`,
      cwd: path.resolve(__dirname, ".."),
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
  ],
});
