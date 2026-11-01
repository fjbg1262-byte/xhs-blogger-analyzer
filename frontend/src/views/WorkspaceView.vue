<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <span class="brand-mark">
          <svg viewBox="0 0 32 32" width="19" height="19" aria-hidden="true">
            <path d="M15 3.6 17.7 12.3 26.4 15 17.7 17.7 15 26.4 12.3 17.7 3.6 15 12.3 12.3Z" fill="currentColor" />
            <path d="M24.1 3.4 24.9 6 27.5 6.8 24.9 7.6 24.1 10.2 23.3 7.6 20.7 6.8 23.3 6Z" fill="currentColor" opacity=".85" />
          </svg>
        </span>
        <div class="brand-copy">
          <strong>薯光</strong>
          <span>真实采集数据</span>
        </div>
      </div>

      <button class="demo-link" type="button" @click="router.push('/demo')">查看演示数据 →</button>
      <button class="new-btn" type="button" @click="openForm">+ 新建采集</button>

      <p class="side-label">采集记录</p>
      <div class="task-list">
        <button
          v-for="task in tasks"
          :key="task.id"
          type="button"
          class="task-item"
          :class="{ active: task.id === selectedId }"
          @click="select(task.id)"
        >
          <span class="status-dot" :class="task.status" />
          <span class="task-copy">
            <b>{{ accountName(task) }}</b>
            <small>{{ task.status_label }} · {{ task.note_count }} 篇 · #{{ task.id }}</small>
          </span>
          <i>{{ task.failed_count || '' }}</i>
        </button>
      </div>
      <p v-if="!tasks.length && !loading" class="side-empty">还没有采集任务</p>

      <div class="side-foot">
        <span>{{ username || '本机账号' }}</span>
        <button type="button" @click="logout">退出</button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="crumb"><span>工作台</span><i>/</i><strong>真实数据</strong></div>
        <div class="top-actions">
          <span v-if="detail" class="demo-badge">{{ detail.task.status_label }}</span>
          <router-link class="real-link" to="/demo">演示数据 ↗</router-link>
        </div>
      </header>

      <div class="content">
        <section v-if="showForm" class="capture">
          <div class="capture-head">
            <div><p class="eyebrow">NEW COLLECTION</p><h2>采集一个博主主页</h2></div>
            <button class="btn ghost" type="button" @click="showForm = false">收起</button>
          </div>
          <form class="capture-form" @submit.prevent="startCollection">
            <label class="field">
              <span>主页链接</span>
              <input v-model="profileUrl" placeholder="https://www.xiaohongshu.com/user/profile/..." />
            </label>
            <label class="field cookie-field">
              <span>登录状态</span>
              <select v-model="cookieId">
                <option :value="0" disabled>选择浏览器登录状态</option>
                <option v-for="cookie in cookies" :key="cookie.id" :value="cookie.id">
                  {{ cookie.nickname || '未命名' }} · {{ cookie.is_valid === false ? '已失效' : '可用' }}
                </option>
              </select>
            </label>
            <button class="btn primary" type="submit" :disabled="starting || !cookieId">
              {{ starting ? '正在开始…' : '开始采集' }}
            </button>
          </form>
          <p v-if="formError" class="form-error">{{ formError }}</p>
          <p v-else-if="!cookies.length" class="form-hint">还没有登录状态：先在浏览器插件里对任意主页点一次采集，插件会保存登录状态。</p>
        </section>

        <section v-if="startingTaskId && (!detail || detail.task.id !== startingTaskId)" class="progress-panel">
          <div class="progress-head">
            <div><b>正在采集 #{{ startingTaskId }}</b><span>{{ notice || '正在读取主页…' }}</span></div>
            <button class="btn ghost" type="button" @click="stopNewTask">停止采集</button>
          </div>
          <div class="progress-stages">
            <div v-for="step in stageSteps" :key="step.key" :class="{ done: step.done, active: step.active }">
              <i>{{ step.done ? '✓' : step.active ? '●' : '' }}</i><span>{{ step.label }}</span>
            </div>
          </div>
          <p v-if="stageText" class="progress-note">{{ stageText }}</p>
        </section>

        <p v-if="loading" class="state">正在读取采集结果…</p>
        <div v-else-if="error" class="state error">{{ error }}</div>
        <div v-else-if="!detail" class="state empty">
          <b>还没有可展示的采集结果</b>
          <span>用浏览器插件在博主主页点一次采集，结果会出现在这里。</span>
          <router-link to="/demo" class="btn ghost">先看演示数据</router-link>
        </div>

        <template v-else>
          <div class="page-head">
            <div>
              <p class="eyebrow">REAL COLLECTION · TASK #{{ detail.task.id }}</p>
              <h1>{{ detail.account.name }}</h1>
              <p class="lede">
                {{ detail.task.note_count }} 篇 · 图文 {{ detail.stats.image_share }}% / 视频 {{ detail.stats.video_share }}%
                · 最近发布 {{ (detail.stats.latest_published_at || '').slice(0, 10) || '未获取' }}
                · 采集于 {{ (detail.task.completed_at || detail.task.created_at || '').slice(0, 16) }}
              </p>
              <p v-if="notice" class="notice">{{ notice }}</p>
            </div>
            <div class="head-actions">
              <button v-if="canStop" class="btn ghost" type="button" :disabled="busy" @click="stopTask">停止采集</button>
              <button v-if="detail.task.failed_count > 0" class="btn ghost" type="button" :disabled="busy" @click="retryFailed">
                补采未完成 {{ detail.task.failed_count }} 篇
              </button>
              <button class="btn ghost" type="button" :disabled="exporting" @click="download('xlsx')">导出 Excel</button>
              <button class="btn primary" type="button" :disabled="exporting" @click="download('feishu')">导出飞书导入包</button>
            </div>
          </div>

          <div class="kpi-row">
            <article class="kpi"><span>公开互动</span><b>{{ compact(detail.stats.total_engagement) }}</b><small>赞 + 藏 + 评 + 分享</small></article>
            <article class="kpi"><span>单篇中位数</span><b>{{ (detail.stats.median_engagement || 0).toLocaleString() }}</b><small>比均值更不易被爆款拉偏</small></article>
            <article class="kpi"><span>头部贡献</span><b>{{ detail.stats.top_share }}%</b><small>Top {{ detail.stats.top_count }} 篇公开互动占比</small></article>
            <article class="kpi"><span>有正文</span><b>{{ detail.stats.body_count }}</b><small>共 {{ detail.stats.note_count }} 篇，失败 {{ detail.stats.failed_count }} 篇</small></article>
          </div>

          <div class="insight-grid">
            <article class="insight">
              <p class="tag">CONCENTRATION</p>
              <b class="figure">{{ detail.stats.top_share }}%</b>
              <small>头部的互动贡献</small>
              <h3>Top {{ detail.stats.top_count }} 篇内容贡献了主要公开互动</h3>
              <p>本批 Top {{ detail.stats.top_count }} 篇贡献 {{ detail.stats.top_share }}% 的赞藏评享。这不等于账号长期只能靠爆款，但说明复盘应优先解释头部内容的结构。</p>
            </article>
            <article class="insight">
              <p class="tag">FORMAT</p>
              <b class="figure">{{ detail.stats.format_ratio || '—' }}x</b>
              <small>相对账号中位数</small>
              <h3>{{ detail.stats.best_type || '暂无' }} 是本批互动中位数最高的形式</h3>
              <p>
                图文 {{ detail.stats.image_count }} 篇 / {{ detail.stats.image_share }}%，视频 {{ detail.stats.video_count }} 篇 / {{ detail.stats.video_share }}%。
                这里比较的是公开互动快照，不是浏览或曝光效率。
              </p>
            </article>
            <article class="insight">
              <p class="tag">TITLE SIGNAL</p>
              <b class="figure">{{ detail.stats.title_pct }}%</b>
              <small>含数字标题占比</small>
              <h3>数字和具体价格是这批标题的主要信号</h3>
              <p>{{ detail.stats.note_count }} 篇里 {{ detail.stats.title_count }} 篇标题带数字。样本有限，只能作为下一批标题的对照，不构成因果。</p>
            </article>
            <article class="insight">
              <p class="tag">CONTENT PILLAR</p>
              <b class="figure">{{ detail.stats.top_tag_count }} 篇</b>
              <small>最高频内容标签</small>
              <h3>「{{ detail.stats.top_tag || '暂无' }}」是当前样本最常见的内容线索</h3>
              <p>该标签出现在 {{ detail.stats.top_tag_count }} 篇里。标签只说明内容覆盖，不等同于搜索流量或推荐权重。</p>
            </article>
          </div>

          <p v-if="detail.task.reason" class="boundary">本次采集说明：{{ detail.task.reason }}</p>

          <div class="library-tabs">
            <button v-for="tab in typeTabs" :key="tab.key" :class="{ active: typeFilter === tab.key }" @click="typeFilter = tab.key">
              {{ tab.label }}<span>{{ typeCount(tab.key) }}</span>
            </button>
          </div>

          <div class="toolbar">
            <label class="search-box">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="10.9" cy="10.9" r="6.6" /><path d="M15.8 15.8 20 20" /></svg>
              <input v-model="search" placeholder="搜索标题、正文或标签" />
            </label>
            <select v-model="sortBy">
              <option value="engagement">按互动排序</option>
              <option value="likes">按点赞排序</option>
              <option value="published">按发布时间</option>
            </select>
            <label class="check"><input v-model="onlyIncomplete" type="checkbox" />只看未完成</label>
            <div class="view-switch">
              <button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">表格</button>
              <button :class="{ active: viewMode === 'cards' }" @click="viewMode = 'cards'">封面</button>
            </div>
          </div>

          <div v-if="viewMode === 'table'" class="table-wrap">
            <table class="note-table">
              <thead>
                <tr><th>笔记</th><th>类型</th><th>发布时间</th><th>赞 / 藏 / 评 / 享</th><th>标签</th><th>来源</th><th>采集</th></tr>
              </thead>
              <tbody>
                <tr v-for="note in pagedNotes" :key="note.id" @click="openNote(note)">
                  <td>
                    <span class="note-cell">
                      <span class="thumb">
                        <img v-if="note.cover_url" :src="note.cover_url" loading="lazy" referrerpolicy="no-referrer" alt="" @error="broken[note.id] = true" v-show="!broken[note.id]" />
                        <b v-if="!note.cover_url || broken[note.id]">{{ note.type }}</b>
                      </span>
                      <span class="note-text"><b>{{ note.title }}</b><small>{{ note.author || '未获取昵称' }} · {{ note.id }}</small></span>
                    </span>
                  </td>
                  <td><span class="type-pill">{{ note.type }}</span></td>
                  <td>{{ note.published_at || '未获取' }}</td>
                  <td class="engage">
                    <span>赞 {{ metric(note.likes) }}</span><span>藏 {{ metric(note.collected) }}</span>
                    <span>评 {{ metric(note.comments) }}</span><span>享 {{ metric(note.shares) }}</span>
                  </td>
                  <td><span class="tags"><i v-for="tag in note.tags.slice(0, 2)" :key="tag">{{ tag }}</i></span></td>
                  <td><a class="source-col" :href="note.note_url" target="_blank" rel="noreferrer" @click.stop>↗</a></td>
                  <td><span v-if="note.incomplete" class="status-warn" :title="note.failure">未完成</span><span v-else class="status-ok">已完成</span></td>
                </tr>
              </tbody>
            </table>
            <div v-if="!visibleNotes.length" class="empty-state">没有符合筛选条件的笔记</div>
          </div>

          <div v-else class="note-grid">
            <article v-for="note in pagedNotes" :key="note.id" class="note-card" @click="openNote(note)">
              <div class="card-cover">
                <img v-if="note.cover_url" :src="note.cover_url" loading="lazy" referrerpolicy="no-referrer" alt="" @error="broken[note.id] = true" v-show="!broken[note.id]" />
                <b v-if="!note.cover_url || broken[note.id]">{{ note.type }}</b>
                <i>{{ note.type }}</i>
              </div>
              <div class="note-card-copy">
                <h3>{{ note.title }}</h3>
                <p>{{ note.tags.join(' · ') || '无标签' }}</p>
                <div><span>赞 {{ metric(note.likes) }}</span><span>藏 {{ metric(note.collected) }}</span><span>评 {{ metric(note.comments) }}</span></div>
              </div>
            </article>
          </div>
          <div v-if="visibleNotes.length > pageSize" class="pager">
            <button class="btn ghost" type="button" :disabled="page === 1" @click="page -= 1">上一页</button>
            <span>第 {{ page }} / {{ pageCount }} 页 · 共 {{ visibleNotes.length }} 篇</span>
            <button class="btn ghost" type="button" :disabled="page === pageCount" @click="page += 1">下一页</button>
          </div>
        </template>
      </div>

      <aside v-if="activeNote" class="drawer">
        <header>
          <span>笔记详情</span>
          <button type="button" aria-label="关闭" @click="closeNote">×</button>
        </header>
        <div v-if="activeNote.cover_url && !broken[activeNote.id]" class="drawer-cover">
          <img :src="activeNote.cover_url" referrerpolicy="no-referrer" alt="" @error="broken[activeNote.id] = true" />
        </div>
        <div class="drawer-body">
          <span class="type-pill">{{ activeNote.type }}</span>
          <h2>{{ activeNote.title }}</h2>
          <p class="drawer-meta">{{ activeNote.author || '未获取昵称' }} · {{ activeNote.published_at || '发布时间未获取' }} · {{ activeNote.id }}</p>
          <div class="drawer-metrics">
            <div><b>{{ metric(activeNote.likes) }}</b><span>点赞</span></div>
            <div><b>{{ metric(activeNote.collected) }}</b><span>收藏</span></div>
            <div><b>{{ metric(activeNote.comments) }}</b><span>评论</span></div>
            <div><b>{{ metric(activeNote.shares) }}</b><span>分享</span></div>
          </div>
          <div v-if="activeNote.incomplete" class="drawer-alert">
            <span>未完成原因</span>
            <p>{{ activeNote.failure || '正文未获取' }}</p>
            <button class="btn ghost" type="button" @click="retryFailed">补采这一批</button>
          </div>
          <div class="drawer-section">
            <span>正文</span>
            <p v-if="loadingDetail">正在读取正文…</p>
            <p v-else>{{ activeDetail?.body || activeNote.body_preview || '这一篇没有采集到正文。' }}</p>
            <small v-if="activeDetail && activeDetail.body_length > 0" class="body-meta">正文 {{ activeDetail.body_length }} 字</small>
          </div>
          <div class="drawer-section">
            <span>标签</span>
            <div class="drawer-tags"><i v-for="tag in activeNote.tags" :key="tag">{{ tag }}</i><em v-if="!activeNote.tags.length">无标签</em></div>
          </div>
          <div class="drawer-section">
            <span>来源链接</span>
            <a class="source-link" :href="activeNote.note_url" target="_blank" rel="noreferrer">{{ activeNote.note_url }}</a>
          </div>
          <div v-if="activeNote.missing_fields.length" class="drawer-section">
            <span>缺失字段</span>
            <div class="drawer-tags"><i v-for="field in activeNote.missing_fields" :key="field">{{ field }}</i></div>
          </div>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { cookieAPI, libraryAPI, workspaceAPI } from '../api/client'
import { clearAuth, currentUsername } from '../auth'

interface TaskCard {
  id: number
  account_id: number
  status: string
  status_label: string
  progress: number
  target: number
  note_count: number
  body_count: number
  failed_count: number
  reason: string
  created_at: string
  completed_at: string
  has_dataset: boolean
}
interface NoteRow {
  id: string
  title: string
  author: string
  type: string
  published_at: string
  likes: number | null
  collected: number | null
  comments: number | null
  shares: number | null
  engagement: number
  tags: string[]
  cover_url: string
  body_preview: string
  body_length: number
  has_body: boolean
  note_url: string
  incomplete: boolean
  failure: string
  missing_fields: string[]
}
interface NoteDetail extends NoteRow {
  body: string
  image_urls: string[]
  video_url: string
  detail_status: string
  text_status: string
  tags_status: string
  metric_source: string
  count_precision: string
}
interface CookieRow {
  id: number
  nickname: string | null
  is_active: boolean
  is_valid: boolean | null
  created_at: string
}
interface Stats {
  note_count: number
  total_engagement: number
  median_engagement: number | null
  top_count: number
  top_share: number
  format_ratio: number | null
  best_type: string
  image_count: number
  image_share: number
  video_count: number
  video_share: number
  title_count: number
  title_pct: number
  top_tag: string
  top_tag_count: number
  latest_published_at: string
  body_count: number
  failed_count: number
}
interface TaskDetail {
  task: TaskCard
  account: { id: number; name: string; profile_url: string; note_count: number }
  notes: NoteRow[]
  stats: Stats
  meta: { status: string; stop_reason: string; pages: number; duplicates: number }
}

const router = useRouter()
const username = currentUsername
const tasks = ref<TaskCard[]>([])
const accountOfTask = ref<Record<number, string>>({})
const selectedId = ref<number | null>(null)
const detail = ref<TaskDetail | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const exporting = ref(false)
const search = ref('')
const sortBy = ref('engagement')
const typeFilter = ref<'all' | '图文' | '视频' | '未完成'>('all')
const onlyIncomplete = ref(false)
const viewMode = ref<'table' | 'cards'>('table')
const activeNote = ref<NoteRow | null>(null)
const activeDetail = ref<NoteDetail | null>(null)
const loadingDetail = ref(false)
const stageSteps = ref<{ key: string; label: string; done: boolean; active: boolean }[]>([])
const stageText = ref('')
const cookies = ref<CookieRow[]>([])
const showForm = ref(false)
const profileUrl = ref('')
const cookieId = ref(0)
const starting = ref(false)
const formError = ref('')
const startingTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = 50
const broken = ref<Record<string, boolean>>({})
let pollTimer: ReturnType<typeof setInterval> | undefined

const typeTabs = [
  { key: 'all' as const, label: '全部' },
  { key: '图文' as const, label: '图文' },
  { key: '视频' as const, label: '视频' },
  { key: '未完成' as const, label: '未完成' },
]
const canStop = computed(() => detail.value !== null && ['pending', 'running'].includes(detail.value.task.status))

const visibleNotes = computed(() => {
  if (!detail.value) return []
  const query = search.value.trim().toLowerCase()
  const rows = detail.value.notes.filter(note => {
    const tabOk =
      typeFilter.value === 'all' ||
      (typeFilter.value === '未完成' ? note.incomplete : note.type === typeFilter.value)
    const queryOk = !query || `${note.title} ${note.body_preview} ${note.tags.join(' ')}`.toLowerCase().includes(query)
    return tabOk && queryOk && (!onlyIncomplete.value || note.incomplete)
  })
  const sorters: Record<string, (a: NoteRow, b: NoteRow) => number> = {
    engagement: (a, b) => b.engagement - a.engagement,
    likes: (a, b) => (b.likes || 0) - (a.likes || 0),
    published: (a, b) => b.published_at.localeCompare(a.published_at),
  }
  return [...rows].sort(sorters[sortBy.value] || sorters.engagement)
})
const pageCount = computed(() => Math.max(1, Math.ceil(visibleNotes.value.length / pageSize)))
const pagedNotes = computed(() => visibleNotes.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch([search, sortBy, typeFilter, onlyIncomplete], () => {
  page.value = 1
})

function accountName(task: TaskCard) {
  return accountOfTask.value[task.account_id] || `账号 #${task.account_id}`
}
function typeCount(key: string) {
  if (!detail.value) return 0
  if (key === 'all') return detail.value.notes.length
  if (key === '未完成') return detail.value.notes.filter(note => note.incomplete).length
  return detail.value.notes.filter(note => note.type === key).length
}
function metric(value: number | null) {
  return value === null || value === undefined ? '未获取' : compact(value)
}
function compact(value: number) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString('zh-CN')
}

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    const response = await workspaceAPI.tasks()
    tasks.value = response.data.tasks as TaskCard[]
    const mapping: Record<number, string> = {}
    for (const account of response.data.accounts as { id: number; name: string }[]) mapping[account.id] = account.name
    accountOfTask.value = mapping
    const first = tasks.value.find(task => task.has_dataset) || tasks.value[0]
    if (first) await select(first.id)
  } catch (exc: any) {
    error.value = exc?.response?.data?.detail || '读取采集记录失败，请确认本地工具正在运行。'
  } finally {
    loading.value = false
  }
}

async function select(id: number) {
  selectedId.value = id
  closeNote()
  notice.value = ''
  page.value = 1
  try {
    const response = await workspaceAPI.task(id)
    detail.value = response.data as TaskDetail
  } catch (exc: any) {
    detail.value = null
    error.value = exc?.response?.data?.detail || '这个任务还没有可用的采集结果。'
  }
}

async function openNote(note: NoteRow) {
  activeNote.value = note
  activeDetail.value = null
  loadingDetail.value = false
  if (!detail.value) return
  loadingDetail.value = true
  try {
    const response = await workspaceAPI.note(detail.value.task.id, note.id)
    activeDetail.value = response.data as NoteDetail
  } catch {
    /* 详情读取失败时保留列表里的正文预览 */
  } finally {
    loadingDetail.value = false
  }
}

function closeNote() {
  activeNote.value = null
  activeDetail.value = null
  loadingDetail.value = false
}

function defaultStages() {
  return [
    { key: 'prepare', label: '准备任务', done: false, active: true },
    { key: 'read', label: '读取主页列表', done: false, active: false },
    { key: 'detail', label: '补充正文与标签', done: false, active: false },
    { key: 'save', label: '保存结果', done: false, active: false },
  ]
}

async function stopNewTask() {
  if (!startingTaskId.value) return
  try {
    await workspaceAPI.stop(startingTaskId.value)
    notice.value = '已请求停止，正在保存已采集数据…'
  } catch (exc: any) {
    notice.value = exc?.response?.data?.detail || '停止失败，请稍后重试。'
  }
}

async function openForm() {
  showForm.value = true
  formError.value = ''
  try {
    const response = await cookieAPI.list()
    cookies.value = response.data as CookieRow[]
    if (!cookieId.value) cookieId.value = cookies.value.find(item => item.is_valid !== false)?.id || 0
  } catch {
    formError.value = '读取登录状态失败，请确认本地工具正在运行。'
  }
}

async function startCollection() {
  formError.value = ''
  const url = profileUrl.value.trim()
  if (!/^https?:\/\/(www\.)?xiaohongshu\.com\/user\/profile\/[A-Za-z0-9_-]{8,64}\/?/.test(url)) {
    formError.value = '请填写小红书博主主页链接，例如 https://www.xiaohongshu.com/user/profile/…'
    return
  }
  if (!cookieId.value) {
    formError.value = '请选择浏览器登录状态。'
    return
  }
  starting.value = true
  try {
    const response = await libraryAPI.create(url, cookieId.value)
    const id = response.data.id as number
    startingTaskId.value = id
    stageSteps.value = defaultStages()
    stageText.value = '准备任务'
    notice.value = '已开始采集，正在读取主页…'
    showForm.value = false
    profileUrl.value = ''
    await loadListQuiet()
    pollNewTask(id)
  } catch (exc: any) {
    formError.value = exc?.response?.data?.detail || '开始采集失败，请检查登录状态或稍后重试。'
  } finally {
    starting.value = false
  }
}

function pollNewTask(id: number) {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const progress = await workspaceAPI.progress(id)
      const task = progress.data.task as TaskCard
      stageSteps.value = (progress.data.steps as typeof stageSteps.value) || stageSteps.value
      stageText.value = (progress.data.stage as string) || ''
      notice.value = `${task.status_label}：已整理 ${task.note_count} 篇`
      if (!['pending', 'running'].includes(task.status)) {
        clearInterval(pollTimer)
        startingTaskId.value = null
        await loadListQuiet()
        if (task.has_dataset) {
          await select(id)
        } else {
          error.value = `采集没有产出可用结果：${task.reason || task.status_label}`
        }
        notice.value = task.status === 'completed' ? '采集完成，已打开结果。' : `采集结束：${task.status_label}${task.reason ? '，' + task.reason : ''}`
      }
    } catch {
      clearInterval(pollTimer)
      startingTaskId.value = null
    }
  }, 2000)
}

function poll() {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!selectedId.value) return
    try {
      const progress = await workspaceAPI.progress(selectedId.value)
      const status = progress.data.task.status
      notice.value = `当前状态：${progress.data.task.status_label}，已整理 ${progress.data.counts.note_count} 篇`
      if (!['pending', 'running'].includes(status)) {
        clearInterval(pollTimer)
        busy.value = false
        notice.value = '补采结束，已刷新结果。'
        await select(selectedId.value)
        await loadListQuiet()
      }
    } catch {
      clearInterval(pollTimer)
      busy.value = false
    }
  }, 1500)
}

async function loadListQuiet() {
  try {
    const response = await workspaceAPI.tasks()
    tasks.value = response.data.tasks as TaskCard[]
  } catch {
    /* keep the current list */
  }
}

async function stopTask() {
  if (!detail.value) return
  busy.value = true
  try {
    await workspaceAPI.stop(detail.value.task.id)
    notice.value = '已请求停止，正在保存已采集数据…'
    poll()
  } catch (exc: any) {
    notice.value = exc?.response?.data?.detail || '停止失败，请稍后重试。'
    busy.value = false
  }
}

async function retryFailed() {
  if (!detail.value) return
  busy.value = true
  try {
    const response = await workspaceAPI.retry(detail.value.task.id)
    notice.value = response.data.message || `已开始补采 ${response.data.queued} 篇`
    poll()
  } catch (exc: any) {
    notice.value = exc?.response?.data?.detail || '补采失败，请稍后重试。'
    busy.value = false
  }
}

async function download(format: 'xlsx' | 'feishu') {
  if (!detail.value) return
  exporting.value = true
  try {
    const response = await workspaceAPI.export(detail.value.task.id, format)
    const url = URL.createObjectURL(response.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${detail.value.account.name || '笔记库'}-${format}.${format === 'feishu' ? 'xlsx' : 'xlsx'}`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (exc: any) {
    notice.value = exc?.response?.data?.detail || '导出失败，请稍后重试。'
  } finally {
    exporting.value = false
  }
}

function logout() {
  clearAuth()
  router.push('/login')
}

onMounted(loadList)
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.shell {
  --xhs: #ff2442;
  --xhs-dark: #d8102f;
  --rust: #b5430c;
  --paper: #f5f0e7;
  --paper-2: #fbf7f0;
  --card: #fffdf9;
  --ink: #28251f;
  --muted: #7d7364;
  --muted-2: #9b8d79;
  --line: #ded4c5;
  --line-soft: #e9e1d5;
  --serif: "Songti SC", "STSong", "SimSun", Georgia, serif;
  display: grid;
  grid-template-columns: 244px minmax(0, 1fr);
  min-height: 100vh;
  background: var(--paper);
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
  line-height: 1.6;
}
.shell * { box-sizing: border-box; }
.shell button, .shell input, .shell select, .shell a { font: inherit; }

.side { position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; padding: 20px 14px 14px; background: var(--paper-2); border-right: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: 10px; padding: 0 6px; margin-bottom: 16px; }
.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; background: var(--xhs); color: #fff; box-shadow: 0 5px 14px rgba(255, 36, 66, .24); }
.brand-copy { display: flex; flex-direction: column; }
.brand-copy strong { font-family: var(--serif); font-size: 18px; line-height: 1.2; }
.brand-copy span { margin-top: 2px; font-size: 10px; color: var(--muted-2); }
.demo-link { border: 1px solid var(--line); background: #fff; color: var(--ink); border-radius: 6px; padding: 7px 10px; font-size: 11.5px; cursor: pointer; }
.demo-link:hover { border-color: var(--xhs); color: var(--xhs-dark); }
.new-btn { margin-top: 6px; border: 0; border-radius: 6px; background: var(--xhs); color: #fff; padding: 8px 10px; font-size: 12px; font-weight: 600; cursor: pointer; }
.new-btn:hover { background: var(--xhs-dark); }
.capture { margin-bottom: 18px; padding: 14px 16px; background: var(--card); border: 1px solid var(--line); border-radius: 7px; }
.capture-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.capture-head h2 { margin: 0; font-family: var(--serif); font-size: 18px; }
.capture-form { display: flex; gap: 8px; align-items: flex-end; margin-top: 12px; flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 220px; }
.field > span { font-size: 10px; letter-spacing: .06em; color: #9a8b74; text-transform: uppercase; }
.field input, .field select { padding: 8px 10px; border: 1px solid var(--line); border-radius: 5px; background: #fdfbf7; font-size: 12px; font-family: inherit; color: var(--ink); }
.cookie-field { flex: 0 0 240px; min-width: 200px; }
.form-error { margin: 8px 0 0; font-size: 11.5px; color: #b03a2e; }
.form-hint { margin: 8px 0 0; font-size: 11px; color: var(--muted-2); }
.pager { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 12px; font-size: 11.5px; color: var(--muted); }
.pager .btn { min-height: 30px; padding: 5px 12px; font-size: 11.5px; }
.progress-panel { margin-bottom: 18px; padding: 14px 16px; background: var(--card); border: 1px solid var(--line); border-radius: 7px; }
.progress-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.progress-head b { font-family: var(--serif); font-size: 15px; }
.progress-head span { display: block; margin-top: 2px; font-size: 11px; color: var(--muted); }
.progress-stages { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 12px; }
.progress-stages > div { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--muted-2); }
.progress-stages > div.done { color: #2f7a55; }
.progress-stages > div.active { color: var(--xhs-dark); font-weight: 600; }
.progress-stages i { font-style: normal; width: 14px; height: 14px; display: grid; place-items: center; border-radius: 50%; border: 1px solid var(--line); font-size: 9px; }
.progress-stages > div.done i { background: #e7f2e9; border-color: #cfe2d5; }
.progress-stages > div.active i { background: #fff0f2; border-color: #f3c3cc; }
.progress-note { margin: 10px 0 0; font-size: 10.5px; color: var(--muted-2); }
.body-meta { display: block; margin-top: 6px; font-size: 9.5px; color: var(--muted-2); }
.side-label { margin: 16px 6px 6px; font-size: 9px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted-2); }
.task-list { display: grid; gap: 2px; overflow-y: auto; }
.task-item { display: flex; align-items: center; gap: 8px; padding: 8px 9px; border: 0; border-radius: 6px; background: transparent; text-align: left; cursor: pointer; color: var(--ink); }
.task-item:hover { background: #f3ece0; }
.task-item.active { background: var(--xhs-soft, #fff0f2); box-shadow: inset 2px 0 0 var(--xhs); }
.task-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.task-copy b { font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-copy small { font-size: 9.5px; color: var(--muted-2); }
.task-item i { font-style: normal; font-size: 9px; color: #a5720f; }
.status-dot { width: 6px; height: 6px; flex: 0 0 6px; border-radius: 50%; background: #2f7a55; }
.status-dot.partial { background: #c08a1e; }
.status-dot.failed, .status-dot.cancelled { background: #b03a2e; }
.status-dot.running, .status-dot.pending { background: var(--xhs); }
.side-empty { margin: 8px 6px; font-size: 11px; color: var(--muted-2); }
.side-foot { margin-top: auto; padding-top: 10px; border-top: 1px solid var(--line-soft); display: flex; align-items: center; justify-content: space-between; font-size: 10.5px; color: var(--muted); }
.side-foot button { border: 0; background: none; color: var(--muted); cursor: pointer; font-size: 10.5px; }
.side-foot button:hover { color: var(--xhs-dark); }

.main { min-width: 0; }
.topbar { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; height: 52px; padding: 0 30px; background: rgba(251, 247, 240, .94); border-bottom: 1px solid var(--line); backdrop-filter: blur(6px); }
.crumb { display: flex; gap: 7px; font-size: 11.5px; color: var(--muted-2); }
.crumb i { font-style: normal; color: #c9bda9; }
.crumb strong { color: #4b453b; font-weight: 600; }
.top-actions { display: flex; align-items: center; gap: 12px; }
.demo-badge { padding: 3px 9px; border-radius: 20px; background: #fff0f2; color: var(--xhs-dark); font-size: 10.5px; font-weight: 700; }
.real-link { font-size: 11.5px; color: var(--muted); text-decoration: none; }
.real-link:hover { color: var(--xhs-dark); }
.content { max-width: 1180px; margin: 0 auto; padding: 26px 30px 60px; }

.state { padding: 40px 0; color: var(--muted); font-size: 13px; }
.state.error { color: #b03a2e; }
.state.empty { display: grid; gap: 10px; place-items: start; }
.state.empty b { font-family: var(--serif); font-size: 20px; color: var(--ink); }

.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 16px; }
.eyebrow { margin: 0 0 6px; font-size: 9px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--muted-2); }
.page-head h1 { margin: 0; font-family: var(--serif); font-size: 28px; line-height: 1.25; }
.lede { margin: 7px 0 0; font-size: 12px; color: var(--muted); }
.notice { margin: 8px 0 0; font-size: 11.5px; color: var(--xhs-dark); }
.head-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 34px; padding: 7px 14px; border: 1px solid transparent; border-radius: 5px; font-size: 12.5px; font-weight: 600; cursor: pointer; white-space: nowrap; text-decoration: none; }
.btn.primary { background: var(--xhs); color: #fff; box-shadow: 0 4px 12px rgba(255, 36, 66, .18); }
.btn.primary:hover { background: var(--xhs-dark); }
.btn.ghost { background: #fff; border-color: var(--line); color: var(--ink); }
.btn.ghost:hover { border-color: var(--rust); color: var(--rust); }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.kpi-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 13px 15px; }
.kpi span { display: block; font-size: 10px; font-weight: 700; letter-spacing: .04em; color: var(--rust); }
.kpi b { display: block; margin-top: 6px; font-family: var(--serif); font-size: 30px; line-height: 1.1; }
.kpi small { display: block; margin-top: 4px; font-size: 10px; color: var(--muted-2); }

.insight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
.insight { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 17px 19px 19px; }
.tag { margin: 0; font-size: 9px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #9a8b74; }
.insight .figure { display: block; margin-top: 11px; font-family: var(--serif); font-size: 40px; line-height: 1; color: var(--rust); }
.insight small { display: block; margin-top: 5px; font-size: 10px; color: var(--muted-2); }
.insight h3 { margin: 14px 0 7px; font-family: var(--serif); font-size: 17px; line-height: 1.45; }
.insight > p:last-child { margin: 0; font-size: 11.5px; line-height: 1.8; color: #5f584d; }
.boundary { margin: 12px 0 0; padding: 9px 12px; background: #efe7da; border-radius: 4px; font-size: 10.5px; color: #776d5d; }

.library-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin: 20px 0 10px; }
.library-tabs button { border: 0; background: none; padding: 8px 11px 9px; font-size: 12px; color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.library-tabs button span { margin-left: 5px; font-size: 10px; color: var(--muted-2); }
.library-tabs button.active { color: var(--ink); font-weight: 700; border-bottom-color: var(--xhs); }
.toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.search-box { flex: 1; min-width: 180px; display: flex; align-items: center; gap: 8px; padding: 0 11px; border: 1px solid var(--line); border-radius: 5px; background: #fdfbf7; color: var(--muted-2); }
.search-box input { flex: 1; min-width: 0; padding: 8px 0; border: 0; background: transparent; font-size: 12px; outline: none; color: var(--ink); }
.toolbar select { width: auto; padding: 7px 9px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font-size: 11.5px; }
.check { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted); white-space: nowrap; }
.check input { width: 13px; height: 13px; }
.view-switch { display: flex; border: 1px solid var(--line); border-radius: 5px; overflow: hidden; }
.view-switch button { border: 0; background: #fff; padding: 7px 11px; font-size: 11.5px; color: var(--muted); cursor: pointer; }
.view-switch button.active { background: #fff0f2; color: var(--xhs-dark); font-weight: 700; }

.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--card); }
.note-table { width: 100%; border-collapse: collapse; }
.note-table th { padding: 9px 10px; background: #f4ecdf; font-size: 10.5px; font-weight: 700; color: #6f6355; text-align: left; white-space: nowrap; }
.note-table td { padding: 8px 10px; border-bottom: 1px solid var(--line-soft); font-size: 11.5px; vertical-align: middle; }
.note-table tbody tr { cursor: pointer; }
.note-table tbody tr:hover { background: #fdf9f2; }
.note-cell { display: flex; align-items: center; gap: 10px; min-width: 0; }
.thumb { width: 42px; height: 42px; flex: 0 0 42px; border-radius: 4px; overflow: hidden; background: #eadfce; display: grid; place-items: center; color: #7d6b56; font-size: 9px; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.note-text { display: flex; flex-direction: column; min-width: 0; }
.note-text b { font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; max-width: 420px; }
.note-text small { margin-top: 2px; font-size: 9.5px; color: var(--muted-2); }
.type-pill { font-size: 9.5px; padding: 2px 7px; border-radius: 20px; border: 1px solid var(--line); background: #f6efe3; color: var(--muted); white-space: nowrap; }
.engage { display: flex; gap: 8px; white-space: nowrap; font-size: 10.5px; color: var(--muted); }
.tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tags i { font-style: normal; font-size: 9.5px; padding: 1px 6px; border-radius: 3px; background: #f4ecdf; color: #7d6b56; }
.source-col { color: var(--rust); text-decoration: none; }
.status-ok { font-size: 10px; color: #2f7a55; }
.status-warn { font-size: 10px; color: #a5720f; }
.empty-state { padding: 28px; text-align: center; color: var(--muted-2); font-size: 12px; }

.note-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.note-card { background: var(--card); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; cursor: pointer; }
.note-card:hover { border-color: var(--xhs); }
.card-cover { position: relative; height: 128px; background: #eadfce; display: grid; place-items: center; color: #8b7a63; font-size: 12px; }
.card-cover img { width: 100%; height: 100%; object-fit: cover; }
.card-cover i { position: absolute; top: 8px; left: 8px; font-style: normal; font-size: 9px; padding: 1px 6px; border-radius: 3px; background: rgba(0, 0, 0, .4); color: #fff; }
.note-card-copy { padding: 10px 11px 12px; }
.note-card-copy h3 { margin: 0; font-size: 11.5px; line-height: 1.55; font-weight: 600; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.note-card-copy p { margin: 5px 0 0; font-size: 9.5px; color: var(--muted-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-card-copy div { display: flex; gap: 8px; margin-top: 7px; font-size: 9.5px; color: var(--muted); }

.drawer { position: fixed; top: 0; right: 0; z-index: 30; width: 420px; max-width: 92vw; height: 100vh; overflow-y: auto; background: var(--card); border-left: 1px solid var(--line); box-shadow: -18px 0 40px rgba(40, 33, 24, .12); }
.drawer header { display: flex; align-items: center; justify-content: space-between; padding: 13px 18px; border-bottom: 1px solid var(--line-soft); font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted-2); }
.drawer header button { border: 0; background: none; font-size: 18px; color: var(--muted); cursor: pointer; }
.drawer-cover { height: 190px; background: #eadfce; }
.drawer-cover img { width: 100%; height: 100%; object-fit: cover; }
.drawer-body { padding: 16px 18px 28px; }
.drawer-body h2 { margin: 8px 0 4px; font-family: var(--serif); font-size: 20px; line-height: 1.4; }
.drawer-meta { margin: 0; font-size: 10px; color: var(--muted-2); }
.drawer-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 13px 0 4px; }
.drawer-metrics div { padding: 8px 6px; border: 1px solid var(--line-soft); border-radius: 4px; background: #fcf8f1; text-align: center; }
.drawer-metrics b { display: block; font-family: var(--serif); font-size: 14px; }
.drawer-metrics span { font-size: 9px; color: var(--muted-2); }
.drawer-alert { margin: 13px 0; padding: 11px 12px; background: #fdf6e7; border: 1px solid #e7d2a4; border-radius: 5px; display: grid; gap: 6px; }
.drawer-alert > span { font-size: 9px; font-weight: 700; letter-spacing: .08em; color: #a5720f; text-transform: uppercase; }
.drawer-alert p { margin: 0; font-size: 11.5px; color: #7a5f24; }
.drawer-alert button { justify-self: start; }
.drawer-section { margin-top: 15px; }
.drawer-section > span { display: block; font-size: 9px; letter-spacing: .1em; text-transform: uppercase; color: #9a8b74; margin-bottom: 5px; }
.drawer-section p { margin: 0; font-size: 12px; line-height: 1.85; color: #4b453b; white-space: pre-wrap; }
.drawer-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.drawer-tags i { font-style: normal; font-size: 10px; padding: 2px 8px; border-radius: 3px; background: #f4ecdf; color: #7d6b56; }
.drawer-tags em { font-style: normal; font-size: 10px; color: var(--muted-2); }
.source-link { display: block; padding: 8px 10px; border: 1px solid var(--line-soft); border-radius: 4px; background: #fcf8f1; font-size: 10px; color: #7d6b56; word-break: break-all; text-decoration: none; font-family: ui-monospace, Consolas, monospace; }

@media (max-width: 1180px) {
  .shell { grid-template-columns: 210px minmax(0, 1fr); }
  .content { padding: 22px 20px 50px; }
  .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .insight-grid { grid-template-columns: 1fr; }
  .note-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
