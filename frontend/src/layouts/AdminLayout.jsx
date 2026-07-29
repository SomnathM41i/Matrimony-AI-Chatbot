import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Users, UserRound, MessageSquare, HeartPulse,
  ChevronLeft, Menu, X, LogOut, ArrowLeftFromLine,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useAuthStore } from '../app/store'

const NAV_ITEMS = [
  { path: '/admin', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/admin/users', label: 'App Users', icon: Users },
  { path: '/admin/profiles', label: 'Profiles', icon: UserRound },
  { path: '/admin/conversations', label: 'Chat Monitoring', icon: MessageSquare },
]

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { logout } = useAuth()
  const user = useAuthStore((s) => s.user)

  const isActive = (path) => {
    if (path === '/admin') return location.pathname === '/admin'
    return location.pathname.startsWith(path)
  }

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-surface-800">
        <div className="flex items-center gap-3">
          <HeartPulse className="w-6 h-6 text-primary-400" />
          <div>
            <p className="text-sm font-semibold text-surface-100">Admin Panel</p>
            <p className="text-xs text-surface-500">myvivahai</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.path}
              onClick={() => { navigate(item.path); setSidebarOpen(false) }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                isActive(item.path)
                  ? 'bg-primary-600/15 text-primary-300 border border-primary-500/20'
                  : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800 border border-transparent'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </button>
          )
        })}
      </nav>

      <div className="p-3 border-t border-surface-800 space-y-2">
        <button
          onClick={() => { navigate('/app/chat'); setSidebarOpen(false) }}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-surface-400 hover:text-surface-200 hover:bg-surface-800 transition-all"
        >
          <ArrowLeftFromLine className="w-4 h-4" />
          Back to Chat
        </button>
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-surface-700 flex items-center justify-center">
            <span className="text-xs font-semibold text-surface-300">
              {user?.name?.[0]?.toUpperCase() || 'A'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-surface-300 truncate">{user?.name}</p>
            <p className="text-xs text-surface-500 truncate">Admin</p>
          </div>
          <button onClick={logout} className="btn-ghost p-1.5">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="h-screen w-screen flex bg-surface-950 overflow-hidden">
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 25, stiffness: 250 }}
              className="fixed inset-y-0 left-0 z-40 w-[260px] bg-surface-900 border-r border-surface-800 flex flex-col overflow-hidden lg:hidden"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <motion.aside
        animate={{ width: 260 }}
        className="h-full bg-surface-900/90 backdrop-blur-xl border-r border-surface-800 flex-col overflow-hidden hidden lg:flex"
      >
        {sidebarContent}
      </motion.aside>

      {/* Main content */}
      <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-surface-800 bg-surface-950/80 backdrop-blur-xl shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden btn-ghost p-1.5"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <ChevronLeft className="w-4 h-4 text-surface-500 hidden lg:block" />
          <span className="text-xs text-surface-500 capitalize">
            {location.pathname === '/admin' ? 'Dashboard' : location.pathname.split('/').pop()?.replace(/-/g, ' ')}
          </span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
