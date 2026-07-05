import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Shield, ShieldOff, Trash2, CheckCircle, XCircle } from 'lucide-react'
import DataTable from '../../components/admin/DataTable'
import { getUsers, updateUser, deleteUser } from '../../services/adminService'

export default function AdminUsers() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, search],
    queryFn: () => getUsers(page, search),
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
        <button
          onClick={() => { if (confirm('Delete this user and all their conversations?')) deleteMutation.mutate(row.id) }}
          className="btn-ghost p-1 text-surface-500 hover:text-red-400"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">App Users</h1>
        <p className="text-sm text-surface-500 mt-1">Manage platform users, roles, and access</p>
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
    </div>
  )
}
