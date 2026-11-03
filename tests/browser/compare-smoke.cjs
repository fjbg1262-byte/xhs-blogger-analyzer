/**
 * 账号对比页检查（Phase 6）。
 *
 *   $env:WORKSPACE_LOGIN_URL="http://127.0.0.1:8000/extension-login?token=...&redirect=%2Fworkspace"
 *   node tests/browser/compare-smoke.cjs
 */
const path = require("path");
const { chromium } = require("playwright");

const URL = process.env.WORKSPACE_LOGIN_URL || "";
const OUT = path.resolve(__dirname, "..", "..", "data", "tasks", "verification", "demo-shots", "workspace-compare.png");

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
  await page.waitForSelector(".note-table tbody tr", { timeout: 20000 });

  // 深链接：?task=7 直接选中 #7
  await page.goto(page.url().split("?")[0] + "?task=7", { waitUntil: "networkidle" });
  await page.waitForSelector(".page-head h1", { timeout: 20000 });
  add("deep_link_task", (await page.locator(".eyebrow").first().innerText()).includes("#7"));

  await page.locator(".view-tabs button").filter({ hasText: "账号对比" }).click();
  await page.waitForSelector(".picker", { timeout: 20000 });
  const picks = await page.locator(".pick").count();
  add("account_picker", picks >= 2, `${picks} accounts`);
  add("default_two_selected", (await page.locator(".pick.active").count()) === 2);

  await page.getByRole("button", { name: "开始对比" }).click();
  await page.waitForSelector(".compare-row", { timeout: 20000 });

  const rows = await page.locator(".compare-row").count();
  add("eight_rows", rows === 9, `${rows} rows (header + 8)`);

  const cells = await page.locator(".compare-row:not(.header) p").count();
  add("two_columns", cells === 16, `${cells} cells`);

  const takeaways = await page.locator(".takeaways article").count();
  add("takeaways", takeaways >= 1, `${takeaways} cards`);

  const plan = await page.locator(".plan-grid article").count();
  add("week_plan", plan === 5, `${plan} items`);

  add("boundary", (await page.locator(".boundary").innerText()).includes("公开互动"));

  // 再选一个账号，对比 3 个
  await page.locator(".pick").nth(2).click();
  await page.getByRole("button", { name: "重新对比" }).click();
  await page.waitForTimeout(1200);
  const cells3 = await page.locator(".compare-row:not(.header) p").count();
  add("three_accounts", cells3 === 24, `${cells3} cells`);

  await page.screenshot({ path: OUT, fullPage: true });
  await browser.close();

  const failed = results.filter(item => !item.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, total: results.length, results }, null, 2));
  if (failed.length) process.exit(1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
