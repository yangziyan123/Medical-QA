<script setup lang="ts">
import type { Citation } from '../api/chat'

defineProps<{
  citations: Citation[]
}>()

function formatScore(score?: number | null) {
  if (score === null || score === undefined) return ''
  return score.toFixed(3)
}
</script>

<template>
  <div class="citations">
    <div class="citations-title">引用来源</div>
    <div v-for="(c, i) in citations" :key="c.chunk_id" class="citation">
      <div class="citation-header">
        <div class="citation-index">CIT-{{ i + 1 }}</div>
        <div class="citation-doc">
          <span class="citation-doc-title">{{ c.document?.title || '未命名文档' }}</span>
          <span v-if="c.document?.version" class="citation-doc-meta">（{{ c.document?.version }}）</span>
        </div>
        <a v-if="c.document?.source_url" class="citation-link" :href="c.document.source_url" target="_blank" rel="noreferrer">
          链接
        </a>
        <div v-if="formatScore(c.score)" class="citation-score">score={{ formatScore(c.score) }}</div>
      </div>
      <div v-if="c.snippet" class="citation-snippet">{{ c.snippet }}</div>
    </div>
  </div>
</template>

<style scoped>
.citations {
  margin-top: 10px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
}
.citations-title {
  font-size: 12px;
  color: #475569;
  font-weight: 800;
  margin-bottom: 6px;
}
.citation {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 10px 10px;
  background: #ffffff;
  margin-bottom: 8px;
}
.citation-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
}
.citation-index {
  font-weight: 900;
  font-size: 12px;
  color: #0f172a;
}
.citation-doc-title {
  font-weight: 800;
  font-size: 12px;
}
.citation-doc-meta,
.citation-score {
  font-size: 12px;
  color: #64748b;
}
.citation-link {
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
}
.citation-link:hover {
  text-decoration: underline;
}
.citation-snippet {
  margin-top: 6px;
  font-size: 12px;
  color: #334155;
  white-space: pre-wrap;
}
</style>

