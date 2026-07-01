import { useState, useCallback, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sendMessage, getConversation } from '../services/chatService'

export function useChat(conversationId = null) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const queryClient = useQueryClient()
  const activeConvId = useRef(conversationId)

  const { isLoading: isLoadingHistory } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: async () => {
      const data = await getConversation(conversationId)
      setMessages(
        data.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        }))
      )
      activeConvId.current = conversationId
      return data
    },
    enabled: !!conversationId,
    retry: false,
  })

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
