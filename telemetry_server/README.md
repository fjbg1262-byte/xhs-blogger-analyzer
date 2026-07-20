# 匿名反馈汇总服务

这是与 Windows 本地工具分开的轻量服务，只接收字段白名单内的匿名产品事件和用户主动填写的反馈。

## 必须配置的环境变量

```text
TELEMETRY_INGEST_KEY=给发布包使用的随机长字符串
TELEMETRY_ADMIN_TOKEN=只有作者知道的后台查看口令
TELEMETRY_DATABASE=/data/telemetry.db
```

生产环境必须为数据库目录配置持久磁盘，否则服务重启后数据可能丢失。

## 本地启动

```powershell
python -m pip install -r telemetry_server/requirements.txt
$env:TELEMETRY_INGEST_KEY = "test-ingest-key"
$env:TELEMETRY_ADMIN_TOKEN = "test-admin-token"
python -m uvicorn telemetry_server.app:app --host 127.0.0.1 --port 8010 --no-access-log
```

打开：

```text
http://127.0.0.1:8010/dashboard
```

## Docker 部署

在 `telemetry_server` 目录构建镜像：

```powershell
docker build -t xhs-telemetry .
```

服务健康检查：

```text
GET /health
```

Windows 发布包使用的接收地址应该是这个服务的 HTTPS 根地址，例如：

```text
https://telemetry.example.com
```

打包时通过 `-TelemetryEndpoint` 和 `-TelemetryIngestKey` 写入。后台查看口令绝不能写进 Windows 发布包。

## 数据边界

服务端只接受：

- 随机安装编号。
- 软件版本。
- 启动、分析状态、报告打开等固定事件。
- 标准错误代码和阶段。
- 用户主动选择及主动填写的最多 500 字反馈。

请求包含额外字段时会被拒绝；事件属性还会被服务端重新过滤。服务不保存 Cookie、主页链接、账号名称、笔记内容、报告正文和请求 IP。
