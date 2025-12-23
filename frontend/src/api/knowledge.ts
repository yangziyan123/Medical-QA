import { apiClient } from './client'

export type KnowledgeImportRequest = {
  source_type?: string
  title: string
  version?: string | null
  source_url?: string | null
  raw_text: string
}

export type KnowledgeImportResponse = { document_id: string; chunk_count: number }

export type KnowledgeSearchItem = {
  chunk_id: string
  document_id: string
  title: string
  version: string | null
  source_url: string | null
  chunk_index: number
  score: number
  text: string
}

export type KnowledgeSearchResponse = { items: KnowledgeSearchItem[] }

export async function apiKnowledgeImport(payload: KnowledgeImportRequest): Promise<KnowledgeImportResponse> {
  const { data } = await apiClient.post('/api/knowledge/import', payload)
  return data
}

export async function apiKnowledgeSearch(q: string, topK = 5): Promise<KnowledgeSearchResponse> {
  const { data } = await apiClient.get('/api/knowledge/search', { params: { q, top_k: topK } })
  return data
}

