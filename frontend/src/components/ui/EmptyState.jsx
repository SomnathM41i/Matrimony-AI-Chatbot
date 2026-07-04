import { Bot } from 'lucide-react'

export default function EmptyState() {
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
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-md">
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
