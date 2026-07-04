import { create } from 'zustand'

function loadUser() {
  try {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function getToken() {
  try {
    return localStorage.getItem('access_token') || null
  } catch {
    return null
  }
}

export const useAuthStore = create((set) => ({
  user: loadUser(),
  token: getToken(),
  setUser: (user) => {
    try { localStorage.setItem('auth_user', JSON.stringify(user)) } catch { /* private browsing */ }
    set({ user })
  },
  setToken: (token) => {
    try { localStorage.setItem('access_token', token) } catch { /* private browsing */ }
    set({ token })
  },
  setAuth: (token, user) => {
    try { localStorage.setItem('access_token', token) } catch { /* private browsing */ }
    try { localStorage.setItem('auth_user', JSON.stringify(user)) } catch { /* private browsing */ }
    set({ token, user })
  },
  logout: () => {
    try { localStorage.removeItem('access_token') } catch { /* private browsing */ }
    try { localStorage.removeItem('auth_user') } catch { /* private browsing */ }
    set({ user: null, token: null })
  },
}))

function loadTokenUsage() {
  try {
    const raw = localStorage.getItem('token_usage')
    if (raw) {
      const parsed = JSON.parse(raw)
      return parsed.total_tokens > 0 ? parsed : null
    }
  } catch {}
  return null
}

export const useTokenStore = create((set) => ({
  lastUsage: loadTokenUsage(),
  setLastUsage: (usage) => {
    set((state) => {
      const prev = state.lastUsage || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
      const accumulated = {
        prompt_tokens: (prev.prompt_tokens || 0) + (usage.prompt_tokens || 0),
        completion_tokens: (prev.completion_tokens || 0) + (usage.completion_tokens || 0),
        total_tokens: (prev.total_tokens || 0) + (usage.total_tokens || 0),
      }
      try { localStorage.setItem('token_usage', JSON.stringify(accumulated)) } catch {}
      return { lastUsage: accumulated }
    })
  },
  clearUsage: () => {
    try { localStorage.removeItem('token_usage') } catch {}
    set({ lastUsage: null })
  },
}))
