<template>
  <section class="delivery-center">
    <div class="delivery-head">
      <div>
        <span class="eyebrow">卖家交付中心</span>
        <h3>生成一份客户愿意读完的 8 维诊断报告</h3>
        <p>客户先看到结论和行动，再按定位、内容、标题、互动、轨迹、搜索、商业与建议逐章阅读；完整研究依据保留在网页附录。</p>
      </div>
      <span class="status-badge" :class="status?.ready ? 'ready' : 'blocked'">
        {{ status?.ready ? '可以交付' : '暂不可交付' }}
      </span>
    </div>

    <div class="context-grid">
      <label>
        <span>客户最关心什么</span>
        <select v-model="form.focus">
          <option value="overall">综合诊断</option>
          <option value="positioning">账号定位</option>
          <option value="growth">涨粉与内容增长</option>
          <option value="content">选题与内容结构</option>
          <option value="commercial">商业化</option>
        </select>
      </label>
      <label>
        <span>客户的原话或问题</span>
        <input v-model="form.buyer_question" maxlength="300" placeholder="例如：为什么内容很多，但账号一直没有清晰定位？" />
      </label>
      <label class="wide">
        <span>你想补充给客户的话</span>
        <input v-model="form.seller_note" maxlength="500" placeholder="可留空；例如：建议先执行第 1 周计划，再带新数据复盘。" />
      </label>
    </div>

    <div class="module-grid">
      <div v-for="item in status?.modules || []" :key="item.name" class="module-item" :class="item.status">
        <strong>{{ item.name }}</strong>
        <span>{{ item.note }}</span>
      </div>
    </div>

    <div v-if="status?.blockers?.length" class="blockers">
      <strong>还差这些：</strong>
      <ul><li v-for="item in status.blockers" :key="item">{{ item }}</li></ul>
    </div>

    <div class="delivery-actions">
      <button v-if="!status?.ready" class="btn secondary" :disabled="busy" @click="regenerate">按新规则重新生成</button>
      <button class="btn secondary" :disabled="busy" @click="saveAndPreview">预览 8 维客户报告</button>
      <button class="btn secondary" :disabled="busy" @click="downloadHtml">下载可交互网页</button>
      <button class="btn secondary" :disabled="busy || !status?.ready" @click="downloadPdf">下载 PDF</button>
      <button class="btn primary" :disabled="busy || !status?.ready" @click="downloadPackage">
        {{ busy ? '正在生成...' : '生成客户交付包' }}
      </button>
    </div>
    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { reportAPI, systemAPI } from '../api/client'

const props = defineProps<{ taskId: number }>()
const status = ref<any>(null)
const busy = ref(false)
const message = ref('')
const form = reactive({ focus: 'overall', buyer_question: '', seller_note: '' })
const EXPECTED_REPORT_RENDERER = 'customer-eight-dimension-v2'

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function load() {
  const [statusRes, contextRes] = await Promise.all([
    reportAPI.deliveryStatus(props.taskId),
    reportAPI.deliveryContext(props.taskId),
  ])
  status.value = statusRes.data.delivery
  Object.assign(form, contextRes.data.context || {})
}

async function saveContext() {
  await reportAPI.saveDeliveryContext(props.taskId, form)
}

async function ensureCurrentRenderer() {
  const response = await systemAPI.health()
  if (response.data?.report_renderer_version !== EXPECTED_REPORT_RENDERER) {
    throw new Error('当前运行的是旧版后端。请先双击“关闭本地工具.bat”，再重新启动分析助手，然后重新预览。任务数据不会丢失。')
  }
}

async function run(action: () => Promise<void>) {
  busy.value = true
  message.value = ''
  try {
    await ensureCurrentRenderer()
    await saveContext()
    await action()
  } catch (error: any) {
    message.value = error.response?.data?.detail || error.message || '生成失败，请检查交付门槛。'
  } finally {
    busy.value = false
  }
}

function saveAndPreview() {
  run(async () => {
    const res = await reportAPI.deliveryPreview(props.taskId)
    const url = URL.createObjectURL(new Blob([res.data], { type: 'text/html;charset=utf-8' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  })
}

function regenerate() {
  run(async () => {
    const res = await reportAPI.regenerateDelivery(props.taskId)
    status.value = res.data.delivery
    message.value = status.value.ready ? '报告已按新规则重新生成，现在可以预览并交付。' : '报告已更新，请按“还差这些”继续补充。'
  })
}

function downloadHtml() {
  run(async () => {
    const res = await reportAPI.deliveryHtml(props.taskId)
    download(new Blob([res.data], { type: 'text/html;charset=utf-8' }), `8维账号内容诊断报告-${props.taskId}.html`)
  })
}

function downloadPdf() {
  run(async () => {
    const res = await reportAPI.deliveryPdf(props.taskId)
    download(new Blob([res.data], { type: 'application/pdf' }), `8维账号内容诊断报告-${props.taskId}.pdf`)
  })
}

function downloadPackage() {
  run(async () => {
    const res = await reportAPI.deliveryPackage(props.taskId)
    download(new Blob([res.data], { type: 'application/zip' }), `8维账号诊断交付包-${props.taskId}.zip`)
    message.value = '8 维交付包已生成。解压检查 PDF 的结论和行动建议后，就可以发给客户。'
  })
}

onMounted(() => load().catch((error: any) => { message.value = error.message || '交付状态加载失败' }))
</script>

<style scoped>
.delivery-center{background:#fff;border:1px solid #e5e7eb;border-top:5px solid #ff3158;border-radius:8px;padding:24px}.delivery-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.eyebrow{color:#ff3158;font-size:12px;font-weight:800}.delivery-head h3{margin:6px 0;font-size:21px}.delivery-head p,.module-item span,.message{color:#6b7280}.status-badge{padding:7px 11px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap}.status-badge.ready{background:#dcfce7;color:#16714a}.status-badge.blocked{background:#fff1f2;color:#be123c}.context-grid{display:grid;grid-template-columns:200px 1fr;gap:12px;margin:20px 0}.context-grid label{display:flex;flex-direction:column;gap:7px;font-size:13px;font-weight:700}.context-grid .wide{grid-column:1/-1}select,input{height:42px;border:1px solid #d1d5db;border-radius:6px;padding:0 11px;background:#fff;font:inherit;font-weight:400}.module-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.module-item{border:1px solid #e5e7eb;border-left:4px solid #9ca3af;border-radius:6px;padding:11px}.module-item.ready{border-left-color:#19a66a}.module-item.limited{border-left-color:#f0a221}.module-item.blocked{border-left-color:#ff3158}.module-item span{display:block;font-size:11px;margin-top:5px;line-height:1.4}.blockers{margin-top:14px;padding:13px;background:#fff7ed;border:1px solid #fed7aa;border-radius:6px}.blockers ul{margin:7px 0 0;padding-left:20px}.delivery-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.btn{border:1px solid #d1d5db;border-radius:6px;padding:10px 14px;font-weight:700;cursor:pointer}.btn.secondary{background:#fff;color:#222}.btn.primary{background:#17171b;color:#fff;border-color:#17171b}.btn:disabled{opacity:.45;cursor:not-allowed}.message{margin:12px 0 0;font-size:13px}@media(max-width:760px){.context-grid,.module-grid{grid-template-columns:1fr}.context-grid .wide{grid-column:auto}.delivery-head{flex-direction:column}.delivery-actions .btn{width:100%}}
</style>
