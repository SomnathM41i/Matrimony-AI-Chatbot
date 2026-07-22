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
  token: !!loadUser(),
  setUser: (user) => {
    try { localStorage.setItem('auth_user', JSON.stringify(user)) } catch { /* private browsing */ }
    set({ user })
  },
  setAuth: (_token, user) => {
    try { localStorage.setItem('auth_user', JSON.stringify(user)) } catch { /* private browsing */ }
    set({ token: true, user })
  },
  logout: () => {
    try { localStorage.removeItem('auth_user') } catch { /* private browsing */ }
    set({ user: null, token: false })
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
