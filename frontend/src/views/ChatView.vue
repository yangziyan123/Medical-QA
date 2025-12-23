<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import CitationList from '../components/CitationList.vue'

const auth = useAuthStore()
const chat = useChatStore()
const router = useRouter()

const question = ref('')
const chatScrollEl = ref<HTMLDivElement | null>(null)
const bottomAnchorEl = ref<HTMLDivElement | null>(null)
const stickToBottom = ref(true)

const currentMessages = computed(() => {
  if (!chat.currentSessionId) return []
  return chat.messagesBySession[chat.currentSessionId] || []
})

const lastAssistantIndex = computed(() => {
  const msgs = currentMessages.value
  for (let i = msgs.length - 1; i >= 0; i -= 1) {
    if (msgs[i]?.role === 'assistant') return i
  }
  return -1
})

const lastRun = computed(() => {
  if (!chat.currentSessionId) return null
  return chat.lastRunBySession[chat.currentSessionId] || null
})

function onChatScroll() {
  const el = chatScrollEl.value
  if (!el) return
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  stickToBottom.value = distance < 120
}

async function scrollToBottom() {
  await nextTick()
  bottomAnchorEl.value?.scrollIntoView({ block: 'end' })
}

async function logout() {
  auth.logout()
  await router.push('/login')
}

async function openAdminKnowledge() {
  await router.push('/admin/knowledge')
}

async function send() {
  const q = question.value.trim()
  if (!q || chat.sending) return
  question.value = ''
  await chat.streamAsk(q)
}

async function selectSession(id: string) {
  await chat.openSession(id)
  stickToBottom.value = true
  await scrollToBottom()
}

async function newSession() {
  await chat.createNewSession('新会话')
  stickToBottom.value = true
  await scrollToBottom()
}

async function renameSession(id: string, currentTitle: string | null) {
  const nextTitle = window.prompt('请输入新的会话名称：', currentTitle || '')
  if (nextTitle === null) return
  const t = nextTitle.trim()
  await chat.renameSession(id, t || null)
}

async function deleteSession(id: string, title: string | null) {
  const ok = window.confirm(`确认删除该会话吗？\n${title || id}`)
  if (!ok) return
  await chat.deleteSession(id)
  stickToBottom.value = true
  await scrollToBottom()
}

onMounted(async () => {
  await chat.refreshSessions()
  if (chat.sessions.length > 0) {
    const first = chat.sessions[0]
    if (first) await chat.openSession(first.id)
  }
  stickToBottom.value = true
  await scrollToBottom()
})

watch(
  () => chat.currentSessionId,
  async (id) => {
    if (id && !chat.messagesBySession[id]) await chat.openSession(id)
    stickToBottom.value = true
    await scrollToBottom()
  },
)

const scrollKey = computed(() => {
  const msgs = currentMessages.value
  if (!msgs.length) return ''
  const last = msgs[msgs.length - 1]!
  return `${last.id}:${last.content.length}:${chat.streamingStage}`
})

watch(
  scrollKey,
  async () => {
    if (stickToBottom.value) await scrollToBottom()
  },
  { flush: 'post' },
)
</script>

<template>
  <div class="page chat-page">
    <header class="topbar">
      <div class="brand">医疗问答（开发版）</div>
      <div class="topbar-right">
        <div class="muted" v-if="auth.user">{{ auth.user.username }}</div>
        <button v-if="auth.user?.role === 'admin'" class="btn" @click="openAdminKnowledge">知识库</button>
        <button class="btn" @click="logout">退出</button>
      </div>
    </header>

    <div class="layout">
      <aside class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">会话</div>
          <button class="btn primary" @click="newSession">新建</button>
        </div>

        <div v-if="chat.loadingSessions" class="muted">加载中…</div>
        <div v-else class="session-list">
          <div
            v-for="s in chat.sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === chat.currentSessionId }"
            role="button"
            tabindex="0"
            @click="selectSession(s.id)"
          >
            <div class="session-main">
              <div class="session-title">{{ s.title || '未命名会话' }}</div>
              <div class="session-meta">{{ new Date(s.updated_at).toLocaleString() }}</div>
            </div>
            <div class="session-actions">
              <button class="btn small" @click.stop="renameSession(s.id, s.title)">改名</button>
              <button class="btn small danger" @click.stop="deleteSession(s.id, s.title)">删除</button>
            </div>
          </div>
        </div>
      </aside>

      <main class="content">
        <div v-if="chat.error" class="error" style="margin-bottom: 12px">{{ chat.error }}</div>
        <div v-if="chat.streamingStage" class="muted" style="margin-bottom: 6px">阶段：{{ chat.streamingStage }}</div>

        <div ref="chatScrollEl" class="chat" @scroll="onChatScroll">
          <div v-if="!chat.currentSessionId" class="muted">请先创建或选择一个会话。</div>
          <div v-else class="messages">
            <div v-for="(m, idx) in currentMessages" :key="m.id" class="msg" :class="m.role">
              <div class="msg-role">{{ m.role }}</div>
              <div class="msg-content">{{ m.content }}</div>
              <div class="msg-meta">{{ new Date(m.created_at).toLocaleString() }}</div>

              <div v-if="m.role === 'assistant' && idx === lastAssistantIndex && lastRun?.citations?.length" class="msg-extra">
                <CitationList :citations="lastRun.citations" />
              </div>
              <div v-if="m.role === 'assistant' && idx === lastAssistantIndex && lastRun?.safety?.disclaimer" class="muted" style="margin-top: 8px">
                免责声明：{{ lastRun.safety.disclaimer }}
              </div>
            </div>
            <div ref="bottomAnchorEl" style="height: 1px"></div>
          </div>
        </div>

        <form class="composer" @submit.prevent="send">
          <input
            v-model="question"
            class="input"
            placeholder="输入你的问题（SSE 流式输出）"
            :disabled="!chat.currentSessionId || chat.sending"
          />
          <button class="btn primary" type="submit" :disabled="!chat.currentSessionId || chat.sending || !question.trim()">
            {{ chat.sending ? '发送中…' : '发送' }}
          </button>
        </form>
        <div class="muted">
          当前模式：SSE（/api/chat/stream）。如果你看不到逐字输出，通常是后端分片过快或被缓冲；已在占位流式中加入轻微延迟。
        </div>
      </main>
    </div>
  </div>
</template>
