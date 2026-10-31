<template>
  <section class="analysis-workspace" aria-label="AI 内容交付">
    <header class="workspace-head"><div><p class="kicker">内容交付工作台</p><h2>从真实笔记，到下一篇内容</h2></div><span class="state-label">{{ stateLabel }}</span></header>
    <form class="request-form" @submit.prevent="generate">
      <label>客户这次最想解决什么？<textarea v-model="goal" rows="3" maxlength="1200" minlength="5" required placeholder="例如：我是刚开始拍手机摄影的新手，希望找到适合周末拍摄的三个选题，重点帮我改标题和开头。" :disabled="running" /></label>
      <div class="request-actions"><label class="consent"><input v-model="consent" type="checkbox" :disabled="running" />同意将本批公开文字与目标发送至 {{ state.provider || '已配置的' }} AI 服务商，由我承担 API 费用</label><button class="btn btn-primary" :disabled="running || collecting || !state.configured || count < 5 || !consent || submitting"><LoaderCircle v-if="running" :size="17" class="spin" /><Sparkles v-else :size="17" />{{ running ? '正在生成' : report ? '重新生成' : '生成解读与创作草稿' }}</button></div>
      <p v-if="!state.configured" class="notice">尚未配置 AI。<router-link to="/settings">前往设置</router-link></p>
      <p v-else class="subtle">{{ state.model }} · 全批 {{ count }} 篇（不受表格筛选影响） · 仅文字分析，不发送 Cookie、密钥、图片或评论</p>
      <p v-if="collecting" class="notice">请先完成或停止采集。</p>
      <p v-if="count < 5" class="notice">至少需要 5 篇不同的笔记；现有表格仍可下载。</p>
    </form>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="state.stage" aria-live="polite" :class="['stage', { error: ['failed','stale'].includes(state.status) }]"><LoaderCircle v-if="running" class="spin" :size="18" />{{ state.stage }}</p>
    <template v-if="report">
      <div class="report-heading"><p class="kicker">{{ report.account_name }} · 本次优先建议</p><h3>{{ report.analysis.headline }}</h3><p class="subtle">客户目标：{{ report.goal }}</p></div>
      <div class="coverage"><span>笔记 <b>{{ report.coverage.notes }}</b></span><span>已采正文 <b>{{ report.coverage.bodies_collected }}</b></span><span>AI 阅读正文摘录 <b>{{ report.coverage.bodies_sent }}</b></span><span>点赞中位数 <b>{{ report.coverage.median_likes ?? '未获取' }}</b></span></div>
      <div class="tabs" role="tablist" aria-label="交付内容"><button v-for="tab in tabs" :key="tab.key" role="tab" :aria-selected="activeTab === tab.key" :class="{ selected: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button></div>
      <div v-if="activeTab === 'overview'" class="ov-dashboard">
        <div class="ov-metrics">
          <article><span>公开互动</span><b>{{ compact(report.analytics?.total_engagement) }}</b><small>赞 + 藏 + 评 + 分享</small></article>
          <article><span>单篇中位数</span><b>{{ decimal(report.analytics?.median_engagement) }}</b><small>比均值更不易被爆款拉偏</small></article>
          <article><span>头部贡献</span><b>{{ percent(report.analytics?.concentration?.top_20pct_share) }}</b><small>Top {{ report.analytics?.concentration?.top_20pct_count ?? 0 }} 篇公开互动占比</small></article>
          <article><span>正文参与</span><b>{{ report.coverage.bodies_sent }}</b><small>AI 实际阅读的正文摘录</small></article>
        </div>
        <div class="ov-story-grid">
          <article v-for="card in report.analytics?.story_cards || []" :key="card.code" class="ov-story">
            <span>{{ card.code }}</span><b>{{ card.value }}</b><small>{{ card.label }}</small>
            <h3>{{ card.title }}</h3><p>{{ card.detail }}</p>
          </article>
        </div>
        <div class="ov-two-col">
          <section class="ov-panel">
            <header><span>内容形式</span><h3>互动中位数与账号相对强度</h3></header>
            <div class="ov-type-list">
              <div v-for="item in report.analytics?.types || []" :key="item.type" class="ov-type-row">
                <div><b>{{ item.type }}</b><small>{{ item.notes }} 篇 · 中位互动 {{ decimal(item.median_engagement) }}</small></div>
                <div class="ov-bar"><i :style="{ width: width(item.median_engagement, typeMax) + '%' }" /></div>
                <strong>{{ multiple(item.intensity_vs_account) }}</strong>
              </div>
            </div>
            <p class="ov-note">倍数为相对本批公开互动中位数，不是浏览量或曝光效率。</p>
          </section>
          <section class="ov-panel ov-concentration">
            <header><span>互动集中度</span><h3>内容表现是否依赖少数爆款</h3></header>
            <div class="ov-donut" :style="{ background: `conic-gradient(#a84616 0 ${report.analytics?.concentration?.top_20pct_share || 0}%, #e5ddd1 ${report.analytics?.concentration?.top_20pct_share || 0}% 100%)` }">
              <div><strong>{{ Math.round(report.analytics?.concentration?.top_20pct_share || 0) }}%</strong><small>头部贡献</small></div>
            </div>
            <p>达到 80% 公开互动需要 <b>{{ report.analytics?.concentration?.notes_for_80pct ?? 0 }}</b> 篇，占本批 {{ percent(report.analytics?.concentration?.notes_for_80pct_share) }}。</p>
          </section>
        </div>
        <div class="ov-two-col">
          <section class="ov-panel">
            <header><span>标题信号</span><h3>哪些表达与更高互动同时出现</h3></header>
            <div class="ov-signal-list">
              <div v-for="signal in (report.analytics?.title_signals || []).slice(0,5)" :key="signal.label">
                <span>{{ signal.label }}<small v-if="!signal.reliable"> · 样本偏少</small></span>
                <b>{{ multiple(signal.lift) }}</b><small>{{ signal.matched_notes }} 篇匹配</small>
              </div>
            </div>
          </section>
          <section class="ov-panel">
            <header><span>主题信号</span><h3>高频标签的内容覆盖</h3></header>
            <div class="ov-tags">
              <span v-for="tag in (report.analytics?.tags || []).slice(0,8)" :key="tag.tag">{{ tag.tag }} <b>{{ tag.notes }}</b></span>
            </div>
            <p class="ov-note">标签频次不代表搜索量、排名或搜索流量。</p>
          </section>
        </div>
        <section class="ov-strategy">
          <header><span>内容战略</span><h3>从清单到可重复的内容系统</h3></header>
          <div>
            <article v-for="item in strategyItems" :key="item.key"><span>{{ item.label }}</span><h4>{{ item.title }}</h4><p>{{ item.value }}</p></article>
          </div>
        </section>
        <section class="ov-panel ov-top-notes">
          <header><span>头部内容</span><h3>先复盘这些高互动样本</h3></header>
          <a v-for="note in (report.analytics?.top_notes || []).slice(0,5)" :key="note.note_id" :href="note.note_url" target="_blank" rel="noopener noreferrer">
            <b>{{ note.rank }}</b><span>{{ note.title || '无标题' }}<small>{{ note.type }} · {{ note.published_at?.slice(0,10) || '日期未知' }}</small></span><strong>{{ compact(note.engagement) }}</strong>
          </a>
        </section>
        <p class="ov-boundary">公开互动 = 点赞 + 收藏 + 评论 + 分享；不是浏览量、点击率、ROI、转化率或粉丝增长。标题、形式和主题差异只作为待验证线索。</p>
      </div>
      <div v-else-if="activeTab === 'drafts'" class="drafts">
        <article v-for="(draft, index) in report.analysis.drafts" :key="index" class="draft">
          <header><span class="index">0{{ index + 1 }}</span><h3>{{ draft.topic }}</h3><button class="icon-button" title="复制这篇创作草稿" aria-label="复制这篇创作草稿" @click="copyDraft(draft)"><Copy :size="18" /></button></header>
          <p>{{ draft.reader_problem }}</p><h4>标题备选</h4><ol><li v-for="title in draft.titles" :key="title">{{ title }}</li></ol>
          <h4>开头草稿</h4><p class="opening">{{ draft.opening }}</p><h4>正文大纲</h4><ol><li v-for="item in draft.outline" :key="item">{{ item }}</li></ol>
          <p><b>怎么测试：</b>{{ draft.test }}</p><p><b>如何复盘：</b>{{ draft.check }}</p>
          <details><summary>查看创作依据 · {{ draft.evidence.length }} 条原文</summary><blockquote v-for="(e, i) in draft.evidence" :key="i">{{ e.quote }}<small>{{ evidenceTitle(e.note_id) }} · {{ e.field === 'title' ? '标题' : '正文摘录' }}</small></blockquote></details>
        </article>
      </div>
      <div v-else-if="activeTab === 'insights'" class="dimensions"><article v-for="section in report.analysis.dimensions" :key="section.key"><header><h3>{{ labels[section.key] }}</h3><span class="state-label">{{ ({supported:'样本观察',limited:'有限线索',unavailable:'资料不足'} as any)[section.status] }}</span></header><div v-for="(f, i) in section.findings" :key="i" class="finding"><h4>{{ f.observation }}</h4><p>{{ f.interpretation }}</p><p><b>建议尝试：</b>{{ f.next_step }}</p><p class="subtle">另一种解释：{{ f.alternative_explanation }}</p><blockquote v-for="(e, j) in f.evidence" :key="j">{{ e.quote }}<small>{{ evidenceTitle(e.note_id) }} · {{ e.field === 'title' ? '标题' : '正文摘录' }}</small></blockquote></div><p class="boundary">{{ section.limitation }} {{ section.boundary }}</p></article></div>
      <div v-else class="evidence"><p class="subtle">{{ report.selection }}</p><p class="subtle">高低组各 {{ report.coverage.high_group.n }} 篇，依据本批已知点赞排序；不是同曝光、同选题实验。</p><details v-for="note in report.evidence" :key="note.note_id"><summary>{{ note.title || '无标题' }} <span class="subtle">· {{ note.metrics.liked_count ?? '未知' }} 赞</span></summary><p>{{ note.body_excerpt || '本次未发送正文，仅标题和标签参与分析。' }}</p><small>{{ note.note_id }} · {{ note.published_at || '发布时间未获取' }}{{ note.body_truncated ? ' · 正文未全部发送' : '' }}</small></details></div>
      <footer class="delivery-actions"><p class="subtle">{{ report.validation }} 草稿发布前需核实事实与原创性。</p><p v-if="!reportGoalMatches" class="notice">上方目标已修改，但当前报告仍是针对“{{ report.goal }}”生成的。请重新生成，或恢复原目标后再复核和交付。</p><label class="consent"><input v-model="reviewed" type="checkbox" :disabled="report.review === 'approved' || !reportGoalMatches" />我已检查原文、解读和创作草稿，确认可以交付</label><div><button class="btn btn-secondary" :disabled="exporting || !reportGoalMatches" @click="exportReport('html', true)"><Eye :size="17" />预览草稿</button><button v-if="report.review !== 'approved'" class="btn btn-primary" :disabled="!reviewed || approving || !reportGoalMatches" @click="approve"><Check :size="17" />确认交付</button><template v-else><button class="btn btn-primary" :disabled="exporting || !reportGoalMatches" @click="exportReport('html')"><Download :size="17" />下载网页版</button><button class="btn btn-secondary" :disabled="exporting || !reportGoalMatches" @click="exportReport('pdf')"><Download :size="17" />{{ exporting ? '正在导出' : '下载 PDF' }}</button></template></div></footer>
      <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Check, Copy, Download, Eye, LoaderCircle, Sparkles } from '@lucide/vue'
import api from '../api/client'
const props = defineProps<{ taskId: number, collecting: boolean, count: number }>()
const state = ref<any>({status:'idle'}), goal = ref(''), consent = ref(false), reviewed = ref(false)
const error = ref(''), notice = ref(''), activeTab = ref('overview')
const submitting = ref(false), approving = ref(false), exporting = ref(false)
const running = computed(() => state.value.status === 'running')
const report = computed(() => state.value.status === 'ready' ? state.value.report : null)
const reportGoalMatches = computed(() => !report.value || goal.value.trim() === String(report.value.goal || '').trim())
const stateLabel = computed(() => {
  if (report.value && !reportGoalMatches.value) return '目标已修改'
  return ({idle:'尚未生成',running:'AI 处理中',ready:report.value?.review === 'approved' ? '已确认交付' : '待复核',failed:'生成失败',stale:'需重新生成'} as any)[state.value.status]
})
const labels: Record<string,string> = {positioning_audience:'内容定位与读者线索',content_structure:'内容方向',title_hook:'标题与开头',engagement_drivers:'高低表现对照',growth_trajectory:'发布节奏',tag_search:'标签与搜索表达',commercial_signals:'商业表达线索',action_plan:'下一步测试'}
const tabs = [{key:'overview',label:'经营总览'},{key:'insights',label:'八维解读'},{key:'drafts',label:'3 个选题与草稿'},{key:'evidence',label:'原始依据'}]
const strategyItems = computed(() => {
  const strategy = report.value?.analysis?.strategy || {}
  return [
    {key:'thesis',label:'内容命题',title:'真正持续解决的问题',value:strategy.content_thesis || '资料不足'},
    {key:'model',label:'可复用模型',title:'能稳定重复的内容结构',value:strategy.repeatable_model || '资料不足'},
    {key:'growth',label:'增长试验',title:'下一步最值得验证什么',value:strategy.growth_path || '资料不足'},
    {key:'risk',label:'主要误判',title:'最需要避免的解释',value:strategy.primary_risk || '资料不足'},
  ]
})
const typeMax = computed(() => Math.max(1, ...((report.value?.analytics?.types || []).map((item:any) => Number(item.median_engagement || 0)))))
let timer: ReturnType<typeof setTimeout> | undefined
let alive = true, generation = 0
function message(e:any) { return typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '请求失败，请检查本地服务后重试。' }
async function refresh(id:number, epoch:number) {
  try { const {data}=await api.get(`/library/${id}/analysis`); if(!alive || epoch!==generation) return; if(state.value.run_id!==data.run_id) reviewed.value=false; state.value=data; if(!goal.value) goal.value=data.goal||''; if(data.report?.review==='approved') reviewed.value=true } catch(e) { if(epoch===generation) error.value=message(e) }
  if(alive && epoch===generation) timer=setTimeout(()=>refresh(id,epoch),3000)
}
watch(()=>props.taskId, id=>{ clearTimeout(timer); generation++; state.value={status:'idle'}; goal.value=''; consent.value=false; reviewed.value=false; error.value=''; notice.value=''; activeTab.value='overview'; refresh(id,generation) },{immediate:true})
onUnmounted(()=>{alive=false;generation++;clearTimeout(timer)})
async function generate() {
  const epoch=generation, id=props.taskId
  submitting.value=true;error.value='';notice.value=''
  try { const {data}=await api.post(`/library/${id}/analysis`,{goal:goal.value,consent:consent.value}); if(epoch===generation){state.value={...state.value,...data};reviewed.value=false} } catch(e){if(epoch===generation)error.value=message(e)} finally{submitting.value=false}
}
async function approve() {
  const epoch=generation
  approving.value=true
  try { const {data}=await api.post(`/library/${props.taskId}/analysis/approve`,{run_id:state.value.run_id,confirmed:reviewed.value});if(epoch===generation)state.value={...state.value,...data} } catch(e){if(epoch===generation)error.value=message(e)}finally{approving.value=false}
}
function evidenceTitle(id:string) { return report.value.evidence.find((e:any)=>e.note_id===id)?.title || id }
function compact(value:any) { const n=Number(value||0); if(Math.abs(n)>=100000000)return `${(n/100000000).toFixed(1)}亿`; if(Math.abs(n)>=10000)return `${(n/10000).toFixed(1)}万`; return n.toLocaleString('zh-CN',{maximumFractionDigits:0}) }
function decimal(value:any) { return value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1}) }
function percent(value:any) { return value == null ? '—' : `${Number(value).toFixed(1)}%` }
function multiple(value:any) { return value == null ? '—' : `${Number(value).toFixed(1)}x` }
function width(value:any, maximum:any) { return Math.max(2,Math.min(100,(Number(value||0)/Math.max(Number(maximum||1),1))*100)) }
async function copyDraft(d:any) {
  try { await navigator.clipboard.writeText([d.topic,d.reader_problem,...d.titles,d.opening,...d.outline,d.test,d.check].join('\n\n'));notice.value='已复制创作草稿' }catch{notice.value='复制未成功，可下载网页版后选中文字。'}
}
async function exportReport(format:string,preview=false) {
  const id=props.taskId
  const win=preview ? window.open('about:blank','_blank') : null
  if(win) win.opener=null
  exporting.value=true;error.value=''
  try { const response=await api.get(`/library/${id}/analysis/export`,{params:{format,preview},responseType:'blob',timeout:200000}); const url=URL.createObjectURL(response.data); if(win){win.location.href=url}else{const a=document.createElement('a');a.href=url;a.download=`内容解读-${id}.${format}`;a.click()}setTimeout(()=>URL.revokeObjectURL(url),60000) } catch(e:any){win?.close();if(e.response?.data instanceof Blob){try{const body=JSON.parse(await e.response.data.text());error.value=body.detail}catch{error.value='导出失败，请重试。'}}else error.value=message(e)}finally{exporting.value=false}
}
</script>

<style scoped>
.analysis-workspace{border-top:2px solid #dc3454;padding-top:24px;min-width:0}.workspace-head,.draft header,.dimensions header{display:flex;justify-content:space-between;gap:16px;align-items:center}.kicker{color:#a42c43;font-size:12px;margin:0 0 6px}.workspace-head h2{font-size:22px;margin:0}.state-label{font-size:12px;color:#526269;white-space:nowrap}.request-form{padding:20px 0;border-bottom:1px solid #e1e5e7}.request-form label{font-size:14px}.request-form textarea{margin-top:8px;resize:vertical;line-height:1.7}.request-actions{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-top:12px}.consent{display:flex;align-items:flex-start;gap:8px;font-size:13px;line-height:1.6}.consent input{width:16px;height:16px;flex-shrink:0;margin-top:3px}.btn{display:inline-flex;gap:7px;align-items:center;justify-content:center;white-space:normal}.subtle,small{color:#657279;font-size:13px}.subtle{margin:10px 0}.notice{color:#24685c;font-size:13px;margin:10px 0}.stage{display:flex;align-items:center;gap:10px;padding:12px 0;font-size:14px}.error{background:#ffedef;color:#94243d;padding:12px;border-radius:4px}.report-heading{padding:18px 0 10px}.report-heading h3{font-size:23px;line-height:1.55;margin:6px 0;max-width:850px}.coverage{display:flex;gap:20px;flex-wrap:wrap;padding:12px 0;color:#66737a;font-size:13px}.coverage b{color:#252f35;margin-left:5px}.tabs{display:flex;gap:24px;border-bottom:1px solid #dce2e5;margin:12px 0}.tabs button{border:0;background:none;padding:12px 0;font:inherit;font-size:14px;border-bottom:3px solid transparent;color:#607078;cursor:pointer}.tabs button.selected{color:#a02b43;border-color:#d53656}.draft,.dimensions>article{border-bottom:1px solid #dce2e5;padding:20px 0}.draft header{justify-content:flex-start}.draft h3,.dimensions h3{font-size:19px;line-height:1.5;margin:0}.index{font-size:15px;font-weight:700;color:#b6304d}.draft .icon-button{margin-left:auto}.icon-button{width:36px;height:36px;flex:0 0 36px;border:1px solid #dce2e5;border-radius:4px;background:white;display:grid;place-items:center;cursor:pointer}.draft p,.finding p{line-height:1.8;font-size:14px;margin:10px 0}.draft h4,.finding h4{font-size:15px;margin:18px 0 8px}.draft li{font-size:14px;line-height:1.9;margin:5px 0}.draft ol{padding-left:23px}.opening{background:#f0f7f5;border-left:3px solid #308879;padding:12px 16px}details{margin:14px 0;font-size:13px}summary{cursor:pointer;color:#2b6c65;line-height:1.8}blockquote{margin:12px 0;padding:12px 16px;background:#f3f7f7;border-left:2px solid #829e9a;font-size:14px;line-height:1.8}blockquote small{display:block;margin-top:6px}.boundary{background:#f4f5f6;padding:12px;color:#637078;font-size:13px;line-height:1.8}.evidence details{padding:10px 0;border-bottom:1px solid #e3e7e8}.evidence p{white-space:pre-wrap;line-height:1.8}.delivery-actions{padding:20px 0}.delivery-actions>div{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.finding{padding-bottom:16px}p,li,blockquote,h3,small{overflow-wrap:anywhere}.spin{animation:spin 1.2s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.spin{animation:none}}@media(max-width:700px){.workspace-head{align-items:flex-start}.workspace-head h2{font-size:20px}.request-actions{flex-direction:column;align-items:stretch}.coverage{gap:10px 20px}.tabs{gap:16px}.report-heading h3{font-size:20px}.dimensions header{align-items:flex-start}}
.analysis-workspace{border-top-color:#a84616;background:#f7f2e9;padding:24px 22px;border-radius:10px;box-shadow:0 12px 36px rgba(68,43,21,.08)}
.workspace-head .kicker,.report-heading .kicker{color:#a84616;letter-spacing:.12em;text-transform:uppercase}.workspace-head h2,.report-heading h3{font-family:"Songti SC","STSong","SimSun",serif;color:#24221e}.report-heading h3{font-size:28px;line-height:1.45}.request-form{border-color:#d9cfc0}.request-form textarea{border-color:#cdbda8;background:#fffdf8}.coverage span{background:#eee5d8;padding:5px 9px;border-radius:2px}.tabs{border-color:#d2c5b4;gap:20px}.tabs button.selected{color:#a84616;border-color:#a84616}.ov-dashboard{display:grid;gap:16px;padding-top:4px}.ov-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.ov-metrics article{background:#fffdf8;border:1px solid #d8cdbd;padding:16px;min-height:116px}.ov-metrics span,.ov-panel header span,.ov-strategy header span{display:block;color:#8b3b17;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.ov-metrics b{display:block;font-family:"Songti SC","STSong",serif;font-size:31px;line-height:1.2;margin:8px 0 4px;color:#25221e}.ov-metrics small{color:#746b5f;font-size:11px;line-height:1.5}.ov-story-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.ov-story{min-height:240px;background:#fffdf8;border:1px solid #d8cdbd;padding:17px;display:flex;flex-direction:column}.ov-story>span{color:#8b8174;font-size:9px;font-weight:800;letter-spacing:.12em}.ov-story>b{font-family:"Songti SC","STSong",serif;font-size:38px;line-height:1.2;color:#a84616;margin:14px 0 1px}.ov-story>small{color:#7c7265;font-size:10px}.ov-story h3{font-family:"Songti SC","STSong",serif;font-size:19px;line-height:1.5;margin:16px 0 8px}.ov-story p{font-size:12px;line-height:1.8;color:#5e574d;margin:auto 0 0}.ov-two-col{display:grid;grid-template-columns:1.1fr .9fr;gap:9px}.ov-panel{background:#fffdf8;border:1px solid #d8cdbd;padding:17px;min-width:0}.ov-panel header h3,.ov-strategy header h3{font-family:"Songti SC","STSong",serif;font-size:19px;line-height:1.4;margin:4px 0 16px}.ov-type-list,.ov-signal-list{display:grid;gap:15px}.ov-type-row{display:grid;grid-template-columns:minmax(105px,1fr) minmax(100px,1.5fr) 52px;gap:12px;align-items:center}.ov-type-row>div:first-child b{display:block;font-size:13px}.ov-type-row small{display:block;color:#7d7468;font-size:10px}.ov-type-row>strong{font-family:"Songti SC","STSong",serif;font-size:18px;color:#a84616;text-align:right}.ov-bar{height:7px;background:#e7dfd3;overflow:hidden}.ov-bar i{display:block;height:100%;background:#a84616}.ov-note{margin:14px 0 0;padding-top:10px;border-top:1px solid #e2d9cc;color:#7b7266;font-size:11px;line-height:1.6}.ov-concentration{text-align:center}.ov-concentration header{text-align:left}.ov-donut{width:146px;height:146px;margin:8px auto 14px;border-radius:50%;display:grid;place-items:center}.ov-donut>div{width:100px;height:100px;border-radius:50%;background:#fffdf8;display:grid;place-items:center;align-content:center}.ov-donut strong{font-family:"Songti SC","STSong",serif;font-size:29px;line-height:1}.ov-donut small{font-size:10px;color:#7d7468}.ov-concentration p{font-size:11px;line-height:1.7;color:#5f584d;margin:0}.ov-signal-list>div{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding-bottom:9px;border-bottom:1px solid #e5ddd1}.ov-signal-list span{font-size:12px;font-weight:700}.ov-signal-list span small{display:block;color:#857b6e;font-weight:400;font-size:9px}.ov-signal-list b{font-family:"Songti SC","STSong",serif;font-size:19px;color:#a84616}.ov-signal-list>div>small{grid-column:2;color:#857b6e;font-size:9px;text-align:right}.ov-tags{display:flex;flex-wrap:wrap;gap:7px}.ov-tags span{background:#eee5d8;padding:7px 9px;color:#514a40;font-size:11px}.ov-tags b{color:#a84616;margin-left:4px}.ov-strategy{background:#27241f;color:#f7f0e5;padding:20px}.ov-strategy header span{color:#dca078}.ov-strategy header h3{color:#fff8ed}.ov-strategy>div{display:grid;grid-template-columns:1fr 1fr;gap:9px}.ov-strategy article{border-top:1px solid #625b51;padding-top:12px}.ov-strategy article>span{font-size:9px;color:#dca078;font-weight:700}.ov-strategy h4{font-family:"Songti SC","STSong",serif;font-size:16px;margin:5px 0 7px}.ov-strategy article p{font-size:11px;line-height:1.8;color:#d7cfc3;margin:0}.ov-top-notes>a{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid #e1d8ca;text-decoration:none;color:#292620}.ov-top-notes>a>b{font-family:"Songti SC","STSong",serif;color:#a84616;font-size:17px}.ov-top-notes>a>span{font-size:12px;line-height:1.5}.ov-top-notes>a small{display:block;color:#81786b;font-size:9px;margin-top:2px}.ov-top-notes>a>strong{font-size:12px;color:#a84616}.ov-boundary{margin:0;padding:11px 13px;background:#eee5d8;color:#6f665a;font-size:11px;line-height:1.65}
@media(max-width:850px){.ov-metrics{grid-template-columns:1fr 1fr}.ov-two-col{grid-template-columns:1fr}.ov-strategy>div{grid-template-columns:1fr}}
@media(max-width:600px){.analysis-workspace{padding:18px 14px}.ov-metrics,.ov-story-grid{grid-template-columns:1fr}.ov-metrics article,.ov-story{min-height:0}.ov-type-row{grid-template-columns:1fr 50px}.ov-type-row .ov-bar{grid-column:1/-1;grid-row:2}.ov-top-notes>a{grid-template-columns:24px 1fr}.ov-top-notes>a>strong{grid-column:2}.report-heading h3{font-size:22px}.tabs{overflow-x:auto;gap:14px}.tabs button{white-space:nowrap}.ov-strategy{padding:16px}}
</style>
