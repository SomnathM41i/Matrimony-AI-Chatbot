import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Eye, Shield, ShieldOff } from 'lucide-react'
import DataTable from '../../components/admin/DataTable'
import { getProfiles, updateProfileStatus } from '../../services/adminService'

const STATUS_COLORS = {
  Active: 'text-green-400 bg-green-500/10',
  Paid: 'text-blue-400 bg-blue-500/10',
  Banned: 'text-red-400 bg-red-500/10',
  Inactive: 'text-amber-400 bg-amber-500/10',
}

export default function AdminProfiles() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ gender: '', status: '', caste: '', city: '' })
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['admin-profiles', page, search, filters],
    queryFn: () => getProfiles(page, { search, ...filters }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ matri_id, status }) => updateProfileStatus(matri_id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-profiles'] })
      toast.success('Profile status updated')
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Failed to update status'),
  })

  const toggleStatus = (profile) => {
    const newStatus = profile.Status === 'Active' ? 'Banned' : 'Active'
    statusMutation.mutate({ matri_id: profile.MatriID, status: newStatus })
  }

  const columns = [
    { key: 'MatriID', label: 'Matri ID' },
    { key: 'Name', label: 'Name' },
    { key: 'Age', label: 'Age' },
    { key: 'Gender', label: 'Gender' },
    { key: 'City', label: 'City' },
    { key: 'Caste', label: 'Caste' },
    { key: 'Religion', label: 'Religion' },
    { key: 'Maritalstatus', label: 'Marital Status' },
    {
      key: 'Status',
      label: 'Status',
      render: (val, row) => (
        <button
          onClick={() => toggleStatus(row)}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[val] || 'text-surface-400 bg-surface-700'}`}
        >
          {val === 'Active' ? <Shield className="w-3 h-3" /> : <ShieldOff className="w-3 h-3" />}
          {val}
        </button>
      ),
    },
    { key: 'Occupation', label: 'Occupation' },
    { key: 'Mobile', label: 'Mobile' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">Matrimony Profiles</h1>
        <p className="text-sm text-surface-500 mt-1">Browse member profiles and manage status</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={filters.gender}
          onChange={(e) => setFilters(f => ({ ...f, gender: e.target.value }))}
          className="input w-auto min-w-[120px] py-2"
        >
          <option value="">All Genders</option>
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters(f => ({ ...f, status: e.target.value }))}
          className="input w-auto min-w-[120px] py-2"
        >
          <option value="">All Status</option>
          <option value="Active">Active</option>
          <option value="Paid">Paid</option>
          <option value="Banned">Banned</option>
          <option value="Inactive">Inactive</option>
        </select>
        <input
          type="text"
          value={filters.caste}
          onChange={(e) => setFilters(f => ({ ...f, caste: e.target.value }))}
          placeholder="Caste..."
          className="input w-auto min-w-[140px] py-2"
        />
        <input
          type="text"
          value={filters.city}
          onChange={(e) => setFilters(f => ({ ...f, city: e.target.value }))}
          placeholder="City..."
          className="input w-auto min-w-[140px] py-2"
        />
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
        searchPlaceholder="Search by name, ID, or mobile..."
      />
    </div>
  )
}
