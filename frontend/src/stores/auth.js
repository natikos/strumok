import { defineStore } from 'pinia'
import { apiRequest } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    async register(payload) {
      return apiRequest('/api/auth/register', {
        method: 'POST',
        body: payload,
      })
    },
    async login(payload) {
      const data = await apiRequest('/api/auth/login', {
        method: 'POST',
        body: payload,
      })
      this.token = data.access_token
      localStorage.setItem('token', data.access_token)
      await this.fetchMe()
    },
    async fetchMe() {
      if (!this.token) return null
      this.user = await apiRequest('/api/auth/me', { token: this.token })
      return this.user
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
  },
})
