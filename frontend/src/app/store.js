import { create } from 'zustand'

function loadUser() {
  try {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = create((set) => ({
  user: loadUser(),
  token: localStorage.getItem('access_token') || null,
  setUser: (user) => {
    localStorage.setItem('auth_user', JSON.stringify(user))
    set({ user })
  },
  setToken: (token) => {
    localStorage.setItem('access_token', token)
    set({ token })
  },
  setAuth: (token, user) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('auth_user', JSON.stringify(user))
    set({ token, user })
  },
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('auth_user')
    set({ user: null, token: null })
  },
}))

export const useTokenStore = create((set) => ({
  lastUsage: null,
  setLastUsage: (usage) => set({ lastUsage: usage }),
}))
