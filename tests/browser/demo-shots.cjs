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
    ["home", 1440, 1000, ""],
    ["library", 1440, 1000, ""],
    ["analysis", 1440, 1000, ""],
    ["analysis-dimensions", 1440, 1000, "?page=analysis&tab=dimensions"],
    ["analysis-drafts", 1440, 1000, "?page=analysis&tab=drafts"],
    ["analysis-evidence", 1440, 1000, "?page=analysis&tab=evidence"],
    ["compare", 1440, 1000, ""],
    ["feishu", 1440, 1000, ""],
    ["history", 1440, 1000, ""],
    ["settings", 1440, 1000, ""],
    ["compare-narrow", 1280, 860, ""],
  ];
  for (const [name, width, height, query] of shots) {
    const page = await browser.newPage({ viewport: { width, height } });
    const key = name.replace(/-.*$/, "");
    const url = query ? `${BASE}/demo${query}` : `${BASE}/demo?page=${key}`;
    await page.goto(url, { waitUntil: "networkidle" });
    if (key === "library") {
      await page.locator(".filter-button").click();
    }
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
    await page.close();
  }
  // 交互状态：采集进行中 / 已停止 / 完成，封面视图、详情抽屉、飞书生成成功
  const statePage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await statePage.goto(`${BASE}/demo`, { waitUntil: "networkidle" });
  await statePage.getByRole("button", { name: "整理当前主页" }).click();
  await statePage.waitForTimeout(1000);
  await statePage.screenshot({ path: path.join(OUT, "home-progress.png"), fullPage: true });
  await statePage.getByRole("button", { name: "停止采集" }).click();
  await statePage.waitForTimeout(300);
  await statePage.screenshot({ path: path.join(OUT, "home-stopped.png"), fullPage: true });
  await statePage.getByRole("button", { name: "继续处理未完成笔记" }).click();
  await statePage.waitForFunction(() => document.body.innerText.includes("采集完成"), null, { timeout: 15000 });
  await statePage.waitForTimeout(300);
  await statePage.screenshot({ path: path.join(OUT, "home-done.png"), fullPage: true });
  await statePage.close();

  const libPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await libPage.goto(`${BASE}/demo?page=library`, { waitUntil: "networkidle" });
  await libPage.locator(".view-switch button").nth(1).click();
  await libPage.waitForTimeout(300);
  await libPage.screenshot({ path: path.join(OUT, "library-covers.png"), fullPage: true });
  await libPage.locator(".view-switch button").first().click();
  await libPage.locator(".note-cell").first().click();
  await libPage.waitForTimeout(300);
  await libPage.screenshot({ path: path.join(OUT, "library-drawer.png"), fullPage: true });
  await libPage.close();

  const feishuPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await feishuPage.goto(`${BASE}/demo?page=feishu`, { waitUntil: "networkidle" });
  await feishuPage.getByRole("button", { name: "生成飞书导入包" }).click();
  await feishuPage.waitForSelector(".delivery-success", { timeout: 5000 });
  await feishuPage.screenshot({ path: path.join(OUT, "feishu-done.png"), fullPage: true });
  await feishuPage.close();

  await browser.close();
  console.log("saved", OUT);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
