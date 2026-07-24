import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Activity, Bot, CreditCard, GitBranch, History, Layers3, Plus, Users,
} from 'lucide-react'
import {
  assignSubscription, confirmPaymentOrder, createAIModel, createAIProvider, createPaymentGateway,
  createCommercialPlan, getAIModels, getAIProviders, getAIRoutes,
  getAIUsageEvents, getCommercialAudit, getCommercialPlans, getCommercialSummary,
  getPaymentGateways, getPaymentOrders, getSubscriptions, publishAIRoute,
  testAIModel, testAIRoute, updateAIModel, updateAIProvider, updateSubscription,
} from '../../services/adminService'

const tabs = [
  ['overview', 'Overview', Activity], ['plans', 'Plans', Layers3],
  ['providers', 'Providers', Bot], ['models', 'Models', Bot],
  ['routes', 'Routing', GitBranch], ['subscriptions', 'Subscriptions', Users],
  ['orders', 'Payments', CreditCard], ['usage', 'Usage', Activity],
  ['audit', 'Audit', History],
]

const inputClass = 'input-field w-full text-sm'
const money = (paise) => `₹${((paise || 0) / 100).toLocaleString('en-IN')}`

export default function CommercialAI() {
  const [tab, setTab] = useState('overview')
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['commercial-admin'] })
  const query = (key, fn, enabled = true) => useQuery({ queryKey: ['commercial-admin', key], queryFn: fn, enabled })

  const { data: summary = {} } = query('summary', getCommercialSummary)
  const { data: plans = [] } = query('plans', getCommercialPlans)
  const { data: providers = [] } = query('providers', getAIProviders)
  const { data: models = [] } = query('models', getAIModels)
  const { data: routes = [] } = query('routes', getAIRoutes)
  const { data: subscriptions = [] } = query('subscriptions', getSubscriptions, tab === 'subscriptions')
  const { data: orders = [] } = query('orders', getPaymentOrders, tab === 'orders')
  const { data: gateways = [] } = query('gateways', getPaymentGateways, tab === 'orders')
  const { data: usage = [] } = query('usage', getAIUsageEvents, tab === 'usage')
  const { data: audit = [] } = query('audit', getCommercialAudit, tab === 'audit')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">Commerce & AI</h1>
        <p className="text-sm text-surface-500 mt-1">Plans, entitlements, model routing, provider costs, payments and audit history.</p>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${tab === key ? 'bg-primary-600/20 text-primary-300' : 'bg-surface-900 text-surface-400 hover:text-white'}`}>
            <Icon className="w-4 h-4" />{label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <Overview summary={summary} plans={plans} providers={providers} models={models} routes={routes} />}
      {tab === 'plans' && <PlansPanel plans={plans} invalidate={invalidate} />}
      {tab === 'providers' && <ProvidersPanel providers={providers} invalidate={invalidate} />}
      {tab === 'models' && <ModelsPanel models={models} providers={providers} invalidate={invalidate} />}
      {tab === 'routes' && <RoutesPanel routes={routes} models={models} invalidate={invalidate} />}
      {tab === 'subscriptions' && <SubscriptionsPanel subscriptions={subscriptions} plans={plans} invalidate={invalidate} />}
      {tab === 'orders' && <OrdersPanel orders={orders} gateways={gateways} invalidate={invalidate} />}
      {tab === 'usage' && <UsagePanel usage={usage} />}
      {tab === 'audit' && <AuditPanel audit={audit} />}
    </div>
  )
}

function Overview({ summary, plans, providers, models, routes }) {
  const cards = [
    ['Active subscriptions', summary.active_subscriptions || 0],
    ['Verified revenue', money(summary.revenue_paise)],
    ['AI tokens tracked', (summary.total_tokens || 0).toLocaleString()],
    ['Estimated AI cost', money(Math.round(summary.estimated_cost_paise || 0))],
  ]
  return <div className="space-y-5">
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map(([label, value]) => <div className="card p-5" key={label}><p className="text-xs text-surface-500">{label}</p><p className="text-2xl font-semibold text-surface-100 mt-2">{value}</p></div>)}
    </div>
    <div className="card p-5 text-sm text-surface-300 space-y-2">
      <p>{plans.filter((p) => p.is_current).length} current plans · {providers.filter((p) => p.enabled).length} enabled providers · {models.filter((m) => m.enabled).length} enabled models</p>
      <p>{routes.filter((r) => r.enabled).length} published task routes. Provider secrets are referenced by environment-variable name and are never returned by this panel.</p>
      <p className="text-amber-300">Manual payment verification is active until a live gateway adapter and credentials are configured.</p>
    </div>
  </div>
}

function PlansPanel({ plans, invalidate }) {
  const [form, setForm] = useState({ code: 'BASIC', name: 'Basic', description: '', price_rupees: 2499, duration_days: 30, ai_credits: 500, daily_message_limit: 200, contact_limit: 30, normal_credit_cost: 1, database_credit_cost: 2 })
  const mutation = useMutation({ mutationFn: (value) => createCommercialPlan({ ...value, price_paise: Number(value.price_rupees) * 100, currency: 'INR', is_active: true }), onSuccess: () => { toast.success('New plan version published'); invalidate() }, onError: errorToast })
  return <div className="grid xl:grid-cols-[360px_1fr] gap-5">
    <Panel title="Publish plan version"><FormFields form={form} setForm={setForm} fields={[
      ['code', 'Plan code'], ['name', 'Name'], ['description', 'Description'], ['price_rupees', 'Price (₹)', 'number'],
      ['duration_days', 'Duration days', 'number'], ['ai_credits', 'AI credits', 'number'],
      ['daily_message_limit', 'Daily messages', 'number'], ['contact_limit', 'Contacts', 'number'],
      ['normal_credit_cost', 'Normal credits/message', 'number'], ['database_credit_cost', 'Database credits/message', 'number'],
    ]} /><SaveButton onClick={() => mutation.mutate(form)} pending={mutation.isPending} label="Publish version" /></Panel>
    <Panel title="Plan history"><Table headers={['Plan', 'Version', 'Price', 'Credits', 'Daily', 'Contacts', 'State']} rows={plans.map((p) => [p.name, `v${p.version}`, money(p.price_paise), p.ai_credits, p.daily_message_limit, p.contact_limit, p.is_current ? 'Current' : 'Historical'])} /></Panel>
  </div>
}

function ProvidersPanel({ providers, invalidate }) {
  const [form, setForm] = useState({ code: 'ollama', name: 'Ollama', adapter_type: 'ollama', base_url: 'http://127.0.0.1:11434/v1/chat/completions', api_key_env: '', enabled: false, verify_ssl: false, timeout_seconds: 60, retry_count: 1 })
  const create = useMutation({ mutationFn: createAIProvider, onSuccess: () => { toast.success('Provider added'); invalidate() }, onError: errorToast })
  const toggle = useMutation({ mutationFn: (p) => updateAIProvider(p.id, { ...p, enabled: !p.enabled }), onSuccess: invalidate, onError: errorToast })
  return <div className="grid xl:grid-cols-[380px_1fr] gap-5">
    <Panel title="Add provider"><FormFields form={form} setForm={setForm} fields={[
      ['code', 'Code'], ['name', 'Name'], ['adapter_type', 'Adapter type'], ['base_url', 'Chat-completions URL'],
      ['api_key_env', 'API-key environment name'], ['timeout_seconds', 'Timeout seconds', 'number'], ['retry_count', 'Retries', 'number'],
    ]} /><label className="flex gap-2 text-sm text-surface-300"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> Enabled</label><SaveButton onClick={() => create.mutate(form)} pending={create.isPending} label="Add provider" /></Panel>
    <Panel title="Configured providers"><div className="space-y-3">{providers.map((p) => <div key={p.id} className="border border-surface-800 rounded-xl p-4 flex flex-wrap items-center gap-3"><div className="flex-1 min-w-56"><p className="text-surface-100 font-medium">{p.name} <span className="text-xs text-surface-500">({p.adapter_type})</span></p><p className="text-xs text-surface-500 break-all">{p.base_url}</p><p className="text-xs text-surface-500">Secret: {p.api_key_env || 'none/local'}</p></div><button onClick={() => toggle.mutate(p)} className={p.enabled ? 'btn-ghost text-green-400' : 'btn-ghost text-surface-500'}>{p.enabled ? 'Enabled' : 'Disabled'}</button></div>)}</div></Panel>
  </div>
}

function ModelsPanel({ models, providers, invalidate }) {
  const [form, setForm] = useState({ provider_id: providers[0]?.id || '', external_id: '', display_name: '', context_window: 8192, max_output_tokens: 1200, supports_json: true, supports_sql: true, input_cost_paise_per_million: 0, output_cost_paise_per_million: 0, enabled: true })
  useEffect(() => { if (!form.provider_id && providers[0]) setForm((f) => ({ ...f, provider_id: providers[0].id })) }, [providers])
  const create = useMutation({ mutationFn: (value) => createAIModel({ ...value, provider_id: Number(value.provider_id) }), onSuccess: () => { toast.success('Model added'); invalidate() }, onError: errorToast })
  const toggle = useMutation({ mutationFn: (m) => updateAIModel(m.id, { ...m, enabled: !m.enabled }), onSuccess: invalidate, onError: errorToast })
  const test = useMutation({ mutationFn: testAIModel, onSuccess: (data) => toast.success(`Response: ${data.content}`), onError: errorToast })
  return <div className="grid xl:grid-cols-[400px_1fr] gap-5">
    <Panel title="Add model"><label className="text-xs text-surface-500">Provider<select className={inputClass} value={form.provider_id} onChange={(e) => setForm({ ...form, provider_id: e.target.value })}>{providers.map((p) => <option value={p.id} key={p.id}>{p.name}</option>)}</select></label><FormFields form={form} setForm={setForm} fields={[
      ['external_id', 'External model ID'], ['display_name', 'Display name'], ['context_window', 'Context window', 'number'], ['max_output_tokens', 'Maximum output', 'number'],
      ['input_cost_paise_per_million', 'Input cost paise / 1M', 'number'], ['output_cost_paise_per_million', 'Output cost paise / 1M', 'number'],
    ]} /><div className="flex gap-4 text-sm text-surface-300"><CheckField label="JSON" value={form.supports_json} set={(v) => setForm({ ...form, supports_json: v })} /><CheckField label="SQL" value={form.supports_sql} set={(v) => setForm({ ...form, supports_sql: v })} /></div><SaveButton onClick={() => create.mutate(form)} pending={create.isPending} label="Add model" /></Panel>
    <Panel title="Models"><div className="space-y-3">{models.map((m) => <div key={m.id} className="border border-surface-800 rounded-xl p-4 flex items-center gap-3"><div className="flex-1"><p className="text-sm text-surface-100">{m.display_name}</p><p className="text-xs text-surface-500">{m.provider_code} · {m.external_id}</p><p className="text-xs text-surface-500">Input ₹{(m.input_cost_paise_per_million / 100).toFixed(2)} / 1M · Output ₹{(m.output_cost_paise_per_million / 100).toFixed(2)} / 1M</p></div><button onClick={() => test.mutate(m.id)} className="btn-ghost">Test</button><button onClick={() => toggle.mutate(m)} className={m.enabled ? 'btn-ghost text-green-400' : 'btn-ghost text-surface-500'}>{m.enabled ? 'Enabled' : 'Disabled'}</button></div>)}</div></Panel>
  </div>
}

function RoutesPanel({ routes, models, invalidate }) {
  const [drafts, setDrafts] = useState({})
  useEffect(() => { setDrafts(Object.fromEntries(routes.map((r) => [r.task_key, r.targets.map((t) => t.model_id).join(',')]))) }, [routes])
  const save = useMutation({ mutationFn: ({ key, ids }) => publishAIRoute(key, ids), onSuccess: () => { toast.success('Route published'); invalidate() }, onError: errorToast })
  const test = useMutation({ mutationFn: testAIRoute, onSuccess: (data) => toast.success(`Response: ${data.content}`), onError: errorToast })
  return <Panel title="Published task routing"><p className="text-xs text-surface-500 mb-4">Enter model IDs in primary-to-fallback order. SQL routes reject models without JSON/SQL capability.</p><div className="space-y-4">{routes.map((r) => <div key={r.task_key} className="border border-surface-800 rounded-xl p-4"><div className="flex flex-wrap gap-3 items-end"><label className="flex-1 min-w-64 text-xs text-surface-500"><span className="text-sm text-surface-200 block mb-1">{r.task_key}</span><input className={inputClass} value={drafts[r.task_key] || ''} onChange={(e) => setDrafts({ ...drafts, [r.task_key]: e.target.value })} /></label><button className="btn-primary" onClick={() => save.mutate({ key: r.task_key, ids: (drafts[r.task_key] || '').split(',').map(Number).filter(Boolean) })}>Publish</button><button className="btn-ghost" onClick={() => test.mutate(r.task_key)}>Test</button></div><p className="text-xs text-surface-500 mt-2">Available: {models.map((m) => `${m.id}=${m.display_name}`).join(' · ')}</p></div>)}</div></Panel>
}

function SubscriptionsPanel({ subscriptions, plans, invalidate }) {
  const [userId, setUserId] = useState('')
  const [planId, setPlanId] = useState(plans.find((p) => p.is_current && p.code !== 'FREE')?.id || '')
  const assign = useMutation({ mutationFn: () => assignSubscription(Number(userId), Number(planId)), onSuccess: () => { toast.success('Subscription assigned'); invalidate() }, onError: errorToast })
  const update = useMutation({ mutationFn: ({ id, body }) => updateSubscription(id, body), onSuccess: () => { toast.success('Subscription updated'); invalidate() }, onError: errorToast })
  return <div className="space-y-5"><Panel title="Manual plan assignment"><div className="grid sm:grid-cols-3 gap-3"><input className={inputClass} placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} /><select className={inputClass} value={planId} onChange={(e) => setPlanId(e.target.value)}>{plans.filter((p) => p.is_current && p.is_active).map((p) => <option key={p.id} value={p.id}>{p.name} v{p.version}</option>)}</select><SaveButton onClick={() => assign.mutate()} pending={assign.isPending} label="Assign plan" /></div></Panel><Panel title="Subscription history"><Table headers={['User', 'Plan', 'Status', 'Credits', 'Daily', 'Expires', 'Actions']} rows={subscriptions.map((s) => [`${s.user_name} (#${s.user_id})`, s.plan_name, s.status, `${s.credits_used}/${s.credits_allocated}`, `${s.daily_messages_used}/${s.daily_message_limit}`, new Date(s.expires_at).toLocaleDateString('en-IN'), <div className="flex gap-1"><button className="btn-ghost text-xs" onClick={() => update.mutate({ id: s.id, body: { credits_delta: 100, extend_days: 0 } })}>+100 credits</button><button className="btn-ghost text-xs" onClick={() => update.mutate({ id: s.id, body: { extend_days: 30, credits_delta: 0 } })}>+30 days</button>{s.status === 'active' && <button className="btn-ghost text-xs text-red-400" onClick={() => update.mutate({ id: s.id, body: { status: 'cancelled', credits_delta: 0, extend_days: 0 } })}>Cancel</button>}</div>])} /></Panel></div>
}

function OrdersPanel({ orders, gateways, invalidate }) {
  const confirm = useMutation({ mutationFn: ({ id, ref }) => confirmPaymentOrder(id, ref), onSuccess: () => { toast.success('Payment confirmed and plan activated'); invalidate() }, onError: errorToast })
  const [gateway, setGateway] = useState({ code: '', name: '', adapter_type: 'manual', key_id_env: '', secret_env: '', webhook_secret_env: '', enabled: false })
  const createGateway = useMutation({ mutationFn: createPaymentGateway, onSuccess: () => { toast.success('Gateway configuration added'); invalidate() }, onError: errorToast })
  return <div className="space-y-5"><Panel title="Payment gateways"><Table headers={['Gateway', 'Adapter', 'Key ID secret', 'Webhook secret', 'State']} rows={gateways.map((g) => [g.name, g.adapter_type, g.key_id_env || '—', g.webhook_secret_env || '—', g.enabled ? 'Enabled' : 'Disabled'])} /><div className="grid md:grid-cols-3 gap-2 mt-4"><input className={inputClass} placeholder="Gateway code" value={gateway.code} onChange={(e) => setGateway({ ...gateway, code: e.target.value })} /><input className={inputClass} placeholder="Display name" value={gateway.name} onChange={(e) => setGateway({ ...gateway, name: e.target.value })} /><input className={inputClass} placeholder="Adapter type" value={gateway.adapter_type} onChange={(e) => setGateway({ ...gateway, adapter_type: e.target.value })} /><input className={inputClass} placeholder="Key ID env name" value={gateway.key_id_env} onChange={(e) => setGateway({ ...gateway, key_id_env: e.target.value })} /><input className={inputClass} placeholder="Secret env name" value={gateway.secret_env} onChange={(e) => setGateway({ ...gateway, secret_env: e.target.value })} /><input className={inputClass} placeholder="Webhook secret env name" value={gateway.webhook_secret_env} onChange={(e) => setGateway({ ...gateway, webhook_secret_env: e.target.value })} /></div><SaveButton onClick={() => createGateway.mutate(gateway)} pending={createGateway.isPending} label="Add gateway configuration" /><p className="text-xs text-surface-500 mt-3">Only the manual adapter is installed. Additional gateway adapters can use these secret references without changing subscription logic.</p></Panel><Panel title="Payment orders"><Table headers={['Reference', 'User', 'Amount', 'Status', 'Created', 'Action']} rows={orders.map((o) => [o.order_reference, o.user_name, money(o.amount_paise), o.status, new Date(o.created_at).toLocaleString('en-IN'), o.status === 'pending' ? <button className="btn-primary text-xs" onClick={() => { const ref = window.prompt('Verified payment reference'); if (ref) confirm.mutate({ id: o.id, ref }) }}>Confirm payment</button> : 'Activated'])} /></Panel></div>
}

function UsagePanel({ usage }) {
  return <Panel title="Normalized provider usage"><Table headers={['Time', 'User', 'Task', 'Provider/model', 'Tokens', 'Cost', 'Latency']} rows={usage.map((u) => [new Date(u.created_at).toLocaleString('en-IN'), `#${u.user_id}`, u.task_key, `${u.provider_code}/${u.model_external_id}`, u.total_tokens.toLocaleString(), `₹${(u.estimated_cost_paise / 100).toFixed(4)}`, `${u.latency_ms} ms`])} /></Panel>
}

function AuditPanel({ audit }) {
  return <Panel title="Administrative audit log"><Table headers={['Time', 'Admin', 'Action', 'Entity', 'ID']} rows={audit.map((a) => [new Date(a.created_at).toLocaleString('en-IN'), `#${a.admin_user_id}`, a.action, a.entity_type, a.entity_id])} /></Panel>
}

function Panel({ title, children }) { return <section className="card p-5"><h2 className="text-sm font-medium text-surface-200 mb-4">{title}</h2>{children}</section> }
function SaveButton({ onClick, pending, label }) { return <button type="button" onClick={onClick} disabled={pending} className="btn-primary mt-3 disabled:opacity-50 flex items-center justify-center gap-2"><Plus className="w-4 h-4" />{pending ? 'Saving…' : label}</button> }
function FormFields({ form, setForm, fields }) { return <div className="space-y-3">{fields.map(([key, label, type = 'text']) => <label key={key} className="block text-xs text-surface-500">{label}<input className={inputClass} type={type} value={form[key]} onChange={(e) => setForm({ ...form, [key]: type === 'number' ? Number(e.target.value) : e.target.value })} /></label>)}</div> }
function CheckField({ label, value, set }) { return <label className="flex gap-2"><input type="checkbox" checked={value} onChange={(e) => set(e.target.checked)} />{label}</label> }
function Table({ headers, rows }) { return <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-surface-500 border-b border-surface-800">{headers.map((h) => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i} className="border-b border-surface-800/60 text-surface-300">{row.map((cell, j) => <td key={j} className="p-2 whitespace-nowrap">{cell}</td>)}</tr>)}</tbody></table>{rows.length === 0 && <p className="text-center text-surface-500 py-8">No records</p>}</div> }
function errorToast(error) { toast.error(typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.response?.data?.detail?.message || error.message || 'Request failed') }
