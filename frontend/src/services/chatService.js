import api from './apiClient'

const baseURL = import.meta.env.VITE_API_URL || '/api'

export function sendMessageStream(message, conversationId = null) {
  const controller = new AbortController()
  const url = `${baseURL}/chat/stream`

  const stream = (async function* () {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ message, conversation_id: conversationId }),
      signal: controller.signal,
    })

    if (!response.ok) {
      let detail = `Request failed with status code ${response.status}`
      try {
        const err = await response.json()
        detail = err.detail || detail
      } catch {}
      throw new Error(detail)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const event = JSON.parse(raw)
            yield event
          } catch {}
        }
      }
    }
  })()

  return { stream, abort: () => controller.abort() }
}

export const sendMessage = async (message, conversationId = null) => {
  const { data } = await api.post('/chat', {
    message,
    conversation_id: conversationId,
  })
  return data
}

export const getConversations = async (page = 1, pageSize = 20) => {
  const { data } = await api.get('/conversations', {
    params: { page, page_size: pageSize },
  })
  return data
}

export const getConversation = async (id) => {
  const { data } = await api.get(`/conversations/${id}`)
  return data
}

export const updateConversation = async (id, updates) => {
  const { data } = await api.patch(`/conversations/${id}`, updates)
  return data
}

export const deleteConversation = async (id) => {
  const { data } = await api.delete(`/conversations/${id}`)
  return data
}
