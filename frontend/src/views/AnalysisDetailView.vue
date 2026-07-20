<template>
  <div class="analysis-detail-page">
    <div class="report-titlebar">
      <div>
        <span>分析任务 #{{ taskId }}</span>
        <h2>分析报告</h2>
      </div>
      <div v-if="task" class="task-state">
        <span :class="statusBadge(task.status)">{{ statusLabel(task.status) }}</span>
        <b>{{ currentProgress }}%</b>
      </div>
    </div>

    <div v-if="loading" class="card state-panel">
      <p>加载中...</p>
    </div>

    <div v-else-if="error" class="card state-panel error-panel">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="task?.status === 'running' || task?.status === 'pending'" class="card progress-panel">
      <div class="progress-main">
        <div class="progress-ring" role="img" :aria-label="`当前进度 ${currentProgress}%`">
          <svg viewBox="0 0 128 128" aria-hidden="true">
            <circle class="ring-bg" cx="64" cy="64" r="54" />
            <circle
              class="ring-value"
              cx="64"
              cy="64"
              r="54"
              :style="{ strokeDashoffset: progressRingOffset }"
            />
          </svg>
          <div class="ring-copy">
            <strong>{{ currentProgress }}%</strong>
            <span>{{ task.status === 'pending' ? '等待' : '进行中' }}</span>
          </div>
        </div>

        <div class="progress-copy">
          <span class="progress-eyebrow">本地分析任务</span>
          <h3>{{ progressMeta.stage }}</h3>
          <p>{{ progressMeta.detail }}</p>
          <button @click="refresh" class="btn btn-secondary">刷新状态</button>
        </div>
      </div>

      <div class="progress-steps" aria-label="分析步骤">
        <div
          v-for="step in progressSteps"
          :key="step.key || step.label"
          :class="['progress-step', step.state]"
        >
          <i aria-hidden="true">{{ step.symbol }}</i>
          <div>
            <strong>{{ step.label }}</strong>
            <span>{{ step.stateLabel }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="task?.status === 'failed'" class="card state-panel error-panel">
      <h3>分析失败</h3>
      <p class="pre-wrap">{{ task.error_message || '任务失败，请检查 Cookie、主页链接和网络状态。' }}</p>
      <div class="failure-actions">
        <button type="button" class="btn btn-secondary" @click="copyDiagnostic">
          {{ diagnosticCopied ? '诊断信息已复制' : '复制诊断信息' }}
        </button>
        <button
          v-if="failureFeedbackAvailable && !failureFeedbackSent"
          type="button"
          class="btn btn-primary"
          @click="failureFeedbackOpen = !failureFeedbackOpen"
        >
          反馈这个问题
        </button>
      </div>
      <div v-if="failureFeedbackOpen && !failureFeedbackSent" class="failure-feedback">
        <label for="failure-comment">发生问题时你看到了什么？（可不填）</label>
        <textarea
          id="failure-comment"
          v-model="failureComment"
          maxlength="500"
          rows="3"
          placeholder="不用描述 Cookie 或账号，只说操作到了哪一步即可。"
        ></textarea>
        <button type="button" class="btn btn-primary" :disabled="failureFeedbackSending" @click="sendFailureFeedback">
          {{ failureFeedbackSending ? '发送中...' : '发送问题反馈' }}
        </button>
      </div>
      <p v-if="failureFeedbackSent" class="feedback-sent">问题已记录，谢谢你帮助改进测试版。</p>
      <p v-if="diagnosticCode" class="diagnostic-code">诊断编号：{{ diagnosticCode }}</p>
    </div>

    <div v-else>
      <ProductReport
        v-if="brief"
        :task-id="taskId"
        :brief="brief"
        :quality="reportQuality"
        :reports="reports"
        :detail-fetch="detailFetch"
        @refresh="load"
      />

      <template v-else>
        <div class="card" style="margin-bottom: 16px;">
          <p style="margin-bottom: 12px; color: #8e8e93;">该任务缺少结构化报告，暂时显示旧版 Markdown。</p>
          <button v-for="rt in reportTypes" :key="rt.key"
            @click="selectReport(rt.key)"
            :class="['btn', selectedReport === rt.key ? 'btn-primary' : 'btn-secondary']"
            style="font-size: 12px; padding: 6px 14px; margin: 0 8px 8px 0;">
            {{ rt.label }}
          </button>
        </div>

        <div class="card">
          <div class="markdown-body" v-html="renderedMarkdown"></div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { taskAPI, reportAPI, telemetryAPI } from '../api/client'
import { marked } from 'marked'
import { defaultReportKey, reportTypes } from '../constants/reports'
import ProductReport from '../components/ProductReport.vue'

const route = useRoute()
const taskId = computed(() => Number(route.params.taskId))
const task = ref<any>(null)
const reports = ref<Record<string, string>>({})
const reportQuality = ref<any>(null)
const brief = ref<any>(null)
const detailFetch = ref<any>(null)
const selectedReport = ref(defaultReportKey)
const loading = ref(true)
const error = ref('')
const diagnosticCopied = ref(false)
const diagnosticCode = ref('')
const failureFeedbackAvailable = ref(false)
const failureFeedbackOpen = ref(false)
const failureFeedbackSending = ref(false)
const failureFeedbackSent = ref(false)
const failureComment = ref('')
const ringCircumference = 339.292

const statusBadge = (s: string) => {
  const map: Record<string, string> = { pending:'badge badge-info', running:'badge badge-warning', completed:'badge badge-success', failed:'badge badge-error', cancelled:'badge' }
  return map[s] || 'badge'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

const renderedMarkdown = computed(() => {
  const md = reports.value[selectedReport.value]
  if (!md) return '<p style="color:#8e8e93;">暂无内容</p>'
  try { return marked(md) } catch { return md }
})

const currentProgress = computed(() => {
  const value = Number(task.value?.progress ?? 0)
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
})

const progressMeta = computed(() => {
  const meta = task.value?.progress_meta || {}
  return {
    stage: meta.stage || (task.value?.status === 'pending' ? '等待开始' : '分析进行中'),
    detail: meta.detail || '本地工具正在处理数据。',
    steps: Array.isArray(meta.steps) ? meta.steps : [],
  }
})

const progressRingOffset = computed(() => {
  return String(ringCircumference - ringCircumference * currentProgress.value / 100)
})

const progressSteps = computed(() => {
  const fallback = [
    { key: 'prepare', label: '准备任务', progress: 5 },
    { key: 'collect', label: '采集主页公开内容', progress: 40 },
    { key: 'analyze', label: '识别主题与互动表现', progress: 70 },
    { key: 'report', label: '生成分析报告', progress: 90 },
    { key: 'finish', label: '保存结果', progress: 100 },
  ]
  const steps = progressMeta.value.steps.length ? progressMeta.value.steps : fallback
  const progress = currentProgress.value
  return steps.map((step: any) => {
    const threshold = Number(step.progress ?? 0)
    const active = progress > 0 && progress < threshold && threshold - progress <= 30
    const done = progress >= threshold
    const state = done ? 'done' : active ? 'active' : 'todo'
    return {
      ...step,
      state,
      symbol: done ? '✓' : active ? '•' : '',
      stateLabel: done ? '已完成' : active ? '进行中' : '待处理',
    }
  })
})

function selectReport(key: string) { selectedReport.value = key }

async function trackReportOpened() {
  const key = `xhs_report_opened_${taskId.value}`
  if (sessionStorage.getItem(key)) return
  try {
    await telemetryAPI.event('report_opened', { task_type: task.value?.task_type || 'full_analysis' })
    sessionStorage.setItem(key, '1')
  } catch {}
}

async function loadFailureFeedbackAvailability() {
  try {
    const res = await telemetryAPI.preferences()
    failureFeedbackAvailable.value = Boolean(res.data.available && res.data.consent === 'granted')
  } catch {
    failureFeedbackAvailable.value = false
  }
}

async function copyDiagnostic() {
  try {
    const res = await telemetryAPI.diagnosticCopied(taskId.value)
    diagnosticCode.value = res.data.diagnostic_code || ''
    await navigator.clipboard.writeText(res.data.copy_text || '')
    diagnosticCopied.value = true
  } catch {
    diagnosticCopied.value = false
  }
}

async function sendFailureFeedback() {
  failureFeedbackSending.value = true
  try {
    const res = await telemetryAPI.feedback({
      task_id: taskId.value,
      feedback_kind: 'failure',
      rating: 'problem',
      reason: 'analysis_failed',
      comment: failureComment.value,
    })
    failureFeedbackSent.value = Boolean(res.data.accepted)
    if (failureFeedbackSent.value) failureFeedbackOpen.value = false
  } finally {
    failureFeedbackSending.value = false
  }
}

async function refresh() {
  try {
    const res = await taskAPI.get(taskId.value)
    task.value = res.data
  } catch {}
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const tRes = await taskAPI.get(taskId.value)
    task.value = tRes.data

    if (tRes.data.status === 'completed') {
      const rRes = await reportAPI.list(taskId.value)
      reports.value = rRes.data.reports || {}
      if (!reports.value[selectedReport.value]) {
        selectedReport.value = Object.keys(reports.value)[0] || defaultReportKey
      }
      try {
        const bRes = await reportAPI.brief(taskId.value)
        brief.value = bRes.data.brief || null
      } catch {
        brief.value = null
      }
      try {
        const qRes = await reportAPI.quality(taskId.value)
        reportQuality.value = qRes.data.quality || null
      } catch {
        reportQuality.value = null
      }
      try {
        const dRes = await taskAPI.detailFetchStatus(taskId.value)
        detailFetch.value = dRes.data || null
      } catch {
        detailFetch.value = null
      }
      trackReportOpened()
    } else if (tRes.data.status === 'failed') {
      loadFailureFeedbackAvailability()
    } else if (tRes.data.status === 'running' || tRes.data.status === 'pending') {
      setTimeout(load, 3000)
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('telemetry-consent-changed', loadFailureFeedbackAvailability)
})

onUnmounted(() => {
  window.removeEventListener('telemetry-consent-changed', loadFailureFeedbackAvailability)
})
</script>

<style scoped>
.analysis-detail-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.report-titlebar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 0 2px;
}

.report-titlebar > div:first-child > span {
  color: #d9133f;
  font-size: 12px;
  font-weight: 900;
}

.report-titlebar h2 {
  position: relative;
  margin-top: 2px;
  font-size: 29px;
  line-height: 1.25;
}

.report-titlebar h2::after {
  content: "";
  display: block;
  width: 58px;
  height: 4px;
  margin-top: 5px;
  border-radius: 2px;
  background: #ffd43b;
}

.task-state {
  display: flex;
  align-items: center;
  gap: 9px;
}

.task-state b {
  color: #746b70;
  font-size: 13px;
}

.state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
}

.state-panel p { color: #746b70; }
.state-panel .btn { margin-top: 4px; }

.progress-panel {
  padding: 28px;
  border-color: #efdce1;
  background: #fff;
}

.progress-main {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 24px;
  align-items: center;
}

.progress-ring {
  position: relative;
  width: 140px;
  height: 140px;
}

.progress-ring svg {
  width: 140px;
  height: 140px;
  transform: rotate(-90deg);
}

.progress-ring circle {
  fill: none;
  stroke-width: 12;
}

.ring-bg {
  stroke: #f1e3e7;
}

.ring-value {
  stroke: #ff3158;
  stroke-linecap: round;
  stroke-dasharray: 339.292;
  transition: stroke-dashoffset 0.35s ease;
}

.ring-copy {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
}

.ring-copy strong {
  font-size: 30px;
  line-height: 1;
  color: #151318;
}

.ring-copy span {
  color: #746b70;
  font-size: 12px;
  font-weight: 900;
}

.progress-copy {
  min-width: 0;
  text-align: left;
}

.progress-eyebrow {
  display: inline-flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 4px 8px;
  border: 1px solid #ffd43b;
  border-radius: 999px;
  background: #fff8d7;
  color: #8b6f00;
  font-size: 12px;
  font-weight: 900;
}

.progress-copy h3 {
  margin-bottom: 7px;
  font-size: 26px;
  line-height: 1.2;
}

.progress-copy p {
  max-width: 620px;
  margin-bottom: 14px;
  color: #746b70;
}

.progress-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 24px;
}

.progress-step {
  min-height: 74px;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  padding: 12px;
  border: 1px solid #efdce1;
  border-radius: 8px;
  background: #fff8f9;
}

.progress-step i {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #f1e3e7;
  color: #746b70;
  font-style: normal;
  font-weight: 950;
}

.progress-step strong,
.progress-step span {
  display: block;
}

.progress-step strong {
  overflow-wrap: anywhere;
  color: #151318;
  font-size: 13px;
  line-height: 1.25;
}

.progress-step span {
  margin-top: 3px;
  color: #91868c;
  font-size: 12px;
  font-weight: 800;
}

.progress-step.done {
  border-color: #bfe9d4;
  background: #f3fbf7;
}

.progress-step.done i {
  background: #1ca96b;
  color: #fff;
}

.progress-step.active {
  border-color: #ffd43b;
  background: #fffdf0;
  box-shadow: 4px 4px 0 #ffe780;
}

.progress-step.active i {
  background: #ffd43b;
  color: #151318;
}

.error-panel {
  border-color: #f3a1b3;
  background: #fff0f3;
  color: #9d1937;
}

.error-panel p { color: #9d1937; }
.pre-wrap { white-space: pre-wrap; }
.failure-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}
.failure-feedback {
  width: min(560px, 100%);
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid #f3a1b3;
  border-radius: 8px;
  background: #fff;
  text-align: left;
}
.failure-feedback .btn { justify-self: end; }
.feedback-sent { color: #087342 !important; font-weight: 800; }
.diagnostic-code {
  padding: 5px 8px;
  border-radius: 5px;
  background: #fff;
  font-family: Consolas, monospace;
  font-size: 12px;
}

@media (max-width: 560px) {
  .report-titlebar { align-items: flex-start; }
  .report-titlebar h2 { font-size: 25px; }
  .progress-panel { padding: 20px; }
  .progress-main { grid-template-columns: 1fr; justify-items: center; text-align: center; }
  .progress-copy { text-align: center; }
  .progress-steps { grid-template-columns: 1fr; }
  .failure-actions { width: 100%; }
  .failure-actions .btn { flex: 1; justify-content: center; }
  .failure-feedback .btn { width: 100%; justify-content: center; }
}

@media (min-width: 561px) and (max-width: 980px) {
  .progress-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
