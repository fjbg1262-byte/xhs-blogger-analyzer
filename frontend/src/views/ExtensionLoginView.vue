<template>
  <main class="extension-login">
    <section class="panel">
      <h1>{{ title }}</h1>
      <p>{{ detail }}</p>
      <router-link v-if="failed" to="/login" class="btn btn-primary">打开登录页</router-link>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { setAuth } from '../auth'

const route = useRoute()
const router = useRouter()

const failed = ref(false)
const title = ref('正在打开分析报告')
const detail = ref('请稍等，正在连接本地分析工具。')

onMounted(() => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  const username = typeof route.query.username === 'string' ? route.query.username : 'local_extension_user'
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'

  if (!token) {
    failed.value = true
    title.value = '没有拿到本地登录信息'
    detail.value = '请回到小红书主页，重新点击插件里的分析按钮。'
    return
  }

  setAuth(token, username)
  router.replace(redirect.startsWith('/') ? redirect : '/dashboard')
})
</script>

<style scoped>
.extension-login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #f5f5f7;
}

.panel {
  width: min(420px, 100%);
  padding: 28px;
  border: 1px solid #e5e5e7;
  border-radius: 8px;
  background: #fff;
  text-align: center;
}

h1 {
  margin: 0 0 10px;
  font-size: 22px;
}

p {
  margin: 0 0 18px;
  color: #666;
  line-height: 1.6;
}
</style>
