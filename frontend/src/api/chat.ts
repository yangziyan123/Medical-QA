import { apiClient } from './client'
import { fetchSSE } from '../utils/sse'

export type SafetyInfo = { disclaimer: string; triage: 'normal' | 'emergency' }
export type CitationDocument = { title: string; version?: string | null; source_url?: string | null }
export type Citation = {
  chunk_id: string
  document?: CitationDocument | null
  snippet?: string | null
  score?: number | null
}

export type ChatAskResponse = {
  session_id: string
  qa_run_id: string
  answer: string
  citations: Citation[]
  safety: SafetyInfo
}

export async function apiChatAsk(question: string, sessionId?: string | null): Promise<ChatAskResponse> {
  const body: Record<string, unknown> = { question }
  if (sessionId) body.session_id = sessionId
  const { data } = await apiClient.post('/api/chat/ask', body)
  return data
}

export type StreamHandlers = {
  onMeta?: (meta: any) => void
  onToken?: (delta: string) => void
  onDone?: (done: ChatAskResponse) => void
  onError?: (message: string) => void
}

export async function apiChatStream(
  baseUrl: string,
  token: string,
  question: string,
  sessionId: string | null,
  handlers: StreamHandlers,
): Promise<ChatAskResponse> {
  let final: ChatAskResponse | null = null
  let streamError: string | null = null
  const controller = new AbortController()

  try {
    await fetchSSE(
      `${baseUrl}/api/chat/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question, session_id: sessionId || undefined }),
        signal: controller.signal,
      },
      (evt) => {
        if (evt.event === 'meta') {
          handlers.onMeta?.(JSON.parse(evt.data))
          return
        }
        if (evt.event === 'token') {
          const { delta } = JSON.parse(evt.data)
          handlers.onToken?.(delta)
          return
        }
        if (evt.event === 'done') {
          final = JSON.parse(evt.data) as ChatAskResponse
          handlers.onDone?.(final)
          return
        }
        if (evt.event === 'error') {
          const msg = JSON.parse(evt.data)?.message || 'stream error'
          streamError = msg
          handlers.onError?.(msg)
          controller.abort()
        }
      },
    )
  } catch (e: any) {
    // If we aborted due to a server "error" SSE event, rethrow that message.
    if (streamError) throw new Error(streamError)
    throw e
  }

  if (streamError) throw new Error(streamError)
  if (!final) throw new Error('Stream ended without done event')
  return final
}
