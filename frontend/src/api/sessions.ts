import { apiClient } from './client'

export type SessionListItem = { id: string; title: string | null; updated_at: string }
export type SessionListResponse = { items: SessionListItem[]; next_cursor: string | null }

export type MessageResponse = { id: string; role: 'system' | 'user' | 'assistant'; content: string; created_at: string }
export type SessionResponse = { id: string; title: string | null; created_at: string; updated_at: string }
export type SessionWithMessagesResponse = { session: SessionResponse; messages: MessageResponse[] }

export async function apiCreateSession(title?: string | null): Promise<SessionResponse> {
  const { data } = await apiClient.post('/api/sessions', { title: title ?? null })
  return data
}

export async function apiListSessions(limit = 20, cursor?: string | null): Promise<SessionListResponse> {
  const params: Record<string, string | number> = { limit }
  if (cursor) params.cursor = cursor
  const { data } = await apiClient.get('/api/sessions', { params })
  return data
}

export async function apiGetSession(sessionId: string): Promise<SessionWithMessagesResponse> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}`)
  return data
}

export async function apiUpdateSessionTitle(sessionId: string, title: string | null): Promise<SessionResponse> {
  const { data } = await apiClient.patch(`/api/sessions/${sessionId}`, { title })
  return data
}

export async function apiDeleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/api/sessions/${sessionId}`)
}
