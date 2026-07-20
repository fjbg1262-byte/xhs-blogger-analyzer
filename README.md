# XHS 博主分析助手 Windows 测试版

面向新手博主和小运营团队的本地分析工具。
打开小红书博主主页，点击浏览器插件，就能把近 100 篇公开内容整理成一份可阅读的分析报告。

> 当前是测试版，本项目不是小红书官方工具。请只用于公开主页内容的学习、复盘和选题参考。
> 当前版本是“浏览器插件 + 本地分析工具”的组合，不是只安装插件就能独立运行的纯插件。

![产品首页](docs/images/home-dashboard.png)

## 普通用户怎么下载安装

如果你只是想使用工具，**不要点击 GitHub 绿色的 `Code -> Download ZIP`**。那个是源码包，不适合普通用户。

请优先使用作者提供的下载包：

```text
XHS博主分析助手-Windows测试版.zip
```

下载后只需要：

1. 解压 zip。
2. 打开 `使用说明.html`。
3. 双击 `XHS分析助手.exe`。
4. 按说明安装 Chrome / Edge 插件。
5. 登录小红书，打开博主主页，点击插件分析。

更适合普通用户的图文说明看这里：

[docs/XHS_DISTRIBUTION_DOWNLOAD_GUIDE.md](docs/XHS_DISTRIBUTION_DOWNLOAD_GUIDE.md)

## 下载方式

### 方式一：网盘下载，推荐普通用户

网盘链接和提取码请以作者发布的 PDF 说明为准。

```text
网盘链接：待补充
提取码：待补充
```

### 方式二：GitHub Release 下载

如果你能正常访问 GitHub，可以打开右侧或顶部的 `Releases`，下载最新版本的：

```text
XHS博主分析助手-Windows测试版.zip
```

不要下载源码包。

## 适用环境

- Windows 电脑
- Chrome 浏览器或 Edge 浏览器
- 已登录的小红书账号

新版 Windows 测试包一般不需要你自己安装 Python / Node.js。

## 它能帮你做什么

如果你经常想研究一个对标账号，但不想手动抄表格、翻笔记、算点赞，这个工具可以帮你把这些事情自动整理出来：

- 看这个账号目前最值得学习的内容主线
- 找出表现更好的主题、标题和选题方向
- 展示每个判断背后的真实样本证据
- 生成主题地图、关键洞察和下一步行动建议
- 保留原来的 9 维深度分析，适合继续细看
- 本地运行，不需要手动复制 Cookie，不默认上传到作者服务器

## 使用方式很简单

先启动本地工具，然后在浏览器里登录小红书，打开一个博主主页，点插件里的“分析当前博主”。

![插件弹窗](docs/images/extension-popup.png)

插件会把当前博主主页交给你电脑上的本地分析工具处理。分析完成后，会自动生成报告页面。

如果只安装 `browser-extension`，但没有启动本地工具，插件无法生成报告。

## 报告长什么样

报告首页会先给出最重要的结论：这个账号值得学习什么、样本够不够、数据是否可靠、哪些模块因为数据不足被降级。

![报告总览](docs/images/report-overview.png)

继续往下看，可以看到关键洞察和主题地图。主题不是只靠固定关键词硬套，而是会结合账号自己的标题和正文，尽量识别这个账号真实反复出现的内容线。

![关键洞察和主题地图](docs/images/insights-topic-map.png)

原来的 9 维分析不会被藏起来，而是改成了可继续深入查看的模块。

![九维深度分析](docs/images/deep-analysis.png)

## 适合谁

适合：

- 刚开始做小红书的新手博主
- 想研究对标账号的小运营团队
- 想快速复盘账号内容结构的人
- 想把公开内容整理成选题参考的人

暂时不适合：

- 想做大规模监控的人
- 想批量高频采集很多账号的人
- 想得到平台官方数据结论的人
- 完全不愿意安装本地工具的人

## 第一次怎么安装

当前测试版主要支持 Windows + Chrome / Edge。

如果你拿到的是新版 Windows 测试包，通常只需要先安装：

- Chrome 浏览器或 Edge 浏览器

Python、Node.js 已经由 Windows 测试包处理，不需要普通用户自己安装。只有源码开发/自行打包时才需要 Python 和 Node.js。

下载或拿到内测压缩包后，先解压，然后双击：

```text
XHS分析助手.exe
```

第一次启动可能会慢一点。以后再双击同一个文件，就会直接启动本地工具并打开浏览器。

浏览器正常会自动打开：

```text
http://127.0.0.1:8000
```

更完整的小白安装说明看这里：

[docs/USER_GUIDE.md](docs/USER_GUIDE.md)

## 安装浏览器插件

Chrome 地址栏输入：

```text
chrome://extensions/
```

Edge 地址栏输入：

```text
edge://extensions/
```

打开开发者模式后，点击“加载已解压的扩展程序”或“加载解压缩的扩展”。

![加载解压扩展](docs/images/load-unpacked.png)

选择项目里的这个文件夹：

```text
browser-extension
```

看到 `XHS Analyzer Helper` 出现在扩展列表里，就说明插件装好了。

![插件安装成功](docs/images/extension-installed.png)

可以把插件固定到浏览器工具栏，之后使用会更方便。

![固定插件](docs/images/pin-extension.png)

## 日常使用步骤

1. 双击 `XHS分析助手.exe`，启动本地工具。
2. 在 Chrome 或 Edge 里登录小红书。
3. 打开要分析的博主主页。
4. 点击浏览器右上角插件图标。
5. 点击“分析当前博主”。
6. 等报告页面生成。

使用结束后，可以双击 `关闭本地工具.bat` 关闭本地服务。

如果插件提示“先打开博主主页”，说明当前页面不是博主主页。  
如果插件提示“本地工具没启动”，说明 `XHS分析助手.exe` 没有启动，或者本地服务没有正常运行。

## 隐私和使用边界

这个工具是本地优先：

- 插件只把必要信息发送到你自己电脑上的 `127.0.0.1`
- 不需要你手动复制 Cookie
- 不需要你提供小红书密码
- 不会默认上传数据到作者服务器
- 只有你明确点击“允许匿名改进”后，才会发送启动、分析状态、报告打开和主动反馈
- 匿名改进不会发送 Cookie、账号链接、昵称、笔记内容或报告正文
- 可以随时在“设置”里关闭

为了降低异常访问风险，建议：

- 一次只分析一个账号
- 不要连续高频分析大量账号
- 报告只作为样本观察，不要说成平台官方数据
- 遇到登录失效、请求失败或页面提示异常时，先停止任务

## 给维护者

生成一份适合分发的 Windows 内测 zip：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_windows_release.ps1 -Version test
```

配置匿名反馈接收端后打包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package_windows_release.ps1 `
  -Version 0.1.0-beta.3 `
  -AppVersion 0.1.0-beta.3 `
  -TelemetryEndpoint "https://your-telemetry.example.com" `
  -TelemetryIngestKey "your-ingest-key"
```

接收端部署说明：

[telemetry_server/README.md](telemetry_server/README.md)

生成文件：

```text
release/XHS博主分析助手-Windows测试版.zip
```

分发和上线建议看：

[docs/SHARING_GUIDE.md](docs/SHARING_GUIDE.md)

产品规划和开发计划看：

[docs/MVP_PRD.md](docs/MVP_PRD.md)  
[docs/MVP_DEVELOPMENT_PLAN.md](docs/MVP_DEVELOPMENT_PLAN.md)

## 开发启动

后端：

```bash
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000
```

前端构建：

```bash
cd frontend
npm install
npm run build
```

打开：

```text
http://127.0.0.1:8000
```

如果需要前端热更新开发，可以单独运行：

```bash
cd frontend
npm run dev
```

此时打开 Vite 开发地址：

```text
http://localhost:5173
```
