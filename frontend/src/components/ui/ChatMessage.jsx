import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { fadeIn } from '../../utils/animations'
import { Bot, User, CameraOff } from 'lucide-react'

function ProfileCard({ src, alt, details }) {
  const [imgError, setImgError] = useState(false)

  return (
    <div className="group flex flex-col sm:flex-row items-start gap-4 bg-gradient-to-br from-surface-900 to-surface-950 border border-surface-700/60 hover:border-primary-500/40 rounded-2xl p-4 my-3 shadow-soft transition-all duration-200 hover:shadow-glow">
      <div className="relative flex-shrink-0 self-center sm:self-start">
        <div className="absolute -inset-0.5 bg-gradient-to-br from-primary-500/40 to-primary-700/40 rounded-xl blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        {imgError ? (
          <div className="relative w-32 h-32 sm:w-48 sm:h-48 rounded-xl border-2 border-dashed border-surface-600 bg-surface-800/50 flex flex-col items-center justify-center text-surface-500 gap-1">
            <CameraOff className="w-6 h-6" />
            <span className="text-[10px]">No photo</span>
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
  const pattern = /(?:^|\n)\s*(?:\d+[\.\)]\s*)?(!\[([^\]]*)\]\(([^)]+)\))\s*([^\n]*)/g
  let lastIndex = 0
  let match

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > lastIndex) {
      const between = content.slice(lastIndex, match.index).trim()
      if (between) parts.push({ type: 'text', content: between })
    }
    parts.push({ type: 'card', src: match[3], alt: match[2], details: match[4].trim() })
    lastIndex = pattern.lastIndex
  }

  if (lastIndex < content.length) {
    const rest = content.slice(lastIndex).trim()
    if (rest) parts.push({ type: 'text', content: rest })
  }

  return parts.length > 0 ? parts : [{ type: 'text', content }]
}

export default function ChatMessage({ message, onRetry }) {
  const isUser = message.role === 'user'
  const isError = message.isError || message.content.startsWith("Sorry, I couldn't process")
    || message.content.startsWith('Sorry, the assistant is receiving')
    || message.content.startsWith('Sorry, the request took too long')
    || message.content.startsWith("Sorry, I couldn't understand")

  const parts = useMemo(() => {
    if (isUser) return null
    return splitContent(message.content)
  }, [message.content, isUser])

  const hasCards = useMemo(() => parts?.some(p => p.type === 'card'), [parts])

  return (
    <motion.div
      {...fadeIn}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isUser ? 'bg-primary-600' : 'bg-surface-700'}`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-primary-400" />
        )}
      </div>
      <div
        className={`max-w-[80%] px-4 py-3 rounded-2xl ${
          isUser
            ? 'bg-primary-600/20 text-primary-100 border border-primary-600/30'
            : isError
            ? 'bg-red-900/20 text-red-300 border border-red-800/30'
            : 'bg-surface-800/80 text-surface-200 border border-surface-700/50'
        }`}
      >
        {!hasCards ? (
          <>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
            {isError && onRetry && (
              <button onClick={onRetry} className="mt-2 text-xs text-primary-400 hover:text-primary-300 underline">
                Retry
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
                part.content && <p key={i} className="whitespace-pre-wrap">{part.content}</p>
              )
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}
