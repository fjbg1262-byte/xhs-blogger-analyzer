<template>
  <div class="app-container" :class="{ 'demo-mode': route.meta.standalone }">
    <header v-if="!route.meta.standalone" class="app-header">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" width="21" height="21">
            <path d="M15 3.6 17.7 12.3 26.4 15 17.7 17.7 15 26.4 12.3 17.7 3.6 15 12.3 12.3Z" fill="currentColor" />
            <path d="M24.1 3.4 24.9 6 27.5 6.8 24.9 7.6 24.1 10.2 23.3 7.6 20.7 6.8 23.3 6Z" fill="currentColor" opacity=".85" />
          </svg>
        </div>
        <div class="brand-copy">
          <strong>薯光</strong>
          <span>0.3.0-beta.6 工作台</span>
        </div>
      </div>
      <nav class="header-nav">
        <template v-if="isAuthenticated()">
          <router-link to="/demo"><span class="nav-icon" aria-hidden="true">▦</span>产品演示</router-link>
          <router-link to="/library"><span class="nav-icon" aria-hidden="true">▤</span>笔记库</router-link>
          <router-link to="/history"><span class="nav-icon" aria-hidden="true">◷</span>旧版报告记录</router-link>
          <router-link to="/settings"><span class="nav-icon" aria-hidden="true">⚙</span>设置</router-link>
          <button class="nav-button" type="button" title="退出登录" @click="logout">
            <span class="nav-icon" aria-hidden="true">↪</span>
            <span>{{ currentUsername || '退出' }}</span>
          </button>
        </template>
        <router-link v-else to="/login"><span class="nav-icon" aria-hidden="true">↪</span>登录</router-link>
      </nav>
    </header>
    <main class="app-main" :class="{ 'demo-main': route.meta.standalone }">
      <router-view />
    </main>
    <TelemetryConsent v-if="!route.meta.standalone" />
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { clearAuth, currentUsername, isAuthenticated } from './auth'
import TelemetryConsent from './components/TelemetryConsent.vue'

const router = useRouter()
const route = useRoute()

function logout() {
  clearAuth()
  router.push('/login')
}
</script>

<style>
:root {
  --brand-red: #ff2442;
  --brand-red-dark: #d8102f;
  --brand-red-soft: #fff0f3;
  --brand-yellow: #ffd43b;
  --brand-green: #1ca96b;
  --brand-blue: #2f6cf5;
  --ink: #151318;
  --muted: #746b70;
  --line: #efdce1;
  --surface: #ffffff;
  --page: #fff8f9;
  --shadow: 0 10px 28px rgba(194, 35, 75, 0.09);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--page);
  color: var(--ink);
  line-height: 1.6;
  letter-spacing: 0;
}
.app-container { min-height: 100vh; display: flex; flex-direction: column; }
.app-container.demo-mode { display: block; background: #f5f0e7; }
.app-header {
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--line);
  padding: 0 28px;
  min-height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 4px 18px rgba(165, 26, 61, 0.05);
}
.brand-lockup { display: flex; align-items: center; gap: 11px; min-width: max-content; }
.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--brand-red);
  color: #fff;
  box-shadow: 0 6px 16px rgba(255, 36, 66, 0.26);
}
.brand-copy { display: flex; flex-direction: column; line-height: 1.2; }
.brand-copy strong { font-family: "Songti SC", "STSong", "SimSun", Georgia, serif; font-size: 18px; font-weight: 700; letter-spacing: 0.02em; }
.brand-copy span { margin-top: 4px; color: var(--brand-red-dark); font-size: 11px; font-weight: 800; }
.header-nav { display: flex; align-items: center; gap: 5px; min-width: 0; }
.header-nav a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  color: #5f575c;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  transition: background 0.18s, color 0.18s, transform 0.18s;
}
.header-nav a:hover, .header-nav a.router-link-active {
  background: var(--brand-red-soft);
  color: var(--brand-red-dark);
}
.header-nav a:hover { transform: translateY(-1px); }
.nav-icon { width: 17px; display: inline-grid; place-items: center; font-size: 16px; line-height: 1; }
.nav-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  background: #fff;
  color: #5f575c;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.nav-button:hover { border-color: #f4a3b5; color: var(--brand-red-dark); }
.app-main {
  flex: 1;
  padding: 30px 24px 48px;
  max-width: 1240px;
  width: 100%;
  margin: 0 auto;
}
.app-main.demo-main { padding: 0; max-width: none; margin: 0; }
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--shadow);
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.18s, box-shadow 0.18s, background 0.18s;
  text-decoration: none;
}
.btn-primary { background: var(--brand-red); color: #fff; box-shadow: 0 7px 16px rgba(255, 49, 88, 0.24); }
.btn-primary:hover { background: var(--brand-red-dark); transform: translateY(-1px); }
.btn-secondary { background: #fff; color: var(--ink); border-color: var(--line); }
.btn-secondary:hover { background: var(--brand-red-soft); border-color: #f5a4b5; }
.btn-danger { background: #d82f3f; color: #fff; }
.btn-danger:hover { background: #b82030; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
input, textarea, select {
  width: 100%;
  padding: 11px 13px;
  border: 1px solid #dfcbd0;
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
input:focus, textarea:focus, select:focus { border-color: var(--brand-red); box-shadow: 0 0 0 3px rgba(255, 49, 88, 0.1); }
label { display: block; font-size: 14px; font-weight: 700; margin-bottom: 6px; color: #51484d; }
.form-group { margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #f1e3e7; font-size: 14px; }
th { background: #fff5f7; font-weight: 800; color: #655b60; }
.badge {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}
.badge-success { background: #dcf8e9; color: #087342; }
.badge-warning { background: #fff4c7; color: #815900; }
.badge-error { background: #ffe1e6; color: #a31535; }
.badge-info { background: #e8efff; color: #2456b8; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
@media (max-width: 768px) {
  .app-header { padding: 12px 16px; align-items: stretch; gap: 10px; flex-direction: column; }
  .header-nav { overflow-x: auto; padding-bottom: 2px; }
  .header-nav a, .nav-button { min-width: max-content; padding: 7px 9px; }
  .nav-button span { display: none; }
  .app-main { padding: 16px; }
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
}
.markdown-body { line-height: 1.8; }
.markdown-body h1 { font-size: 24px; margin: 24px 0 16px; color: var(--ink); }
.markdown-body h2 { font-size: 20px; margin: 20px 0 12px; color: var(--ink); }
.markdown-body h3 { font-size: 16px; margin: 16px 0 8px; }
.markdown-body p { margin: 8px 0; }
.markdown-body table { margin: 12px 0; }
.markdown-body th, .markdown-body td { padding: 8px 12px; border: 1px solid #f0dfe4; }
.markdown-body code { background: #fff0f3; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.markdown-body pre { background: #2b2529; color: #fff; padding: 16px; border-radius: 8px; overflow-x: auto; }
</style>
