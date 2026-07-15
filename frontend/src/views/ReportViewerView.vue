<template>
  <div>
    <router-link to="/dashboard" class="btn btn-secondary" style="margin-bottom: 16px;">返回</router-link>

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
      <div class="card">
        <p style="margin-bottom: 12px; color: #8e8e93;">该任务缺少结构化报告，暂时显示旧版 Markdown。</p>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px;">
          <button v-for="rt in reportTypes" :key="rt.key"
            @click="selectedReport = rt.key"
            :class="['btn', selectedReport === rt.key ? 'btn-primary' : 'btn-secondary']"
            style="font-size: 12px; padding: 6px 14px;">
            {{ rt.label }}
          </button>
        </div>
        <div class="markdown-body" v-html="renderedMarkdown"></div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { reportAPI, taskAPI } from '../api/client'
import { marked } from 'marked'
import { defaultReportKey, reportTypes } from '../constants/reports'
import ProductReport from '../components/ProductReport.vue'

const route = useRoute()
const taskId = computed(() => Number(route.params.taskId))
const initialReport = computed(() => String(route.params.reportType || defaultReportKey))
const selectedReport = ref(initialReport.value)
const reports = ref<Record<string, string>>({})
const reportQuality = ref<any>(null)
const brief = ref<any>(null)
const detailFetch = ref<any>(null)

const renderedMarkdown = computed(() => {
  const md = reports.value[selectedReport.value]
  if (!md) return '<p style="color:#8e8e93;">暂无内容</p>'
  try { return marked(md) } catch { return md }
})

async function load() {
  try {
    const res = await reportAPI.list(taskId.value)
    reports.value = res.data.reports || {}
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
  } catch {}
}

onMounted(load)
</script>
