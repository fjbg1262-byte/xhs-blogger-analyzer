<template>
  <section class="compare">
    <div class="compare-head">
      <div>
        <p class="eyebrow">ACCOUNT BENCHMARK</p>
        <h2>账号对比</h2>
        <p class="lede">选 2 至 5 个已采集账号，按同一套八维看差异；对比只用公开互动和已采集字段。</p>
      </div>
      <button class="btn primary" type="button" :disabled="loading || selected.length < 2 || selected.length > 5" @click="run">
        {{ result ? '重新对比' : '开始对比' }}
      </button>
    </div>

    <div v-if="loadingAccounts" class="state">正在读取账号…</div>
    <div v-else-if="!accounts.length" class="state">还没有可对比的账号，先完成一次采集。</div>

    <div v-else class="picker">
      <button
        v-for="account in accounts"
        :key="account.id"
        type="button"
        class="pick"
        :class="{ active: selected.includes(account.id) }"
        @click="toggle(account.id)"
      >
        <span class="avatar">{{ account.name.slice(0, 1) }}</span>
        <span class="pick-copy"><b>{{ label(account) }}</b><small>{{ account.note_count }} 篇</small></span>
        <i>{{ selected.includes(account.id) ? '✓' : '+' }}</i>
      </button>
    </div>
    <p class="hint">已选 {{ selected.length }} 个账号（最多 5 个，至少 2 个）。</p>

    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="loading" class="state">正在生成对比…</div>

    <template v-else-if="result">
      <div class="account-cards">
        <article v-for="account in result.accounts" :key="account.task_id">
          <span class="avatar">{{ account.name.slice(0, 1) }}</span>
          <h3>{{ label(account) }}</h3>
          <p>{{ account.notes }} 篇 · 图文 {{ account.image_share }}% / 视频 {{ account.video_share }}%</p>
          <div><b>{{ compact(account.total_engagement) }}</b><small>公开互动</small><b>{{ Math.round(account.median_engagement) }}</b><small>单篇中位数</small></div>
        </article>
      </div>

      <div class="table-wrap">
        <div class="compare-table">
          <div class="compare-row header" :style="gridStyle"><span>维度</span><b v-for="account in result.accounts" :key="account.task_id">{{ label(account) }}</b></div>
          <div v-for="row in result.rows" :key="row.title" class="compare-row" :style="gridStyle">
            <span>{{ row.title }}</span>
            <p v-for="(cell, index) in row.values" :key="index">{{ cell }}</p>
          </div>
        </div>
      </div>

      <div class="takeaways">
        <article v-for="item in result.takeaways" :key="item.title">
          <p class="tag">{{ item.kind }}</p>
          <h3>{{ item.title }}</h3>
          <p>{{ item.body }}</p>
        </article>
      </div>

      <div class="plan">
        <div class="plan-head"><p class="eyebrow">ONE WEEK PLAN</p><h3>按对比结果排下周动作</h3><small>5 个可执行动作</small></div>
        <div class="plan-grid">
          <article v-for="item in result.plan" :key="item.day"><span>{{ item.day }}</span><b>{{ item.title }}</b><p>{{ item.copy }}</p></article>
        </div>
      </div>

      <p class="boundary">{{ result.boundary }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { workspaceAPI } from '../api/client'

interface AccountCard { id: number; name: string; note_count: number; last_task_id: number | null }
interface Profile {
  task_id: number
  name: string
  notes: number
  image_share: number
  video_share: number
  total_engagement: number
  median_engagement: number
  best_type: string
}
interface Result {
  accounts: Profile[]
  rows: { title: string; values: string[] }[]
  takeaways: { kind: string; title: string; body: string }[]
  plan: { day: string; title: string; copy: string }[]
  boundary: string
}

const accounts = ref<AccountCard[]>([])
const selected = ref<number[]>([])
const loadingAccounts = ref(true)
const loading = ref(false)
const error = ref('')
const result = ref<Result | null>(null)

const gridStyle = computed(() => ({
  gridTemplateColumns: `140px repeat(${Math.max(1, result.value?.accounts.length || 1)}, minmax(0, 1fr))`,
}))

function label(account: { name: string; id?: number; task_id?: number }) {
  const identifier = account.id ?? account.task_id
  const duplicates = accounts.value.filter(item => item.name === account.name).length
  return duplicates > 1 && identifier ? `${account.name} #${identifier}` : account.name
}
function compact(value: number) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString('zh-CN')
}
function toggle(id: number) {
  if (selected.value.includes(id)) {
    selected.value = selected.value.filter(item => item !== id)
    return
  }
  if (selected.value.length >= 5) return
  selected.value = [...selected.value, id]
}

async function loadAccounts() {
  loadingAccounts.value = true
  try {
    const response = await workspaceAPI.tasks()
    accounts.value = (response.data.accounts as AccountCard[]).filter(account => account.last_task_id)
    selected.value = accounts.value.slice(0, 2).map(account => account.id)
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '读取账号失败。'
  } finally {
    loadingAccounts.value = false
  }
}

async function run() {
  const taskIds = selected.value
    .map(id => accounts.value.find(account => account.id === id)?.last_task_id)
    .filter((id): id is number => typeof id === 'number')
  if (taskIds.length < 2) {
    error.value = '至少选择 2 个已有采集结果的账号。'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const response = await workspaceAPI.compare(taskIds)
    result.value = response.data as Result
  } catch (exc: any) {
    result.value = null
    error.value = exc?.response?.data?.detail || '对比失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(loadAccounts)
</script>

<style scoped>
.compare { --xhs: #ff2442; --xhs-dark: #d8102f; --rust: #b5430c; --card: #fffdf9; --ink: #28251f; --muted: #7d7364; --muted-2: #9b8d79; --line: #ded4c5; --line-soft: #e9e1d5; --serif: "Songti SC", "STSong", "SimSun", Georgia, serif; color: var(--ink); }
.compare * { box-sizing: border-box; }
.compare-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.eyebrow { margin: 0 0 6px; font-size: 9px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--muted-2); }
.compare-head h2 { margin: 0; font-family: var(--serif); font-size: 24px; }
.lede { margin: 6px 0 0; font-size: 11.5px; color: var(--muted); }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 34px; padding: 7px 14px; border: 1px solid transparent; border-radius: 5px; font-size: 12.5px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.btn.primary { background: var(--xhs); color: #fff; }
.btn.primary:hover { background: var(--xhs-dark); }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.state { padding: 28px 0; color: var(--muted); font-size: 12.5px; }
.error { margin: 10px 0 0; padding: 9px 11px; background: #fdeceb; color: #a33a2c; border-radius: 4px; font-size: 11.5px; }

.picker { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; margin-top: 14px; }
.pick { display: flex; align-items: center; gap: 9px; padding: 10px 12px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; text-align: left; cursor: pointer; }
.pick.active { border-color: var(--xhs); background: #fff0f2; }
.avatar { width: 30px; height: 30px; flex: 0 0 30px; display: grid; place-items: center; border-radius: 7px; background: #c0442a; color: #fff; font-size: 13px; font-weight: 700; }
.pick-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.pick-copy b { font-family: var(--serif); font-size: 13px; }
.pick-copy small { font-size: 9.5px; color: var(--muted-2); }
.pick i { font-style: normal; color: var(--xhs); font-size: 12px; }
.hint { margin: 8px 0 0; font-size: 10.5px; color: var(--muted-2); }

.account-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 16px; }
.account-cards article { padding: 13px 14px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.account-cards h3 { margin: 8px 0 2px; font-family: var(--serif); font-size: 15px; }
.account-cards p { margin: 0; font-size: 10.5px; color: var(--muted); }
.account-cards div { display: flex; align-items: baseline; gap: 6px; margin-top: 9px; flex-wrap: wrap; }
.account-cards b { font-family: var(--serif); font-size: 18px; color: var(--rust); }
.account-cards small { font-size: 9.5px; color: var(--muted-2); margin-right: 8px; }

.table-wrap { margin-top: 12px; border: 1px solid var(--line); border-radius: 6px; overflow-x: auto; background: var(--card); }
.compare-table { min-width: 640px; }
.compare-row { display: grid; border-bottom: 1px solid var(--line-soft); }
.compare-row > span { padding: 9px 12px; font-size: 10.5px; color: var(--muted); background: #faf5ec; border-right: 1px solid var(--line-soft); }
.compare-row > p, .compare-row > b { margin: 0; padding: 9px 12px; font-size: 11px; line-height: 1.6; border-right: 1px solid var(--line-soft); }
.compare-row > b { font-family: var(--serif); font-size: 12px; }
.compare-row.header { background: #f4ecdf; }
.compare-row.header > span, .compare-row.header > b { font-weight: 700; color: #6f6355; background: transparent; }
.compare-row:last-child { border-bottom: 0; }

.takeaways { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin-top: 12px; }
.takeaways article { padding: 14px 16px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.takeaways h3 { margin: 7px 0 5px; font-family: var(--serif); font-size: 15px; line-height: 1.5; }
.takeaways p:last-child { margin: 0; font-size: 11.5px; line-height: 1.75; color: #4b453b; }
.tag { margin: 0; font-size: 9px; letter-spacing: .12em; text-transform: uppercase; color: #9a8b74; }

.plan { margin-top: 12px; padding: 14px 16px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.plan-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.plan-head h3 { margin: 0; font-family: var(--serif); font-size: 16px; }
.plan-head small { font-size: 10px; color: var(--muted-2); }
.plan-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin-top: 11px; }
.plan-grid article { padding: 10px 11px; border: 1px solid var(--line-soft); border-radius: 5px; background: #fcf8f1; }
.plan-grid span { font-size: 9px; letter-spacing: .06em; color: var(--rust); }
.plan-grid b { display: block; margin-top: 4px; font-size: 11.5px; }
.plan-grid p { margin: 4px 0 0; font-size: 10px; line-height: 1.65; color: var(--muted); }
.boundary { margin: 12px 0 0; padding: 9px 12px; background: #efe7da; border-radius: 4px; font-size: 10.5px; color: #776d5d; }

@media (max-width: 1180px) {
  .plan-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
