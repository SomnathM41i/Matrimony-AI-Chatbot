import { Heart, Sparkles, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function PartnerPreferences() {
  const navigate = useNavigate()

  return (
    <div className="h-full flex flex-col bg-surface-950 items-center justify-center px-6">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-pink-500/30 to-rose-600/30 border border-pink-500/30 flex items-center justify-center mb-6">
        <Heart className="w-10 h-10 text-pink-400" />
      </div>
      <div className="relative">
        <Sparkles className="absolute -top-3 -right-3 w-5 h-5 text-yellow-400 animate-pulse" />
        <h2 className="text-2xl font-bold gradient-text mb-2">
          Partner Preferences
        </h2>
      </div>
      <p className="text-surface-400 text-sm max-w-md text-center leading-relaxed mb-8">
        Set your preferences for age, education, location, caste, and more.
        We'll find your perfect match from our database.
      </p>
      <div className="bg-surface-900/50 border border-surface-700/50 rounded-2xl px-8 py-5 flex items-center gap-3">
        <Sparkles className="w-5 h-5 text-primary-400" />
        <span className="text-surface-300 text-sm font-medium">Coming Soon</span>
      </div>
      <button
        onClick={() => navigate('/app/chat')}
        className="mt-8 text-sm text-surface-500 hover:text-surface-300 transition-colors flex items-center gap-2"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Chat
      </button>
    </div>
  )
}