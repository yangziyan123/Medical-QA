<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

const title = computed(() => (mode.value === 'login' ? '登录' : '注册'))

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    if (mode.value === 'register') await auth.register(username.value, password.value)
    await auth.login(username.value, password.value)
    await router.push('/chat')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page page-center">
    <div class="card">
      <h1 class="h1">{{ title }}</h1>

      <div class="tabs">
        <button class="tab" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button class="tab" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <form class="form" @submit.prevent="submit">
        <label class="label">
          <span>用户名</span>
          <input v-model.trim="username" class="input" autocomplete="username" />
        </label>
        <label class="label">
          <span>密码</span>
          <input v-model="password" class="input" type="password" autocomplete="current-password" />
        </label>

        <div v-if="error" class="error">{{ error }}</div>

        <button class="btn primary" type="submit" :disabled="submitting || !username || !password">
          {{ submitting ? '提交中…' : title }}
        </button>
      </form>

      <p class="muted">
        提示：这是开发环境页面；注册成功后会自动登录并跳转到聊天页。
      </p>
    </div>
  </div>
</template>

