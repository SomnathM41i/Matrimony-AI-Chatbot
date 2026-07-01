import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { fadeIn } from '../utils/animations'
import { useAuth } from '../hooks/useAuth'
import { LogIn, UserPlus, Mail, Lock, User } from 'lucide-react'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const { login, register, loginError, registerError, isLoginLoading, isRegisterLoading } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (mode === 'login') {
        await login({ email, password })
      } else {
        await register({ name, email, password })
      }
    } catch {
      // error handled by mutation
    }
  }

  const error = mode === 'login' ? loginError : registerError

  return (
    <AnimatePresence mode="wait">
      <motion.div {...fadeIn} key={mode} className="card p-8">
        <div className="flex mb-6 bg-surface-800 rounded-xl p-1">
          <button
            onClick={() => setMode('login')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === 'login' ? 'bg-primary-600 text-white' : 'text-surface-400 hover:text-surface-200'
            }`}
          >
            <LogIn className="w-4 h-4 inline mr-1.5" />
            Sign In
          </button>
          <button
            onClick={() => setMode('register')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === 'register' ? 'bg-primary-600 text-white' : 'text-surface-400 hover:text-surface-200'
            }`}
          >
            <UserPlus className="w-4 h-4 inline mr-1.5" />
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="label text-sm text-surface-400 mb-1.5 block">Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input pl-10"
                  placeholder="Your name"
                  required
                />
              </div>
            </div>
          )}

          <div>
            <label className="label text-sm text-surface-400 mb-1.5 block">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input pl-10"
                placeholder="you@example.com"
                required
              />
            </div>
          </div>

          <div>
            <label className="label text-sm text-surface-400 mb-1.5 block">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input pl-10"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-lg px-3 py-2">
              {error?.response?.data?.detail || error?.message || 'An error occurred'}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoginLoading || isRegisterLoading}
            className="btn-primary w-full"
          >
            {isLoginLoading || isRegisterLoading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {mode === 'login' ? 'Signing in...' : 'Creating account...'}
              </span>
            ) : mode === 'login' ? (
              'Sign In'
            ) : (
              'Create Account'
            )}
          </button>
        </form>
      </motion.div>
    </AnimatePresence>
  )
}
