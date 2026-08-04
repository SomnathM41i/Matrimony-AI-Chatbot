import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, Bot, Heart, Search, Sparkles } from 'lucide-react'

const SUGGESTIONS_LINKED = [
  'माझ्या जोडीदाराच्या पसंती सांगा',
  'पुण्यातील 5 मुलींची प्रोफाइल दाखवा',
  'मुंबईतील मुलांची प्रोफाइल दाखवा',
  'success stories दाखवा',
]

const SUGGESTIONS_NO_ID = [
  'मला Matri ID जोडायचा आहे',
  'पुण्यातील 5 मुलींची प्रोफाइल दाखवा',
  'माझ्या जोडीदाराच्या पसंती सांगा',
  'success stories दाखवा',
]

export default function EmptyState({ onSend, needsMatriId = false }) {
  const navigate = useNavigate()
  const [idInput, setIdInput] = useState('')
  const suggestions = needsMatriId ? SUGGESTIONS_NO_ID : SUGGESTIONS_LINKED

  const handleIdSubmit = (e) => {
    e.preventDefault()
    const value = idInput.trim()
    if (!value) return
    onSend?.(value)
    setIdInput('')
  }

  return (
    <div className="flex flex-col items-center text-center px-4 py-4 w-full max-w-xl mx-auto">
      <div className="relative mb-6">
        <div className="absolute inset-0 bg-primary-600/40 blur-3xl rounded-full opacity-50" />
        <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 border border-primary-400/30 flex items-center justify-center shadow-glow">
          <Bot className="w-8 h-8 text-white" />
        </div>
      </div>

      <h2 className="text-2xl font-semibold gradient-text mb-3">
        {needsMatriId ? 'नमस्कार, आपले स्वागत आहे! 🙏' : 'तुम्ही काय शोधत आहात?'}
      </h2>
      <p className="text-surface-400 text-sm max-w-lg leading-relaxed">
        {needsMatriId
          ? 'तुमचा matrimony ID शेअर करा, जेणेकरून मी तुमच्या partner expectations नुसार तुमचा perfect partner शोधून देऊ शकेन.'
          : 'सदस्य, प्रोफाइल, success stories किंवा matrimony संबंधित कोणताही प्रश्न मला विचारा. मी डेटाबेसमधून माहिती शोधून real-time उत्तर देऊ शकतो.'}
      </p>

      {needsMatriId && (
        <form onSubmit={handleIdSubmit} className="mt-7 w-full max-w-md">
          <label className="text-xs text-surface-400 mb-2 block text-left">
            तुमचा Matrimony ID टाका — मी तुमचा perfect partner शोधून देईन
          </label>
          <div className="flex gap-2.5">
            <div className="relative flex-1">
              <input
                type="text"
                value={idInput}
                onChange={(e) => setIdInput(e.target.value.toUpperCase())}
                placeholder="उदा. ES92669"
                className="input flex-1 !pr-11 uppercase tracking-wider"
                maxLength={15}
                autoComplete="off"
                spellCheck="false"
              />
              <Search className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500 pointer-events-none" aria-hidden="true" />
            </div>
            <button type="submit" disabled={!idInput.trim()} className="btn-primary flex items-center gap-2">
              शोधा
            </button>
          </div>
        </form>
      )}

      <button
        onClick={() => navigate('/app/profile')}
        className="mt-7 w-full max-w-md group relative overflow-hidden rounded-xl bg-gradient-to-r from-pink-600/20 via-rose-600/20 to-pink-600/20 border border-pink-500/30 hover:border-pink-400/50 px-5 py-4 transition-all duration-300"
      >
        <div className="absolute inset-0 bg-gradient-to-r from-pink-500/5 to-rose-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500/30 to-rose-500/30 border border-pink-500/30 flex items-center justify-center flex-shrink-0">
            <Heart className="w-5 h-5 text-pink-400" />
          </div>
          <div className="text-left flex-1 min-w-0">
            <p className="text-sm font-semibold text-pink-200 flex items-center gap-2">
              तुमच्या जोडीदाराच्या पसंती
              <Sparkles className="w-3.5 h-3.5 text-yellow-400" />
            </p>
            <p className="text-xs text-surface-400 mt-0.5">
              पसंती सेट करा आणि तुमचा perfect partner शोधा
            </p>
          </div>
          <ArrowUpRight className="w-4 h-4 text-pink-400/50 group-hover:text-pink-300 transition-colors flex-shrink-0" />
        </div>
      </button>

      <div className="mt-8 w-full max-w-md">
        <p className="text-[11px] uppercase tracking-widest text-surface-500 mb-3">
          काही उदाहरणे विचारून पहा
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {suggestions.map((text) => (
            <button
              key={text}
              onClick={() => onSend?.(text)}
              className="group text-xs text-surface-300 bg-surface-800/60 border border-surface-700/60 rounded-xl px-3.5 py-3 text-left hover:bg-surface-800 hover:border-primary-500/40 hover:text-surface-100 transition-all duration-200 flex items-center justify-between gap-2"
            >
              <span className="leading-snug">{text}</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-surface-600 group-hover:text-primary-400 transition-colors flex-shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
