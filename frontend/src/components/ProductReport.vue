<template>
  <div class="product-report">
    <section class="report-hero">
      <div class="hero-main">
        <div class="eyebrow-row">
          <span class="eyebrow"><span aria-hidden="true">✦</span>账号判断</span>
        </div>
        <div class="account-row">
          <div class="avatar">
            <img v-if="summary.avatar_url" :src="summary.avatar_url" alt="" />
            <span v-else>{{ accountInitial }}</span>
          </div>
          <div class="account-text">
            <strong>{{ summary.nickname || '未命名账号' }}</strong>
            <span class="account-positioning">{{ summary.positioning || '内容账号分析' }}</span>
            <span v-if="summary.bio" class="account-bio">{{ summary.bio }}</span>
          </div>
        </div>
        <h2>{{ summary.one_sentence || '本次报告已生成，建议先查看关键洞察和行动方案。' }}</h2>
      </div>
      <div class="hero-side">
        <div class="metric-panel-head">
          <span>本次样本摘要</span>
          <strong>{{ qualityText }}</strong>
        </div>
        <div class="metric">
          <span>粉丝数</span>
          <strong>{{ summary.follower_count ? formatNumber(summary.follower_count) : '-' }}</strong>
        </div>
        <div class="metric">
          <span>样本数</span>
          <strong>{{ formatNumber(dataQuality.sample_count || 0) }}</strong>
        </div>
        <div class="metric">
          <span>数据可信度</span>
          <strong>{{ confidenceLabel(summary.data_confidence) }}</strong>
        </div>
        <div class="metric">
          <span>质检分</span>
          <strong>{{ quality?.score ?? '-' }}</strong>
        </div>
      </div>
    </section>

    <section class="quick-judgement">
      <div class="judgement-block">
        <span class="block-label">最值得学</span>
        <h3>{{ strongestInsight?.title || '暂未形成足够稳定的强结论' }}</h3>
        <p>{{ strongestInsight?.summary || '当前数据更适合先补充样本，再做选题判断。' }}</p>
        <button v-if="strongestInsight" class="text-button" @click="focusEvidence(strongestInsight)">
          查看支撑样本<span aria-hidden="true">→</span>
        </button>
      </div>
      <div class="judgement-block caution">
        <span class="block-label">不建议照抄</span>
        <h3>{{ firstAvoid?.title || '不要照抄全量内容' }}</h3>
        <p>{{ firstAvoid?.reason || '优先学习高表现样本里的选题对象、标题承诺和场景，不要用平均内容代表整个账号。' }}</p>
        <button v-if="firstAvoid" class="text-button danger" @click="focusEvidence(firstAvoid)">
          查看低表现样本<span aria-hidden="true">→</span>
        </button>
      </div>
    </section>

    <section class="data-flow-panel">
      <div class="data-flow-head">
        <div>
          <span class="eyebrow">数据采集状态</span>
          <h3>这次报告用了哪些数据</h3>
        </div>
        <span class="data-flow-rule">{{ contentAnalysisStatus }}</span>
      </div>
      <div class="data-flow-grid">
        <div class="flow-metric">
          <span>主页笔记样本</span>
          <strong>{{ formatNumber(dataQuality.sample_count || 0) }}</strong>
          <small>用于主题、标题、点赞表现分析</small>
        </div>
        <div class="flow-metric">
          <span>详情补采</span>
          <strong>{{ detailFetchSummary }}</strong>
          <small>用于正文、标签、收藏评论等字段补充</small>
        </div>
        <div class="flow-metric" :class="{ weak: contentCoverageWeak }">
          <span>正文覆盖</span>
          <strong>{{ formatRatio(dataQuality.content_text_completeness) }}</strong>
          <small>{{ contentCoverageWeak ? '低于 50%，正文结构只做弱参考' : '可进入正文结构分析' }}</small>
        </div>
        <div class="flow-metric" :class="{ weak: tagCoverageWeak }">
          <span>标签覆盖</span>
          <strong>{{ formatRatio(dataQuality.tag_completeness) }}</strong>
          <small>{{ tagCoverageWeak ? '低于 50%，SEO 只做弱参考' : '可进入标签与 SEO 分析' }}</small>
        </div>
      </div>
    </section>

    <section v-if="qualityMessages.length || dataWarnings.length || weakInsights.length" class="warning-band">
      <div>
        <strong>这些结论已降级</strong>
        <p>数据缺口会影响分析深度，页面不会把这些部分写成强建议。</p>
        <button
          v-if="canFetchDetails"
          class="detail-fetch-button"
          :disabled="detailFetching"
          @click="startDetailFetch"
        >
          <span aria-hidden="true">⌕</span>{{ detailFetching ? '正在启动补采...' : '补充正文与标签分析' }}
        </button>
      </div>
      <ul>
        <li v-for="message in qualityMessages" :key="message">{{ message }}</li>
        <li v-for="warning in dataWarnings" :key="warning">{{ warning }}</li>
        <li v-for="item in weakInsights" :key="item.id">{{ item.title }}：{{ item.action }}</li>
        <li v-if="detailFetch?.enabled">
          正文与标签补采：成功 {{ detailFetch.success_count || 0 }} / {{ detailFetch.requested_count || 0 }} 条，失败 {{ detailFetch.failed_count || 0 }} 条。
        </li>
      </ul>
    </section>

    <section class="section-block">
      <div class="section-head">
        <div>
          <span class="eyebrow">关键洞察</span>
          <h3>先看这几条，再决定学什么</h3>
        </div>
      </div>
      <div class="insight-grid">
        <article v-for="insight in strongInsights" :key="insight.id" class="insight-card">
          <div class="card-topline">
            <span>{{ confidenceLabel(insight.confidence) }}</span>
            <span>{{ insight.sample_size || 0 }} 条样本</span>
          </div>
          <h4>{{ insight.title }}</h4>
          <p>{{ insight.summary }}</p>
          <div class="metric-row">
            <span v-for="metric in metricEntries(insight.metric)" :key="metric.label">
              {{ metric.label }} {{ metric.value }}
            </span>
          </div>
          <p class="matter">{{ insight.why_it_matters }}</p>
          <button class="text-button" @click="focusEvidence(insight)">看证据<span aria-hidden="true">→</span></button>
        </article>
      </div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <div>
          <span class="eyebrow">主题地图</span>
          <h3>哪些内容线表现更值得继续测</h3>
          <p class="section-note">“主题样本数”是归入该主题的全部笔记数；点击一行后，证据区展示该主题内按点赞排序的代表样本。</p>
        </div>
        <span class="muted">未归类 {{ formatPercent(dataQuality.topic_unclassified_pct) }}</span>
      </div>
      <div class="topic-table">
        <div class="topic-row header">
          <span>主题</span>
          <span>主题样本数</span>
          <span>均赞</span>
          <span>爆款率</span>
          <span>判断</span>
        </div>
        <button v-for="topic in topTopics" :key="topic.name" class="topic-row" @click="focusTopic(topic)">
          <span>
            <strong>{{ topic.name }}</strong>
            <small>{{ (topic.representative_titles || []).slice(0, 2).join(' / ') }}</small>
          </span>
          <span>{{ topic.count }}</span>
          <span>{{ formatNumber(topic.avg_likes) }}</span>
          <span>{{ formatPercent(topic.burst_rate) }}</span>
          <span>{{ topic.confidence === 'low' ? '仅观察' : '可参考' }}</span>
        </button>
      </div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <div>
          <span class="eyebrow">9 维分析</span>
          <h3>原有分析不隐藏，改成可深挖模块</h3>
        </div>
      </div>
      <div class="dimension-layout">
        <div class="dimension-tabs" role="tablist" aria-label="9 维报告">
          <button
            v-for="rt in reportTypes"
            :key="rt.key"
            :class="{ active: activeDimension === rt.key }"
            role="tab"
            @click="activeDimension = rt.key"
          >
            {{ rt.label }}
          </button>
        </div>
        <article class="dimension-panel">
          <div class="dimension-panel-head">
            <strong>{{ activeReportLabel }}</strong>
            <span v-if="dimensionWarning">{{ dimensionWarning }}</span>
          </div>
          <div class="markdown-body" v-html="renderedDimensionMarkdown"></div>
        </article>
      </div>
    </section>

    <section ref="evidenceSection" class="section-block">
      <div class="section-head">
        <div>
          <span class="eyebrow">证据样本库</span>
          <h3>{{ evidenceTitle }}</h3>
          <p class="section-note">{{ evidenceSubtitle }}</p>
        </div>
        <span class="muted">{{ evidenceCountLabel }}</span>
        <button v-if="selectedEvidenceIds.length" class="text-button" @click="clearEvidenceFilter">
          查看全部
        </button>
      </div>
      <div class="evidence-grid">
        <article v-for="note in visibleEvidence" :key="note.note_id" class="evidence-card">
          <div class="card-topline">
            <span>{{ note.date || '未知日期' }}</span>
            <span>{{ note.topic || '未归类' }}</span>
          </div>
          <h4>{{ note.title || '未命名笔记' }}</h4>
          <p>{{ formatNumber(note.likes || 0) }} 赞 · {{ note.type || '笔记' }}</p>
          <p class="evidence-reason">{{ note.evidence_reason || '这条样本用于辅助复核本次判断。' }}</p>
          <div v-if="note.used_by?.length" class="used-by">
            <span v-for="usage in note.used_by" :key="`${note.note_id}-${usage.id}`">
              {{ usage.type }}：{{ usage.title }}
            </span>
          </div>
        </article>
      </div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <div>
          <span class="eyebrow">行动方案</span>
          <h3>下一轮可以直接照这个顺序试</h3>
        </div>
      </div>
      <div class="action-grid">
        <article v-for="action in recommendedActions" :key="action.id" class="action-card">
          <h4>{{ action.title }}</h4>
          <ol>
            <li v-for="step in action.steps" :key="step">{{ step }}</li>
          </ol>
          <div v-if="action.seven_day_plan?.length" class="seven-day-plan">
            <strong>7 天执行表</strong>
            <div v-for="day in action.seven_day_plan" :key="`${action.id}-${day.day}`" class="day-row">
              <span>第 {{ day.day }} 天</span>
              <div>
                <b>{{ day.task }}</b>
                <p>{{ day.goal }}</p>
              </div>
            </div>
          </div>
          <button class="text-button" @click="focusEvidence(action)">查看行动依据<span aria-hidden="true">→</span></button>
        </article>
      </div>
    </section>

    <ReportFeedback :task-id="taskId" />

    <section class="export-row">
      <button class="btn btn-secondary" @click="downloadBriefJson"><span aria-hidden="true">{ }</span>导出 JSON</button>
      <button class="btn btn-secondary" @click="downloadShareHtml"><span aria-hidden="true">↗</span>导出脱敏分享版</button>
      <button class="btn btn-primary" @click="downloadMarkdownZip"><span aria-hidden="true">↓</span>导出 Markdown</button>
    </section>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { marked } from 'marked'
import { defaultReportKey, reportTypes } from '../constants/reports'
import { reportAPI, taskAPI } from '../api/client'
import ReportFeedback from './ReportFeedback.vue'

const props = defineProps<{
  taskId: number
  brief: any
  quality: any
  reports: Record<string, string>
  detailFetch?: any
}>()

const emit = defineEmits<{
  refresh: []
}>()

const activeDimension = ref(defaultReportKey)
const selectedEvidenceIds = ref<string[]>([])
const activeEvidenceSource = ref('')
const evidenceSection = ref<HTMLElement | null>(null)
const detailFetching = ref(false)

const summary = computed(() => props.brief?.account_summary || {})
const dataQuality = computed(() => props.brief?.data_quality || {})
const strongInsights = computed(() => props.brief?.strong_insights || [])
const weakInsights = computed(() => props.brief?.weak_insights || [])
const recommendedActions = computed(() => props.brief?.recommended_actions || [])
const avoidActions = computed(() => props.brief?.avoid_actions || [])
const evidenceNotes = computed(() => props.brief?.evidence_notes || [])
const firstAvoid = computed(() => avoidActions.value[0])
const strongestInsight = computed(() => strongInsights.value[0])
const accountInitial = computed(() => String(summary.value.nickname || '账').slice(0, 1))
const contentCoverageWeak = computed(() => (dataQuality.value.content_text_completeness || 0) < 0.5)
const tagCoverageWeak = computed(() => (dataQuality.value.tag_completeness || 0) < 0.5)

const dataWarnings = computed(() => dataQuality.value.warnings || [])
const canFetchDetails = computed(() => {
  if (detailFetching.value) return true
  if (props.detailFetch?.enabled && props.detailFetch?.success_count > 0) return false
  return (dataQuality.value.content_text_completeness || 0) < 0.5 || (dataQuality.value.tag_completeness || 0) < 0.5
})

const topTopics = computed(() => {
  const topics = props.brief?.topic_clusters || []
  return [...topics]
    .sort((a, b) => (b.avg_likes || 0) - (a.avg_likes || 0))
    .slice(0, 8)
})

const quality = computed(() => props.quality || null)
const qualityText = computed(() => {
  if (!quality.value) return '未生成质检'
  return quality.value.passed ? '报告质量通过' : '报告需复查'
})
const qualityMessages = computed(() => {
  const q = quality.value
  if (!q) return []
  return [...(q.blocking_issues || []), ...(q.warnings || [])].map((item: any) => item.message || String(item))
})

const activeReportLabel = computed(() => reportTypes.find((rt) => rt.key === activeDimension.value)?.label || '报告')
const renderedDimensionMarkdown = computed(() => {
  const md = props.reports?.[activeDimension.value]
  if (!md) return '<p style="color:#6b7280;">暂无内容</p>'
  try {
    return marked(md)
  } catch {
    return md
  }
})

const dimensionWarning = computed(() => {
  const label = activeReportLabel.value
  const matched = [...(props.brief?.insufficient_modules || [])].find((item: any) => label.includes(item.module.replace('与', '')))
  if (matched) return matched.impact
  if (label.includes('标签')) return dataQuality.value.tag_completeness < 0.5 ? '标签数据不足，本模块只作弱参考。' : ''
  if (label.includes('内容')) return dataQuality.value.content_text_completeness < 0.5 ? '正文数据不足，结构判断已降级。' : ''
  if (label.includes('互动')) return dataQuality.value.comment_completeness < 0.5 ? '评论数据不足，互动归因只作弱参考。' : ''
  return ''
})

const evidenceById = computed(() => {
  const map = new Map<string, any>()
  for (const note of evidenceNotes.value) {
    if (note.note_id) map.set(note.note_id, note)
  }
  return map
})

const visibleEvidence = computed(() => {
  if (!selectedEvidenceIds.value.length) return evidenceNotes.value.slice(0, 12)
  return selectedEvidenceIds.value.map((id) => evidenceById.value.get(id)).filter(Boolean)
})

const evidenceTitle = computed(() => {
  if (!selectedEvidenceIds.value.length) return '默认展示高赞和被引用样本'
  return activeEvidenceSource.value ? `正在查看「${activeEvidenceSource.value}」的证据` : '正在查看所选证据'
})
const evidenceSubtitle = computed(() => {
  if (!selectedEvidenceIds.value.length) {
    return props.brief?.evidence_policy?.default_sort || '默认证据池按点赞数从高到低展示。'
  }
  return props.brief?.evidence_policy?.insight_sort || '当前证据按相关范围内点赞数优先展示，不是按时间排序。'
})
const evidenceCountLabel = computed(() => {
  const total = selectedEvidenceIds.value.length || Math.min(evidenceNotes.value.length, 12)
  return `当前显示 ${visibleEvidence.value.length} / ${total} 条证据`
})
const detailFetchSummary = computed(() => {
  if (!props.detailFetch?.enabled) return '未补采'
  return `${props.detailFetch.success_count || 0}/${props.detailFetch.requested_count || 0}`
})
const contentAnalysisStatus = computed(() => {
  if (!props.detailFetch?.enabled) return '当前主要基于主页列表数据'
  if (contentCoverageWeak.value || tagCoverageWeak.value) return '已补采，但正文/标签覆盖不足，相关结论降级'
  return '正文与标签覆盖达标，可进入结构分析'
})

function confidenceLabel(value: string) {
  const map: Record<string, string> = { high: '高', medium: '中', low: '低' }
  return map[value] || value || '-'
}

function formatNumber(value: any) {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(n >= 100000 ? 0 : 1)}万`
  return new Intl.NumberFormat('zh-CN').format(Math.round(n * 10) / 10)
}

function formatPercent(value: any) {
  if (value === undefined || value === null || value === '') return '-'
  const n = Number(value)
  return `${Math.round(n * 10) / 10}%`
}

function formatRatio(value: any) {
  if (value === undefined || value === null || value === '') return '-'
  const n = Number(value || 0)
  return `${Math.round(n * 1000) / 10}%`
}

function metricEntries(metric: Record<string, any> = {}) {
  const labels: Record<string, string> = {
    avg_likes: '均赞',
    burst_rate: '爆款率',
    above_avg_rate: '高于均值',
    vs_overall_pct: '相对整体',
    pareto_80pct_pct: '贡献80%点赞的笔记占比',
    top10pct_share: 'Top10%贡献',
  }
  return Object.entries(metric).slice(0, 3).map(([key, value]) => ({
    label: labels[key] || key,
    value: key.includes('rate') || key.includes('pct') || key.includes('share') ? formatPercent(value) : formatNumber(value),
  }))
}

function focusEvidence(item: any) {
  selectedEvidenceIds.value = item.evidence_note_ids || item.note_ids || []
  activeEvidenceSource.value = item.title || item.name || ''
  nextTick(() => evidenceSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function focusTopic(topic: any) {
  selectedEvidenceIds.value = topic.evidence_note_ids || topic.note_ids || []
  activeEvidenceSource.value = topic.name || ''
  nextTick(() => evidenceSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function clearEvidenceFilter() {
  selectedEvidenceIds.value = []
  activeEvidenceSource.value = ''
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function downloadBriefJson() {
  const payload = { brief: props.brief, quality: props.quality }
  downloadBlob(
    new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }),
    `xhs-report-${props.taskId}.json`,
  )
}

async function downloadMarkdownZip() {
  const res = await reportAPI.exportMarkdown(props.taskId)
  downloadBlob(new Blob([res.data], { type: 'application/zip' }), `xhs-report-${props.taskId}.zip`)
}

async function downloadShareHtml() {
  const res = await reportAPI.exportShare(props.taskId)
  downloadBlob(new Blob([res.data], { type: 'text/html;charset=utf-8' }), `xhs-share-report-${props.taskId}.html`)
}

async function startDetailFetch() {
  detailFetching.value = true
  try {
    await taskAPI.detailFetch(props.taskId, 25)
    emit('refresh')
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '补采启动失败')
  } finally {
    detailFetching.value = false
  }
}
</script>

<style scoped>
.product-report {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.report-hero,
.quick-judgement,
.data-flow-panel,
.section-block,
.warning-band,
.export-row {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.report-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 22px;
  padding: 26px;
}

.hero-main h2 {
  margin: 18px 0 0;
  max-width: 760px;
  font-size: 27px;
  line-height: 1.35;
  letter-spacing: 0;
}

.muted,
.warning-band p,
.section-note,
.flow-metric small,
.insight-card p,
.action-card li,
.evidence-card p,
.account-bio,
.day-row p {
  color: #6b7280;
}

.eyebrow-row,
.section-head,
.card-topline,
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.eyebrow,
.block-label {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.account-row {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 14px;
}

.avatar {
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  border-radius: 50%;
  background: #dbeafe;
  color: #1d4ed8;
  display: grid;
  place-items: center;
  overflow: hidden;
  font-size: 24px;
  font-weight: 800;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.account-text {
  min-width: 0;
}

.account-text strong,
.account-text span {
  display: block;
}

.account-text strong {
  font-size: 18px;
  line-height: 1.3;
}

.account-text span {
  line-height: 1.5;
}

.account-positioning {
  display: inline-block !important;
  width: fit-content;
  max-width: 100%;
  margin-top: 7px;
  padding: 4px 9px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8 !important;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
}

.account-bio {
  margin-top: 7px;
}

.hero-side {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  align-self: start;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  padding: 12px;
}

.metric {
  background: #fff;
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 12px;
}

.metric-panel-head {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 0 2px 4px;
}

.metric-panel-head span {
  color: #6b7280;
  font-size: 13px;
  font-weight: 700;
}

.metric-panel-head strong {
  color: #166534;
  background: #dcfce7;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  white-space: nowrap;
}

.metric span,
.card-topline,
.topic-row small {
  display: block;
  color: #6b7280;
  font-size: 12px;
}

.metric strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  line-height: 1.2;
}

.quick-judgement {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.judgement-block {
  padding: 20px;
}

.judgement-block + .judgement-block {
  border-left: 1px solid #e5e7eb;
}

.judgement-block h3,
.data-flow-head h3,
.section-head h3,
.insight-card h4,
.action-card h4,
.evidence-card h4 {
  margin: 6px 0 8px;
  line-height: 1.35;
  letter-spacing: 0;
}

.caution .block-label {
  color: #b45309;
}

.data-flow-panel {
  padding: 18px 20px;
}

.data-flow-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.data-flow-rule {
  max-width: 360px;
  color: #374151;
  background: #f3f4f6;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.data-flow-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.flow-metric {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.flow-metric.weak {
  border-color: #fde68a;
  background: #fffbeb;
}

.flow-metric span,
.flow-metric small {
  display: block;
}

.flow-metric span {
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.flow-metric strong {
  display: block;
  margin: 5px 0;
  font-size: 22px;
  line-height: 1.2;
}

.section-note {
  max-width: 760px;
  margin: 2px 0 0;
  line-height: 1.55;
}

.warning-band {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 20px;
  padding: 18px 20px;
  background: #fffbeb;
}

.warning-band ul {
  margin: 0;
  padding-left: 18px;
  color: #92400e;
}

.detail-fetch-button {
  margin-top: 12px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
  padding: 9px 12px;
}

.detail-fetch-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.section-block {
  padding: 20px;
}

.insight-grid,
.evidence-grid,
.action-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.insight-card,
.evidence-card,
.action-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}

.metric-row {
  justify-content: flex-start;
  margin: 12px 0;
}

.metric-row span {
  background: #f3f4f6;
  color: #374151;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
}

.matter {
  border-left: 3px solid #bfdbfe;
  padding-left: 10px;
}

.evidence-reason {
  margin-top: 10px;
  border-left: 3px solid #d1fae5;
  padding-left: 10px;
  line-height: 1.65;
}

.used-by {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.used-by span {
  max-width: 100%;
  background: #f3f4f6;
  color: #374151;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.text-button {
  border: none;
  background: transparent;
  color: #2563eb;
  font-weight: 700;
  padding: 0;
  cursor: pointer;
}

.text-button.danger {
  color: #b45309;
}

.topic-table {
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.topic-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) 80px 100px 100px 100px;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: none;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  text-align: left;
  color: #1f2937;
}

.topic-row:not(.header) {
  cursor: pointer;
}

.topic-row:not(.header):hover {
  background: #f9fafb;
}

.topic-row.header {
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.topic-row:last-child {
  border-bottom: none;
}

.dimension-layout {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 18px;
  margin-top: 14px;
}

.dimension-tabs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dimension-tabs button {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
  font-weight: 600;
  padding: 10px 12px;
  text-align: left;
}

.dimension-tabs button.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.dimension-panel {
  min-width: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}

.dimension-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5e7eb;
}

.dimension-panel-head span {
  color: #92400e;
  font-size: 13px;
}

.action-card ol {
  margin: 8px 0 12px;
  padding-left: 20px;
}

.seven-day-plan {
  margin: 12px 0;
  border-top: 1px solid #e5e7eb;
  padding-top: 12px;
}

.seven-day-plan > strong {
  display: block;
  margin-bottom: 8px;
}

.day-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}

.day-row:last-child {
  border-bottom: none;
}

.day-row span {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.day-row b,
.day-row p {
  display: block;
  line-height: 1.5;
}

.day-row p {
  margin: 2px 0 0;
}

.export-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
}

@media (max-width: 900px) {
  .report-hero,
  .quick-judgement,
  .data-flow-head,
  .warning-band,
  .dimension-layout {
    grid-template-columns: 1fr;
  }

  .data-flow-head {
    display: block;
  }

  .data-flow-rule {
    display: inline-block;
    margin-top: 8px;
  }

  .judgement-block + .judgement-block {
    border-left: none;
    border-top: 1px solid #e5e7eb;
  }

  .insight-grid,
  .evidence-grid,
  .action-grid,
  .data-flow-grid {
    grid-template-columns: 1fr;
  }

  .topic-row {
    grid-template-columns: 1fr 58px 76px 76px;
  }

  .topic-row span:last-child {
    display: none;
  }
}

@media (max-width: 560px) {
  .report-hero,
  .section-block,
  .judgement-block,
  .data-flow-panel,
  .warning-band,
  .export-row {
    padding: 14px;
  }

  .hero-main h2 {
    font-size: 22px;
  }

  .dimension-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .topic-row {
    grid-template-columns: 1fr 56px;
  }

  .topic-row span:nth-child(3),
  .topic-row span:nth-child(4) {
    display: none;
  }

  .export-row {
    flex-direction: column;
  }

  .day-row {
    grid-template-columns: 1fr;
  }
}

/* Launch-inspired visual system: bold hierarchy with real report data in focus. */
.product-report {
  --report-red: #ff3158;
  --report-red-dark: #d9133f;
  --report-pink: #fff0f3;
  --report-yellow: #ffd43b;
  --report-green: #1ca96b;
  --report-blue: #2f6cf5;
  --report-ink: #151318;
  --report-muted: #746b70;
  --report-line: #efdce1;
  gap: 20px;
}

.report-hero,
.quick-judgement,
.data-flow-panel,
.section-block,
.warning-band,
.export-row {
  border-color: var(--report-line);
  box-shadow: 0 10px 28px rgba(194, 35, 75, 0.07);
}

.report-hero {
  position: relative;
  padding: 32px;
  border-top: 7px solid var(--report-red);
  overflow: hidden;
}

.report-hero::after {
  content: "REPORT";
  position: absolute;
  right: 328px;
  top: 13px;
  color: #fde8ed;
  font-size: 36px;
  font-weight: 950;
  letter-spacing: 0;
  pointer-events: none;
}

.hero-main,
.hero-side {
  position: relative;
  z-index: 1;
}

.hero-main h2 {
  position: relative;
  margin-top: 22px;
  color: var(--report-ink);
  font-size: 31px;
  font-weight: 950;
}

.hero-main h2::after {
  content: "";
  display: block;
  width: 128px;
  height: 6px;
  margin-top: 12px;
  background: var(--report-yellow);
  border-radius: 2px;
  transform: rotate(-1deg);
}

.eyebrow,
.block-label {
  color: var(--report-red-dark);
  font-weight: 900;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.avatar {
  width: 64px;
  height: 64px;
  flex-basis: 64px;
  border: 3px solid #fff;
  background: var(--report-pink);
  color: var(--report-red-dark);
  box-shadow: 0 0 0 2px #ffabc0, 4px 4px 0 var(--report-yellow);
}

.account-text strong {
  font-size: 20px;
  font-weight: 950;
}

.account-positioning {
  border-radius: 5px;
  background: var(--report-pink);
  color: var(--report-red-dark) !important;
}

.hero-side {
  border-color: #e8234b;
  background: var(--report-red);
  box-shadow: 6px 6px 0 #ffd43b;
}

.metric-panel-head span,
.hero-side .metric-panel-head strong {
  color: #fff;
}

.hero-side .metric-panel-head strong {
  background: #151318;
}

.metric {
  border-color: #fff;
  box-shadow: 0 4px 12px rgba(129, 0, 34, 0.08);
}

.metric strong {
  color: var(--report-ink);
  font-weight: 950;
}

.quick-judgement {
  overflow: hidden;
}

.judgement-block {
  position: relative;
  padding: 24px;
}

.judgement-block:first-child {
  border-top: 4px solid var(--report-green);
}

.judgement-block.caution {
  border-top: 4px solid var(--report-yellow);
  background: #fffdf3;
}

.judgement-block h3,
.section-head h3,
.data-flow-head h3 {
  color: var(--report-ink);
  font-weight: 950;
}

.data-flow-panel {
  border-left: 5px solid var(--report-blue);
}

.data-flow-rule {
  border-radius: 5px;
  background: #eef3ff;
  color: #214fae;
}

.flow-metric {
  border-color: var(--report-line);
  background: #fffafa;
}

.flow-metric strong {
  color: var(--report-red-dark);
  font-weight: 950;
}

.warning-band {
  border-color: #f0d477;
  background: #fff9df;
}

.detail-fetch-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 6px;
  background: var(--report-red);
  box-shadow: 4px 4px 0 #f0cb25;
}

.section-block {
  position: relative;
  padding: 24px;
}

.section-head {
  padding-bottom: 12px;
  border-bottom: 2px solid #f7e8ec;
}

.section-head::after {
  content: "";
  position: absolute;
  left: 24px;
  top: 72px;
  width: 62px;
  height: 3px;
  background: var(--report-yellow);
}

.insight-card,
.evidence-card,
.action-card {
  border-color: var(--report-line);
  box-shadow: 0 8px 20px rgba(194, 35, 75, 0.06);
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s;
}

.insight-card {
  border-top: 4px solid var(--report-red);
}

.evidence-card {
  border-top: 4px solid var(--report-green);
}

.action-card {
  border-top: 4px solid var(--report-blue);
}

.insight-card:hover,
.evidence-card:hover,
.action-card:hover {
  transform: translateY(-2px);
  border-color: #f3a4b6;
  box-shadow: 0 12px 24px rgba(194, 35, 75, 0.11);
}

.metric-row span,
.used-by span {
  border-radius: 5px;
  background: var(--report-pink);
  color: #7d2540;
}

.matter {
  border-left-color: var(--report-yellow);
  background: #fffdf3;
  padding: 9px 10px;
}

.evidence-reason {
  border-left-color: var(--report-green);
  background: #f3fbf7;
  padding: 9px 10px;
}

.text-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--report-red-dark);
}

.text-button.danger {
  color: #9a6500;
}

.topic-table,
.dimension-panel,
.dimension-tabs button {
  border-color: var(--report-line);
}

.topic-row.header {
  background: var(--report-pink);
  color: #6c3646;
}

.topic-row:not(.header):hover {
  background: #fff8f9;
}

.dimension-tabs button {
  border-radius: 6px;
  font-weight: 800;
}

.dimension-tabs button.active {
  border-color: var(--report-red);
  background: var(--report-red);
  color: #fff;
  box-shadow: 3px 3px 0 var(--report-yellow);
}

.day-row span {
  color: var(--report-red-dark);
}

.export-row {
  border-top: 4px solid var(--report-red);
  background: #fff;
}

@media (max-width: 900px) {
  .report-hero::after { right: 24px; opacity: 0.65; }
  .hero-side { box-shadow: 4px 4px 0 #ffd43b; }
  .section-head::after { display: none; }
}

@media (max-width: 560px) {
  .report-hero { padding-top: 22px; }
  .report-hero::after { display: none; }
  .hero-main h2 { font-size: 24px; }
  .account-row { align-items: flex-start; }
  .account-bio { display: -webkit-box !important; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
}
</style>
