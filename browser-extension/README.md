# XHS Analyzer Helper

这是 `XHS 博主分析助手` 的 Chrome / Edge 浏览器插件。

普通用户请优先看：

```text
docs/USER_GUIDE.md
```

项目维护者看分发方案：

```text
docs/SHARING_GUIDE.md
```

## 插件作用

插件负责在小红书博主主页上发起分析任务。

用户不需要手动复制 Cookie，只需要：

1. 启动本地分析工具。
2. 在浏览器里登录小红书。
3. 打开一个博主主页。
4. 点击插件里的“分析当前博主”。

## 安装方式

Chrome：

```text
chrome://extensions/
```

Edge：

```text
edge://extensions/
```

打开“开发者模式 / 开发人员模式”，点击“加载已解压的扩展程序”，选择本项目中的：

```text
browser-extension
```

## 注意

本插件必须配合本地工具使用。

如果本地后端没有启动，插件会提示“本地工具没启动”。

本插件只把必要信息发送到用户电脑本机的 `127.0.0.1`，不默认上传到远程服务器。
