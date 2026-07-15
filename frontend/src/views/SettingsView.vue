<template>
  <div>
    <h2 style="margin-bottom: 24px;">设置</h2>

    <div class="card" style="margin-bottom: 16px;">
      <h3 style="margin-bottom: 16px;">LLM 配置</h3>
      <p style="font-size: 13px; color: #8e8e93; margin-bottom: 16px;">
        AI 增强功能需要配置模型 API Key。基础采集、分析和报告生成不依赖 AI。
      </p>

      <div class="form-group">
        <label>模型厂商</label>
        <select v-model="llmProvider">
          <option v-for="(_, p) in presets" :key="p" :value="p">
            {{ providerLabel(p) }}
          </option>
        </select>
      </div>

      <div class="form-group">
        <label>API Key</label>
        <input v-model="llmApiKey" type="password" :placeholder="'输入 ' + providerLabel(llmProvider) + ' API Key'" />
      </div>

      <div class="form-group" v-if="llmProvider === 'custom'">
        <label>自定义 API 地址</label>
        <input v-model="llmApiUrl" placeholder="https://your-api.com/v1" />
      </div>

      <div class="form-group">
        <label>模型名称 <span style="font-weight: 400; color: #8e8e93;">（留空使用厂商默认值）</span></label>
        <input v-model="llmModel" :placeholder="defaultModel" />
      </div>

      <button @click="saveLlmConfig" class="btn btn-primary" :disabled="!llmApiKey">
        {{ saving ? '保存中...' : '保存 LLM 配置' }}
      </button>
      <span v-if="llmSaved" style="margin-left: 12px; color: #065f46; font-size: 14px;">已保存</span>

      <div v-if="currentProvider" style="margin-top: 16px; padding: 12px; background: #f0f5ff; border-radius: 8px; font-size: 13px;">
        <strong>当前配置：</strong>
        {{ providerLabel(currentProvider) }} / {{ currentModel || defaultModel }}
        <span v-if="hasKey" style="color: #065f46;"> / Key 已配置</span>
        <span v-else style="color: #991b1b;"> / 未配置 Key</span>
      </div>
    </div>

    <div class="card" style="margin-bottom: 16px;">
      <h3 style="margin-bottom: 16px;">Cookie 管理</h3>

      <div style="margin-bottom: 16px; padding: 16px; background: #fff8e1; border-radius: 8px; font-size: 13px; line-height: 1.8;">
        <strong>如何获取 Cookie：</strong>
        <ol style="margin: 8px 0 0 20px;">
          <li>用 Chrome 打开 xiaohongshu.com 并登录。</li>
          <li>按 F12 打开开发者工具，进入 Application / Cookies。</li>
          <li>选择 xiaohongshu.com，复制 Cookie 字符串。</li>
          <li>也可以在 Console 输入 <code>document.cookie</code>，复制输出内容。</li>
        </ol>
        <p style="margin-top: 8px; color: #92400e;">
          Cookie 只保存在本地数据库中。为降低异常访问风险，请不要同时创建大量采集任务。
        </p>
      </div>

      <div class="form-group">
        <label>粘贴 Cookie</label>
        <textarea v-model="newCookieJson" rows="4" style="font-size: 12px; font-family: monospace;"
          placeholder="a1=xxxxx; web_session=yyyyy; ..."></textarea>
        <p style="font-size: 12px; color: #8e8e93; margin-top: 4px;">
          常见必要字段包括 <code>a1</code> 和 <code>web_session</code>。Cookie 过期后需要重新导入。
        </p>
      </div>
      <button @click="addCookie" class="btn btn-primary" :disabled="!newCookieJson">添加 Cookie</button>

      <table style="margin-top: 16px;">
        <thead><tr><th>ID</th><th>名称</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="c in cookies" :key="c.id">
            <td>{{ c.id }}</td>
            <td>{{ c.nickname || '-' }}</td>
            <td>
              <span :class="c.is_valid === true ? 'badge badge-success' : c.is_valid === false ? 'badge badge-error' : 'badge badge-info'">
                {{ c.is_valid === true ? '有效' : c.is_valid === false ? '失效' : '未验证' }}
              </span>
            </td>
            <td><button @click="deleteCookie(c.id)" class="btn btn-danger" style="padding: 4px 12px; font-size: 12px;">删除</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top: 16px;">
      <h3 style="margin-bottom: 16px;">系统信息</h3>
      <table>
        <tbody>
          <tr><td>后端状态</td><td><span class="badge badge-success">运行中</span></td></tr>
          <tr><td>Spider_XHS</td><td><span :class="spiderAvailable ? 'badge badge-success' : 'badge badge-error'">{{ spiderAvailable ? '可用' : '不可用' }}</span></td></tr>
          <tr><td>单次最多采集</td><td>{{ limits.max_notes_per_task }} 条笔记</td></tr>
          <tr><td>同时运行任务</td><td>{{ limits.max_active_tasks_per_user }} 个</td></tr>
          <tr><td>单次对标数量</td><td>{{ limits.max_competitor_count }} 个</td></tr>
          <tr><td>数据目录</td><td style="font-size: 12px;">data/tasks/</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { cookieAPI } from '../api/client'
import api from '../api/client'

const llmProvider = ref('openai')
const llmApiKey = ref('')
const llmApiUrl = ref('')
const llmModel = ref('')
const presets = ref<Record<string, string>>({})
const currentProvider = ref('')
const currentModel = ref('')
const hasKey = ref(false)
const llmSaved = ref(false)
const saving = ref(false)

const defaultModel = computed(() => {
  const m: Record<string, string> = {
    openai: 'gpt-4o-mini',
    deepseek: 'deepseek-chat',
    kimi: 'moonshot-v1-8k',
    qwen: 'qwen-plus',
    glm: 'glm-4-flash',
    claude: 'claude-sonnet-4-20250514',
  }
  return m[llmProvider.value] || ''
})

function providerLabel(p: string) {
  const labels: Record<string, string> = {
    openai: 'OpenAI',
    deepseek: 'DeepSeek',
    kimi: 'Kimi',
    qwen: '通义千问',
    glm: '智谱 GLM',
    claude: 'Claude',
    custom: '自定义',
  }
  return labels[p] || p
}

async function loadLlmConfig() {
  try {
    const res = await api.get('/settings/llm')
    const d = res.data
    presets.value = d.presets || {}
    llmProvider.value = d.provider || 'openai'
    llmApiUrl.value = d.api_url || ''
    llmModel.value = d.model || ''
    currentProvider.value = d.provider || ''
    currentModel.value = d.model || ''
    hasKey.value = d.has_key || false
  } catch {}
}

async function saveLlmConfig() {
  saving.value = true
  try {
    const body: Record<string, string> = {
      llm_provider: llmProvider.value,
      llm_api_key: llmApiKey.value,
    }
    if (llmApiUrl.value) body.llm_api_url = llmApiUrl.value
    if (llmModel.value) body.llm_model = llmModel.value

    await api.post('/settings/llm', body)
    llmSaved.value = true
    currentProvider.value = llmProvider.value
    currentModel.value = llmModel.value || defaultModel.value
    hasKey.value = true
    setTimeout(() => llmSaved.value = false, 2000)
  } catch (e) {
    alert('保存失败')
  } finally {
    saving.value = false
  }
}

const newCookieJson = ref('')
const cookies = ref<any[]>([])
const spiderAvailable = ref(true)
const limits = ref({
  max_notes_per_task: 100,
  max_active_tasks_per_user: 1,
  max_competitor_count: 5,
})

async function addCookie() {
  if (!newCookieJson.value) return
  try {
    await cookieAPI.create(newCookieJson.value)
    newCookieJson.value = ''
    loadCookies()
  } catch (e) { console.error(e) }
}

async function deleteCookie(id: number) {
  if (!confirm('确定删除这个 Cookie 吗？')) return
  try {
    await cookieAPI.delete(id)
    loadCookies()
  } catch {}
}

async function loadCookies() {
  try {
    const res = await cookieAPI.list()
    cookies.value = res.data
  } catch {}
}

onMounted(() => {
  loadLlmConfig()
  loadCookies()
  api.get('/health').then(r => {
    spiderAvailable.value = r.data.spider_xhs_available
    limits.value = r.data.limits || limits.value
  }).catch(() => spiderAvailable.value = false)
})
</script>
