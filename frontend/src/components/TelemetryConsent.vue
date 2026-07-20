<template>
  <aside v-if="visible" class="consent-bar" aria-live="polite">
    <div class="consent-copy">
      <span class="consent-icon" aria-hidden="true">✓</span>
      <div>
        <strong>愿意帮助我们改进测试版吗？</strong>
        <p>只记录启动、分析成功或失败、报告打开和主动反馈，不会上传 Cookie、账号链接、笔记或报告内容。</p>
      </div>
    </div>
    <div class="consent-actions">
      <button class="privacy-link" type="button" @click="detailsOpen = !detailsOpen">
        {{ detailsOpen ? '收起说明' : '查看说明' }}
      </button>
      <button class="btn btn-secondary" type="button" :disabled="saving" @click="choose('denied')">暂不</button>
      <button class="btn btn-primary" type="button" :disabled="saving" @click="choose('granted')">
        {{ saving ? '保存中...' : '允许匿名改进' }}
      </button>
    </div>
    <ul v-if="detailsOpen" class="privacy-details">
      <li v-for="item in privacySummary" :key="item">{{ item }}</li>
      <li>可随时在“设置”中关闭，关闭后不再发送。</li>
    </ul>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { authToken } from '../auth'
import { telemetryAPI } from '../api/client'

const visible = ref(false)
const saving = ref(false)
const detailsOpen = ref(false)
const privacySummary = ref<string[]>([])
let loadedForToken = ''

async function load() {
  const token = authToken.value
  if (!token || token === loadedForToken) return
  loadedForToken = token
  try {
    const res = await telemetryAPI.preferences()
    privacySummary.value = res.data.privacy_summary || []
    visible.value = Boolean(res.data.available && res.data.consent === 'unknown')
  } catch {
    visible.value = false
  }
}

async function choose(consent: 'granted' | 'denied') {
  saving.value = true
  try {
    await telemetryAPI.setConsent(consent)
    visible.value = false
    window.dispatchEvent(new CustomEvent('telemetry-consent-changed', { detail: consent }))
  } finally {
    saving.value = false
  }
}

watch(authToken, load, { immediate: true })
</script>

<style scoped>
.consent-bar {
  position: fixed;
  left: 50%;
  bottom: 18px;
  z-index: 300;
  width: min(920px, calc(100% - 28px));
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px 20px;
  align-items: center;
  padding: 16px 18px;
  border: 1px solid #e7c7cf;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 16px 46px rgba(64, 16, 29, 0.2);
  transform: translateX(-50%);
}

.consent-copy {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 11px;
}

.consent-icon {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #dcf8e9;
  color: #087342;
  font-weight: 950;
}

.consent-copy strong,
.consent-copy p {
  display: block;
}

.consent-copy p {
  margin-top: 3px;
  color: #746b70;
  font-size: 13px;
  line-height: 1.55;
}

.consent-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.consent-actions .btn {
  min-height: 36px;
  padding: 7px 12px;
  white-space: nowrap;
}

.privacy-link {
  border: 0;
  background: transparent;
  color: #d9133f;
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.privacy-details {
  grid-column: 1 / -1;
  margin: 0;
  padding: 12px 12px 0 48px;
  border-top: 1px solid #f1e3e7;
  color: #655b60;
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 760px) {
  .consent-bar {
    grid-template-columns: 1fr;
    bottom: 10px;
    padding: 14px;
  }

  .consent-actions {
    display: grid;
    grid-template-columns: auto 1fr 1.4fr;
  }

  .consent-actions .btn {
    justify-content: center;
    padding-inline: 8px;
  }

  .privacy-details {
    padding-left: 28px;
  }
}
</style>
