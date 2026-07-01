import api from './apiClient'

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
