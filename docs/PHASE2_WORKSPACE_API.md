# Phase 2 后端：真实数据接线

日期：2026-11-01。对应 [开发顺序](product/DEVELOPMENT_PLAN.md) 第 4 节 Phase 2。

## 目标与范围

Phase 1 的 Demo 用模拟数据。Phase 2 要让它换成真实采集结果，但**不改现有采集器、不改 `dataset.json` 契约**：

- 采集仍由浏览器插件 + `backend/services/library_collector.py` 完成，结果写入 `data/tasks/<id>/dataset.json`。
- 新增一层只读的 workspace 读模型，把同一个 dataset 映射成新 UI 需要的笔记行、任务卡和公开互动统计。
- 新增「停止 / 补采未完成笔记」两个写操作，复用原有 worker 与任务表。

## 新增接口

`backend/routers/workspace.py`，前缀 `/api/workspace`，与其它接口一样需要登录。

| 方法 | 路径 | 返回 |
|---|---|---|
| GET | `/tasks` | 采集任务卡列表 + 每个账号的最新任务 + 数量汇总 |
| GET | `/tasks/{id}` | 任务卡、账号、100 条笔记行、统计、dataset 元信息 |
| GET | `/tasks/{id}/progress` | 轻量轮询：状态、进度、笔记数、正文数、失败数 |
| GET | `/tasks/{id}/export?format=xlsx\|csv\|feishu` | 复用旧导出契约（同一份 `select_rows` + `xlsx_bytes`） |
| POST | `/tasks/{id}/stop` | 停止运行中的采集，已采集数据保留 |
| POST | `/tasks/{id}/retry?max_count=10` | 只补采详情失败的笔记，不重跑整批 |

笔记行字段：`id, title, author, type, published_at, likes, collected, comments, shares, engagement, tags, cover_url, body, note_url, incomplete, failure, missing_fields`。缺失值保持 `null`，不补 0。

统计字段：`total_engagement, mean_engagement, median_engagement, percentiles, metric_totals, top_count, top_share, types, image/video_share, best_type, format_ratio, title_pct, top_tag, top_tag_count, latest_published_at, body_count, failed_count, metric_basis`。

## 数据来源与口径

- 全部来自已保存的 `dataset.json`，**没有任何网络请求和模型调用**；`builder` 只读文件。
- 统计复用 `backend/services/analysis_analytics.py:build_report_analytics`，与客户报告同一套口径：公开互动 = 赞 + 藏 + 评 + 享；头部 = Top 20%；形式强度 = 该形式互动中位数 / 账号中位数。
- 用任务 #8（100 篇真实采集）核对：`12.7万 / 472.5 / 75.5% / 视频 1.3x / AI 75 篇`，与原报告页展示一致。
- 账号名优先取数据库昵称，其次取笔记作者昵称，最后回退到主页 ID 尾部。

## 补采与停止

- `retry_worker` 复用 `Collector.get_note_detail` 与 `note_library.apply_detail`，逐篇写回 dataset，结束后按剩余失败数把任务标成 `completed` 或 `partial`。
- 停止走原有 `_cancel_task`；若任务状态在库里是运行中但内存态已丢失（例如换进程），直接把任务标成 `cancelled`，已采集数据仍可下载。
- 重试次数上限 50，默认 10，避免一次补采把账号打到风控。

## 已验证

- `tests/test_workspace_api.py`：7 项通过。覆盖任务卡统计、笔记映射、统计口径、空 dataset、跨用户 404、导出三种格式、停止冲突、补采队列与补采 worker 写回。
- 真实数据 smoke：本地用运行时数据副本启动后端，8 个任务、4 个账号、100 篇笔记、`/tasks/8` 与 `/progress`、飞书导出 115KB，全部正常。
- 前端 `WorkspaceView`（`/workspace`）用同一套视觉接真实数据，无头 Edge 检查：账号名、4 个 KPI、4 个洞察卡、100 行表格、任务列表全部渲染，无运行时报错。

## 开发运行方式

```powershell
# 用运行时数据的副本，避免改动真实库
$env:XHS_APP_HOME="C:\Users\hgghhy\xhs-blogger-analyzer\data\dev-runtime"
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

本地开发登录：用 `_create_jwt` 生成 `local_extension_user` 的 token，打开
`http://127.0.0.1:8000/extension-login?token=<token>&username=local_extension_user&redirect=%2Fworkspace`，
token 有效期 24 小时。真实使用时由浏览器插件走同一条登录链路。

## 从页面发起采集

`/workspace` 侧栏有「+ 新建采集」：填主页链接、选一个已保存的浏览器登录状态，提交到既有的 `POST /api/library/`。

- 登录状态来自 `GET /api/cookies/`（插件采集时自动保存 `browser_extension`）。
- 创建成功后按任务 id 轮询 `/api/workspace/tasks/{id}/progress`，结束自动打开结果；失败时把 `error_message` 显示在页面上。
- 同时只允许一个运行中任务（沿用 `_ensure_task_slot`），重复提交会返回 429 的中文提示。
- 主页链接在前端先做格式校验，后端 `_normalize_profile_url` 再做一次域名与路径校验。

## 分页

100 篇不再一次性铺满页面：默认每页 50 篇，底部有「上一页 / 第 x / y 页 / 下一页」。筛选、排序、切换任务都会回到第 1 页。

## 还没做

1. **八维 / 3 个选题 / 原始依据仍是演示数据**：真实分析属于 Phase 5，需要模型配置和人工复核。
2. **笔记详情按需加载**：现在整批正文一起返回，100 篇约 100KB；后续可改为点击详情再取。
3. **采集任务没有分阶段进度条**：现在只有百分比与篇数，收尾时可补「读取主页 / 补详情」两段进度。
