<template>
  <div>
    <h2 style="margin-bottom: 24px;">AI 工具</h2>

    <div class="card" style="margin-bottom: 16px;">
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <button :class="['btn', tab === 'deconstruct' ? 'btn-primary' : 'btn-secondary']" @click="tab = 'deconstruct'">爆款拆解</button>
        <button :class="['btn', tab === 'diagnose' ? 'btn-primary' : 'btn-secondary']" @click="tab = 'diagnose'">账号诊断</button>
        <button :class="['btn', tab === 'rewrite' ? 'btn-primary' : 'btn-secondary']" @click="tab = 'rewrite'">标题仿写</button>
      </div>
    </div>

    <div v-if="tab === 'deconstruct'" class="card">
      <div class="form-group">
        <label>选择已完成的分析任务</label>
        <select v-model="taskId">
          <option value="">请选择</option>
          <option v-for="t in tasks" :key="t.id" :value="t.id">Task #{{ t.id }} ({{ t.status }})</option>
        </select>
      </div>
      <button @click="runDeconstruct" class="btn btn-primary" :disabled="!taskId || aiLoading">开始拆解</button>
      <div v-if="aiResult" class="markdown-body" style="margin-top: 16px; white-space: pre-wrap;">{{ aiResult }}</div>
    </div>

    <div v-if="tab === 'diagnose'" class="card">
      <div class="form-group">
        <label>选择已完成的分析任务</label>
        <select v-model="taskId">
          <option value="">请选择</option>
          <option v-for="t in tasks" :key="t.id" :value="t.id">Task #{{ t.id }} ({{ t.status }})</option>
        </select>
      </div>
      <div class="form-group">
        <label>领域（可选）</label>
        <input v-model="niche" placeholder="例如：AI、美妆、健身" />
      </div>
      <button @click="runDiagnose" class="btn btn-primary" :disabled="!taskId || aiLoading">开始诊断</button>
      <div v-if="aiResult" class="markdown-body" style="margin-top: 16px; white-space: pre-wrap;">{{ aiResult }}</div>
    </div>

    <div v-if="tab === 'rewrite'" class="card">
      <div class="form-group">
        <label>原始标题</label>
        <input v-model="originalTitle" placeholder="粘贴你想改写的小红书标题" />
      </div>
      <div class="form-group">
        <label>改写风格</label>
        <select v-model="rewriteStyle">
          <option value="high-engagement">高互动</option>
          <option value="authoritative">专业权威</option>
          <option value="curiosity-gap">好奇心缺口</option>
          <option value="storytelling">故事叙述</option>
          <option value="listicle">清单体</option>
        </select>
      </div>
      <button @click="runRewrite" class="btn btn-primary" :disabled="!originalTitle || aiLoading">生成改写</button>
      <div v-if="aiResult" class="markdown-body" style="margin-top: 16px; white-space: pre-wrap;">{{ aiResult }}</div>
    </div>

    <div v-if="aiLoading" style="text-align: center; padding: 20px; color: #8e8e93;">AI 分析中...</div>
    <div v-if="aiError" style="margin-top: 16px; padding: 12px; background: #fee2e2; border-radius: 8px; color: #991b1b;">{{ aiError }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { taskAPI, aiAPI } from '../api/client'

const tab = ref('deconstruct')
const taskId = ref<number | ''>('')
const niche = ref('')
const originalTitle = ref('')
const rewriteStyle = ref('high-engagement')
const tasks = ref<any[]>([])
const aiResult = ref('')
const aiError = ref('')
const aiLoading = ref(false)

async function runDeconstruct() {
  if (!taskId.value) return
  aiLoading.value = true; aiResult.value = ''; aiError.value = ''
  try {
    const res = await aiAPI.deconstruct(taskId.value as number)
    aiResult.value = res.data.result
  } catch (e: any) { aiError.value = e.response?.data?.detail || e.message }
  finally { aiLoading.value = false }
}

async function runDiagnose() {
  if (!taskId.value) return
  aiLoading.value = true; aiResult.value = ''; aiError.value = ''
  try {
    const res = await aiAPI.diagnose(taskId.value as number, niche.value || undefined)
    aiResult.value = res.data.result
  } catch (e: any) { aiError.value = e.response?.data?.detail || e.message }
  finally { aiLoading.value = false }
}

async function runRewrite() {
  aiLoading.value = true; aiResult.value = ''; aiError.value = ''
  try {
    const res = await aiAPI.rewrite(originalTitle.value, rewriteStyle.value)
    aiResult.value = res.data.result
  } catch (e: any) { aiError.value = e.response?.data?.detail || e.message }
  finally { aiLoading.value = false }
}

onMounted(async () => {
  try {
    const res = await taskAPI.list()
    tasks.value = res.data.filter((t: any) => t.status === 'completed')
  } catch {}
})
</script>
