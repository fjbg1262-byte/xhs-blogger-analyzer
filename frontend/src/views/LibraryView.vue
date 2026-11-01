<template>
  <section class="library">
    <div class="intro"><p class="eyebrow">小红书内容工作台 · 0.3.0-beta.6</p><h1>笔记库与内容交付</h1></div>
    <section class="card">
      <form class="create" @submit.prevent="create">
        <input v-model="profileUrl" aria-label="博主主页链接" placeholder="粘贴小红书博主主页链接" required />
        <select v-model="cookieId" aria-label="已保存的登录状态"><option :value="0">选择已保存的登录状态</option><option v-for="c in cookies" :key="c.id" :value="c.id">{{ c.nickname || `登录状态 ${c.id}` }}</option></select>
        <button class="btn btn-primary" :disabled="busy || !cookieId">开始整理</button>
      </form>
      <p class="hint">也可以在浏览器里打开博主主页，点击插件的「整理当前主页」。首次使用先启动本地工具并登录小红书。<router-link to="/settings">管理登录状态</router-link></p>
    </section>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <div class="task-bar"><label>整理记录 <select v-model="selected" @change="choose"><option :value="0">请选择</option><option v-for="t in tasks" :key="t.id" :value="t.id">#{{ t.id }} · {{ statusText(t.status) }} · {{ t.created_at?.slice(0,16) }}</option></select></label><button class="btn btn-secondary" @click="refresh">刷新</button><button v-if="active" class="btn btn-secondary" @click="cancel">停止并保留已有数据</button></div>
    <template v-if="selected">
      <div class="stats"><div><b>{{ dataset.rows.length }}</b><span>已整理笔记</span></div><div><b>{{ dataset.summary?.detail_success || 0 }}</b><span>详情获取成功</span></div><div><b>{{ dataset.summary?.likes_median ?? '—' }}</b><span>本批点赞中位数</span></div><div><b>{{ statusText(currentTask?.status || dataset.status) }}</b><span>{{ currentTask?.progress_meta?.stage || '等待开始' }}</span></div></div>
      <p class="hint">{{ active ? '正在采集，可以先下载已获取的数据。' : dataset.stop_reason }} {{ currentTask?.error_message || '' }}</p>
      <LibraryAnalysis :key="selected" :task-id="selected" :collecting="active" :count="dataset.rows.length" />
      <div class="filters"><input v-model="q" aria-label="搜索笔记" placeholder="搜索标题、正文或标签" /><select v-model="sort" aria-label="排序"><option value="list_order">主页返回顺序</option><option value="liked_count">点赞从高到低</option><option value="collected_count">收藏从高到低</option><option value="comment_count">评论从高到低</option><option value="published_at">发布时间从新到旧</option></select><input v-model="after" type="date" aria-label="起始日期" /><input v-model="before" type="date" aria-label="结束日期" /><label class="check"><input v-model="aboveMedian" type="checkbox" />不低于点赞中位数</label><label class="check"><input v-model="top20" type="checkbox" />Top20（当前排序）</label></div>
      <div class="exports"><span>当前筛选 {{ visibleRows.length }} / {{ dataset.rows.length }} 篇</span><button v-for="f in formats" :key="f.key" class="btn btn-secondary" :disabled="!visibleRows.length || exporting" @click="download(f.key)">{{ f.label }}</button></div>
      <div class="table-wrap card"><table><thead><tr><th>笔记 / 封面</th><th>发布时间</th><th>赞 / 藏 / 评</th><th>类型</th><th>详情与正文</th></tr></thead><tbody><tr v-for="r in visibleRows" :key="r.note_id"><td class="note"><img v-if="r.cover_url" :src="r.cover_url" alt="笔记封面" loading="lazy" referrerpolicy="no-referrer" @error="imageError" /><a :href="r.note_url" target="_blank" rel="noopener noreferrer">{{ r.title || '无标题' }}</a><small>{{ r.sticky ? '置顶 · ' : '' }}{{ r.author_nickname }} · {{ r.note_id }}</small></td><td>{{ r.published_at?.slice(0,16).replace('T',' ') || '未获取' }}</td><td>{{ r.liked_count ?? '—' }} / {{ r.collected_count ?? '—' }} / {{ r.comment_count ?? '—' }}</td><td>{{ r.type }}</td><td><span>{{ r.detail_status }}</span><small>{{ r.text_status }} · {{ r.tags_status }}</small><details><summary>查看内容与采集情况</summary><p class="body-text">{{ r.content_text || '未获取正文或原文为空' }}</p><p>{{ r.tags.join(' · ') }}</p><p v-if="r.missing_fields.length">缺失：{{ r.missing_fields.join('、') }}</p><p>{{ r.failure_reason }}</p><a v-if="r.video_url" :href="r.video_url" target="_blank" rel="noopener noreferrer">视频链接</a><a v-for="(url,i) in r.image_urls" :key="url" :href="url" target="_blank" rel="noopener noreferrer"> 图片{{ i+1 }} </a></details></td></tr><tr v-if="!visibleRows.length"><td colspan="5">{{ active ? '正在等待主页数据…' : '没有符合筛选条件的笔记。' }}</td></tr></tbody></table></div>
      <p class="hint">空白表示未获取，0 表示接口返回零。主页可能包含置顶；本批数据不代表全账号。媒体提供链接，可能过期。飞书版是单表导入文件，链接不会自动转成附件。</p>
    </template>
    <section v-else class="card empty"><h2>你的内容工作底稿</h2><p>还没有选中的整理记录。</p></section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { cookieAPI, taskAPI } from '../api/client'
import LibraryAnalysis from '../components/LibraryAnalysis.vue'
const route = useRoute(), router = useRouter()
const profileUrl = ref(''), cookieId = ref(0), selected = ref(Number(route.query.task) || 0)
const cookies = ref<any[]>([]), tasks = ref<any[]>([]), dataset = ref<any>({ rows: [], summary: {} })
const error = ref(''), busy = ref(false), exporting = ref(false), q = ref(''), sort = ref('list_order'), after = ref(''), before = ref(''), aboveMedian = ref(false), top20 = ref(false)
const formats = [{key:'xlsx',label:'下载 Excel'},{key:'csv',label:'下载 CSV'},{key:'feishu',label:'下载飞书导入版'}]
const currentTask = computed(() => tasks.value.find(t => t.id === selected.value))
const active = computed(() => ['pending','running'].includes(currentTask.value?.status))
const visibleRows = computed(() => {
  const baseline = dataset.value.summary?.likes_median
  const rows = dataset.value.rows.filter((r:any) => (!q.value || `${r.title} ${r.content_text} ${r.tags.join(' ')}`.toLowerCase().includes(q.value.toLowerCase())) && (!after.value || r.published_at?.slice(0,10) >= after.value) && (!before.value || (r.published_at && r.published_at.slice(0,10) <= before.value)) && (!aboveMedian.value || (baseline != null && r.liked_count != null && r.liked_count >= baseline)))
  rows.sort((a:any,b:any) => {
    const av=a[sort.value], bv=b[sort.value]
    if(av == null) return bv == null ? 0 : 1
    if(bv == null) return -1
    const result = av < bv ? -1 : av > bv ? 1 : 0
    return sort.value === 'list_order' ? result : -result
  })
  return top20.value ? rows.slice(0,20) : rows
})
function statusText(s:string) { return ({pending:'等待开始',running:'采集中',completed:'已完成',partial:'部分完成',cancelled:'已停止',failed:'采集失败'} as any)[s] || s || '等待开始' }
function message(e:any) { error.value = e.response?.data?.detail || e.message || '操作失败，请重试' }
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false, refreshing = false
async function refresh() {
  if(refreshing) return
  refreshing = true
  const id = selected.value
  try { tasks.value = (await taskAPI.list()).data.filter((t:any)=>t.task_type==='note_collection'); if(id) { const result=await api.get(`/library/${id}`); if(id===selected.value) dataset.value=result.data } } catch(e) { message(e) } finally { refreshing=false }
}
async function poll() { await refresh(); if(!disposed) timer=setTimeout(poll,3000) }
async function choose() { dataset.value={rows:[],summary:{}}; await router.replace({path:'/library',query:selected.value ? {task:selected.value}: {}}); await refresh() }
async function create() { busy.value=true; error.value=''; try { const result=await api.post('/library/',{profile_url:profileUrl.value,cookie_id:cookieId.value}); selected.value=result.data.id; await choose() } catch(e) { message(e) } finally { busy.value=false } }
async function cancel() { try { await taskAPI.cancel(selected.value); await refresh() } catch(e) { message(e) } }
async function download(format:string) {
  exporting.value=true; error.value=''
  try { const response=await api.get(`/library/${selected.value}/export`,{params:{format,sort:sort.value,top:top20.value?20:0,q:q.value,after:after.value,before:before.value,above_median:aboveMedian.value},responseType:'blob'}); const url=URL.createObjectURL(response.data); const a=document.createElement('a'); a.href=url; a.download=`小红书笔记库-${selected.value}-${format}.${format==='csv'?'csv':'xlsx'}`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000) } catch(e) { message(e) } finally { exporting.value=false }
}
function imageError(event:Event) { (event.target as HTMLImageElement).style.display='none' }
onMounted(async()=>{ try { cookies.value=(await cookieAPI.list()).data; cookieId.value=cookies.value[0]?.id||0 } catch(e){message(e)}; await poll() })
onUnmounted(()=>{disposed=true;clearTimeout(timer)})
</script>

<style scoped>
.library{display:grid;gap:20px}.intro h1{font-size:30px;margin:5px 0 10px}.intro p,.hint{color:#645e65}.eyebrow{font-size:12px;letter-spacing:2px}.create{display:grid;grid-template-columns:2fr 1fr auto;gap:12px}.hint{font-size:12px;margin-top:12px}.task-bar{display:flex;align-items:end;gap:14px}.task-bar label{flex:1}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.stats>div{background:white;padding:20px;border:1px solid #eadde0;border-radius:8px}.stats b{display:block;font-size:25px}.stats span{font-size:12px;color:#6c656b}.filters{display:flex;flex-wrap:wrap;gap:10px}.filters>input,.filters>select{width:auto;flex:1;min-width:140px}.check{display:flex;align-items:center;gap:5px;font-size:12px}.check input{width:auto}.exports{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.exports span{margin-right:auto;font-size:13px}.table-wrap{overflow-x:auto;padding:0}.table-wrap table{min-width:900px}td{vertical-align:top}td small{display:block;color:#82727c;margin-top:4px}.note{min-width:240px;max-width:330px}.note img{float:left;width:54px;height:65px;object-fit:cover;margin-right:10px;border-radius:4px}.note a{color:#155969}.body-text{white-space:pre-wrap;max-height:300px;overflow:auto}details{max-width:340px;font-size:12px}summary{cursor:pointer;color:#155969}.error{padding:12px;background:#ffe8ea;color:#942b38}.empty{padding:38px}.empty p{margin-top:12px}@media(max-width:750px){.create{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.intro h1{font-size:24px}}
</style>
