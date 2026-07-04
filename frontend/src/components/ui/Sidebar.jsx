import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, History, Plus, LogOut, Trash2, Menu, X, Database, Wifi, WifiOff,
} from 'lucide-react'
import { useHistory } from '../../hooks/useHistory'
import { useAuth } from '../../hooks/useAuth'
import { truncate, formatDate } from '../../utils/formatter'
import { useDatabaseStatus } from '../../hooks/useDatabaseStatus'
import { useTokenStore } from '../../app/store'

export default function Sidebar() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { conversations, deleteConversation } = useHistory()
  const { user, logout } = useAuth()
  const { dbConnected, loading } = useDatabaseStatus()
  const lastUsage = useTokenStore((s) => s.lastUsage)

  const currentConvId = location.pathname.match(/\/app\/chat\/(\d+)/)?.[1]

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  const handleNewChat = () => {
    navigate('/app/chat')
    setOpen(false)
  }

  const handleDelete = async (e, id) => {
    e.stopPropagation()
    if (confirm('Delete this conversation?')) {
      await deleteConversation(id)
      if (currentConvId === String(id)) {
        navigate('/app/chat')
      }
    }
  }

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-surface-800">
        <button onClick={handleNewChat} className="btn-primary w-full flex items-center justify-center gap-2">
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      <nav className="flex px-3 pt-3 gap-1 border-b border-surface-800">
        <button
          onClick={() => { navigate('/app/chat'); setOpen(false) }}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
            location.pathname.startsWith('/app/chat')
              ? 'bg-primary-600/20 text-primary-300'
              : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Chat
        </button>
        <button
          onClick={() => { navigate('/app/history'); setOpen(false) }}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
            location.pathname === '/app/history'
              ? 'bg-primary-600/20 text-primary-300'
              : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800'
          }`}
        >
          <History className="w-4 h-4" />
          History
        </button>
      </nav>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => { navigate(`/app/chat/${conv.id}`); setOpen(false) }}
            className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all group flex items-center justify-between ${
              String(conv.id) === currentConvId
                ? 'bg-surface-800 border border-surface-700'
                : 'hover:bg-surface-800/50 border border-transparent'
            }`}
          >
            <div className="min-w-0 flex-1">
              <p className="text-surface-200 truncate">{truncate(conv.title, 35)}</p>
              <p className="text-xs text-surface-500 mt-0.5">{formatDate(conv.updated_at)}</p>
            </div>
            <button
              onClick={(e) => handleDelete(e, conv.id)}
              className="lg:opacity-0 lg:group-hover:opacity-100 p-1 text-surface-500 hover:text-red-400 transition-all"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </button>
        ))}
        {conversations.length === 0 && (
          <p className="text-surface-500 text-sm text-center py-8">No conversations yet</p>
        )}
      </div>

      <div className="px-4 py-2 border-t border-surface-800 space-y-1.5">
        <div className="flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-surface-500" />
          <span className="text-xs text-surface-500">MySQL</span>
          {loading ? (
            <span className="w-2 h-2 rounded-full bg-surface-600 animate-pulse ml-auto" />
          ) : dbConnected ? (
            <span className="flex items-center gap-1 ml-auto text-green-400 text-xs">
              <Wifi className="w-3 h-3" />
              Connected
            </span>
          ) : (
            <span className="flex items-center gap-1 ml-auto text-red-400 text-xs">
              <WifiOff className="w-3 h-3" />
              Disconnected
            </span>
          )}
        </div>
        {lastUsage && (
          <div className="flex items-center gap-2 text-xs text-surface-500">
            <span>Tokens</span>
            <span className="ml-auto font-mono text-primary-400">
              {lastUsage.total_tokens}
            </span>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-surface-800">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-primary-600/30 flex items-center justify-center">
            <span className="text-xs font-semibold text-primary-300">
              {user?.name?.[0]?.toUpperCase() || '?'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-surface-200 truncate">{user?.name || 'User'}</p>
            <p className="text-xs text-surface-500 truncate">{user?.email}</p>
          </div>
        </div>
        <button onClick={logout} className="btn-ghost w-full flex items-center justify-center gap-2 text-sm">
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed top-4 left-4 z-50 lg:hidden btn-ghost p-2"
      >
        {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 25, stiffness: 250 }}
              className="fixed inset-y-0 left-0 z-40 w-[280px] bg-surface-900 border-r border-surface-800 flex flex-col overflow-hidden lg:hidden"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <motion.aside
        animate={{ width: 280 }}
        className="h-full bg-surface-900/90 backdrop-blur-xl border-r border-surface-800 flex-col overflow-hidden hidden lg:flex"
      >
        {sidebarContent}
      </motion.aside>
    </>
  )
}
