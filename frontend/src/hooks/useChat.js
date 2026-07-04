import { useState, useCallback, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sendMessage, getConversation } from '../services/chatService'
import { useTokenStore } from '../app/store'

export function useChat(conversationId = null) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const queryClient = useQueryClient()
  const activeConvId = useRef(conversationId)

  useEffect(() => {
    setMessages([])
    activeConvId.current = conversationId || null
  }, [conversationId])

  const { data: conversationData, isLoading: isLoadingHistory } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => getConversation(conversationId),
    enabled: !!conversationId,
    retry: false,
  })

  useEffect(() => {
    if (!conversationData) return
    setMessages(
      conversationData.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at,
      }))
    )
    activeConvId.current = conversationId
  }, [conversationData, conversationId])

  const setLastUsage = useTokenStore((s) => s.setLastUsage)

  const chatMutation = useMutation({
    mutationFn: ({ message, convId }) => sendMessage(message, convId),
    onMutate: async ({ message }) => {
      const userMsg = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      setStreaming(true)
    },
    onSuccess: (data) => {
      const botMsg = {
        id: data.message_id,
        role: 'assistant',
        content: data.reply,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, botMsg])
      activeConvId.current = data.conversation_id
      if (data.usage?.total_tokens > 0) setLastUsage(data.usage)
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => {
      const errorMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMsg])
    },
    onSettled: () => {
      setStreaming(false)
    },
  })

  const send = useCallback(
    (message) => {
      if (!message.trim() || chatMutation.isPending) return
      chatMutation.mutate({
        message: message.trim(),
        convId: activeConvId.current,
      })
    },
    [chatMutation]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    activeConvId.current = null
  }, [])

  return {
    messages,
    streaming,
    send,
    clearMessages,
    isLoadingHistory,
    conversationId: activeConvId.current,
  }
}
