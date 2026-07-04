import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { MessageSquare, Trash2, Calendar } from 'lucide-react'
import { useHistory } from '../hooks/useHistory'
import { formatDate, truncate } from '../utils/formatter'
import { stagger, fadeIn } from '../utils/animations'

export default function History() {
  const navigate = useNavigate()
  const { conversations, isLoading, deleteConversation } = useHistory()

  const handleDelete = async (e, id) => {
    e.stopPropagation()
    if (confirm('Delete this conversation?')) {
      await deleteConversation(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold gradient-text mb-6">Chat History</h1>

        {conversations.length === 0 ? (
          <div className="text-center py-16">
            <MessageSquare className="w-12 h-12 text-surface-600 mx-auto mb-4" />
            <p className="text-surface-400">No conversations yet</p>
            <button onClick={() => navigate('/app/chat')} className="btn-primary mt-4">
              Start a new chat
            </button>
          </div>
        ) : (
          <motion.div {...stagger} className="space-y-2">
            {conversations.map((conv) => (
              <motion.div
                key={conv.id}
                {...fadeIn}
                onClick={() => navigate(`/app/chat/${conv.id}`)}
                className="card p-4 flex items-center gap-4 cursor-pointer hover:border-surface-600 transition-all group"
              >
                <div className="w-10 h-10 rounded-xl bg-primary-600/20 flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="w-5 h-5 text-primary-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-surface-200 font-medium truncate">
                    {truncate(conv.title, 60)}
                  </p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-surface-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formatDate(conv.updated_at)}
                    </span>
                    <span className="text-xs text-surface-500">
                      {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="lg:opacity-0 lg:group-hover:opacity-100 p-2 text-surface-500 hover:text-red-400 transition-all rounded-lg hover:bg-red-900/20"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  )
}
