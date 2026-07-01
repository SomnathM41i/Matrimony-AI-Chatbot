import { motion } from 'framer-motion'
import { fadeIn } from '../../utils/animations'
import { Bot, User } from 'lucide-react'

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const isError = message.content.startsWith('Sorry, I encountered')

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
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
    </motion.div>
  )
}
