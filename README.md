# 小红书博主深度分析工具

> AI 驱动的小红书博主研究管线，一键输出 8 维度深度分析报告。

输入任意小红书博主主页 URL，自动完成：**数据采集 → 量化分析 → 结构化报告**，全程 < 10 分钟。

---

## 效果预览

分析 [@数字生命卡兹克](https://www.xiaohongshu.com/user/profile/62c98736000000001501e075) 的 413 条笔记后产出的报告：

| 报告 | 内容 |
|------|------|
| [博主画像卡片](reports/00_博主画像卡片.md) | 定位、人设、受众 |
| [内容结构分析](reports/01_内容结构分析.md) | 8 类主题分布、图文 vs 视频对比 |
| [标题与文案分析](reports/02_标题与文案分析.md) | 8 种标题公式、Hook 模式 |
| [互动归因分析](reports/03_互动归因分析.md) | 帕累托分析、Top vs Bottom 对比 |
| [成长轨迹分析](reports/04_成长轨迹分析.md) | 4 阶段划分、关键转折点 |
| [标签与SEO分析](reports/05_标签与SEO分析.md) | 标签组合策略、效率排名 |
| [商业化分析](reports/06_商业化分析.md) | 变现路径、商业 vs 自然对比 |
| [竞争定位分析](reports/07_竞争定位分析.md) | 生态位、可复制性 |
| [策略建议与行动计划](reports/08_策略建议与行动计划.md) | 模板库、行动清单 |

---

## 快速开始

### 前置条件

- **Node.js** 18+（用于 Playwright 数据采集）
- **Python** 3.8+（用于分析和报告生成）
- **Chrome/Edge**（Playwright 会下载 Chromium）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/fjbg1262-byte/xhs-blogger-analyzer
cd xhs-blogger-analyzer

# 2. 安装 Node.js 依赖
npm install

# 3. 安装 Playwright 浏览器（首次需要）
npx playwright install chromium

# 4. 安装 Claude Code Skill（可选，用 Claude 自动执行）
cp skill/xhs-blogger-deep-research.md ~/.claude/skills/
```

### 使用

#### 方式 A：Claude Code 自动执行（推荐）

```bash
# 打开 Claude Code
claude

# 在对话中输入：
/xhs-blogger-deep-research

# 然后按 Claude 的引导操作（提供博主 URL + Cookie 即可）
```

#### 方式 B：手动分步执行

```bash
# Step 1: 采集笔记数据
node scrape.js --url "https://www.xiaohongshu.com/user/profile/用户ID" --cookies cookies.json

# Step 2: 量化分析
python analyze_all.py --notes ./data/all_notes.json --output ./data/results.json

# Step 3: 生成报告
python generate_reports.py --input ./data/results.json --output ./reports
```

---

## 获取 Cookie

小红书 API 需要登录态，需要从浏览器导出 Cookie：

1. 用 Chrome 打开 [xiaohongshu.com](https://www.xiaohongshu.com) 并登录
2. 按 `F12` 打开开发者工具 → `Application` → `Cookies` → `xiaohongshu.com`
3. 全选 Cookie 条目 → `Export as JSON`（或用 [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) 插件）
4. 保存为 `cookies.json` 放到项目目录

> ⚠️ Cookie 有有效期，过期后需要重新导出。Cookie 文件请勿提交到 Git。

---

## 输出说明

```
xhs-blogger-analyzer/
├── data/
│   └── all_notes.json      # 采集到的笔记原始数据
│   └── results.json         # 量化分析结果（所有指标）
├── reports/                 # 生成的报告文件
│   ├── 00_博主画像卡片.md
│   ├── 01_内容结构分析.md
│   ├── ...
│   └── README.md            # 报告索引
```

---

## 分析框架

| 维度 | 方法 | 输出 |
|------|------|------|
| 博主画像 | 人设要素拆解 + 受众推断 | 画像卡片 |
| 内容结构 | 8 类主题分类 + 图文/视频对比 | 分布表 |
| 标题与文案 | 8 特征量化 + 8 公式检测 + Hook 分析 | 公式库 |
| 互动归因 | 帕累托分析 + Top/Bottom 对比 | 归因表 |
| 成长轨迹 | 断点检测 + 阶段划分 + 转折点分析 | 时间线 |
| 标签与SEO | 频率统计 + 共现分析 + 效率排名 | 标签排行 |
| 商业化 | 商业信号检测 + 变现路径分析 | 商业化报告 |
| 竞争定位 | 生态位 + 可复制性 | 定位分析 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 浏览器自动化 | Playwright (Chromium) |
| 数据采集 | API 拦截 + Cookie 注入 |
| 量化分析 | Python 标准库 |
| 报告生成 | Python Markdown |
| AI 编排 | Claude Code Skill |

---

## 免责声明

- 本工具仅用于**学术研究和内容分析**
- 采集的数据均为**公开可见信息**
- 请遵守小红书用户协议，合理使用
- 不得用于任何商业爬取、数据倒卖等违规行为

---

## License

MIT
