/**
 * 给 Demo 的每个页面截图，用于视觉复核。
 *
 * 用法：
 *   node tests/browser/demo-shots.cjs
 *   $env:DEMO_BASE_URL="http://127.0.0.1:8123"; $env:DEMO_SHOTS_OUT="C:\\tmp\\shots"; node tests/browser/demo-shots.cjs
 *
 * 默认输出到 data/tasks/verification/demo-shots（不进入版本库）。
 */
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.env.DEMO_BASE_URL || "http://127.0.0.1:4173";
const ROOT = path.resolve(__dirname, "..", "..");
const OUT = process.env.DEMO_SHOTS_OUT || path.join(ROOT, "data", "tasks", "verification", "demo-shots");

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const shots = [
    ["home", 1440, 1000],
    ["library", 1440, 1000],
    ["analysis", 1440, 1000],
    ["compare", 1440, 1000],
    ["feishu", 1440, 1000],
    ["history", 1440, 1000],
    ["compare-narrow", 1280, 860],
  ];
  for (const [name, width, height] of shots) {
    const page = await browser.newPage({ viewport: { width, height } });
    const key = name.replace("-narrow", "");
    await page.goto(`${BASE}/demo?page=${key}`, { waitUntil: "networkidle" });
    if (key === "library") {
      await page.locator(".filter-button").click();
    }
    if (key === "analysis") {
      await page.locator(".dimension-card button").first().click();
    }
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
    await page.close();
  }
  await browser.close();
  console.log("saved", OUT);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
