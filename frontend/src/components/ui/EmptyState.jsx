import { useNavigate } from 'react-router-dom'
import { Bot, Heart, Sparkles } from 'lucide-react'

export default function EmptyState() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center text-center px-6">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-600/30 to-primary-800/30 border border-primary-600/30 flex items-center justify-center mb-6">
        <Bot className="w-8 h-8 text-primary-400" />
      </div>
      <h2 className="text-xl font-semibold gradient-text mb-2">
        myvivahai — Matrimony AI Assistant
      </h2>
      <p className="text-surface-400 text-sm max-w-md leading-relaxed">
        Ask me anything about members, pricing plans, success stories, or general
        matrimony questions. I can query the database and provide real-time answers.
      </p>

      <button
        onClick={() => navigate('/app/partner-preferences')}
        className="mt-6 w-full max-w-md group relative overflow-hidden rounded-xl bg-gradient-to-r from-pink-600/20 via-rose-600/20 to-pink-600/20 border border-pink-500/30 hover:border-pink-400/50 px-5 py-4 transition-all duration-300"
      >
        <div className="absolute inset-0 bg-gradient-to-r from-pink-500/5 to-rose-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500/30 to-rose-500/30 border border-pink-500/30 flex items-center justify-center flex-shrink-0">
            <Heart className="w-5 h-5 text-pink-400" />
          </div>
          <div className="text-left flex-1 min-w-0">
            <p className="text-sm font-semibold text-pink-200 flex items-center gap-2">
              Your Partner Preferences
              <Sparkles className="w-3.5 h-3.5 text-yellow-400" />
            </p>
            <p className="text-xs text-surface-400 mt-0.5">
              Set preferences & see your perfect partner list
            </p>
          </div>
        </div>
      </button>

      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-md">
        {[
          'Show me 5 female profiles in Pune',
          'What are your membership plans?',
          'Tell me about refund policy',
          'Show success stories',
        ].map((text) => (
          <div
            key={text}
            className="text-xs text-surface-400 bg-surface-800/50 border border-surface-700/50 rounded-xl px-3 py-2.5 text-left hover:bg-surface-700/50 hover:border-surface-600/50 transition-colors cursor-default"
          >
            {text}
          </div>
        ))}
      </div>
    </div>
  )
}