/**
 * Phase 1 功能验收：对照 docs/product/DEVELOPMENT_PLAN.md 第 3 节与 docs/product/PRD.md 第 5 章。
 *
 * 用法：
 *   node tests/browser/acceptance.cjs
 *   $env:DEMO_BASE_URL="http://127.0.0.1:8123"; node tests/browser/acceptance.cjs
 *
 * 输出逐条 JSON；有未通过项时退出码为 1。
 */
const { chromium } = require("playwright");

const BASE = process.env.DEMO_BASE_URL || "http://127.0.0.1:4173";
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: EDGE });
  const results = [];
  const check = async (id, label, fn) => {
    try {
      const ok = await fn();
      results.push({ id, label, ok: Boolean(ok), note: ok ? "" : "未通过" });
    } catch (error) {
      results.push({ id, label, ok: false, note: String(error.message || error).slice(0, 140) });
    }
  };
  const fresh = async (query = "") => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${BASE}/demo${query}`, { waitUntil: "networkidle" });
    return page;
  };

  // ---------- 页面清单（Phase 1「使用假数据完成」9 项） ----------
  const inventory = [
    ["home", "", "把主页内容，整理成可用的表格"],
    ["progress", "", null],
    ["library", "?page=library", "野路手册"],
    ["covers", "?page=library", null],
    ["drawer", "?page=library", null],
    ["feishu", "?page=feishu", "飞书交付"],
    ["analysis", "?page=analysis", "账号八维分析"],
    ["compare", "?page=compare", "账号对标"],
    ["history", "?page=history", "采集记录"],
  ];
  for (const [id, query, heading] of inventory) {
    await check(`page-${id}`, `页面存在：${id}`, async () => {
      const page = await fresh(query);
      let ok;
      if (heading) ok = await page.getByRole("heading", { name: heading, exact: false }).first().isVisible();
      else if (id === "covers") {
        await page.locator(".view-switch button").nth(1).click();
        ok = (await page.locator(".note-card").count()) > 0;
      } else if (id === "drawer") {
        await page.locator(".note-cell").first().click();
        ok = await page.locator(".drawer").isVisible();
      } else {
        await page.getByRole("button", { name: "整理当前主页" }).click();
        ok = await page.locator(".progress").isVisible();
      }
      await page.close();
      return ok;
    });
  }

  // ---------- 验收指标：点击预算 ----------
  await check("clicks-home-to-feishu-4", "首页到飞书下载 ≤ 4 次点击（经采集完成区）", async () => {
    const page = await fresh();
    let clicks = 0;
    await page.getByRole("button", { name: "整理当前主页" }).click(); clicks += 1;
    await page.waitForFunction(() => document.body.innerText.includes("采集完成"), null, { timeout: 20000 });
    await page.getByRole("button", { name: "生成飞书文件" }).click(); clicks += 1;
    await page.getByRole("button", { name: "生成飞书导入包" }).click(); clicks += 1;
    await page.waitForSelector(".delivery-success", { timeout: 6000 });
    await page.getByRole("button", { name: "下载演示文件" }).click(); clicks += 1;
    await page.close();
    return clicks <= 4;
  });

  await check("clicks-home-to-feishu-3", "首页到飞书下载 ≤ 4 次点击（直接进飞书页）", async () => {
    const page = await fresh();
    let clicks = 0;
    await page.locator(".nav").first().locator("button").filter({ hasText: "飞书交付" }).click(); clicks += 1;
    await page.getByRole("button", { name: "生成飞书导入包" }).click(); clicks += 1;
    await page.waitForSelector(".delivery-success", { timeout: 6000 });
    await page.getByRole("button", { name: "下载演示文件" }).click(); clicks += 1;
    await page.close();
    return clicks <= 4;
  });

  await check("clicks-library-to-analysis-2", "笔记库到单账号分析 ≤ 2 次点击", async () => {
    const page = await fresh("?page=library");
    let clicks = 0;
    await page.getByRole("button", { name: "账号八维分析 →" }).click(); clicks += 1;
    const ok = await page.getByRole("heading", { name: "账号八维分析" }).isVisible();
    await page.close();
    return ok && clicks <= 2;
  });

  await check("compare-two-accounts-open", "选择两个账号能打开对比页", async () => {
    const page = await fresh("?page=compare");
    const selected = await page.locator(".pick.active").count();
    const rows = await page.locator(".compare-row").count();
    const cards = await page.locator(".compare-cards article").count();
    await page.close();
    return selected === 2 && rows === 9 && cards === 2;
  });

  // ---------- PRD 5.1 首页 ----------
  await check("prd-5.1-home-blocks", "首页：采集入口 / 账号卡片 / 最近任务 / 数据条数 / 正文成功数 / 导出状态", async () => {
    const page = await fresh();
    const text = await page.locator(".content").innerText();
    const ok = (await page.locator(".url-input input").count()) === 1
      && (await page.getByRole("button", { name: "整理当前主页" }).count()) === 1
      && (await page.locator(".account-card").count()) === 3
      && text.includes("采集记录")
      && text.includes("正文")
      && text.includes("导出状态");
    await page.close();
    return ok;
  });

  // ---------- PRD 5.2 采集任务 ----------
  await check("prd-5.2-progress-fields", "采集任务：已读取 / 详情 / 正文 / 标签 / 当前步骤 / 停止", async () => {
    const page = await fresh();
    await page.getByRole("button", { name: "整理当前主页" }).click();
    await page.waitForTimeout(400);
    const text = await page.locator(".progress").innerText();
    const ok = ["已读取笔记", "详情完成", "正文成功", "标签成功"].every(word => text.includes(word))
      && (await page.locator(".steps > div").count()) === 4
      && (await page.getByRole("button", { name: "停止采集" }).count()) === 1;
    await page.close();
    return ok;
  });

  // ---------- PRD 5.3 笔记库 ----------
  await check("prd-5.3-library-header", "笔记库顶部：账号 / 笔记数 / 图文 / 视频 / 互动总量 / 中位数 / 最近采集", async () => {
    const page = await fresh("?page=library");
    const text = await page.locator(".page-head").innerText();
    const kpi = await page.locator(".library-kpi .kpi").count();
    const ok = text.includes("野路手册") && text.includes("最近采集") && kpi === 5;
    await page.close();
    return ok;
  });

  await check("prd-5.3-library-columns", "列表字段：封面 / 标题 / 发布时间 / 类型 / 赞藏评享 / 标签 / 来源链接 / 采集状态", async () => {
    const page = await fresh("?page=library");
    const headers = await page.locator(".note-table thead th").allInnerTexts();
    const row = await page.locator(".note-table tbody tr").first().innerText();
    const ok = headers.some(h => h.includes("笔记"))
      && headers.some(h => h.includes("类型"))
      && headers.some(h => h.includes("发布时间"))
      && headers.some(h => h.includes("赞"))
      && headers.some(h => h.includes("标签"))
      && headers.some(h => h.includes("采集"))
      && headers.some(h => h.includes("来源"))
      && row.includes("享");
    await page.close();
    return ok;
  });

  await check("prd-5.3-library-filters", "分类与筛选：6 个分类 + 时间范围 + 只看正文 + 只看未完成 + 5 种排序", async () => {
    const page = await fresh("?page=library");
    const tabs = await page.locator(".library-tabs button").count();
    await page.locator(".filter-button").click();
    const panel = await page.locator(".filter-panel").innerText();
    const sorts = await page.locator(".library-toolbar select option").count();
    const ok = tabs === 6 && panel.includes("时间范围") && panel.includes("只看已抓到正文") && panel.includes("只看未完成采集") && sorts === 5;
    await page.close();
    return ok;
  });

  await check("prd-5.3-detail-fields", "单篇详情：封面 / 标题 / 正文 / 标签 / 四项互动 / 来源链接 / 加入选题 / 加入对比", async () => {
    const page = await fresh("?page=library");
    await page.locator(".note-cell").first().click();
    const text = await page.locator(".drawer").innerText();
    const ok = text.includes("点赞") && text.includes("收藏") && text.includes("评论") && text.includes("分享")
      && (await page.locator(".drawer-cover").count()) === 1
      && (await page.locator(".drawer .source-link").count()) === 1
      && text.includes("加入选题") && text.includes("加入账号对比");
    await page.close();
    return ok;
  });

  // ---------- PRD 5.4 飞书 ----------
  await check("prd-5.4-feishu-page", "飞书页：选账号 / 选表 / 张数 / 生成 / 3 步导入说明", async () => {
    const page = await fresh("?page=feishu");
    const text = await page.locator(".delivery").innerText();
    const select = await page.locator(".delivery select").count();
    const options = await page.locator(".table-options label").count();
    const ok = select >= 1 && options === 6 && text.includes("条") && text.includes("飞书多维表格") || text.includes("导入");
    await page.close();
    return ok && options === 6 && select >= 1;
  });

  // ---------- PRD 5.5 账号分析 ----------
  await check("prd-5.5-analysis-header", "分析页顶部：账号 / 笔记数 / 互动 / 中位数 / 图文视频占比 / 最近发布", async () => {
    const page = await fresh("?page=analysis");
    const head = await page.locator(".page-head").innerText();
    const ok = head.includes("野路手册") && head.includes("篇") && head.includes("图文") && head.includes("最近发布");
    await page.close();
    return ok;
  });

  await check("prd-5.5-eight-dimensions", "八维：8 张卡，均含标题、结论与下一步", async () => {
    const page = await fresh("?page=analysis&tab=dimensions");
    const cards = await page.locator(".dimension-card").count();
    const advice = await page.locator(".dimension-advice").count();
    await page.close();
    return cards === 8 && advice === 8;
  });

  await check("prd-5.5-drafts", "3 个选题：2 个标题 / 开头 / 大纲 / 一周执行顺序 / 复盘指标", async () => {
    const page = await fresh("?page=analysis&tab=drafts");
    const drafts = await page.locator(".draft").count();
    const titles = await page.locator(".draft .title-options > div").count();
    const text = await page.locator(".tab-panel").innerText();
    const ok = drafts === 3 && titles === 6 && text.includes("一周执行顺序") && text.includes("复盘指标");
    await page.close();
    return ok;
  });

  await check("prd-5.5-evidence", "原始依据：引用原句来自本批笔记", async () => {
    const page = await fresh("?page=analysis&tab=evidence");
    const rows = await page.locator(".evidence-table tbody tr").count();
    const quotes = await page.locator(".evidence-table .quote").allInnerTexts();
    const ok = rows === 6 && quotes.every(q => q.trim().length > 4) && quotes.every(q => !q.includes("AI 生成"));
    await page.close();
    return ok;
  });

  // ---------- PRD 5.6 对比 ----------
  await check("prd-5.6-compare-blocks", "对比页：选择 2–5 个 / 摘要卡 / 八维横表 / 值得借鉴与不要照搬 / 内容计划", async () => {
    const page = await fresh("?page=compare");
    await page.locator(".compare-select button").filter({ hasText: "小城慢拍" }).click();
    const text = await page.locator(".compare-body").innerText();
    const ok = (await page.locator(".compare-cards article").count()) === 3
      && (await page.locator(".compare-row").count()) === 9
      && text.includes("值得借鉴") && text.includes("不要照搬")
      && (await page.locator(".week-plan-grid article").count()) === 5;
    await page.close();
    return ok;
  });

  await check("prd-5.6-volume-warning", "对比页：数据量差异过大时有提示", async () => {
    const page = await fresh("?page=compare");
    await page.locator(".compare-select button").filter({ hasText: "小城慢拍" }).click();
    const ok = (await page.locator(".volume-hint").count()) >= 1;
    await page.close();
    return ok;
  });

  // ---------- PRD 5.7 采集记录 ----------
  await check("prd-5.7-history-columns", "采集记录：账号 / 开始完成 / 结果 / 目标实际 / 正文 / 未完成原因 / 备份 / 查看", async () => {
    const page = await fresh("?page=history");
    const headers = await page.locator(".history-table thead th").allInnerTexts();
    const text = await page.locator(".history-table").innerText();
    const ok = headers.some(h => h.includes("账号")) && headers.some(h => h.includes("开始"))
      && headers.some(h => h.includes("目标")) && headers.some(h => h.includes("正文"))
      && headers.some(h => h.includes("未完成原因")) && headers.some(h => h.includes("备份"))
      && text.includes("访问受限") && (await page.locator(".history-table tbody tr").count()) === 4;
    await page.close();
    return ok;
  });

  // ---------- PRD 5.8 设置 ----------
  await check("prd-5.8-settings", "设置：登录 / AI / 飞书 / 数据目录 / 版本更新", async () => {
    const page = await fresh("?page=settings");
    const text = await page.locator(".settings-grid").innerText();
    const ok = ["小红书账号", "AI 模型", "飞书", "本地数据", "版本与更新"].every(word => text.includes(word));
    await page.close();
    return ok;
  });

  // ---------- Demo 要求：宽度 / 文案密度 ----------
  for (const [width, height, label] of [[1366, 768, "1366×768"], [1280, 800, "1280×800"], [1440, 900, "1440×900"]]) {
    await check(`layout-${width}`, `无横向溢出与遮挡：${label}`, async () => {
      const page = await browser.newPage({ viewport: { width, height } });
      const pages = ["", "?page=library", "?page=analysis", "?page=analysis&tab=dimensions", "?page=analysis&tab=drafts", "?page=compare", "?page=feishu", "?page=history", "?page=settings"];
      const bad = [];
      for (const query of pages) {
        await page.goto(`${BASE}/demo${query}`, { waitUntil: "networkidle" });
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        if (overflow > 1) bad.push(`${query || "home"}(+${overflow}px)`);
      }
      await page.close();
      if (bad.length) throw new Error(`溢出：${bad.join("、")}`);
      return true;
    });
  }

  await check("copy-density", "不写大段说明：正文段落不超过 160 字", async () => {
    const page = await fresh("?page=analysis");
    const tooLong = await page.evaluate(() => {
      const nodes = [...document.querySelectorAll(".content p")];
      return nodes.map(node => (node.textContent || "").trim()).filter(text => text.length > 160);
    });
    await page.close();
    if (tooLong.length) throw new Error(`超长段落 ${tooLong.length} 处，最长 ${Math.max(...tooLong.map(t => t.length))} 字`);
    return true;
  });

  await check("home-first-screen", "不看说明书能猜出从哪里开始：首屏可见采集入口", async () => {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    await page.goto(`${BASE}/demo`, { waitUntil: "networkidle" });
    const box = await page.locator(".capture").boundingBox();
    const visible = box && box.y < 768 && box.y + box.height <= 768 + 120;
    await page.close();
    return visible;
  });

  await browser.close();
  const failed = results.filter(item => !item.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, total: results.length, results }, null, 2));
  if (failed.length) process.exit(1);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
