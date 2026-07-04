import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Bot, MessageSquare, Database, Search, Shield, Zap,
  ArrowRight, Sparkles, ChevronRight, Heart, Users,
  Globe, Clock, BarChart3, LayoutDashboard,
} from 'lucide-react'
import { useAuthStore } from '../app/store'

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.6 },
}

const stagger = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-40px' },
  transition: { staggerChildren: 0.1, duration: 0.5 },
}

export default function Landing() {
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.token)
  const isLoggedIn = !!token

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100 overflow-hidden">

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-surface-950/80 backdrop-blur-xl border-b border-surface-800/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center shadow-glow">
              <span className="text-sm font-bold text-white">m</span>
            </div>
            <span className="font-semibold text-lg gradient-text">myvivahai</span>
          </div>
          <div className="flex items-center gap-3">
            {isLoggedIn ? (
              <button
                onClick={() => navigate('/app/chat')}
                className="btn-primary text-sm inline-flex items-center gap-1.5 whitespace-nowrap"
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                Dashboard
              </button>
            ) : (
              <>
                <button
                  onClick={() => navigate('/login')}
                  className="btn-ghost text-sm"
                >
                  Sign In
                </button>
                <button
                  onClick={() => navigate('/login')}
                  className="btn-primary text-sm inline-flex items-center gap-1.5 whitespace-nowrap"
                >
                  Get Started
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center pt-20 pb-24 px-4 sm:px-6">
        <div className="absolute inset-0 bg-gradient-to-b from-primary-950/20 via-surface-950 to-surface-950 pointer-events-none" />
        <div className="absolute top-1/4 left-1/3 w-[600px] h-[600px] bg-primary-800/10 rounded-full blur-[150px] pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-primary-600/5 rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-primary-700/5 rounded-full blur-[80px] pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative w-full">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary-600/10 border border-primary-600/20 text-primary-300 text-sm mb-8"
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered Matrimony Assistant
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-bold leading-[1.1] mb-6"
          >
            <span className="text-surface-100">Your Intelligent</span>{' '}
            <span className="gradient-text">Matrimony</span>
            <br />
            <span className="text-surface-100">Matchmaker</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg sm:text-xl text-surface-400 max-w-2xl mx-auto mb-10 leading-relaxed"
          >
            Instantly search member profiles, browse membership plans, explore success stories,
            and get answers — all through natural conversation with AI.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <button
              onClick={() => navigate(isLoggedIn ? '/app/chat' : '/login')}
              className="btn-primary text-base px-8 py-3.5 inline-flex items-center justify-center gap-2 whitespace-nowrap w-full sm:w-auto shadow-glow hover:shadow-[0_0_25px_rgba(168,85,247,0.6)] transition-shadow duration-300"
            >
              {isLoggedIn ? 'Go to Dashboard' : 'Start Free'}
              <ArrowRight className="w-4 h-4" />
            </button>
            {!isLoggedIn && (
              <button
                onClick={() => navigate('/login')}
                className="btn-secondary text-base px-8 py-3.5 inline-flex items-center justify-center gap-2 whitespace-nowrap w-full sm:w-auto"
              >
                <MessageSquare className="w-4 h-4" />
                Learn More
              </button>
            )}
          </motion.div>

          {/* Hero Stats */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto"
          >
            {[
              { icon: Users, value: '10K+', label: 'Active Profiles' },
              { icon: Zap, value: 'AI', label: 'Powered Search' },
              { icon: Globe, value: 'Real-time', label: 'Database Queries' },
              { icon: Clock, value: '24/7', label: 'Availability' },
            ].map((s) => (
              <div key={s.label} className="text-center group">
                <div className="w-12 h-12 rounded-xl bg-primary-600/10 border border-primary-600/20 flex items-center justify-center mx-auto mb-3 group-hover:bg-primary-600/20 group-hover:border-primary-600/40 transition-all duration-300">
                  <s.icon className="w-5 h-5 text-primary-400" />
                </div>
                <div className="text-xl sm:text-2xl font-bold text-primary-400">{s.value}</div>
                <div className="text-xs text-surface-500 mt-1">{s.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-4 sm:px-6 border-t border-surface-800/50 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-surface-900/20 to-surface-950 pointer-events-none" />
        <div className="max-w-6xl mx-auto relative">
          <motion.div {...fadeUp} className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-600/10 border border-primary-600/20 text-primary-300 text-xs mb-4">
              <Sparkles className="w-3 h-3" />
              Features
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything You Need
            </h2>
            <p className="text-surface-400 text-lg max-w-xl mx-auto">
              Powerful tools to find matches, manage memberships, and grow your matrimony platform.
            </p>
          </motion.div>

          <motion.div {...stagger} className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Search,
                title: 'Smart Profile Search',
                description: 'Search member profiles by age, city, religion, caste, and more using natural language queries.',
              },
              {
                icon: Bot,
                title: 'AI Conversations',
                description: 'Chat naturally with AI to find matches, explore plans, and get instant answers to any question.',
              },
              {
                icon: Database,
                title: 'Real-time Database',
                description: 'Queries your live database instantly — no manual searching through forms or filters.',
              },
              {
                icon: Shield,
                title: 'Secure & Private',
                description: 'Your data is protected. All queries are authenticated and sensitive fields are never exposed.',
              },
              {
                icon: Zap,
                title: 'Instant Results',
                description: 'Get responses in seconds. AI generates SQL, queries the database, and formats results instantly.',
              },
              {
                icon: Heart,
                title: 'Success Stories',
                description: 'Browse and share success stories. Let happy couples inspire new connections on your platform.',
              },
            ].map((feat) => (
              <motion.div
                key={feat.title}
                {...stagger}
                className="card p-6 hover:border-primary-500/40 hover:shadow-glow transition-all duration-300 group relative overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-primary-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <div className="w-11 h-11 rounded-xl bg-primary-600/15 flex items-center justify-center mb-4 group-hover:bg-primary-600/25 group-hover:scale-110 transition-all duration-300">
                  <feat.icon className="w-5 h-5 text-primary-400" />
                </div>
                <h3 className="text-lg font-semibold text-surface-100 mb-2 group-hover:text-primary-300 transition-colors duration-300">{feat.title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed">{feat.description}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="py-16 px-4 sm:px-6 bg-surface-900/40 border-t border-surface-800/50">
        <div className="max-w-5xl mx-auto">
          <motion.div {...stagger} className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: '10,000+', label: 'Member Profiles' },
              { value: '50+', label: 'Cities Covered' },
              { value: '1,000+', label: 'Success Stories' },
              { value: '99.9%', label: 'Uptime' },
            ].map((stat) => (
              <motion.div key={stat.label} {...stagger} className="text-center">
                <div className="text-2xl sm:text-3xl font-bold gradient-text mb-1">{stat.value}</div>
                <div className="text-sm text-surface-500">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* How it Works */}
      <section className="py-24 px-4 sm:px-6 border-t border-surface-800/50">
        <div className="max-w-5xl mx-auto">
          <motion.div {...fadeUp} className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-600/10 border border-primary-600/20 text-primary-300 text-xs mb-4">
              <BarChart3 className="w-3 h-3" />
              Process
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">How It Works</h2>
            <p className="text-surface-400 text-lg max-w-xl mx-auto">
              Three simple steps to find what you're looking for.
            </p>
          </motion.div>

          <div className="grid sm:grid-cols-3 gap-8 relative">
            {/* Connector line */}
            <div className="hidden sm:block absolute top-14 left-[calc(16.67%+2rem)] right-[calc(16.67%+2rem)] h-0.5 bg-gradient-to-r from-primary-600/30 via-primary-500/50 to-primary-600/30 pointer-events-none" />

            {[
              {
                step: '01',
                title: 'Ask Naturally',
                description: 'Type your question in plain English — "Show me female profiles in Pune" or "Tell me about membership plans".',
                icon: MessageSquare,
              },
              {
                step: '02',
                title: 'AI Processes It',
                description: 'Our AI understands your intent, generates the right database query, and fetches accurate results in real time.',
                icon: Bot,
              },
              {
                step: '03',
                title: 'Get Your Answer',
                description: 'Results are formatted into a clear, conversational response — complete with profile photos and key details.',
                icon: Heart,
              },
            ].map((item) => (
              <motion.div
                key={item.step}
                {...fadeUp}
                className="text-center relative"
              >
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-600/20 to-primary-800/20 border border-primary-600/30 flex items-center justify-center mx-auto mb-5 relative z-10 backdrop-blur-sm">
                  <item.icon className="w-7 h-7 text-primary-400" />
                </div>
                <div className="w-8 h-8 rounded-full bg-primary-600 text-white text-sm font-bold flex items-center justify-center mx-auto mb-4 -mt-10 relative z-20 border-2 border-surface-950">
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold text-surface-100 mb-2">{item.title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed max-w-xs mx-auto">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Examples */}
      <section className="py-24 px-4 sm:px-6 bg-surface-900/30 border-t border-surface-800/50">
        <div className="max-w-5xl mx-auto">
          <motion.div {...fadeUp} className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-600/10 border border-primary-600/20 text-primary-300 text-xs mb-4">
              <Sparkles className="w-3 h-3" />
              Try It
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">Try These Questions</h2>
            <p className="text-surface-400 text-lg max-w-xl mx-auto">
              See what myvivahai can do. Just type any of these into the chat.
            </p>
          </motion.div>

          <motion.div {...stagger} className="grid sm:grid-cols-2 gap-4 max-w-2xl mx-auto">
            {[
              { q: 'Show me 5 female profiles in Pune', icon: Users },
              { q: 'What are your membership plans?', icon: BarChart3 },
              { q: 'Tell me about the refund policy', icon: Shield },
              { q: 'Show me success stories', icon: Heart },
              { q: 'List active male members in Mumbai', icon: Search },
              { q: 'Find profiles with age between 25-30', icon: Users },
            ].map(({ q, icon: Icon }) => (
              <motion.div
                key={q}
                {...stagger}
                onClick={() => navigate(isLoggedIn ? '/app/chat' : '/login')}
                className="card px-5 py-4 flex items-center gap-3 cursor-pointer hover:border-primary-500/30 hover:bg-surface-800/50 hover:shadow-glow transition-all duration-300 group"
              >
                <div className="w-9 h-9 rounded-lg bg-primary-600/10 flex items-center justify-center flex-shrink-0 group-hover:bg-primary-600/20 transition-colors">
                  <Icon className="w-4 h-4 text-primary-400" />
                </div>
                <span className="text-sm text-surface-300 group-hover:text-surface-100 transition-colors flex-1">{q}</span>
                <ChevronRight className="w-4 h-4 text-surface-600 group-hover:text-primary-400 transition-colors flex-shrink-0" />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4 sm:px-6 border-t border-surface-800/50 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-950/20 via-surface-950 to-surface-950 pointer-events-none" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-primary-700/10 rounded-full blur-[120px] pointer-events-none" />
        <motion.div {...fadeUp} className="max-w-2xl mx-auto text-center relative">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-600/20 to-primary-800/20 border border-primary-600/30 flex items-center justify-center mx-auto mb-6 backdrop-blur-sm">
            <Bot className="w-10 h-10 text-primary-400" />
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4 leading-tight">
            Ready to{' '}
            <span className="gradient-text">Transform</span>{' '}
            Your Matrimony Platform?
          </h2>
          <p className="text-surface-400 text-lg mb-8 max-w-lg mx-auto leading-relaxed">
            Sign in to your account and start finding matches with the power of AI.
          </p>
          <button
            onClick={() => navigate(isLoggedIn ? '/app/chat' : '/login')}
            className="btn-primary text-base px-10 py-3.5 inline-flex items-center justify-center gap-2 whitespace-nowrap shadow-glow hover:shadow-[0_0_25px_rgba(168,85,247,0.6)] transition-shadow duration-300"
          >
            {isLoggedIn ? 'Go to Dashboard' : 'Sign In to Your Account'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-800/50 py-10 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center">
              <span className="text-xs font-bold text-white">m</span>
            </div>
            <span className="text-sm font-medium text-surface-400">myvivahai</span>
          </div>
          <div className="flex items-center gap-6">
            <button className="text-xs text-surface-500 hover:text-surface-300 transition-colors cursor-default">Privacy Policy</button>
            <button className="text-xs text-surface-500 hover:text-surface-300 transition-colors cursor-default">Terms of Service</button>
            <button className="text-xs text-surface-500 hover:text-surface-300 transition-colors cursor-default">Contact</button>
          </div>
          <p className="text-xs text-surface-600">
            &copy; {new Date().getFullYear()} myvivahai. All rights reserved.
          </p>
        </div>
      </footer>

    </div>
  )
}