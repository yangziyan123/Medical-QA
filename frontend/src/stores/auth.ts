import { defineStore } from 'pinia'
import { apiLogin, apiMe, apiRegister, type UserResponse } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null as UserResponse | null,
    loadingMe: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    async register(username: string, password: string) {
      await apiRegister(username, password)
    },
    async login(username: string, password: string) {
      const token = await apiLogin(username, password)
      this.token = token.access_token
      localStorage.setItem('token', this.token)
      await this.fetchMe()
    },
    async fetchMe() {
      this.loadingMe = true
      try {
        this.user = await apiMe()
      } finally {
        this.loadingMe = false
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
  },
})

