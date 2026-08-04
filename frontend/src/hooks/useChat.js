import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { sendMessage, sendMessageStream, getConversation } from '../services/chatService'
import { useTokenStore, useAuthStore } from '../app/store'
import { getApiErrorMessage } from '../utils/apiError'

export function useChat(conversationId = null, onNewConversation) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [currentSteps, setCurrentSteps] = useState([])
  const queryClient = useQueryClient()
  const activeConvId = useRef(conversationId)
  const lastSentRef = useRef('')
  const abortRef = useRef(null)
  const pendingResendRef = useRef('')

  const STREAM_TIMEOUT_MS = 120000
  const STREAM_TIMEOUT_MSG = 'Sorry, the request took too long. Please try again.'

  useEffect(() => {
    setMessages([])
    setStreaming(false)
    pendingResendRef.current = ''
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
    const loadedMsgs = conversationData.messages.map((m) => {
      const meta = m.metadata || {}
      return {
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at,
        questionnaire: meta.questionnaire_options
          ? { options: meta.questionnaire_options, progress: meta.questionnaire_progress }
          : null,
        suggestions: meta.suggestions || null,
      }
    })
    setMessages(loadedMsgs)
    activeConvId.current = conversationId

    const lastMsg = loadedMsgs[loadedMsgs.length - 1]
    if (loadedMsgs.length > 0 && lastMsg.role === 'user') {
      lastSentRef.current = lastMsg.content
      pendingResendRef.current = lastMsg.content
    }
  }, [conversationData, conversationId])

  const setLastUsage = useTokenStore((s) => s.setLastUsage)

  const startStream = useCallback(
    (message, skipUserMsg = false) => {
      if (!message.trim() || streaming) return
      lastSentRef.current = message
      const msgConvId = activeConvId.current

      if (!skipUserMsg) {
        const userMsg = {
          id: `temp-${Date.now()}`,
          role: 'user',
          content: message,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, userMsg])
      }

      const botMsg = {
        id: `temp-bot-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, botMsg])
      setCurrentSteps([])
      setStreaming(true)

      const { stream, abort } = sendMessageStream(message, msgConvId)
      abortRef.current = abort

      let watchdogAborted = false
      const watchdog = setTimeout(() => {
        watchdogAborted = true
        abortRef.current?.()
      }, STREAM_TIMEOUT_MS)

      ;(async () => {
        let doneEvent = null
        try {
          for await (const event of stream) {
            if (event.type === 'status') {
              setCurrentSteps((prev) => [...prev, { step: event.step, startedAt: Date.now() }])
            } else if (event.type === 'token') {
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant' && last.id === botMsg.id) {
                  updated[updated.length - 1] = { ...last, content: last.content + event.content }
                }
                return updated
              })
            } else if (event.type === 'done') {
              doneEvent = event
            } else if (event.type === 'error') {
              throw new Error(event.content)
            }
          }
        } catch (err) {
          if (err.name === 'AbortError' && !watchdogAborted) return
          const text = watchdogAborted ? STREAM_TIMEOUT_MSG : getApiErrorMessage(err)
          toast.error(text, { id: 'chat-error' })
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant' && last.id === botMsg.id) {
              updated[updated.length - 1] = {
                ...last,
                content: text,
                isError: true,
                originalMessage: lastSentRef.current,
              }
            } else {
              updated.push({
                id: `err-${Date.now()}`,
                role: 'assistant',
                content: text,
                isError: true,
                originalMessage: lastSentRef.current,
                created_at: new Date().toISOString(),
              })
            }
            return updated
          })
          return
        } finally {
          clearTimeout(watchdog)
          setStreaming(false)
          setCurrentSteps([])
          abortRef.current = null
        }

        if (doneEvent) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant' && last.id === botMsg.id) {
              updated[updated.length - 1] = {
                ...last,
                id: doneEvent.message_id,
                questionnaire: doneEvent.questionnaire || last.questionnaire || null,
                suggestions: doneEvent.suggestions || last.suggestions || null,
              }
            }
            return updated
          })
          if (doneEvent.conversation_id !== msgConvId) {
            activeConvId.current = doneEvent.conversation_id
            onNewConversation?.(doneEvent.conversation_id)
          }
          if (doneEvent.usage?.total_tokens > 0) {
            setLastUsage(doneEvent.usage)
            const store = useAuthStore.getState()
            if (store.user) {
              store.setUser({ ...store.user, total_tokens: (store.user.total_tokens || 0) + doneEvent.usage.total_tokens })
            }
          }
          queryClient.invalidateQueries({ queryKey: ['conversations'] })
          queryClient.invalidateQueries({ queryKey: ['commercial-me'] })
          queryClient.invalidateQueries({ queryKey: ['commercial-usage'] })
          if (!useAuthStore.getState().user?.matri_id) {
            queryClient.invalidateQueries({ queryKey: ['me'] })
          }
        }
      })()
    },
    [streaming]
  )

  const send = useCallback((message) => {
    startStream(message, false)
  }, [startStream])

  const abort = useCallback(() => {
    abortRef.current?.()
      setStreaming(false)
      setCurrentSteps([])
      abortRef.current = null
      setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'assistant' && !last.content) {
        return prev.slice(0, -1)
      }
      return prev
    })
  }, [])

  const retry = useCallback(() => {
    if (lastSentRef.current) startStream(lastSentRef.current, false)
  }, [startStream])

  const clearMessages = useCallback(() => {
    setMessages([])
    activeConvId.current = null
  }, [])

  useEffect(() => {
    if (pendingResendRef.current && !streaming) {
      const msg = pendingResendRef.current
      pendingResendRef.current = ''
      startStream(msg, true)
    }
  })

  return {
    messages,
    streaming,
    currentSteps,
    send,
    abort,
    retry,
    clearMessages,
    isLoadingHistory,
    conversationId: activeConvId.current,
  }
}
