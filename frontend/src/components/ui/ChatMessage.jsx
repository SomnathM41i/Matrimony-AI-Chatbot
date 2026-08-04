import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { fadeIn } from '../../utils/animations'
import { Bot, CameraOff, RotateCcw, User } from 'lucide-react'
import ThinkingIndicator from './ThinkingIndicator'
import { formatTime } from '../../utils/formatter'

function ProfileCard({ src, alt, details }) {
  const [imgError, setImgError] = useState(false)

  return (
    <div className="group flex flex-col sm:flex-row items-start gap-4 bg-gradient-to-br from-surface-900 to-surface-950 border border-surface-700/60 hover:border-primary-500/40 rounded-2xl p-4 my-3 shadow-soft transition-all duration-200 hover:shadow-glow">
      <div className="relative flex-shrink-0 self-center sm:self-start">
        <div className="absolute -inset-0.5 bg-gradient-to-br from-primary-500/40 to-primary-700/40 rounded-xl blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        {imgError ? (
          <div className="relative w-32 h-32 sm:w-48 sm:h-48 rounded-xl border-2 border-dashed border-surface-600 bg-surface-800/50 flex flex-col items-center justify-center text-surface-500 gap-1">
            <CameraOff className="w-6 h-6" aria-hidden="true" />
            <span className="text-[10px]">फोटो नाही</span>
          </div>
        ) : (
          <img
            src={src}
            alt={alt || ''}
            className="relative w-32 h-32 sm:w-48 sm:h-48 rounded-xl object-cover border-2 border-primary-500/20"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        )}
      </div>
      <div className="min-w-0 flex-1 text-center sm:text-left">
        <h4 className="text-base font-semibold text-surface-100 truncate">{alt}</h4>
        <p className="text-sm text-surface-300 mt-1.5 leading-relaxed whitespace-pre-wrap">{details}</p>
      </div>
    </div>
  )
}

function ProfileCardSimple({ src, alt }) {
  return (
    <div className="group flex flex-col sm:flex-row items-start gap-4 bg-gradient-to-br from-surface-900 to-surface-950 border border-surface-700/60 hover:border-primary-500/40 rounded-2xl p-4 my-3 shadow-soft transition-all duration-200">
      <div className="relative flex-shrink-0 self-center sm:self-start">
        <div className="absolute -inset-0.5 bg-gradient-to-br from-primary-500/40 to-primary-700/40 rounded-xl blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <img
          src={src}
          alt={alt || ''}
          className="relative w-32 h-32 sm:w-48 sm:h-48 rounded-xl object-cover border-2 border-primary-500/20"
          loading="lazy"
        />
      </div>
      <div className="min-w-0 flex-1 text-center sm:text-left">
        <h4 className="text-base font-semibold text-surface-100">{alt || 'Profile'}</h4>
      </div>
    </div>
  )
}

function splitContent(content) {
  const parts = []
  const cardInfo = []

  const imgRe = /(?:^|\n)\s*(?:\d+[\.\)]\s*)?(!\[([^\]]*)\]\(([^)]+)\))\s*([^\n]*)/g
  let m
  while ((m = imgRe.exec(content)) !== null) {
    cardInfo.push({ index: m.index, end: imgRe.lastIndex, src: m[3], alt: m[2], details: m[4].trim() })
  }

  const photoRe = /(?:Photo\s*URL:\s*)?\[Photo\s*URL\]\(([^)]+)\)/gi
  while ((m = photoRe.exec(content)) !== null) {
    if (cardInfo.some(c => c.index <= m.index && c.end >= m.index + m[0].length)) continue
    const before = content.slice(0, m.index)
    const nameMatch = before.match(/\*\*([^*]+)\*\*\s*$/m)
    const alt = nameMatch ? nameMatch[1].trim() : 'Profile'
    const lineStart = content.lastIndexOf('\n', m.index) + 1
    const afterMatch = content.slice(m.index + m[0].length).match(/[^\n]*/)
    const details = (afterMatch ? afterMatch[0].trim() : '')
    cardInfo.push({ index: lineStart, end: m.index + m[0].length + (afterMatch ? afterMatch[0].length : 0), src: m[1], alt, details })
  }

  cardInfo.sort((a, b) => a.index - b.index)

  let lastIdx = 0
  for (const c of cardInfo) {
    if (c.index > lastIdx) {
      const between = content.slice(lastIdx, c.index).trim()
      if (between) parts.push({ type: 'text', content: between })
    }
    parts.push({ type: 'card', src: c.src, alt: c.alt, details: c.details })
    lastIdx = c.end
  }
  if (lastIdx < content.length) {
    const rest = content.slice(lastIdx).trim()
    if (rest) parts.push({ type: 'text', content: rest })
  }

  return parts.length > 0 ? parts : [{ type: 'text', content }]
}

function Avatar({ isUser, userName }) {
  if (isUser) {
    return (
      <div className="flex-shrink-0 w-9 h-9 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 ring-2 ring-primary-400/30 flex items-center justify-center shadow-soft mt-0.5" aria-hidden="true">
        {userName?.[0] ? (
          <span className="text-sm font-semibold text-white">{userName[0].toUpperCase()}</span>
        ) : (
          <User className="w-4 h-4 text-white" />
        )}
      </div>
    )
  }
  return (
    <div className="flex-shrink-0 w-9 h-9 rounded-full bg-gradient-to-br from-surface-700 to-surface-800 ring-2 ring-surface-600/40 flex items-center justify-center shadow-soft mt-0.5" aria-hidden="true">
      <Bot className="w-5 h-5 text-primary-300" />
    </div>
  )
}

export default function ChatMessage({ message, onRetry, onSend, streaming, currentSteps, userName }) {
  const isUser = message.role === 'user'
  const content = typeof message.content === 'string'
    ? message.content
    : message.content?.message || ''
  const isStreaming = streaming && !isUser && !content
  const isError = message.isError || content.startsWith("Sorry, I couldn't process")
    || content.startsWith('Sorry, the assistant is receiving')
    || content.startsWith('Sorry, the request took too long')
    || content.startsWith("Sorry, I couldn't understand")

  const parts = useMemo(() => {
    if (isUser || isStreaming) return null
    return splitContent(content)
  }, [content, isUser, isStreaming])

  const hasCards = useMemo(() => parts?.some(p => p.type === 'card'), [parts])
  const time = useMemo(() => formatTime(message.created_at), [message.created_at])
  const options = message.questionnaire?.options || []
  const suggestions = message.suggestions || []

  return (
    <motion.div
      {...fadeIn}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <Avatar isUser={isUser} userName={userName} />
      <div className={`flex flex-col min-w-0 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`max-w-full sm:max-w-[520px] px-4 py-3 text-sm leading-relaxed shadow-soft ${
            isUser
              ? 'bg-gradient-to-br from-primary-600 to-primary-700 text-white rounded-2xl rounded-tr-sm'
              : isError
              ? 'bg-red-950/50 text-red-300 border border-red-900/50 rounded-2xl rounded-tl-sm'
              : isStreaming
              ? 'bg-surface-800/50 text-surface-300 border border-surface-700/40 rounded-2xl rounded-tl-sm'
              : 'bg-surface-800/90 text-surface-200 border border-surface-700/60 rounded-2xl rounded-tl-sm'
          }`}
        >
          {isStreaming ? (
            <ThinkingIndicator steps={currentSteps} />
          ) : !hasCards ? (
            <>
              <p className="whitespace-pre-wrap break-words">{content}</p>
              {isError && onRetry && (
                <button
                  onClick={onRetry}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs text-primary-300 hover:text-primary-200 underline underline-offset-2"
                >
                  <RotateCcw className="w-3 h-3" />
                  पुन्हा प्रयत्न करा
                </button>
              )}
            </>
          ) : (
            <div className="space-y-1 text-sm leading-relaxed">
              {parts.map((part, i) =>
                part.type === 'card' ? (
                  part.details ? (
                    <ProfileCard key={i} src={part.src} alt={part.alt} details={part.details} />
                  ) : (
                    <ProfileCardSimple key={i} src={part.src} alt={part.alt} />
                  )
                ) : (
                  part.content && <p key={i} className="whitespace-pre-wrap break-words">{part.content}</p>
                )
              )}
            </div>
          )}
          {!isUser && !isError && !isStreaming && options.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {options.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => onSend?.(opt.label)}
                  disabled={streaming}
                  className="inline-flex items-center rounded-full border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 transition-all duration-200 hover:border-primary-400/60 hover:bg-primary-500/20 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
          {!isUser && !isError && !isStreaming && suggestions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="सुचना">
              {suggestions.map((text) => (
                <button
                  key={text}
                  onClick={() => onSend?.(text)}
                  disabled={streaming}
                  className="inline-flex items-center rounded-full border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 transition-all duration-200 hover:border-primary-400/60 hover:bg-primary-500/20 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {text}
                </button>
              ))}
            </div>
          )}
        </div>
        {time && (
          <span className={`text-[10px] text-surface-600 mt-1 px-1 ${isUser ? 'text-right' : 'text-left'}`}>
            {time}
          </span>
        )}
      </div>
    </motion.div>
  )
}
