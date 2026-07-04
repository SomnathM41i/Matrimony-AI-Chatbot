import { useState, useCallback, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { sendMessage, getConversation } from '../services/chatService'
import { useTokenStore } from '../app/store'

export function useChat(conversationId = null, onNewConversation) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const queryClient = useQueryClient()
  const activeConvId = useRef(conversationId)
  const lastSentRef = useRef('')

  useEffect(() => {
    setMessages([])
    setStreaming(false)
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
    if (String(conversationData.id) !== String(conversationId)) return
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

  const { mutate, isPending } = useMutation({
    mutationFn: ({ message, convId }) => sendMessage(message, convId),
    onMutate: async ({ message }) => {
      lastSentRef.current = message
      const userMsg = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      setStreaming(true)
    },
    onSuccess: (data, variables) => {
      if (variables.convId !== activeConvId.current) return
      const botMsg = {
        id: data.message_id,
        role: 'assistant',
        content: data.reply,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, botMsg])
      if (data.conversation_id !== activeConvId.current) {
        activeConvId.current = data.conversation_id
        onNewConversation?.(data.conversation_id)
      }
      if (data.usage?.total_tokens > 0) setLastUsage(data.usage)
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: (error, variables) => {
      if (variables.convId !== activeConvId.current) return
      const text = error?.response?.data?.detail || error?.message || 'Sorry, I encountered an error.'
      toast.error(text, { id: 'chat-error' })
      const errorMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: text,
        isError: true,
        originalMessage: lastSentRef.current,
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
      if (!message.trim() || isPending) return
      mutate({
        message: message.trim(),
        convId: activeConvId.current,
      })
    },
    [isPending]
  )

  const retry = useCallback(() => {
    if (lastSentRef.current) send(lastSentRef.current)
  }, [send])

  const clearMessages = useCallback(() => {
    setMessages([])
    activeConvId.current = null
  }, [])

  return {
    messages,
    streaming,
    send,
    retry,
    clearMessages,
    isLoadingHistory,
    conversationId: activeConvId.current,
  }
}
