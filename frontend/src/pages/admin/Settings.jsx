import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Eye, EyeOff, Wifi, WifiOff, Loader2, Save, RefreshCw, Server, Brain } from 'lucide-react'
import { getAdminSettings, updateAdminSettings, testLlm, testDb } from '../../services/adminService'

function StatusBadge({ status }) {
  if (status === 'connected' || status === 'configured') {
    return <span className="inline-flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full"><Wifi className="w-3 h-3" />{status}</span>
  }
  if (status === 'failed' || status === 'not configured' || status === 'unreachable') {
    return <span className="inline-flex items-center gap-1 text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full"><WifiOff className="w-3 h-3" />{status}</span>
  }
  return <span className="text-xs text-surface-500">{status}</span>
}

export default function AdminSettings() {
  const [showKey, setShowKey] = useState(false)
  const [showPw, setShowPw] = useState(false)
  const [llmTesting, setLlmTesting] = useState(false)
  const [dbTesting, setDbTesting] = useState(false)

  const { data: settingsData, isLoading, refetch } = useQuery({
    queryKey: ['admin-settings'],
    queryFn: getAdminSettings,
  })

  const updateMutation = useMutation({
    mutationFn: updateAdminSettings,
    onSuccess: (data) => {
      toast.success('Settings saved')
      refetch()
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Failed to save settings'),
  })

  const handleTestLlm = async () => {
    setLlmTesting(true)
    try {
      const res = await testLlm()
      toast(res.status === 'connected' ? 'LLM connected' : `Failed: ${res.message || res.status}`, { icon: res.status === 'connected' ? '✅' : '❌' })
      refetch()
    } catch { toast.error('Test failed') }
    finally { setLlmTesting(false) }
  }

  const handleTestDb = async () => {
    setDbTesting(true)
    try {
      const res = await testDb()
      toast(res.status === 'connected' ? 'Database connected' : 'Database failed', { icon: res.status === 'connected' ? '✅' : '❌' })
      refetch()
    } catch { toast.error('Test failed') }
    finally { setDbTesting(false) }
  }

  const handleSave = (e) => {
    e.preventDefault()
    const form = e.target
    updateMutation.mutate({
      llm_model: form.llm_model.value,
      intent_model: form.intent_model.value,
      llm_api_key: form.llm_api_key.value,
      db_host: form.db_host.value,
      db_port: parseInt(form.db_port.value),
      db_user: form.db_user.value,
      db_password: form.db_password.value,
      db_name: form.db_name.value,
    })
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" /></div>
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">Settings</h1>
        <p className="text-sm text-surface-500 mt-1">Manage LLM and database configuration</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* LLM Card */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-surface-200 flex items-center gap-2">
              <Brain className="w-4 h-4 text-primary-400" /> LLM Configuration
            </h2>
            <StatusBadge status={settingsData?.llm_status} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Main Model</label>
              <input name="llm_model" defaultValue={settingsData?.llm_model || ''} className="input py-2 text-sm" placeholder="llama-3.3-70b-versatile" />
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Intent Model</label>
              <input name="intent_model" defaultValue={settingsData?.intent_model || ''} className="input py-2 text-sm" placeholder="llama-3.1-8b-instant" />
            </div>
          </div>

          <div>
            <label className="text-xs text-surface-400 mb-1 block">API Key</label>
            <div className="relative">
              <input
                name="llm_api_key"
                type={showKey ? 'text' : 'password'}
                defaultValue={settingsData?.llm_api_key || ''}
                className="input py-2 text-sm pr-10 font-mono"
                placeholder="gsk_..."
              />
              <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300 cursor-pointer">
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button type="button" onClick={handleTestLlm} disabled={llmTesting} className="btn-secondary text-sm flex items-center gap-2 w-fit">
            {llmTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Test LLM Connection
          </button>
        </div>

        {/* DB Card */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-surface-200 flex items-center gap-2">
              <Server className="w-4 h-4 text-primary-400" /> Database Configuration
            </h2>
            <StatusBadge status={settingsData?.db_status} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Host</label>
              <input name="db_host" defaultValue={settingsData?.db_host || ''} className="input py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Port</label>
              <input name="db_port" type="number" defaultValue={settingsData?.db_port || 3306} className="input py-2 text-sm font-mono" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-surface-400 mb-1 block">User</label>
              <input name="db_user" defaultValue={settingsData?.db_user || ''} className="input py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Database</label>
              <input name="db_name" defaultValue={settingsData?.db_name || ''} className="input py-2 text-sm font-mono" />
            </div>
          </div>

          <div>
            <label className="text-xs text-surface-400 mb-1 block">Password</label>
            <div className="relative">
              <input
                name="db_password"
                type={showPw ? 'text' : 'password'}
                defaultValue={settingsData?.db_password || ''}
                className="input py-2 text-sm pr-10 font-mono"
                placeholder="password"
              />
              <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300 cursor-pointer">
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button type="button" onClick={handleTestDb} disabled={dbTesting} className="btn-secondary text-sm flex items-center gap-2 w-fit">
            {dbTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Test DB Connection
          </button>
        </div>

        <div className="flex items-center gap-4">
          <button type="submit" disabled={updateMutation.isPending} className="btn-primary flex items-center gap-2">
            {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Settings
          </button>
          {updateMutation.isSuccess && (
            <span className="text-xs text-amber-400">⚠️ Restart required for changes to take full effect</span>
          )}
        </div>
      </form>
    </div>
  )
}
