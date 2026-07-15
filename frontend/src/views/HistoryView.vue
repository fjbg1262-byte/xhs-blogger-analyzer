<template>
  <div>
    <h2 style="margin-bottom: 24px;">历史记录</h2>

    <div class="card">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>类型</th>
            <th>状态</th>
            <th>进度</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
            <td>{{ t.id }}</td>
            <td>{{ taskTypeLabel(t.task_type) }}</td>
            <td><span :class="statusBadge(t.status)">{{ statusLabel(t.status) }}</span></td>
            <td>{{ t.progress }}%</td>
            <td>{{ formatTime(t.created_at) }}</td>
            <td>
              <router-link v-if="t.status === 'completed'" :to="`/analysis/${t.id}`" class="btn btn-secondary" style="padding: 4px 12px; font-size: 12px;">查看</router-link>
              <button v-else-if="t.status === 'running' || t.status === 'pending'" @click="refresh" class="btn btn-secondary" style="padding: 4px 12px; font-size: 12px;">刷新</button>
            </td>
          </tr>
          <tr v-if="tasks.length === 0">
            <td colspan="6" style="text-align: center; color: #8e8e93; padding: 40px;">暂无记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { taskAPI } from '../api/client'

const tasks = ref<any[]>([])

const statusBadge = (s: string) => {
  const map: Record<string, string> = { pending:'badge badge-info', running:'badge badge-warning', completed:'badge badge-success', failed:'badge badge-error' }
  return map[s] || 'badge'
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

function taskTypeLabel(type: string) {
  const map: Record<string, string> = { full_analysis: '完整分析', competitor_discovery: '对标发现' }
  return map[type] || type
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.slice(0, 19).replace('T', ' ')
}

async function refresh() {
  try {
    const res = await taskAPI.list()
    tasks.value = res.data
  } catch {}
}

onMounted(refresh)
</script>
