# 项目目录与版本规则

开发根目录仍为 `C:/Users/hgghhy/xhs-blogger-analyzer`，避免无必要搬动Git和运行环境。

| 目录 | 用途 |
|---|---|
| backend/ | 后端；新主链路为routers/library、services/library_collector、services/note_library、tasks/library_worker |
| backend/services/library_analysis.py | 固定批次材料、AI结构校验、证据核验和客户报告数据 |
| backend/services/analysis_analytics.py | 公开互动、内容形式、集中度、标题信号、标签与节奏计算 |
| backend/services/analysis_report.py | 分页咨询式HTML/PDF报告结构与视觉系统 |
| backend/services/structured_ai.py | OpenAI/Claude/兼容接口的有界结构化调用与错误脱敏 |
| backend/tasks/analysis_worker.py | AI后台任务、进度、数据指纹、过期隔离和人工确认 |
| browser-extension/ | 固定开发扩展目录；版本0.4.0，连接0.3后端 |
| frontend/src/views/LibraryView.vue | 主页整理、笔记库、AI交付和表格导出页面 |
| frontend/src/components/LibraryAnalysis.vue | 客户目标、解读、创作草稿、证据、复核和下载 |
| spider_xhs/、static/ | 运行中使用的采集SDK及资源；不能当重复代码直接删 |
| docs/ | 当前产品边界、使用方法、目录和验证记录 |
| scripts/ | 启动与构建；新打包入口build_organizer.ps1 |
| tests/ | 离线采集、接口与导出回归测试 |
| release/ | 干净新交付包、对应源码快照；不在其中开发 |
| .build/ | 可删除的构建中间文件 |
| archive/ | 旧文档、唯一历史样本、变更前源码快照、清理审计；不打包 |
| data/、logs/、reports/ | 开发机私有运行数据；不打包，不拿来当测试样本发布 |
| .venv/、node_modules/ | 本机依赖，可由锁文件恢复 |

analyze_all.py、generate_reports.py及旧版后端仍有调用依赖，暂保留根目录，不为美观移动破坏导入。repo、repo_yize是旧报告而不是第二个Git仓库，归档。未提交的源码和开发记录必须保留。

## 本次版本核验

- 旧交付beta.10：BUILD_INFO记录2026-08-05、Git d8d727d。它不代表所有未提交更改；EXE内部源码不能仅靠外部同名文件推断。
- Edge配置：指向release/XHS博主分析助手-Windows测试版-0.1.0-beta.9/browser-extension。配置state字段缺失，不能据此断言当前启用状态。
- 开发源码：基于d8d727d且有大量未提交修改，新功能在保留这些改动的基础上增加。
- 新版本：应用0.3.0-beta.7、扩展0.4.0，两者版本号体系不同。新启动器会检查organizer_schema，避免误用旧8000端口服务。

beta.9若仍被浏览器配置引用，只保留该目录中的扩展兼容路径，直到用户在浏览器切换到固定加载路径；它不属于可交付版本。

## 构建回溯

先安装 `requirements.lock.txt` 以及 `frontend`、`spider_xhs` 的 `package-lock.json` 锁定依赖，再运行 `scripts/build_organizer.ps1 -Version 0.3.0-beta.7`。每次新版本生成 `source-版本.zip` 与 `SOURCE_MANIFEST.json`（逐文件哈希、Git提交和dirty状态），实际构建的源码以快照和指纹为准，不能只凭Git提交号。

发布目录不可覆盖使用中的同名版本；新版本必须使用新目录。自检会验证 AI schema、分析路由、前端资源和 Excel；扫描会拒绝 Cookie、数据库、日志、密钥配置等运行数据，处理后再生成 ZIP。运行中的用户数据库放到 `LOCALAPPDATA`，避免用过的程序文件夹污染交付。

依赖锁与源码快照保证明确输入，不承诺跨机器 PyInstaller 产物逐字节一致；Python/Node 版本也会记入构建信息。兼容已有数据，打包版运行目录仍为 `%LOCALAPPDATA%/XHSOrganizer/0.2`，不代表产品版本。
