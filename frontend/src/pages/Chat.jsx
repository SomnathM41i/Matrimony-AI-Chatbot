import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Bot, Plus, Send, Square } from 'lucide-react'
import ChatMessage from '../components/ui/ChatMessage'
import EmptyState from '../components/ui/EmptyState'
import { useChat } from '../hooks/useChat'
import { useAuth } from '../hooks/useAuth'

export default function Chat() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const prevMsgLen = useRef(0)

  const { messages, streaming, currentSteps, send, abort, retry, clearMessages } = useChat(
    conversationId || null,
    (newId) => navigate(`/app/chat/${newId}`, { replace: true })
  )

  const needsMatriId = !user?.matri_id
  const userName = user?.name || ''

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior })
  }, [])

  useEffect(() => {
    const len = messages.length
    const el = scrollRef.current
    if (!el) { prevMsgLen.current = len; return }
    const threshold = 100
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    if (len > prevMsgLen.current) {
      scrollToBottom(len === prevMsgLen.current + 1 ? 'smooth' : 'auto')
    } else if (isNearBottom) {
      scrollToBottom('smooth')
    }
    prevMsgLen.current = len
  }, [messages, streaming, scrollToBottom])

  const autosize = useCallback(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [])

  useEffect(() => {
    setInput('')
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.focus()
    }
  }, [conversationId])

  const handleSend = () => {
    if (!input.trim() || streaming) return
    send(input)
    setInput('')
    if (inputRef.current) inputRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    clearMessages()
    navigate('/app/chat')
    inputRef.current?.focus()
  }

  return (
    <div className="h-full flex flex-col bg-surface-950">
      <header className="flex items-center gap-3 h-16 px-4 sm:px-6 border-b border-surface-800 bg-surface-950/90 backdrop-blur-xl z-10 flex-shrink-0">
        <div className="w-12 lg:hidden flex-shrink-0" />
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 border border-primary-400/30 flex items-center justify-center shadow-glow flex-shrink-0">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-surface-100 truncate leading-tight">
              myvivahai AI Assistant
            </p>
            <p className="text-[11px] text-surface-500 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Online
            </p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleNewChat}
            aria-label="नवीन चॅट"
            className="btn-secondary !px-3.5 !py-2 flex items-center gap-1.5 text-xs"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Chat</span>
          </button>
          <div className="hidden md:flex items-center gap-2.5 pl-3 border-l border-surface-800">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-600 to-primary-800 ring-2 ring-primary-500/20 flex items-center justify-center">
              <span className="text-xs font-semibold text-primary-200">
                {userName?.[0]?.toUpperCase() || '?'}
              </span>
            </div>
            <div className="hidden lg:block min-w-0">
              <p className="text-xs text-surface-200 truncate max-w-[150px] leading-tight">
                {userName || 'User'}
              </p>
              <p className="text-[10px] text-surface-500 truncate max-w-[150px]">
                {needsMatriId ? 'Matrimony ID लिंक करा' : user?.matri_id}
              </p>
            </div>
          </div>
        </div>
      </header>

      <div
        ref={scrollRef}
        role="log"
        aria-live="polite"
        aria-busy={streaming}
        className={`flex-1 overflow-y-auto px-4 sm:px-6 py-6 bg-[radial-gradient(ellipse_at_top,rgba(147,51,234,0.05),transparent_55%)] ${
          messages.length === 0 ? 'flex flex-col justify-center' : ''
        }`}
      >
        <div className={messages.length === 0 ? 'w-full' : 'max-w-3xl mx-auto space-y-5'}>
          {messages.length === 0 ? (
            <EmptyState onSend={send} needsMatriId={needsMatriId} />
          ) : (
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onRetry={retry}
                  onSend={send}
                  streaming={streaming}
                  currentSteps={currentSteps}
                  userName={userName}
                />
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>

      <div className="px-4 sm:px-6 pb-4 pt-2 bg-gradient-to-t from-surface-950 via-surface-950/95 to-transparent flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <div
            className={`flex items-end gap-2 bg-surface-900/95 border border-surface-700/80 rounded-2xl p-2 shadow-soft transition-all duration-200 focus-within:border-primary-500/60 focus-within:ring-1 focus-within:ring-primary-500/30 ${
              streaming ? 'opacity-90' : ''
            }`}
          >
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => { setInput(e.target.value); autosize() }}
              onKeyDown={handleKeyDown}
              placeholder="तुमचा प्रश्न विचारा…"
              aria-label="संदेश"
              className="flex-1 bg-transparent border-none outline-none resize-none px-3 py-2.5 max-h-[120px] text-surface-100 placeholder-surface-500 text-sm leading-relaxed"
              disabled={streaming}
            />
            {streaming ? (
              <button
                onClick={abort}
                aria-label="उत्तर थांबवा"
                className="p-3 rounded-xl bg-red-600/20 text-red-300 border border-red-500/40 hover:bg-red-600/30 transition-all duration-200 flex-shrink-0"
                title="थांबवा"
              >
                <Square className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                aria-label="पाठवा"
                className="p-3 rounded-xl bg-gradient-to-r from-primary-600 to-primary-500 text-white hover:shadow-glow hover:from-primary-500 hover:to-primary-400 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                title="पाठवा"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
          <p className="text-center text-[11px] text-surface-600 mt-2" aria-live="polite">
            {streaming
              ? 'उत्तर येत आहे…'
              : 'Enter दाबून पाठवा • Shift + Enter नवी ओळ'}
          </p>
        </div>
      </div>
    </div>
  )
}
