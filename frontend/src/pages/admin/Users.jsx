import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Shield, ShieldOff, Trash2, CheckCircle, XCircle, CreditCard, X } from 'lucide-react'
import DataTable from '../../components/admin/DataTable'
import { getUsers, updateUser, deleteUser } from '../../services/adminService'
import { getCommercialPlans, assignSubscription } from '../../services/adminService'

function AssignPlanModal({ user, plans, onClose, onAssign }) {
  const [planId, setPlanId] = useState('')
  const [pending, setPending] = useState(false)

  const handleAssign = async () => {
    if (!planId) return
    setPending(true)
    try {
      await onAssign(user.id, Number(planId))
      onClose()
    } catch {
      /* toast handled by parent */
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-surface-900 border border-surface-700 rounded-2xl w-full max-w-sm mx-4 p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-100">
            Assign Plan — {user.name}
          </h3>
          <button onClick={onClose} className="btn-ghost p-1 text-surface-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
        <select
          value={planId}
          onChange={(e) => setPlanId(e.target.value)}
          className="input-field w-full mb-4"
        >
          <option value="">Select a plan...</option>
          {plans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — ₹{(p.price_paise / 100).toLocaleString('en-IN')} / {p.duration_days}d · {p.ai_credits} credits · {p.daily_message_limit}/day
            </option>
          ))}
        </select>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn-ghost px-4 py-2 text-sm">Cancel</button>
          <button
            onClick={handleAssign}
            disabled={!planId || pending}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
          >
            {pending ? 'Assigning...' : 'Assign Plan'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AdminUsers() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [assignTarget, setAssignTarget] = useState(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, search],
    queryFn: () => getUsers(page, search),
  })

  const { data: plans = [] } = useQuery({
    queryKey: ['admin-commercial-plans'],
    queryFn: getCommercialPlans,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, ...body }) => updateUser(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('User updated')
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Failed to update user'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('User deleted')
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Failed to delete user'),
  })

  const assignMutation = useMutation({
    mutationFn: ({ userId, planId }) => assignSubscription(userId, planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('Plan assigned')
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Failed to assign plan'),
  })

  const toggleAdmin = (user) => {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    updateMutation.mutate({ id: user.id, role: newRole })
  }

  const toggleActive = (user) => {
    updateMutation.mutate({ id: user.id, is_active: !user.is_active })
  }

  const toggleVerified = (user) => {
    updateMutation.mutate({ id: user.id, is_verified: !user.is_verified })
  }

  const columns = [
    { key: 'id', label: 'ID' },
    {
      key: 'is_online',
      label: 'Online',
      render: (val) => (
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
          val ? 'bg-green-500/20 text-green-300' : 'bg-surface-700 text-surface-500'
        }`}>
          <span className={`w-2 h-2 rounded-full ${val ? 'bg-green-400 shadow-sm shadow-green-400/50' : 'bg-surface-500'}`} />
          {val ? 'Online' : 'Offline'}
        </span>
      ),
    },
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
    {
      key: 'role',
      label: 'Role',
      render: (val, row) => (
        <button
          onClick={() => toggleAdmin(row)}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
            val === 'admin' ? 'bg-purple-500/20 text-purple-300' : 'bg-surface-700 text-surface-400'
          }`}
        >
          {val === 'admin' ? <Shield className="w-3 h-3" /> : <ShieldOff className="w-3 h-3" />}
          {val}
        </button>
      ),
    },
    {
      key: 'subscription',
      label: 'Plan',
      render: (val) => {
        if (!val) return <span className="text-xs text-surface-500">None</span>
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary-500/10 text-primary-300">
            <CreditCard className="w-3 h-3" />
            {val.plan_name}
          </span>
        )
      },
    },
    {
      key: 'is_active',
      label: 'Active',
      render: (val, row) => (
        <button onClick={() => toggleActive(row)} className="btn-ghost p-1">
          {val ? <CheckCircle className="w-4 h-4 text-green-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
        </button>
      ),
    },
    {
      key: 'is_verified',
      label: 'Verified',
      render: (val, row) => (
        <button onClick={() => toggleVerified(row)} className="btn-ghost p-1">
          {val ? <CheckCircle className="w-4 h-4 text-green-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
        </button>
      ),
    },
    {
      key: 'last_login',
      label: 'Last Login',
      render: (val) => val ? new Date(val).toLocaleDateString() : '—',
    },
    {
      key: 'created_at',
      label: 'Joined',
      render: (val) => val ? new Date(val).toLocaleDateString() : '—',
    },
    {
      key: 'id',
      label: '',
      render: (_, row) => (
        <div className="flex gap-1">
          <button
            onClick={() => setAssignTarget(row)}
            className="btn-ghost p-1 text-xs text-primary-400 hover:text-primary-300"
            title="Assign plan"
          >
            <CreditCard className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => { if (confirm('Delete this user and all their conversations?')) deleteMutation.mutate(row.id) }}
            className="btn-ghost p-1 text-surface-500 hover:text-red-400"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">App Users</h1>
        <p className="text-sm text-surface-500 mt-1">Manage platform users, roles, access, and plan assignments</p>
      </div>

      <DataTable
        columns={columns}
        data={data?.items || []}
        total={data?.total || 0}
        page={page}
        perPage={20}
        onPageChange={setPage}
        search={search}
        onSearch={(s) => { setSearch(s); setPage(1) }}
        loading={isLoading}
        searchPlaceholder="Search by name or email..."
      />

      {assignTarget && (
        <AssignPlanModal
          user={assignTarget}
          plans={plans}
          onClose={() => setAssignTarget(null)}
          onAssign={(userId, planId) => assignMutation.mutateAsync({ userId, planId })}
        />
      )}
    </div>
  )
}
