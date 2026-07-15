<template>
  <div>
    <h2 style="margin-bottom: 24px;">账号对比</h2>

    <div class="form-group">
      <label>选择要对比的分析任务（至少 2 个）</label>
      <select v-model="selectedTaskIds" multiple style="height: 120px;">
        <option v-for="t in completedTasks" :key="t.id" :value="t.id">
          Task #{{ t.id }} ({{ t.created_at?.slice(0, 10) || '' }})
        </option>
      </select>
    </div>

    <button @click="runCompare" class="btn btn-primary" :disabled="selectedTaskIds.length < 2 || loading">
      {{ loading ? '对比中...' : '开始对比' }}
    </button>

    <div v-if="comparisonData" class="card" style="margin-top: 24px;">
      <h3 style="margin-bottom: 16px;">对比结果</h3>
      <div v-for="item in comparisonData" :key="item.task_id" style="margin-bottom: 20px; padding: 16px; background: #f5f5f7; border-radius: 8px;">
        <h4>Task #{{ item.task_id }}</h4>
        <div class="markdown-body" v-html="renderProfile(item.profile)"></div>
        <div v-if="item.metrics" style="margin-top: 8px;">
          <span style="margin-right: 16px;">均赞：{{ item.metrics.avg_likes }}</span>
          <span style="margin-right: 16px;">中位数：{{ item.metrics.median_likes }}</span>
          <span>最高赞：{{ item.metrics.max_likes }}</span>
        </div>
      </div>

      <button v-if="selectedTaskIds.length === 2" @click="runAICompare" class="btn btn-primary" :disabled="aiLoading">
        {{ aiLoading ? 'AI 分析中...' : 'AI 深度对比' }}
      </button>

      <div v-if="aiResult" class="markdown-body" style="margin-top: 16px; white-space: pre-wrap; background: #f0f5ff; padding: 16px; border-radius: 8px;">
        {{ aiResult }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { taskAPI, reportAPI, aiAPI } from '../api/client'
import { marked } from 'marked'

const tasks = ref<any[]>([])
const selectedTaskIds = ref<number[]>([])
const comparisonData = ref<any[] | null>(null)
const loading = ref(false)
const aiLoading = ref(false)
const aiResult = ref('')

const completedTasks = computed(() => tasks.value.filter((t: any) => t.status === 'completed'))

function renderProfile(md: string) {
  if (!md) return ''
  try { return marked(md) } catch { return md }
}

async function runCompare() {
  if (selectedTaskIds.value.length < 2) return
  loading.value = true
  try {
    const res = await reportAPI.compare(selectedTaskIds.value)
    comparisonData.value = res.data.comparison
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function runAICompare() {
  if (selectedTaskIds.value.length !== 2) return
  aiLoading.value = true
  aiResult.value = ''
  try {
    const res = await aiAPI.compare(selectedTaskIds.value[0], selectedTaskIds.value[1])
    aiResult.value = res.data.result
  } catch (e: any) { console.error(e) }
  finally { aiLoading.value = false }
}

onMounted(async () => {
  try {
    const res = await taskAPI.list()
    tasks.value = res.data
  } catch {}
})
</script>
