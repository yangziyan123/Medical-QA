<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { apiKnowledgeImport, apiKnowledgeSearch, type KnowledgeSearchItem } from '../api/knowledge'

const auth = useAuthStore()
const router = useRouter()

const importTitle = ref('发热处理（开发样例）')
const importVersion = ref('2025-12')
const importUrl = ref('https://example.com')
const importText = ref('发热是常见症状。\n\n当体温超过 39℃ 时，应评估是否伴随呼吸困难、意识障碍等紧急情况。')
const importResult = ref('')

const searchQ = ref('发热')
const searchTopK = ref(5)
const searchItems = ref<KnowledgeSearchItem[]>([])

const error = ref('')
const busy = ref(false)

async function goBack() {
  await router.push('/chat')
}

async function doImport() {
  error.value = ''
  importResult.value = ''
  busy.value = true
  try {
    const res = await apiKnowledgeImport({
      source_type: 'guideline',
      title: importTitle.value,
      version: importVersion.value,
      source_url: importUrl.value,
      raw_text: importText.value,
    })
    importResult.value = `导入成功：document_id=${res.document_id} chunk_count=${res.chunk_count}`
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '导入失败'
  } finally {
    busy.value = false
  }
}

async function doSearch() {
  error.value = ''
  busy.value = true
  try {
    const res = await apiKnowledgeSearch(searchQ.value, searchTopK.value)
    searchItems.value = res.items
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '检索失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">知识库管理（开发版）</div>
      <div class="topbar-right">
        <div class="muted" v-if="auth.user">{{ auth.user.username }}（{{ auth.user.role }}）</div>
        <button class="btn" @click="goBack">返回聊天</button>
      </div>
    </header>

    <div style="padding: 12px; display: grid; gap: 12px; max-width: 1100px; margin: 0 auto">
      <div v-if="error" class="error">{{ error }}</div>

      <div class="card" style="width: 100%">
        <div class="h1">导入 raw_text</div>
        <div class="form" style="margin-top: 10px">
          <label class="label">
            <span>标题</span>
            <input v-model="importTitle" class="input" :disabled="busy" />
          </label>
          <label class="label">
            <span>版本</span>
            <input v-model="importVersion" class="input" :disabled="busy" />
          </label>
          <label class="label">
            <span>来源 URL</span>
            <input v-model="importUrl" class="input" :disabled="busy" />
          </label>
          <label class="label">
            <span>原文（raw_text）</span>
            <textarea v-model="importText" class="input" rows="8" :disabled="busy" />
          </label>
          <button class="btn primary" :disabled="busy || !importTitle || !importText" @click="doImport">
            {{ busy ? '处理中…' : '导入' }}
          </button>
          <div v-if="importResult" class="muted">{{ importResult }}</div>
        </div>
      </div>

      <div class="card" style="width: 100%">
        <div class="h1">检索调试</div>
        <div class="composer" style="margin-top: 10px">
          <input v-model="searchQ" class="input" placeholder="输入检索词" :disabled="busy" />
          <button class="btn primary" :disabled="busy || !searchQ" @click="doSearch">检索</button>
        </div>
        <div class="muted" style="margin-top: 8px">top_k={{ searchTopK }}</div>

        <div style="margin-top: 10px; display: grid; gap: 8px">
          <div v-for="item in searchItems" :key="item.chunk_id" class="citation">
            <div class="citation-header">
              <div class="citation-doc">
                <span class="citation-doc-title">{{ item.title }}</span>
                <span v-if="item.version" class="citation-doc-meta">（{{ item.version }}）</span>
              </div>
              <a v-if="item.source_url" class="citation-link" :href="item.source_url" target="_blank" rel="noreferrer">链接</a>
              <div class="citation-score">score={{ item.score.toFixed(3) }}</div>
            </div>
            <div class="citation-snippet">{{ item.text }}</div>
          </div>
          <div v-if="searchItems.length === 0" class="muted">暂无结果</div>
        </div>
      </div>
    </div>
  </div>
</template>

