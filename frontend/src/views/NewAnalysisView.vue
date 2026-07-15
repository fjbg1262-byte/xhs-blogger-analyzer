<template>
  <div class="new-analysis-page">
    <header class="page-intro">
      <div>
        <span><b aria-hidden="true">✦</b>三步生成报告</span>
        <h2>开始一次账号分析</h2>
        <p>填写主页、确认本地登录状态，然后交给分析工具。</p>
      </div>
      <div class="intro-mark" aria-hidden="true">◎</div>
    </header>

    <div class="card analysis-card">
      <section class="step">
        <div class="step-index"><b aria-hidden="true">⌕</b><span>1</span></div>
        <div class="step-body">
          <h3>要分析谁？</h3>
          <p>粘贴博主主页链接，或者直接填写主页里的用户 ID。</p>
          <input
            v-model="profileUrl"
            placeholder="例如：https://www.xiaohongshu.com/user/profile/xxxx，或直接填用户 ID"
          />
        </div>
      </section>

      <section class="step">
        <div class="step-index"><b aria-hidden="true">◇</b><span>2</span></div>
        <div class="step-body">
          <h3>登录凭证</h3>
          <p>如果已经保存过，直接选择；如果你用插件导出，把插件导出的完整内容粘贴进来，或导入导出的文件。</p>

          <select v-model="selectedCookieId">
            <option value="">选择已保存的登录凭证</option>
            <option v-for="c in cookies" :key="c.id" :value="c.id">
              {{ c.nickname || `登录凭证 #${c.id}` }}
              {{ c.is_valid === true ? '可用' : c.is_valid === false ? '不可用' : '' }}
            </option>
          </select>

          <div class="credential-tools">
            <label class="file-button">
              <span aria-hidden="true">↑</span>导入插件文件
              <input type="file" accept=".json,.txt,.cookies" @change="importCredentialFile" />
            </label>
            <button class="btn btn-secondary" type="button" @click="rawCookieJson = ''"><span aria-hidden="true">×</span>清空</button>
          </div>

          <textarea
            v-model="rawCookieJson"
            placeholder="把插件导出的完整内容粘贴到这里。不要只复制其中一行，尽量选择“全部 Cookie / 全部域名”后导出。"
            rows="5"
          ></textarea>

          <div class="hint">
            看不懂登录凭证没关系。你只需要确认插件导出时选中了 xiaohongshu.com 和 .xiaohongshu.com 的全部内容。
          </div>
        </div>
      </section>

      <section class="step">
        <div class="step-index"><b aria-hidden="true">↗</b><span>3</span></div>
        <div class="step-body">
          <h3>开始</h3>
          <label class="checkbox-label">
            <input type="checkbox" v-model="enableAi" />
            启用 AI 增强分析
          </label>

          <div class="actions">
            <button @click="startAnalysis" class="btn btn-primary" :disabled="!canStart || loading">
              <span aria-hidden="true">↗</span>{{ loading ? '创建中...' : '开始分析' }}
            </button>
            <button v-if="createdTaskId" @click="goToTask" class="btn btn-secondary">
              查看进度
            </button>
          </div>
        </div>
      </section>

      <div v-if="error" class="error-box">
        {{ error }}
      </div>

      <div v-if="createdTaskId" class="success-box">
        任务已创建（ID: {{ createdTaskId }}），系统正在后台分析。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { taskAPI, cookieAPI } from '../api/client'

const router = useRouter()
const profileUrl = ref('')
const selectedCookieId = ref<number | ''>('')
const rawCookieJson = ref('')
const enableAi = ref(false)
const loading = ref(false)
const error = ref('')
const createdTaskId = ref<number | null>(null)
const cookies = ref<any[]>([])

const canStart = computed(() => {
  return profileUrl.value.trim() && (selectedCookieId.value !== '' || rawCookieJson.value.trim())
})

async function importCredentialFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  rawCookieJson.value = await file.text()
  input.value = ''
}

async function startAnalysis() {
  error.value = ''
  loading.value = true
  createdTaskId.value = null

  try {
    let cookieId = selectedCookieId.value as number
    if (rawCookieJson.value.trim() && !cookieId) {
      const res = await cookieAPI.create(rawCookieJson.value, '插件导入')
      cookieId = res.data.id
      await loadCookies()
    }

    if (!cookieId) {
      error.value = '请选择已保存的登录凭证，或粘贴/导入插件导出的内容。'
      return
    }

    const res = await taskAPI.create(profileUrl.value.trim(), cookieId, enableAi.value)
    createdTaskId.value = res.data.id
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '创建任务失败'
  } finally {
    loading.value = false
  }
}

function goToTask() {
  if (createdTaskId.value) {
    router.push(`/analysis/${createdTaskId.value}`)
  }
}

async function loadCookies() {
  try {
    const res = await cookieAPI.list()
    cookies.value = res.data
  } catch {}
}

onMounted(loadCookies)
</script>

<style scoped>
.new-analysis-page {
  max-width: 860px;
}

.page-intro {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  padding: 22px 24px;
  border: 1px solid #ed214a;
  border-radius: 8px;
  background: #ff3158;
  color: #fff;
  box-shadow: 0 12px 26px rgba(205, 26, 69, 0.15);
}

.page-intro span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 900;
}

.page-intro h2 {
  margin-top: 4px;
  font-size: 29px;
  line-height: 1.25;
}

.page-intro p {
  margin-top: 6px;
  color: #fff5f7;
}

.intro-mark {
  width: 60px;
  height: 60px;
  flex: 0 0 60px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #fff;
  color: #d9133f;
  font-size: 30px;
  font-weight: 950;
  box-shadow: 5px 5px 0 #ffd43b;
}

.analysis-card {
  max-width: none;
  padding: 8px 24px 18px;
}
.step {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 16px;
  padding: 22px 0;
  border-bottom: 1px solid #f0dfe4;
}
.step:last-of-type {
  border-bottom: none;
}
.step-index {
  position: relative;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #ff3158;
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
  box-shadow: 3px 3px 0 #ffd43b;
}
.step-index > b { font-size: 19px; line-height: 1; }
.step-index span {
  position: absolute;
  right: -5px;
  top: -7px;
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #151318;
  color: #fff;
  font-size: 10px;
}
.step-body h3 {
  font-size: 18px;
  font-weight: 900;
  margin-bottom: 4px;
}
.step-body p,
.hint {
  color: #746b70;
  font-size: 13px;
  margin-bottom: 10px;
}
.credential-tools {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 10px 0;
}
.file-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  margin: 0;
  padding: 10px 16px;
  border: 1px solid #efdce1;
  border-radius: 6px;
  background: #fff0f3;
  color: #a91f42;
  font-size: 14px;
  font-weight: 800;
  gap: 6px;
  cursor: pointer;
}
.file-button input {
  display: none;
}
textarea {
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  cursor: pointer;
  width: fit-content;
  padding: 9px 11px;
  border: 1px solid #efdce1;
  border-radius: 6px;
  background: #fff8f9;
}
.checkbox-label input {
  width: auto;
}
.actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.error-box {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid #f3a1b3;
  background: #fff0f3;
  border-radius: 8px;
  color: #991b1b;
  font-size: 14px;
}
.success-box {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid #a5e6c8;
  background: #e9f9f1;
  border-radius: 8px;
  color: #065f46;
  font-size: 14px;
}

@media (max-width: 620px) {
  .page-intro { padding: 18px; }
  .page-intro h2 { font-size: 25px; }
  .intro-mark { display: none; }
  .analysis-card { padding: 6px 16px 14px; }
  .step { grid-template-columns: 40px 1fr; gap: 12px; }
  .step-index { width: 36px; height: 36px; }
}
</style>
