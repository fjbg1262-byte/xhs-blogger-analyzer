# 小红书内容整理与 AI 交付

当前开发版本：应用 `0.3.0-beta.6`，浏览器扩展 `0.4.0`。

把可访问主页返回的最多100篇公开笔记整理成可搜索、筛选和导出的笔记库，再把固定的一批内容接入 AI 工作台。客户填写目标后，系统生成结合原笔记内容的账号解读、3个原创选题、每组2个标题、开头和正文大纲。结果必须人工复核后才能导出 HTML 或 PDF。

## 当前能力

- 采集：主页分页、逐篇详情、限重试、停止保留数据、部分完成导出。
- 整理：28列 Excel、UTF-8 CSV、飞书单表导入版；数值、空白和0区分。
- AI：支持 OpenAI、Claude 及 OpenAI 兼容接口；卖家配置自己的 Key，客户不提供密钥。
- 内容对应：AI写到的原句必须来自本批笔记；未知笔记ID或不存在的内容不会进入交付结果。
- 隔离：笔记库变化、生成规则升级或运行中断后，旧结果不能确认或下载。
- 复核：未确认报告只能预览草稿；确认后才开放正式 HTML/PDF 下载。
- 安全：表格和报告不导出 API Key、Cookie、数据库路径、内部日志或模型请求原文。

## 产品演示（纯前端 Demo）

Phase 1 的纯前端 Demo 就是本地程序的入口页，产品名「薯光」：启动后打开 `http://127.0.0.1:8000/` 会直接进入 Demo，开发时 `npm run dev` 后访问 `/demo`。所有数据为模拟数据，不访问小红书；右上角「进入真实工具」才是需要登录的笔记库。

- 页面：首页与采集进度、笔记库（表格 / 封面）、单篇详情、账号八维分析（经营总览 / 八维解读 / 3 个选题与草稿 / 原始依据）、2 至 5 个账号对标、飞书交付、采集记录、设置。
- 深链接：每页都可以单独打开给评审，例如 `?page=compare`、`?page=analysis&tab=drafts`；点击左侧导航时地址栏会同步当前页，刷新不丢位置。
- 功能验收：`node tests/browser/acceptance.cjs`，对照开发顺序 Phase 1 与 PRD 第 5 章逐条检查，明细见 [Phase 1 验收记录](docs/PHASE1_ACCEPTANCE.md)。
- 点击验收：`node tests/browser/demo-smoke.cjs`（用本机 Edge 无头跑完整点击流程）。
- 页面截图：`node tests/browser/demo-shots.cjs`，输出到 `data/tasks/verification/demo-shots/`。

## 从这里开始

- [产品、字段和 AI 交付规则](docs/ORGANIZER_SPEC.md)
- [安装、AI 配置、复核与导出](docs/ORGANIZER_USER_GUIDE.md)
- [目录、版本和构建规则](docs/PROJECT_LAYOUT.md)
- [当前进度与验证](docs/IMPLEMENTATION_STATUS.md)
- [Phase 1 前端验收记录](docs/PHASE1_ACCEPTANCE.md)
- [测试记录及真实环境待验收项](docs/VERIFICATION.md)
- [商品化竞品拆解、产品定位、飞书规范与开发路线](docs/product/README.md)

## 本地开发

保留现有 `.venv`；新环境使用 Python 3.10 并安装 `requirements.lock.txt`，在 `frontend` 和 `spider_xhs` 中分别执行 `npm ci`。运行 `scripts/start_local.ps1`。固定开发扩展目录是根目录下的 `browser-extension`。

测试：`.venv\Scripts\python.exe -m unittest discover -s tests -v`。

前端构建：在 `frontend` 执行 `npm run build`。

交付构建：`powershell -ExecutionPolicy Bypass -File scripts/build_organizer.ps1 -Version 0.3.0-beta.6`。构建脚本会生成源码快照、EXE目录、前端资源、浏览器扩展、自检、密钥/运行数据扫描、ZIP和源码ZIP。

## 数据与旧版本

交付程序只监听本机 `127.0.0.1:8000`。为兼容已有数据，打包版运行目录仍是 `%LOCALAPPDATA%/XHSOrganizer/0.2`；它不是产品版本号。开发源码数据仍在项目的 `data` 等目录，均不进入交付包。

旧报告引擎和旧页面暂留兼容，不作为 0.3 主入口。不要运行旧的 `build_windows_exe.ps1` 或 `package_windows_release.ps1` 发布新产品。

本版本仍须用真实授权账号和真实有效模型 Key 完成质量验收。当前离线回归、模拟模型和前端构建不能证明小红书接口长期稳定，也不能证明某个模型生成的解读质量已经达标。
