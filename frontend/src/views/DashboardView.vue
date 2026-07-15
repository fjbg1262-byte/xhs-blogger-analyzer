<template>
  <div class="dashboard-page">
    <section class="dashboard-hero">
      <div class="hero-copy">
        <div class="launch-label"><span aria-hidden="true">✦</span>本地测试版</div>
        <h2>把对标账号，拆成下一步行动</h2>
        <p>打开博主主页，采集近 100 篇公开内容，生成有证据、有边界的分析报告。</p>
        <router-link to="/analysis/new" class="btn hero-button"><span aria-hidden="true">＋</span>新建分析</router-link>
      </div>
      <div class="hero-flow" aria-label="分析流程">
        <div><i class="flow-icon" aria-hidden="true">◎</i><span>打开主页</span><b>01</b></div>
        <div><i class="flow-icon" aria-hidden="true">⌁</i><span>自动分析</span><b>02</b></div>
        <div><i class="flow-icon" aria-hidden="true">▤</i><span>生成报告</span><b>03</b></div>
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi-card" v-for="kpi in kpis" :key="kpi.label">
        <div class="kpi-icon" :class="kpi.tone" aria-hidden="true">{{ kpi.icon }}</div>
        <div>
          <span>{{ kpi.label }}</span>
          <strong>{{ kpi.value }}</strong>
          <small>{{ kpi.sub }}</small>
        </div>
      </article>
    </section>

    <section class="recent-section">
      <div class="section-heading">
        <div>
          <span>分析记录</span>
          <h3>最近分析</h3>
        </div>
        <div class="local-note"><span aria-hidden="true">✓</span>数据保存在本机</div>
      </div>
      <div class="table-wrap" v-if="tasks.length > 0">
        <table>
          <thead>
            <tr>
              <th>账号</th>
              <th>类型</th>
              <th>状态</th>
              <th>进度</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id">
              <td><strong>#{{ t.account_id || '-' }}</strong></td>
              <td>{{ taskTypeLabel(t.task_type) }}</td>
              <td><span :class="statusBadge(t.status)">{{ statusLabel(t.status) }}</span></td>
              <td>{{ t.progress }}%</td>
              <td class="time-cell">{{ formatTime(t.created_at) }}</td>
              <td>
                <router-link v-if="t.status === 'completed'" :to="`/analysis/${t.id}`" class="row-action">
                  查看报告<span aria-hidden="true">→</span>
                </router-link>
                <button v-else-if="t.status === 'running' || t.status === 'pending'" @click="pollTask(t.id)" class="row-action">
                  刷新<span aria-hidden="true">↻</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">
        <span class="empty-icon" aria-hidden="true">◎</span>
        <strong>还没有分析记录</strong>
        <span>从一个你真正想学习的账号开始。</span>
        <router-link to="/analysis/new">开始第一次分析<span aria-hidden="true">→</span></router-link>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { taskAPI } from '../api/client'

const tasks = ref<any[]>([])
const polling = ref(false)

const kpis = ref([
  { label: '总分析次数', value: '-', sub: '所有账号', icon: '◎', tone: 'red' },
  { label: '已完成任务', value: '-', sub: '可查看完整报告', icon: '✓', tone: 'green' },
  { label: '运行中任务', value: '-', sub: '当前本地队列', icon: '↻', tone: 'blue' },
])

async function loadTasks() {
  try {
    const res = await taskAPI.list()
    tasks.value = res.data
    const completed = res.data.filter((t: any) => t.status === 'completed')
    const running = res.data.filter((t: any) => t.status === 'running' || t.status === 'pending')
    kpis.value[0].value = String(res.data.length)
    kpis.value[1].value = String(completed.length)
    kpis.value[2].value = String(running.length)
  } catch (e) {
    console.error('Failed to load tasks', e)
  }
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.slice(0, 19).replace('T', ' ')
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function taskTypeLabel(type: string) {
  const map: Record<string, string> = {
    full_analysis: '完整分析',
    competitor_discovery: '对标发现',
  }
  return map[type] || type
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending: 'badge badge-info',
    running: 'badge badge-warning',
    completed: 'badge badge-success',
    failed: 'badge badge-error',
    cancelled: 'badge',
  }
  return map[status] || 'badge'
}

function pollTask(id: number) {
  polling.value = true
  const check = async () => {
    try {
      const res = await taskAPI.get(id)
      const task = res.data
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx >= 0) tasks.value[idx] = task
      if (task.status === 'running' || task.status === 'pending') setTimeout(check, 3000)
      else {
        polling.value = false
        loadTasks()
      }
    } catch { polling.value = false }
  }
  setTimeout(check, 1000)
}

onMounted(loadTasks)
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-hero {
  min-height: 286px;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(340px, 0.75fr);
  gap: 30px;
  align-items: center;
  padding: 38px 42px;
  background: #ff3158;
  color: #fff;
  border: 1px solid #e92048;
  border-radius: 8px;
  box-shadow: 0 16px 34px rgba(205, 26, 69, 0.18);
  overflow: hidden;
}

.launch-label {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 5px 9px;
  background: #fff;
  color: #d9133f;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.hero-copy h2 {
  max-width: 680px;
  font-size: 40px;
  line-height: 1.15;
  font-weight: 950;
  letter-spacing: 0;
}

.hero-copy p {
  max-width: 650px;
  margin: 14px 0 22px;
  color: #fff7f8;
  font-size: 16px;
}

.hero-button {
  background: #151318;
  color: #fff;
  box-shadow: 5px 5px 0 #ffd43b;
}

.hero-button:hover {
  background: #000;
  color: #fff;
  transform: translate(-1px, -1px);
}

.hero-flow {
  display: grid;
  gap: 10px;
}

.hero-flow > div {
  min-height: 62px;
  display: grid;
  grid-template-columns: 32px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  background: #fff;
  color: #241e22;
  box-shadow: 5px 5px 0 rgba(110, 0, 29, 0.15);
}

.hero-flow span { font-weight: 900; }
.hero-flow b { color: #ff3158; font-size: 18px; }
.flow-icon { font-style: normal; font-size: 23px; font-weight: 900; }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border: 1px solid #efdce1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 9px 24px rgba(194, 35, 75, 0.07);
}

.kpi-card > div:last-child { min-width: 0; }
.kpi-card span, .kpi-card small { display: block; }
.kpi-card span { color: #746b70; font-size: 12px; font-weight: 800; }
.kpi-card strong { display: block; margin: 1px 0; font-size: 28px; line-height: 1.2; }
.kpi-card small { color: #91868c; font-size: 12px; }

.kpi-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  font-size: 21px;
  font-weight: 950;
}

.kpi-icon.red { background: #fff0f3; color: #d9133f; }
.kpi-icon.green { background: #e5f8ef; color: #118354; }
.kpi-icon.blue { background: #eaf0ff; color: #2f6cf5; }

.recent-section {
  border: 1px solid #efdce1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(194, 35, 75, 0.07);
  overflow: hidden;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  border-bottom: 1px solid #f1e3e7;
}

.section-heading span { color: #d9133f; font-size: 12px; font-weight: 900; }
.section-heading h3 { margin-top: 2px; font-size: 21px; }
.local-note { display: inline-flex; align-items: center; gap: 6px; color: #118354; font-size: 12px; font-weight: 800; }
.table-wrap { overflow-x: auto; }
.time-cell { min-width: 150px; font-size: 12px; white-space: nowrap; }

.row-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 0;
  background: transparent;
  color: #d9133f;
  font-size: 12px;
  font-weight: 900;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
}

.empty-state {
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #746b70;
  text-align: center;
}

.empty-state strong { color: #151318; font-size: 17px; }
.empty-icon { color: #ff3158; font-size: 34px; font-weight: 950; }
.empty-state a { display: inline-flex; align-items: center; gap: 4px; margin-top: 6px; color: #d9133f; font-weight: 900; text-decoration: none; }

@media (max-width: 880px) {
  .dashboard-hero { grid-template-columns: 1fr; padding: 28px; }
  .hero-copy h2 { font-size: 34px; }
  .hero-flow { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .hero-flow > div { grid-template-columns: 1fr; text-align: center; justify-items: center; }
}

@media (max-width: 620px) {
  .dashboard-hero { padding: 22px 18px; }
  .hero-copy h2 { font-size: 29px; }
  .hero-flow { grid-template-columns: 1fr; }
  .hero-flow > div { grid-template-columns: 28px 1fr auto; justify-items: initial; text-align: left; }
  .kpi-grid { grid-template-columns: 1fr; }
  .section-heading { align-items: flex-start; }
  .local-note { display: none; }
}
</style>
