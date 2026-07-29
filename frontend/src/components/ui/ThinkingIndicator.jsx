import { useState, useEffect, useRef } from 'react'
import { Check, Brain, Database, Sparkles, MessageSquare } from 'lucide-react'

const STEP_LABELS = {
  analyze: { icon: Brain, label: 'Analyzing your question' },
  search: { icon: Database, label: 'Searching profiles' },
  ai_search: { icon: Sparkles, label: 'AI-powered search' },
  format: { icon: MessageSquare, label: 'Formatting results' },
  think: { icon: Brain, label: 'Thinking' },
}

export default function ThinkingIndicator({ steps }) {
  const [tick, setTick] = useState(0)
  const rafRef = useRef()

  useEffect(() => {
    if (!steps || steps.length === 0) return
    function loop() {
      setTick(t => t + 1)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafRef.current)
  }, [steps.length])

  if (!steps || steps.length === 0) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex gap-1">
          <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    )
  }

  const currentIdx = steps.length - 1

  function elapsed(s, i) {
    if (i < currentIdx) {
      const next = steps[i + 1]
      return ((next.startedAt - s.startedAt) / 1000).toFixed(1)
    }
    return ((Date.now() - s.startedAt) / 1000).toFixed(1)
  }

  return (
    <div className="flex flex-col gap-1.5 py-1">
      {steps.map((s, i) => {
        const config = STEP_LABELS[s.step] || { icon: Brain, label: s.step }
        const Icon = config.icon
        const isCurrent = i === currentIdx
        const isPast = i < currentIdx

        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${isPast ? 'bg-primary-500/20 text-primary-400' : isCurrent ? 'bg-primary-500/30 text-primary-300' : 'bg-surface-700/50 text-surface-500'}`}>
              {isPast ? (
                <Check className="w-3 h-3" />
              ) : (
                <Icon className={`w-3 h-3 ${isCurrent ? 'animate-pulse' : ''}`} />
              )}
            </div>
            <span className={`${isPast ? 'text-primary-400' : isCurrent ? 'text-primary-300' : 'text-surface-500'}`}>
              {config.label}
            </span>
            <span className="text-surface-500 ml-auto tabular-nums">{elapsed(s, i)}s</span>
          </div>
        )
      })}
    </div>
  )
}
