<template>
  <div>
    <h2 style="margin-bottom: 24px;">对标搜索</h2>
    <p style="color: #8e8e93; margin-bottom: 20px;">输入关键词，发现同类博主并创建分析任务。</p>

    <div class="card" style="max-width: 640px; margin-bottom: 24px;">
      <div class="form-group">
        <label>搜索关键词</label>
        <input v-model="keyword" placeholder="例如：AI 博主、穿搭、美食" @keyup.enter="search" />
      </div>
      <div class="form-group">
        <label>Cookie</label>
        <select v-model="selectedCookieId">
          <option value="">选择 Cookie</option>
          <option v-for="c in cookies" :key="c.id" :value="c.id">{{ c.nickname || `Cookie #${c.id}` }}</option>
        </select>
      </div>
      <button @click="search" class="btn btn-primary" :disabled="!keyword || !selectedCookieId || searching">
        {{ searching ? '创建中...' : '创建对标发现任务' }}
      </button>
    </div>

    <div v-if="discoveryTaskId" class="card" style="margin-top: 16px; background: #d1fae5;">
      对标发现任务已创建（ID: {{ discoveryTaskId }}）。
      <router-link :to="`/analysis/${discoveryTaskId}`" style="margin-left: 8px;">查看进度</router-link>
    </div>

    <div v-if="error" class="card" style="margin-top: 16px; background: #fee2e2; color: #991b1b;">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { taskAPI, cookieAPI } from '../api/client'

const keyword = ref('')
const selectedCookieId = ref<number | ''>('')
const cookies = ref<any[]>([])
const searching = ref(false)
const discoveryTaskId = ref<number | null>(null)
const error = ref('')

async function search() {
  if (!keyword.value || !selectedCookieId.value) return
  searching.value = true
  error.value = ''
  try {
    const res = await taskAPI.competitorDiscover(keyword.value, 10, selectedCookieId.value as number)
    discoveryTaskId.value = res.data.id
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '创建任务失败'
  } finally {
    searching.value = false
  }
}

onMounted(async () => {
  try {
    const res = await cookieAPI.list()
    cookies.value = res.data
  } catch {}
})
</script>
