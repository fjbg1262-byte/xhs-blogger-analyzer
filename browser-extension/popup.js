const REQUIRED = ["web_session"];
const NICE_TO_HAVE = ["a1"];
const BACKEND_BASE = "http://127.0.0.1:8000";
const FRONTEND_BASE = "http://127.0.0.1:8000";
const COOKIE_QUERIES = [
  { domain: "xiaohongshu.com" },
  { domain: ".xiaohongshu.com" },
  { url: "https://www.xiaohongshu.com/" },
  { url: "https://xiaohongshu.com/" },
  { url: "https://edith.xiaohongshu.com/" },
  { url: "https://creator.xiaohongshu.com/" },
  { url: "https://www.xiaohongshu.com/explore" }
];

const statusBox = document.getElementById("statusBox");
const statusTitle = document.getElementById("statusTitle");
const statusDetail = document.getElementById("statusDetail");
const analyzeBtn = document.getElementById("analyzeBtn");
const checkBtn = document.getElementById("checkBtn");
const copyBtn = document.getElementById("copyBtn");
const downloadBtn = document.getElementById("downloadBtn");
const openXhsBtn = document.getElementById("openXhsBtn");
const openAppBtn = document.getElementById("openAppBtn");

let currentCookieText = "";
let currentProfileUrl = "";

function setStatus(kind, title, detail) {
  statusBox.className = `status ${kind}`;
  statusTitle.textContent = title;
  statusDetail.textContent = detail;
}

function setBusy(isBusy) {
  analyzeBtn.disabled = isBusy;
  checkBtn.disabled = isBusy;
  analyzeBtn.textContent = isBusy ? "正在创建任务..." : "整理当前主页";
}

function getActiveTab() {
  return chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => tabs[0]);
}

function isProfileUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    return ["xiaohongshu.com", "www.xiaohongshu.com"].includes(url.hostname) && /^\/user\/profile\/[A-Za-z0-9_-]{8,64}\/?$/.test(url.pathname);
  } catch {
    return false;
  }
}

async function refreshCurrentPage() {
  const tab = await getActiveTab();
  currentProfileUrl = tab?.url || "";

  if (!isProfileUrl(currentProfileUrl)) {
    setStatus("warn", "先打开博主主页", "请在小红书里打开一个博主主页，再点击整理。");
    return false;
  }

  return true;
}

function getAllCookies() {
  return Promise.all(
    COOKIE_QUERIES.map((query) => chrome.cookies.getAll(query).catch(() => []))
  ).then((groups) => {
    const seen = new Set();
    const cookies = [];
    for (const group of groups) {
      for (const cookie of group) {
        if (!cookie.name || seen.has(cookie.name)) continue;
        seen.add(cookie.name);
        cookies.push(cookie);
      }
    }
    return cookies;
  });
}

function toCookieHeader(cookies) {
  return cookies
    .filter((cookie) => cookie.name && typeof cookie.value === "string")
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

function missing(names, required) {
  const set = new Set(names);
  return required.filter((name) => !set.has(name));
}

function cookieNames(cookies) {
  return cookies.map((cookie) => cookie.name).sort();
}

async function refreshCredential(showReadyStatus = true) {
  const cookies = await getAllCookies();
  const names = cookieNames(cookies);
  const missingRequired = missing(names, REQUIRED);
  const missingNiceToHave = missing(names, NICE_TO_HAVE);
  currentCookieText = toCookieHeader(cookies);

  if (!cookies.length) {
    copyBtn.disabled = true;
    downloadBtn.disabled = true;
    setStatus("warn", "还没有检测到登录", "请先在这个浏览器里登录小红书。");
    return false;
  }

  copyBtn.disabled = false;
  downloadBtn.disabled = false;

  if (missingRequired.length) {
    setStatus("warn", "登录状态不可用", "请重新登录小红书，或刷新当前页面后再试。");
    return false;
  }

  if (!showReadyStatus) return true;

  if (missingNiceToHave.length) {
    setStatus("warn", "缺少部分登录信息", "没有读取到 a1，请先刷新已登录的小红书页面后重试。");
    return true;
  }

  setStatus("ok", "可以整理", `已读取 ${cookies.length} 项登录信息，可以开始整理。`);
  return true;
}

async function checkBackend() {
  try {
    const response = await fetch(`${BACKEND_BASE}/api/health`, { method: "GET" });
    const payload = await response.json();
    return response.ok && payload.organizer_schema === "1.0";
  } catch {
    return false;
  }
}

async function analyzeCurrentBlogger() {
  setBusy(true);
  try {
    const pageOk = await refreshCurrentPage();
    if (!pageOk) return;

    const credentialOk = await refreshCredential(false);
    if (!credentialOk) return;

    const backendOk = await checkBackend();
    if (!backendOk) {
      setStatus("error", "请启动新版整理器", "需要 0.3 内容交付版；如果旧版本占用端口，请先关闭旧工具。");
      return;
    }

    setStatus("ok", "正在创建任务", "马上打开笔记库，采集过程中也能下载已有数据。");
    const response = await fetch(`${BACKEND_BASE}/api/extension/collect-current`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_url: currentProfileUrl,
        cookie_text: currentCookieText
      })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || "任务创建失败，请稍后再试。");
    }

    chrome.tabs.create({ url: data.report_url || FRONTEND_BASE });
  } catch (error) {
    setStatus("error", "没有成功开始整理", error.message || "请刷新小红书页面后重试。");
  } finally {
    setBusy(false);
  }
}

async function copyCredential() {
  if (!currentCookieText) await refreshCredential(false);
  await navigator.clipboard.writeText(currentCookieText);
  setStatus("ok", "已复制", "登录凭证已经复制，仅供本机备用，请勿转发给他人。");
}

function downloadCredential() {
  if (!currentCookieText) return;
  const blob = new Blob([currentCookieText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "xhs-login-credential.txt";
  a.click();
  URL.revokeObjectURL(url);
}

analyzeBtn.addEventListener("click", analyzeCurrentBlogger);

checkBtn.addEventListener("click", () => {
  Promise.all([refreshCurrentPage(), refreshCredential()]).catch((error) => {
    setStatus("error", "读取失败", error.message || "请确认扩展权限已经开启。");
  });
});

copyBtn.addEventListener("click", () => {
  copyCredential().catch((error) => {
    setStatus("error", "复制失败", error.message || "请重试。");
  });
});

downloadBtn.addEventListener("click", downloadCredential);

openXhsBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: "https://www.xiaohongshu.com/" });
});

openAppBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: FRONTEND_BASE });
});

Promise.all([refreshCurrentPage(), refreshCredential(false)]).catch(() => {
  setStatus("warn", "等待检查", "请先登录小红书，并打开要整理的博主主页。");
});
