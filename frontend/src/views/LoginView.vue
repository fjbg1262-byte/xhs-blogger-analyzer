<template>
  <div class="login-page">
    <div class="login-panel">
      <h1>XHS Analyzer</h1>
      <p>登录后管理自己的 Cookie、任务和报告。</p>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <div class="form-group">
        <label>用户名</label>
        <input v-model="username" autocomplete="username" @keyup.enter="submit" />
      </div>

      <div class="form-group">
        <label>密码</label>
        <input v-model="password" type="password" autocomplete="current-password" @keyup.enter="submit" />
      </div>

      <button class="btn btn-primary" style="width: 100%; justify-content: center;" :disabled="loading || !canSubmit" @click="submit">
        {{ loading ? '处理中...' : mode === 'login' ? '登录' : '注册并登录' }}
      </button>

      <div v-if="error" class="error">{{ error }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authAPI } from '../api/client'
import { setAuth } from '../auth'

const router = useRouter()
const route = useRoute()
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const canSubmit = computed(() => username.value.trim().length >= 2 && password.value.length >= 6)

async function submit() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const apiCall = mode.value === 'login' ? authAPI.login : authAPI.register
    const res = await apiCall(username.value.trim(), password.value)
    setAuth(res.data.access_token, res.data.username)
    router.push(String(route.query.redirect || '/dashboard'))
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 104px);
  display: grid;
  place-items: center;
}
.login-panel {
  width: min(420px, 100%);
  background: #fff;
  border: 1px solid #e5e5e7;
  border-radius: 8px;
  padding: 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.login-panel h1 {
  font-size: 24px;
  margin-bottom: 4px;
}
.login-panel p {
  color: #8e8e93;
  font-size: 14px;
  margin-bottom: 20px;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 20px;
}
.tabs button {
  border: 1px solid #d1d1d6;
  background: #fff;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
}
.tabs button.active {
  background: #007aff;
  border-color: #007aff;
  color: #fff;
}
.error {
  margin-top: 16px;
  padding: 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #991b1b;
  font-size: 14px;
}
</style>
