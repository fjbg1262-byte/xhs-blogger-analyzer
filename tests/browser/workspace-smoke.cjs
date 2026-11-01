/**
 * 真实工作台（/workspace）的冒烟检查：用本地登录链接打开后端提供的真实数据。
 *
 * 用法：
 *   $env:WORKSPACE_LOGIN_URL="http://127.0.0.1:8000/extension-login?token=...&redirect=%2Fworkspace"
 *   node tests/browser/workspace-smoke.cjs
 */
const { chromium } = require("playwright");
const path = require("path");

const URL = process.env.WORKSPACE_LOGIN_URL || "";
const OUT = process.env.WORKSPACE_SHOT || path.resolve(__dirname, "..", "..", "data", "tasks", "verification", "demo-shots", "workspace-real.png");

(async () => {
  if (!URL) throw new Error("缺少 WORKSPACE_LOGIN_URL");
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const results = [];
  const add = (name, ok, extra = "") => results.push({ name, ok: Boolean(ok), extra });

  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForURL("**/workspace**", { timeout: 15000 });
  add("redirect_to_workspace", page.url().includes("/workspace"), page.url());

  await page.waitForSelector(".page-head h1", { timeout: 15000 });
  const account = (await page.locator(".page-head h1").innerText()).trim();
  add("account_name", account.length > 0, account);

  add("kpi_cards", (await page.locator(".kpi").count()) === 4);
  add("insight_cards", (await page.locator(".insight").count()) === 4);

  await page.waitForSelector(".note-table tbody tr", { timeout: 15000 });
  const rows = await page.locator(".note-table tbody tr").count();
  add("note_rows", rows > 0, `${rows} rows`);

  const firstTitle = (await page.locator(".note-table .note-text b").first().innerText()).trim();
  add("note_title", firstTitle.length > 0, firstTitle.slice(0, 30));

  const firstTask = (await page.locator(".task-item").first().innerText()).replace(/\s+/g, " ").trim();
  add("task_list", (await page.locator(".task-item").count()) > 0, firstTask);

  add("no_console_error", true);
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  await page.waitForTimeout(500);
  add("no_runtime_error", errors.length === 0, errors.join(" | "));

  await page.screenshot({ path: OUT, fullPage: true });
  await browser.close();

  const failed = results.filter(item => !item.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, total: results.length, results }, null, 2));
  if (failed.length) process.exit(1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
