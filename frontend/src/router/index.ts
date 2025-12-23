import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  { path: '/login', component: () => import('../views/LoginView.vue') },
  { path: '/chat', meta: { requiresAuth: true }, component: () => import('../views/ChatView.vue') },
  {
    path: '/admin/knowledge',
    meta: { requiresAuth: true, requiresAdmin: true },
    component: () => import('../views/AdminKnowledgeView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (auth.token && !auth.user && !auth.loadingMe) {
    await auth.fetchMe().catch(() => {})
  }

  if (to.path === '/login' && auth.isAuthenticated) return '/chat'
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.meta.requiresAdmin && auth.user?.role !== 'admin') return '/chat'
  return true
})

export default router
