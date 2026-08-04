import { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import {
  User as UserIcon, Mail, Save, Link2, ClipboardList, Trash2, RefreshCw, CheckCircle2, Sparkles,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useAuthStore } from '../app/store'
import { fadeIn } from '../utils/animations'
import { getApiErrorMessage } from '../utils/apiError'
import {
  updateProfile, linkMatriId, getPreferences,
  startPreferenceFlow, nextPreferenceQuestion, savePreferences, clearPreferences,
} from '../services/profileService'

const CUSTOM = 'custom'

export default function Profile() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [name, setName] = useState(user?.name || '')
  const [profileImage, setProfileImage] = useState(user?.profile_image || '')
  const [matriInput, setMatriInput] = useState(user?.matri_id || '')

  const [savingProfile, setSavingProfile] = useState(false)
  const [linking, setLinking] = useState(false)
  const [linked, setLinked] = useState(null)

  const [running, setRunning] = useState(false)
  const [flowLoading, setFlowLoading] = useState(false)
  const [current, setCurrent] = useState(null)
  const [answers, setAnswers] = useState([])
  const [textValue, setTextValue] = useState('')

  const [prefs, setPrefs] = useState(null)
  const [clearing, setClearing] = useState(false)

  const loadPrefs = async () => {
    try {
      setPrefs(await getPreferences())
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'पसंती लोड करता आल्या नाहीत'))
    }
  }

  useEffect(() => {
    loadPrefs()
  }, [])

  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    try {
      const updated = await updateProfile({ name, profile_image: profileImage })
      useAuthStore.getState().setUser(updated)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      toast.success('प्रोफाइल जतन झाले')
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'प्रोफाइल जतन करता आले नाही'))
    } finally {
      setSavingProfile(false)
    }
  }

  const handleLink = async (e) => {
    e.preventDefault()
    if (!matriInput.trim()) return
    setLinking(true)
    try {
      const res = await linkMatriId(matriInput.trim())
      setLinked(res)
      useAuthStore.getState().setUser(res.user)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      toast.success(`${res.member?.name || res.member?.matri_id} ला लिंक केले`)
      await loadPrefs()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'MatriID लिंक करता आला नाही'))
    } finally {
      setLinking(false)
    }
  }

  const handleStartFlow = async () => {
    setRunning(true)
    setAnswers([])
    setTextValue('')
    setFlowLoading(true)
    try {
      setCurrent(await startPreferenceFlow())
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'प्रश्नावली सुरू करता आली नाही'))
      setRunning(false)
    } finally {
      setFlowLoading(false)
    }
  }

  const advance = async (nextAnswers) => {
    setFlowLoading(true)
    try {
      const res = await nextPreferenceQuestion(nextAnswers)
      setCurrent(res)
      if (res.done) {
        await loadPrefs()
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'तुमचे उत्तर प्रक्रिया करता आले नाही'))
    } finally {
      setFlowLoading(false)
    }
  }

  const handleOption = (option) => {
    if (flowLoading) return
    const nextAnswers = [...answers, { node_id: current.node_id, option_id: option.id }]
    setAnswers(nextAnswers)
    advance(nextAnswers)
  }

  const handleCustomSubmit = () => {
    if (flowLoading) return
    if (!textValue.trim()) return
    const nextAnswers = [...answers, { node_id: current.node_id, option_id: CUSTOM, value: textValue.trim() }]
    setAnswers(nextAnswers)
    setTextValue('')
    advance(nextAnswers)
  }

  const handleClearPrefs = async () => {
    if (!confirm('सर्व जतन केलेल्या पसंती हटवायच्या?')) return
    setClearing(true)
    try {
      await clearPreferences()
      setPrefs(null)
      setLinked(null)
      setRunning(false)
      setCurrent(null)
      toast.success('पसंती हटवल्या')
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'पसंती हटवता आल्या नाहीत'))
    } finally {
      setClearing(false)
    }
  }

  const handleSavePrefs = async () => {
    if (!current?.filters_so_far) return
    try {
      await savePreferences(current.filters_so_far)
      toast.success('पसंती जतन झाल्या')
      await loadPrefs()
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'पसंती जतन करता आल्या नाहीत'))
    }
  }

  const doneFilters = current?.done ? current.filters : null
  const filterEntries = Object.entries(prefs?.filters || {})

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold gradient-text">माझे प्रोफाइल</h1>

        {/* Edit profile */}
        <motion.div {...fadeIn} className="card p-6">
          <h2 className="text-lg font-semibold text-surface-200 mb-4 flex items-center gap-2">
            <UserIcon className="w-5 h-5 text-primary-400" /> प्रोफाइल संपादित करा
          </h2>
          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div>
              <label className="text-sm text-surface-400 mb-1.5 block">नाव</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                className="input" placeholder="तुमचे नाव" required maxLength={256} />
            </div>
            <div>
              <label className="text-sm text-surface-400 mb-1.5 block">ईमेल (फक्त वाचण्यासाठी)</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input type="email" value={user?.email || ''} className="input pl-10 opacity-60" disabled />
              </div>
            </div>
            <div>
              <label className="text-sm text-surface-400 mb-1.5 block">प्रोफाइल फोटो URL (ऐच्छिक)</label>
              <input type="url" value={profileImage} onChange={(e) => setProfileImage(e.target.value)}
                className="input" placeholder="https://..." maxLength={512} />
            </div>
            <button type="submit" disabled={savingProfile} className="btn-primary flex items-center gap-2">
              {savingProfile ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              प्रोफाइल जतन करा
            </button>
          </form>
        </motion.div>

        {/* Link MatriID */}
        <motion.div {...fadeIn} className="card p-6">
          <h2 className="text-lg font-semibold text-surface-200 mb-1 flex items-center gap-2">
            <Link2 className="w-5 h-5 text-primary-400" /> तुमचा Matrimony ID लिंक करा
          </h2>
          <p className="text-sm text-surface-500 mb-4">
            matrimony website वरील तुमच्या प्रोफाइलमधील MatriID टाका. आम्ही तुमच्या
            partner expectations वाचून तुम्हाला योग्य प्रश्न विचारू.
          </p>
          <form onSubmit={handleLink} className="flex gap-3">
            <input type="text" value={matriInput} onChange={(e) => setMatriInput(e.target.value)}
              className="input flex-1" placeholder="उदा. WP12345" required maxLength={15} />
            <button type="submit" disabled={linking || !matriInput.trim()} className="btn-primary flex items-center gap-2">
              {linking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
              लिंक करा
            </button>
          </form>

          {linked && (
            <div className="mt-4 rounded-xl bg-surface-800/60 border border-surface-700 p-4">
              <div className="flex items-center gap-4">
                {linked.member?.photo_url ? (
                  <img src={linked.member.photo_url} alt="" className="w-14 h-14 rounded-xl object-cover" />
                ) : (
                  <div className="w-14 h-14 rounded-xl bg-primary-600/30 flex items-center justify-center">
                    <UserIcon className="w-6 h-6 text-primary-300" />
                  </div>
                )}
                <div className="flex-1">
                  <p className="text-surface-200 font-medium">{linked.member?.name}</p>
                  <p className="text-xs text-surface-500">
                    {linked.member?.matri_id} · {linked.member?.gender} · {linked.member?.age || '?'} years
                  </p>
                </div>
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              </div>
              {Object.keys(linked.summary || {}).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-surface-500 mb-2">partner expectations सापडल्या:</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(linked.summary).map(([k, v]) => (
                      <span key={k} className="text-xs bg-surface-900 border border-surface-700 rounded-lg px-2 py-1 text-surface-300">
                        {k}: <span className="text-primary-300">{v}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {linked.saved_search_used && (
                <p className="text-xs text-surface-500 mt-3">
                  तुमच्या saved search मधून ({linked.saved_search_source}) रिकामी माहिती भरली.
                </p>
              )}
              <button onClick={handleStartFlow} className="btn-primary mt-4 flex items-center gap-2">
                <Sparkles className="w-4 h-4" /> Partner preference questionnaire सुरू करा
              </button>
            </div>
          )}
        </motion.div>

        {/* Questionnaire */}
        {(running || current) && (
          <motion.div {...fadeIn} className="card p-6">
            <h2 className="text-lg font-semibold text-surface-200 mb-4 flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary-400" /> जोडीदार निवड प्रश्नावली
            </h2>

            {current?.done ? (
              <div>
                <div className="flex items-center gap-2 text-green-400 mb-3">
                  <CheckCircle2 className="w-5 h-5" />
                  <p className="font-medium">पसंती जतन झाल्या!</p>
                </div>
                <p className="text-sm text-surface-500 mb-4">
                  तुमच्या पसंती आता chat मध्ये profiles शोधताना आपोआप वापरल्या जातील.
                </p>
                {Object.entries(current.filters || {}).length > 0 ? (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {Object.entries(current.filters).map(([k, v]) => (
                      <span key={k} className="text-xs bg-surface-900 border border-surface-700 rounded-lg px-2 py-1 text-surface-300">
                        {k}: <span className="text-primary-300">{v}</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-surface-500 mb-4">कोणत्याही विशिष्ट पसंती नाहीत — आम्ही सर्व योग्य profiles दाखवू.</p>
                )}
                <div className="flex gap-3">
                  <button onClick={handleStartFlow} className="btn-secondary flex items-center gap-2">
                    <RefreshCw className="w-4 h-4" /> पुन्हा सुरू करा
                  </button>
                  <button onClick={handleSavePrefs} className="btn-ghost flex items-center gap-2">
                    <Save className="w-4 h-4" /> पुन्हा जतन करा
                  </button>
                </div>
              </div>
            ) : current?.node ? (
              <div>
                <div className="mb-3">
                  <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary-600 to-primary-400 transition-all duration-300"
                      style={{ width: `${(current.node.progress.current / current.node.progress.total) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-surface-500 mt-1.5">
                    {current.node.category_label} · प्रश्न {current.node.progress.current} पैकी {current.node.progress.total}
                  </p>
                </div>

                <h3 className="text-surface-100 font-medium mb-4">{current.node.question}</h3>

                <div className="flex flex-col gap-2">
                  {current.node.options.map((option) => (
                    <button
                      key={option.id}
                      onClick={() => handleOption(option)}
                      disabled={flowLoading}
                      className="text-left px-4 py-3 rounded-xl bg-surface-800/60 border border-surface-700 text-surface-200
                                 hover:border-primary-500 hover:bg-primary-600/10 transition-all disabled:opacity-50"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                {current.node.type === 'text' && (
                  <div className="mt-4 flex gap-3">
                    <input
                      type="text"
                      value={textValue}
                      onChange={(e) => setTextValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleCustomSubmit() } }}
                      className="input flex-1"
                      placeholder={current.node.placeholder || 'तुमचे उत्तर लिहा'}
                    />
                    <button onClick={handleCustomSubmit} disabled={flowLoading || !textValue.trim()} className="btn-primary">
                      पुढे
                    </button>
                  </div>
                )}

                {flowLoading && (
                  <p className="text-sm text-surface-500 mt-4 flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin" /> पुढील प्रश्न लोड होत आहे…
                  </p>
                )}
              </div>
            ) : null}
          </motion.div>
        )}

        {/* Saved preferences */}
        <motion.div {...fadeIn} className="card p-6">
          <h2 className="text-lg font-semibold text-surface-200 mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-primary-400" /> जतन केलेल्या पसंती
          </h2>
          {!prefs ? (
            <p className="text-sm text-surface-500">लोड होत आहे…</p>
          ) : filterEntries.length === 0 ? (
            <p className="text-sm text-surface-500">
              अजून कोणत्याही पसंती जतन झालेल्या नाहीत. सुरुवातीसाठी तुमचा Matrimony ID लिंक करा आणि प्रश्नावली पूर्ण करा.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2 mb-4">
                {filterEntries.map(([k, v]) => (
                  <span key={k} className="text-xs bg-surface-900 border border-surface-700 rounded-lg px-2 py-1 text-surface-300">
                    {k}: <span className="text-primary-300">{v}</span>
                  </span>
                ))}
              </div>
              <button onClick={handleStartFlow} className="btn-secondary mr-3 flex items-center gap-2">
                <ClipboardList className="w-4 h-4" /> प्रश्नावली पुन्हा पहा
              </button>
              <button onClick={handleClearPrefs} disabled={clearing} className="btn-ghost text-red-400 hover:text-red-300 flex items-center gap-2">
                <Trash2 className="w-4 h-4" /> {clearing ? 'हटवत आहे…' : 'सर्व हटवा'}
              </button>
            </>
          )}
        </motion.div>
      </div>
    </div>
  )
}
