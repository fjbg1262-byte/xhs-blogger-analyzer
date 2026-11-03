/**
 * 八维分析页检查（Phase 5）：需要先写入一份分析结果。
 *
 *   .venv\Scripts\python.exe scripts/dev_seed_analysis.py --task 8
 *   $env:WORKSPACE_LOGIN_URL="http://127.0.0.1:8000/extension-login?token=...&redirect=%2Fworkspace"
 *   node tests/browser/analysis-smoke.cjs
 */
const path = require("path");
const { chromium } = require("playwright");

const URL = process.env.WORKSPACE_LOGIN_URL || "";
const OUT = path.resolve(__dirname, "..", "..", "data", "tasks", "verification", "demo-shots", "workspace-analysis.png");

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

  // 切到八维分析
  await page.locator(".view-tabs button").filter({ hasText: "八维分析" }).click();
  await page.waitForSelector(".analysis", { timeout: 15000 });
  await page.waitForSelector(".dimension-card", { timeout: 20000 });

  add("analysis_tab", await page.locator(".analysis").isVisible());
  add("headline", await page.locator(".headline").isVisible());

  const dims = await page.locator(".dimension-card").count();
  add("eight_dimensions", dims === 8, `${dims} dims`);

  const badges = await page.locator(".dimension-card header i").allInnerTexts();
  add("status_badges", badges.includes("有依据") && badges.includes("数据有限") && badges.includes("未获取"), badges.join("/"));

  const unavailable = await page.locator(".dimension-card .empty").count();
  add("missing_data_explicit", unavailable >= 1, `${unavailable} unavailable`);

  const drafts = await page.locator(".draft").count();
  add("three_drafts", drafts === 3, `${drafts} drafts`);

  const titles = await page.locator(".draft .title-options > div").count();
  const outline = await page.locator(".draft").first().locator("ol li").count();
  add("draft_details", titles === 6 && outline >= 3, `${titles} titles`);

  const quotes = await page.locator(".dimension-card blockquote").count();
  add("evidence_quotes", quotes >= 4, `${quotes} quotes`);

  // 复核确认（重复运行时报告可能已经确认过）
  const approve = page.getByRole("button", { name: /我已复核，确认交付/ });
  const pending = await approve.isVisible().catch(() => false);
  if (pending) {
    await approve.click();
    await page.waitForTimeout(800);
  }
  const approved = (await page.locator(".delivery h3").innerText()).includes("已确认");
  add("review_gate", pending || approved, pending ? "本次点击确认" : "报告已是已确认状态");
  add("approved_state", approved);

  // 模型未配置时（切到没有分析的任务）提示配置，而不是空白
  await page.locator(".task-item").filter({ hasText: "#7" }).click();
  await page.waitForTimeout(800);
  await page.locator(".view-tabs button").filter({ hasText: "八维分析" }).click();
  await page.waitForTimeout(600);
  add("model_notice", await page.locator(".notice").isVisible());

  await page.locator(".task-item").filter({ hasText: "#8" }).click();
  await page.waitForTimeout(800);
  await page.locator(".view-tabs button").filter({ hasText: "八维分析" }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT, fullPage: true });

  await browser.close();
  const failed = results.filter(item => !item.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, total: results.length, results }, null, 2));
  if (failed.length) process.exit(1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
