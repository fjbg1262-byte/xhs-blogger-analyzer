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

  // 100 篇分页：每页 50
  const page1 = await page.locator(".note-table tbody tr").count();
  await page.locator(".pager button").filter({ hasText: "下一页" }).click();
  await page.waitForTimeout(400);
  const page2 = await page.locator(".note-table tbody tr").count();
  const pagerText = (await page.locator(".pager span").innerText()).trim();
  add("pagination", page1 === 50 && page2 === 50 && pagerText.includes("2 / 2"), `${page1}/${page2} ${pagerText}`);

  // 服务端筛选：切到「图文」，总数与 tab 计数一致
  await page.locator(".library-tabs button").filter({ hasText: "图文" }).click();
  await page.waitForTimeout(500);
  const imagePager = (await page.locator(".pager span").innerText()).trim();
  const firstType = (await page.locator(".note-table tbody tr .type-pill").first().innerText()).trim();
  add("filter_type", imagePager.includes("60") && firstType === "图文", `${imagePager} / ${firstType}`);
  await page.locator(".library-tabs button").filter({ hasText: "全部" }).click();
  await page.waitForTimeout(500);

  // 搜索走服务端
  await page.locator(".search-box input").fill("AI");
  await page.waitForTimeout(800);
  const searchPager = (await page.locator(".pager span").innerText()).trim();
  add("filter_search", /共 \d+ 篇/.test(searchPager) && !searchPager.includes("共 100 篇"), searchPager);
  await page.locator(".search-box input").fill("");
  await page.waitForTimeout(800);

  // 多选与批量导出入口
  await page.locator(".note-table tbody tr .check input").first().check();
  await page.waitForTimeout(200);
  const selection = (await page.locator(".selection-bar").innerText()).replace(/\s+/g, " ").trim();
  add("multi_select", selection.includes("已选择 1 篇"), selection);
  await page.locator(".selection-bar .link-btn").filter({ hasText: "清空" }).click();

  // 导出按钮：Excel / CSV / 飞书
  const exportButtons = (await page.locator(".head-actions").innerText()).replace(/\s+/g, " ");
  add("export_buttons", exportButtons.includes("导出 CSV") && exportButtons.includes("导出 Excel") && exportButtons.includes("飞书"), exportButtons.slice(0, 60));

  // 笔记详情按需加载：列表只带预览，打开抽屉再取正文
  await page.locator(".note-table tbody tr").first().click();
  await page.waitForSelector(".drawer", { timeout: 8000 });
  await page.waitForSelector(".body-meta", { timeout: 10000 });
  const bodyMeta = (await page.locator(".body-meta").innerText()).trim();
  add("note_detail_on_demand", bodyMeta.includes("正文"), bodyMeta);
  await page.locator(".drawer header button").click();

  // 新建采集表单：打开、校验、收起（不真的发起网络采集）
  await page.locator(".new-btn").click();
  add("collection_form", await page.locator(".capture-form").isVisible());
  await page.locator(".capture-form input").fill("https://example.com/not-xhs");
  await page.getByRole("button", { name: "开始采集" }).click();
  await page.waitForTimeout(300);
  const formError = (await page.locator(".form-error").innerText()).trim();
  add("collection_validation", formError.includes("小红书"), formError);
  await page.getByRole("button", { name: "收起" }).click();

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
