<template>
  <section class="analysis">
    <div v-if="loading" class="state">正在读取分析结果…</div>

    <div v-else-if="error" class="state error">{{ error }}</div>

    <template v-else>
      <div class="analysis-head">
        <div>
          <p class="eyebrow">ACCOUNT DIAGNOSIS</p>
          <h2>{{ accountName }} · 八维分析</h2>
          <p class="lede">{{ statusLine }}</p>
        </div>
        <div class="head-actions">
          <span v-if="report?.model || state?.model" class="chip">{{ report?.model || state?.model }}</span>
          <button v-if="state?.status === 'ready'" class="btn ghost" type="button" @click="resetForm">重新生成</button>
        </div>
      </div>

      <div v-if="!state?.configured && !['ready', 'failed', 'stale'].includes(state?.status || '')" class="notice">
        <b>还没有配置模型</b>
        <span>八维分析需要你自己的模型 API。笔记库、筛选和导出不受影响。</span>
        <router-link class="btn ghost" to="/settings">去设置模型</router-link>
      </div>

      <form v-else-if="(showForm || !state || state.status === 'idle' || state.status === 'failed' || state.status === 'stale') && state?.status !== 'ready'" class="goal-form" @submit.prevent="start">
        <div class="field">
          <span>这次分析想解决什么</span>
          <textarea v-model="goal" rows="3" placeholder="例如：想找出更适合继续做的方向，并给下周 3 个能直接发的选题。"></textarea>
        </div>
        <label class="consent">
          <input v-model="consent" type="checkbox" />
          <span>同意把这批公开文字发给我配置的模型服务，并承担对应 API 费用。</span>
        </label>
        <p v-if="state?.status === 'failed' || state?.status === 'stale'" class="error-note">{{ state.stage }}</p>
        <div class="form-actions">
          <button class="btn primary" type="submit" :disabled="busy || !consent || goal.trim().length < 5">
            {{ busy ? '正在提交…' : state?.status === 'failed' ? '重试生成' : '生成八维分析' }}
          </button>
          <span class="hint">生成通常需要几十秒；期间可以切回笔记库继续筛选和导出。</span>
        </div>
      </form>

      <div v-else-if="state.status === 'running'" class="running">
        <div class="spinner" aria-hidden="true">◌</div>
        <div><b>正在生成</b><p>{{ state.stage || '模型正在阅读这批笔记。' }}</p></div>
        <button class="btn ghost" type="button" @click="refresh">刷新进度</button>
      </div>

      <template v-else-if="state.status === 'ready' && report">
        <div class="headline">
          <p class="tag">本次优先</p>
          <h3>{{ report.analysis.headline || findingOf(priorityDimension)?.observation || '先看优先维度' }}</h3>
          <p class="subtle">目标：{{ report.goal }}</p>
        </div>

        <div class="strategy-grid">
          <article><p class="tag">内容主线</p><p>{{ report.analysis.strategy.content_thesis }}</p></article>
          <article><p class="tag">可复用模型</p><p>{{ report.analysis.strategy.repeatable_model }}</p></article>
          <article><p class="tag">增长路径</p><p>{{ report.analysis.strategy.growth_path }}</p></article>
          <article><p class="tag">主要风险</p><p>{{ report.analysis.strategy.primary_risk }}</p></article>
        </div>

        <div class="section-row"><h3>八维解读</h3><span class="hint">每维只保留一条发现，引用原句来自本批笔记</span></div>
        <div class="dimension-grid">
          <article v-for="(dim, index) in report.analysis.dimensions" :key="dim.key" class="dimension-card">
            <header>
              <span class="index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div><h4>{{ labels[dim.key] || dim.key }}</h4><small>{{ dim.key === report.analysis.priority_dimension ? '本次优先维度' : '' }}</small></div>
              <i :class="dim.status">{{ statusLabel(dim.status) }}</i>
            </header>
            <template v-if="dim.findings.length">
              <p class="observation">{{ dim.findings[0].observation }}</p>
              <p>{{ dim.findings[0].interpretation }}</p>
              <p class="next"><b>下一步</b>{{ dim.findings[0].next_step }}</p>
              <p class="subtle">另一种解释：{{ dim.findings[0].alternative_explanation }}</p>
              <blockquote v-for="(quote, i) in dim.findings[0].evidence" :key="i">
                {{ quote.quote }}<small>{{ evidenceLabel(quote.note_id) }} · {{ quote.field === 'title' ? '标题' : '正文摘录' }}</small>
              </blockquote>
            </template>
            <p v-else class="empty">这个维度本批数据不足，未做推测：未获取。</p>
            <p class="boundary">{{ dim.limitation }}</p>
          </article>
        </div>

        <div class="section-row"><h3>下周可以做的 3 个选题</h3><span class="hint">每个选题含 2 个标题、开头、大纲和复盘指标</span></div>
        <div class="draft-list">
          <article v-for="(draft, index) in report.analysis.drafts" :key="index" class="draft">
            <span class="draft-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="draft-body">
              <p class="tag">读者问题</p>
              <h4>{{ draft.topic }}</h4>
              <p class="subtle">{{ draft.reader_problem }}</p>
              <div class="title-options">
                <div><span>标题 A</span><b>{{ draft.titles[0] }}</b></div>
                <div><span>标题 B</span><b>{{ draft.titles[1] }}</b></div>
              </div>
              <div class="block"><span>开头</span><p class="opening">{{ draft.opening }}</p></div>
              <div class="block"><span>正文大纲</span><ol><li v-for="step in draft.outline" :key="step">{{ step }}</li></ol></div>
              <div class="draft-foot">
                <p><b>测试</b>{{ draft.test }}</p>
                <p><b>复盘</b>{{ draft.check }}</p>
              </div>
              <blockquote v-for="(quote, i) in draft.evidence" :key="i">{{ quote.quote }}<small>{{ evidenceLabel(quote.note_id) }}</small></blockquote>
            </div>
          </article>
        </div>

        <div class="delivery">
          <div>
            <p class="eyebrow">DELIVERY</p>
            <h3>{{ report.review === 'approved' ? '已确认，可正式导出' : '复核后确认交付' }}</h3>
            <p class="hint">{{ report.validation }} 数据缺失处写「未获取」，没有补造数字。</p>
          </div>
          <div class="delivery-actions">
            <button v-if="report.review !== 'approved'" class="btn primary" type="button" :disabled="busy" @click="approve">
              {{ busy ? '正在确认…' : '我已复核，确认交付' }}
            </button>
            <button class="btn ghost" type="button" :disabled="downloading" @click="download('html', report.review !== 'approved')">下载网页版</button>
            <button class="btn ghost" type="button" :disabled="downloading || report.review !== 'approved'" @click="download('pdf', false)">下载 PDF</button>
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import api from '../api/client'

const props = defineProps<{ taskId: number; accountName: string }>()

interface Evidence { note_id: string; field: 'title' | 'body_excerpt'; quote: string }
interface Finding { observation: string; interpretation: string; next_step: string; alternative_explanation: string; evidence: Evidence[] }
interface Dimension { key: string; status: 'supported' | 'limited' | 'unavailable'; findings: Finding[]; limitation: string }
interface Draft { topic: string; reader_problem: string; titles: string[]; opening: string; outline: string[]; evidence: Evidence[]; test: string; check: string }
interface Report {
  goal: string
  review: string
  validation: string
  model: string
  analysis: {
    priority_dimension: string
    headline?: string
    dimensions: Dimension[]
    drafts: Draft[]
    strategy: { content_thesis: string; repeatable_model: string; growth_path: string; primary_risk: string }
  }
  evidence: { note_id: string; title: string }[]
}
interface State {
  status: string
  stage?: string
  run_id?: string
  goal?: string
  report?: Report
  configured?: boolean
  model?: string
  provider?: string
}

const labels: Record<string, string> = {
  positioning_audience: '内容定位与读者线索',
  content_structure: '内容方向',
  title_hook: '标题与开头',
  engagement_drivers: '高低表现对照',
  growth_trajectory: '发布节奏',
  tag_search: '标签与搜索表达',
  commercial_signals: '商业表达线索',
  action_plan: '下一步测试',
}
const statusLabels: Record<string, string> = { supported: '有依据', limited: '数据有限', unavailable: '未获取' }

const state = ref<State | null>(null)
const loading = ref(true)
const busy = ref(false)
const downloading = ref(false)
const error = ref('')
const goal = ref('')
const consent = ref(false)
const showForm = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

const report = computed(() => state.value?.report || null)
const priorityDimension = computed(() => report.value?.analysis.priority_dimension || '')
const statusLine = computed(() => {
  if (!state.value) return ''
  if (state.value.status === 'ready') return `已生成 · ${state.value.report?.analysis.dimensions.length || 0} 个维度 · 3 个选题`
  if (state.value.status === 'running') return '正在生成，可以切回笔记库继续使用'
  if (state.value.status === 'failed') return '生成失败，笔记库和导出不受影响'
  if (state.value.status === 'stale') return '笔记库变化或规则升级，需要重新生成'
  return '还没有生成分析'
})

function statusLabel(status: string) {
  return statusLabels[status] || '未获取'
}
function findingOf(key: string) {
  return report.value?.analysis.dimensions.find(item => item.key === key)?.findings[0]
}
function evidenceLabel(noteId: string) {
  const note = report.value?.evidence.find(item => item.note_id === noteId)
  return note?.title ? note.title.slice(0, 22) : noteId
}

async function load() {
  loading.value = true
  try {
    const response = await api.get(`/library/${props.taskId}/analysis`)
    state.value = response.data as State
    if (state.value.goal) goal.value = state.value.goal
    if (state.value.status === 'ready') error.value = ''
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '读取分析状态失败。'
  } finally {
    loading.value = false
    schedule()
  }
}

function schedule() {
  clearInterval(timer)
  if (state.value?.status === 'running') {
    timer = setInterval(refresh, 2500)
  }
}

async function refresh() {
  try {
    const response = await api.get(`/library/${props.taskId}/analysis`)
    state.value = response.data as State
    schedule()
  } catch {
    /* 轮询失败时保留上次状态 */
  }
}

async function start() {
  busy.value = true
  error.value = ''
  try {
    const response = await api.post(`/library/${props.taskId}/analysis`, { goal: goal.value.trim(), consent: consent.value })
    state.value = { ...(state.value || {}), status: response.data.status || 'running', stage: response.data.stage }
    showForm.value = false
    schedule()
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '提交失败，请稍后重试。'
  } finally {
    busy.value = false
  }
}

async function approve() {
  if (!report.value || !state.value?.run_id) return
  busy.value = true
  try {
    const response = await api.post(`/library/${props.taskId}/analysis/approve`, { run_id: state.value.run_id, confirmed: true })
    state.value = response.data as State
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '确认失败，请刷新后重试。'
  } finally {
    busy.value = false
  }
}

async function download(format: 'html' | 'pdf', preview: boolean) {
  downloading.value = true
  try {
    const response = await api.get(`/library/${props.taskId}/analysis/export`, {
      params: { format, preview },
      responseType: 'blob',
      timeout: 120000,
    })
    const url = URL.createObjectURL(response.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `八维分析-${props.accountName}.${format}`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '导出失败，请稍后重试。'
  } finally {
    downloading.value = false
  }
}

function resetForm() {
  showForm.value = true
}

watch(() => props.taskId, () => {
  state.value = null
  goal.value = ''
  consent.value = false
  showForm.value = false
  void load()
})

onMounted(load)
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.analysis { --xhs: #ff2442; --xhs-dark: #d8102f; --rust: #b5430c; --card: #fffdf9; --ink: #28251f; --muted: #7d7364; --muted-2: #9b8d79; --line: #ded4c5; --line-soft: #e9e1d5; --serif: "Songti SC", "STSong", "SimSun", Georgia, serif; color: var(--ink); }
.analysis * { box-sizing: border-box; }
.state { padding: 36px 0; color: var(--muted); font-size: 13px; }
.state.error { color: #b03a2e; }
.analysis-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.eyebrow { margin: 0 0 6px; font-size: 9px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--muted-2); }
.analysis-head h2 { margin: 0; font-family: var(--serif); font-size: 24px; }
.lede { margin: 6px 0 0; font-size: 11.5px; color: var(--muted); }
.head-actions { display: flex; align-items: center; gap: 8px; }
.chip { font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 20px; padding: 3px 9px; white-space: nowrap; }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 34px; padding: 7px 14px; border: 1px solid transparent; border-radius: 5px; font-size: 12.5px; font-weight: 600; cursor: pointer; text-decoration: none; white-space: nowrap; }
.btn.primary { background: var(--xhs); color: #fff; }
.btn.primary:hover { background: var(--xhs-dark); }
.btn.ghost { background: #fff; border-color: var(--line); color: var(--ink); }
.btn.ghost:hover { border-color: var(--rust); color: var(--rust); }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.notice { margin-top: 16px; padding: 14px 16px; background: #fdf6e7; border: 1px solid #e7d2a4; border-radius: 6px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 12px; color: #7a5f24; }
.notice b { font-size: 13px; }
.notice .btn { margin-left: auto; }

.goal-form { margin-top: 16px; padding: 16px 18px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.field { display: grid; gap: 6px; }
.field > span { font-size: 9px; letter-spacing: .1em; text-transform: uppercase; color: #9a8b74; }
.field textarea { width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 5px; background: #fdfbf7; font: inherit; font-size: 12.5px; line-height: 1.7; color: var(--ink); resize: vertical; }
.consent { display: flex; gap: 8px; align-items: flex-start; margin-top: 12px; font-size: 11px; color: var(--muted); }
.consent input { width: 13px; height: 13px; margin-top: 2px; }
.form-actions { display: flex; align-items: center; gap: 14px; margin-top: 12px; flex-wrap: wrap; }
.hint { font-size: 10.5px; color: var(--muted-2); }
.error-note { margin: 10px 0 0; padding: 9px 11px; background: #fdeceb; color: #a33a2c; border-radius: 4px; font-size: 11.5px; }

.running { margin-top: 16px; padding: 16px; display: flex; align-items: center; gap: 14px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.running p { margin: 3px 0 0; font-size: 11.5px; color: var(--muted); }
.running .btn { margin-left: auto; }
.spinner { font-size: 22px; color: var(--xhs); animation: spin 1.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }

.headline { margin-top: 18px; padding: 18px 20px; background: var(--card); border: 1px solid var(--line); border-left: 3px solid var(--rust); border-radius: 0 6px 6px 0; }
.headline h3 { margin: 6px 0 4px; font-family: var(--serif); font-size: 19px; line-height: 1.5; }
.tag { margin: 0; font-size: 9px; letter-spacing: .12em; text-transform: uppercase; color: #9a8b74; }
.subtle { margin: 6px 0 0; font-size: 10.5px; color: var(--muted-2); }

.strategy-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }
.strategy-grid article { padding: 13px 14px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.strategy-grid p:last-child { margin: 7px 0 0; font-size: 11.5px; line-height: 1.75; color: #4b453b; }

.section-row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 22px 0 10px; }
.section-row h3 { margin: 0; font-family: var(--serif); font-size: 17px; }

.dimension-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.dimension-card { padding: 15px 16px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.dimension-card header { display: flex; align-items: center; gap: 10px; padding-bottom: 9px; border-bottom: 1px solid var(--line-soft); }
.dimension-card .index { font-family: var(--serif); font-size: 22px; color: var(--rust); line-height: 1; }
.dimension-card header div { flex: 1; min-width: 0; }
.dimension-card h4 { margin: 0; font-family: var(--serif); font-size: 14px; }
.dimension-card header small { font-size: 9.5px; color: var(--muted-2); }
.dimension-card header i { font-style: normal; font-size: 9px; padding: 2px 7px; border-radius: 20px; border: 1px solid var(--line); color: var(--muted); }
.dimension-card header i.supported { color: #2f7a55; border-color: #cfe2d5; background: #edf6ef; }
.dimension-card header i.limited { color: #a5720f; border-color: #ecdcb9; background: #fbf3e2; }
.dimension-card header i.unavailable { color: #7a6f61; background: #f1ece3; }
.dimension-card .observation { margin: 11px 0 6px; font-family: var(--serif); font-size: 14px; line-height: 1.55; font-weight: 700; }
.dimension-card > p { margin: 0 0 6px; font-size: 11.5px; line-height: 1.8; color: #4b453b; }
.dimension-card .next { padding: 8px 10px; background: #f8f1e6; border-left: 2px solid var(--rust); border-radius: 0 4px 4px 0; }
.dimension-card .next b { display: block; font-size: 9px; letter-spacing: .08em; color: var(--rust); margin-bottom: 3px; }
.dimension-card .boundary { margin-top: 9px; padding-top: 8px; border-top: 1px dashed var(--line-soft); font-size: 10px; color: var(--muted-2); }
.dimension-card .empty { margin: 12px 0 0; font-size: 11.5px; color: var(--muted); }
blockquote { margin: 8px 0 0; padding: 8px 10px; background: #fcf8f1; border-left: 2px solid #c9b79f; font-size: 11px; line-height: 1.75; color: #5f584d; }
blockquote small { display: block; margin-top: 3px; font-size: 9px; color: var(--muted-2); }

.draft-list { display: grid; gap: 10px; }
.draft { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 14px; padding: 16px 18px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.draft-index { font-family: var(--serif); font-size: 26px; color: var(--rust); line-height: 1; }
.draft h4 { margin: 6px 0 3px; font-family: var(--serif); font-size: 17px; line-height: 1.45; }
.title-options { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
.title-options > div { padding: 9px 11px; background: #f8f1e6; border-radius: 4px; }
.title-options span { display: block; font-size: 9px; letter-spacing: .08em; color: #9a8b74; text-transform: uppercase; }
.title-options b { display: block; margin-top: 3px; font-size: 12px; line-height: 1.6; }
.block { margin-top: 11px; }
.block > span { display: block; font-size: 9px; font-weight: 700; letter-spacing: .08em; color: #8a3b18; text-transform: uppercase; margin-bottom: 4px; }
.opening { margin: 0; padding: 9px 11px; background: #fdfbf7; border-left: 2px solid var(--rust); font-family: var(--serif); font-size: 12px; line-height: 1.85; }
.draft ol { margin: 0; padding-left: 18px; columns: 2; column-gap: 20px; }
.draft li { font-size: 11.5px; line-height: 1.75; margin-bottom: 3px; break-inside: avoid; }
.draft-foot { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 11px; }
.draft-foot p { margin: 0; font-size: 11px; line-height: 1.75; color: #4b453b; }
.draft-foot b { display: block; font-size: 9px; letter-spacing: .08em; color: #8a3b18; margin-bottom: 2px; }

.delivery { margin-top: 20px; padding: 16px 18px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
.delivery h3 { margin: 4px 0 4px; font-family: var(--serif); font-size: 17px; }
.delivery-actions { display: flex; gap: 8px; flex-wrap: wrap; }

@media (max-width: 1180px) {
  .strategy-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dimension-grid { grid-template-columns: 1fr; }
  .title-options { grid-template-columns: 1fr; }
  .draft-foot { grid-template-columns: 1fr; }
}
</style>
