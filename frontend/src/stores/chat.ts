import { defineStore } from 'pinia'
import { apiChatAsk, apiChatStream } from '../api/chat'
import { apiBaseUrl } from '../api/client'
import {
  apiCreateSession,
  apiDeleteSession,
  apiGetSession,
  apiListSessions,
  apiUpdateSessionTitle,
  type MessageResponse,
  type SessionListItem,
} from '../api/sessions'
import { useAuthStore } from './auth'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [] as SessionListItem[],
    nextCursor: null as string | null,
    currentSessionId: null as string | null,
    messagesBySession: {} as Record<string, MessageResponse[]>,
    lastRunBySession: {} as Record<string, any>,
    loadingSessions: false,
    loadingSession: false,
    sending: false,
    streamingStage: '' as string,
    error: '' as string,
  }),
  actions: {
    async refreshSessions() {
      this.loadingSessions = true
      this.error = ''
      try {
        const res = await apiListSessions(50, null)
        this.sessions = res.items
        this.nextCursor = res.next_cursor
      } catch (e: any) {
        this.error = e?.response?.data?.detail || e?.message || '加载会话失败'
      } finally {
        this.loadingSessions = false
      }
    },
    async createNewSession(title?: string) {
      const session = await apiCreateSession(title || null)
      this.currentSessionId = session.id
      await this.refreshSessions()
      await this.openSession(session.id)
      return session
    },
    async renameSession(sessionId: string, title: string | null) {
      await apiUpdateSessionTitle(sessionId, title)
      await this.refreshSessions()
      if (this.currentSessionId === sessionId) {
        await this.openSession(sessionId)
      }
    },
    async deleteSession(sessionId: string) {
      await apiDeleteSession(sessionId)
      delete this.messagesBySession[sessionId]
      delete this.lastRunBySession[sessionId]
      await this.refreshSessions()
      if (this.currentSessionId === sessionId) {
        const next = this.sessions[0]?.id || null
        this.currentSessionId = next
        if (next) await this.openSession(next)
      }
    },
    async openSession(sessionId: string) {
      this.loadingSession = true
      this.error = ''
      try {
        const res = await apiGetSession(sessionId)
        this.currentSessionId = res.session.id
        this.messagesBySession[res.session.id] = res.messages
      } catch (e: any) {
        this.error = e?.response?.data?.detail || e?.message || '加载会话详情失败'
      } finally {
        this.loadingSession = false
      }
    },
    async ask(question: string) {
      if (!question.trim()) return

      this.sending = true
      this.error = ''
      try {
        const res = await apiChatAsk(question, this.currentSessionId)
        this.lastRunBySession[res.session_id] = res
        await this.refreshSessions()
        await this.openSession(res.session_id)
        return res
      } catch (e: any) {
        this.error = e?.response?.data?.detail || e?.message || '提问失败'
        throw e
      } finally {
        this.sending = false
      }
    },

    appendLocalMessage(sessionId: string, msg: Omit<MessageResponse, 'id' | 'created_at'> & { id?: string }) {
      const list = (this.messagesBySession[sessionId] || []).slice()
      list.push({
        id: msg.id || `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        role: msg.role,
        content: msg.content,
        created_at: new Date().toISOString(),
      })
      this.messagesBySession[sessionId] = list
    },

    updateLocalMessage(sessionId: string, messageId: string, patch: Partial<Pick<MessageResponse, 'content'>>) {
      const list = (this.messagesBySession[sessionId] || []).slice()
      const idx = list.findIndex((m) => m.id === messageId)
      if (idx === -1) return
      const current = list[idx]
      if (!current) return
      list[idx] = { ...current, ...patch }
      this.messagesBySession[sessionId] = list
    },

    async streamAsk(question: string) {
      if (!question.trim()) return
      if (!this.currentSessionId) throw new Error('No session selected')

      const auth = useAuthStore()
      if (!auth.token) throw new Error('Not authenticated')

      const sessionId = this.currentSessionId
      this.sending = true
      this.streamingStage = 'starting'
      this.error = ''

      this.appendLocalMessage(sessionId, { role: 'user', content: question })
      const assistantLocalId = `local-assistant-${Date.now()}`
      this.appendLocalMessage(sessionId, { id: assistantLocalId, role: 'assistant', content: '' })

      try {
        const done = await apiChatStream(apiBaseUrl, auth.token, question, sessionId, {
          onMeta: (meta) => {
            this.streamingStage = meta?.stage || ''
          },
          onToken: (delta) => {
            const cur = (this.messagesBySession[sessionId] || []).find((m) => m.id === assistantLocalId)
            this.updateLocalMessage(sessionId, assistantLocalId, { content: (cur?.content || '') + delta })
          },
        })

        this.streamingStage = ''
        this.lastRunBySession[done.session_id] = done
        await this.refreshSessions()
        await this.openSession(done.session_id)
        return done
      } catch (e: any) {
        this.error = e?.message || '流式提问失败'
        this.updateLocalMessage(sessionId, assistantLocalId, { content: `${this.error}\n（可重试）` })
        throw e
      } finally {
        this.sending = false
      }
    },
  },
})
