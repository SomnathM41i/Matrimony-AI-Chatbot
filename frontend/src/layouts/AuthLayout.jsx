import { motion } from 'framer-motion'
import { fadeIn } from '../utils/animations'

export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary-950/50 via-surface-950 to-surface-950" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-800/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary-600/5 rounded-full blur-3xl" />

      <motion.div {...fadeIn} className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-600 to-primary-800 mb-4 shadow-glow">
            <span className="text-2xl font-bold text-white">⬡</span>
          </div>
          <h1 className="text-2xl font-bold gradient-text">myvivahai</h1>
          <p className="text-surface-400 text-sm mt-1">AI Matrimony Assistant</p>
        </div>
        {children}
      </motion.div>
    </div>
  )
}
