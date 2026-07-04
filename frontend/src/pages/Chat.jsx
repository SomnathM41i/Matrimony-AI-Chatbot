import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Send } from 'lucide-react'
import ChatMessage from '../components/ui/ChatMessage'
import TypingIndicator from '../components/ui/TypingIndicator'
import EmptyState from '../components/ui/EmptyState'
import { useChat } from '../hooks/useChat'

export default function Chat() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const prevMsgLen = useRef(0)

  const { messages, streaming, send, retry, isLoadingHistory } = useChat(
    conversationId || null,
    (newId) => navigate(`/app/chat/${newId}`, { replace: true })
  )

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
  }, [])

  useEffect(() => {
    const len = messages.length
    const el = messagesEndRef.current?.parentElement
    if (!el) { scrollToBottom('auto'); prevMsgLen.current = len; return }
    const threshold = 100
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    if (len > prevMsgLen.current) {
      scrollToBottom(len === prevMsgLen.current + 1 ? 'smooth' : 'auto')
    } else if (isNearBottom) {
      scrollToBottom('smooth')
    }
    prevMsgLen.current = len
  }, [messages, streaming, scrollToBottom])

  useEffect(() => {
    setInput('')
    inputRef.current?.focus()
  }, [conversationId])

  const handleSend = () => {
    if (!input.trim() || streaming) return
    send(input)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col bg-surface-950">
      <div className={`flex-1 overflow-y-auto px-4 py-6 ${messages.length === 0 ? 'flex flex-col justify-center' : 'space-y-4'}`}>
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <AnimatePresence>
            {messages.map((msg) => (
              <ChatMessage key={msg.id + '-' + (msg.content || '').slice(0, 20)} message={msg} onRetry={retry} />
            ))}
          </AnimatePresence>
        )}

        {streaming && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-surface-800 p-4">
        <div className="max-w-4xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about members, plans, or anything..."
            className="input flex-1"
            disabled={streaming}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="btn-primary px-4"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
