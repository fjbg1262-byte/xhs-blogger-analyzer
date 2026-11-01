/**
 * Phase 1 纯前端 Demo 的无头点击验收。
 *
 * 用法：先启动一个能访问 Demo 的地址（dev / preview / 打包后的本地程序），再运行：
 *   node tests/browser/demo-smoke.cjs
 *   $env:DEMO_BASE_URL="http://127.0.0.1:8123"; node tests/browser/demo-smoke.cjs
 *
 * 依赖本机 Edge 和仓库根目录的 playwright。全部通过时退出码为 0，并输出 JSON 结果。
 */
const { chromium } = require("playwright");

const BASE = process.env.DEMO_BASE_URL || "http://127.0.0.1:4173";

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const checks = [];
  const add = (name, passed) => checks.push([name, Boolean(passed)]);

  await page.goto(`${BASE}/demo`, { waitUntil: "networkidle" });
  add("home", await page.getByRole("heading", { name: "把主页内容，整理成可用的表格" }).isVisible());

  await page.getByRole("button", { name: "整理当前主页" }).click();
  add("collection_counts", await page.locator(".progress-counts").isVisible());
  add("collection_stop", await page.getByRole("button", { name: "停止采集" }).isVisible());
  await page.getByRole("button", { name: "停止采集" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("已停止"), null, { timeout: 5000 });
  add("stopped_keeps_data", await page.locator(".stopped-actions").isVisible());
  add("resume_available", await page.getByRole("button", { name: "继续处理未完成笔记" }).isVisible());
  await page.getByRole("button", { name: "继续处理未完成笔记" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("采集完成"), null, { timeout: 15000 });
  add("collection_complete", await page.getByText("已整理 100 篇笔记", { exact: false }).isVisible());
  add("resume_notice", await page.locator(".retry-ok").isVisible());

  await page.getByRole("button", { name: "查看笔记库" }).click();
  await page.locator(".note-cell").first().click();
  add("note_detail", await page.locator(".note-drawer").isVisible());
  add("note_source_link", (await page.locator(".note-drawer .source-link").innerText()).includes("xiaohongshu.com"));
  await page.locator(".note-drawer header button").click();
  await page.locator(".view-switch button").nth(1).click();
  add("cover_view", (await page.locator(".note-card").count()) > 0);

  await page.locator(".library-tabs button").filter({ hasText: "互动较高" }).click();
  add("high_engagement_tab", (await page.locator(".note-card").count()) > 0);
  await page.locator(".library-tabs button").filter({ hasText: "全部" }).click();
  await page.locator(".filter-button").click();
  add("filter_panel", await page.locator(".filter-panel").isVisible());
  await page.locator(".filter-check").filter({ hasText: "只看未完成采集" }).locator("input").check();
  add("filter_incomplete_only", (await page.locator(".note-card").count()) === 1);
  await page.getByRole("button", { name: "重置筛选" }).click();
  await page.locator(".filter-button").click();

  await page.locator(".library-tabs button").filter({ hasText: "未完成" }).click();
  add("incomplete_filter", (await page.locator(".note-card").count()) === 1);
  await page.locator(".note-card").first().click();
  add("incomplete_reason", await page.locator(".drawer-alert").isVisible());
  await page.locator(".note-drawer header button").click();

  await page.locator(".demo-nav button").filter({ hasText: "账号分析" }).click();
  add("eight_dimensions", (await page.locator(".dimension-card").count()) === 8);
  add("three_topics", (await page.locator(".topic-grid article").count()) === 3);
  await page.locator(".dimension-card button").first().click();
  add("dimension_advice", await page.locator(".dimension-advice").isVisible());
  add("topic_outline", (await page.locator(".topic-grid article").first().locator(".topic-detail li").count()) >= 3);

  await page.locator(".demo-nav button").filter({ hasText: "账号对比" }).click();
  add("comparison_rows", (await page.locator(".compare-row").count()) === 9);
  await page.locator(".compare-select button").filter({ hasText: "小城慢拍" }).click();
  add("comparison_three_accounts", (await page.locator(".compare-row:not(.header) p").count()) === 24);
  add("comparison_week_plan", (await page.locator(".week-plan-grid article").count()) === 5);

  await page.locator(".demo-nav button").filter({ hasText: "飞书交付" }).click();
  await page.getByRole("button", { name: "生成飞书导入包" }).click();
  await page.waitForSelector(".delivery-success", { timeout: 5000 });
  add("feishu_generated", await page.locator(".delivery-success").isVisible());

  await page.locator(".demo-nav button").filter({ hasText: "采集记录" }).click();
  add("history_rows", (await page.locator(".history-table tbody tr").count()) === 4);
  add("history_finish_time", (await page.locator(".history-table .finish-time").count()) === 4);
  add("history_failure_reason", (await page.locator(".history-table .reason-cell").count()) === 2);

  await page.locator(".sidebar-bottom button").filter({ hasText: "设置" }).click();
  add("settings_cards", (await page.locator(".settings-grid article").count()) === 4);

  await page.goto(`${BASE}/demo?page=compare`, { waitUntil: "networkidle" });
  add("deep_link_page", await page.getByRole("heading", { name: "账号对标" }).isVisible());
  await page.locator(".demo-nav button").filter({ hasText: "采集记录" }).click();
  add("url_follows_nav", new URL(page.url()).searchParams.get("page") === "history");

  await browser.close();
  const failed = checks.filter(([, passed]) => !passed);
  console.log(JSON.stringify({ passed: checks.length - failed.length, total: checks.length, checks: Object.fromEntries(checks) }));
  if (failed.length) process.exit(1);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
