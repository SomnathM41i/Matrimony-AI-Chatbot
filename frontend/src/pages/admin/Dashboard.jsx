import { useQuery } from '@tanstack/react-query'
import { Users, UserCheck, UserX, CreditCard, Activity, Shield } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import StatsCard from '../../components/admin/StatsCard'
import { getAdminStats } from '../../services/adminService'

const COLORS = ['#6366f1', '#22c55e', '#ef4444', '#f59e0b']

export default function AdminDashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: getAdminStats,
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const pieData = [
    { name: 'Male', value: stats?.male_members || 0 },
    { name: 'Female', value: stats?.female_members || 0 },
  ]

  const barData = [
    { name: 'Total', value: stats?.total_members || 0 },
    { name: 'Active', value: stats?.active_members || 0 },
    { name: 'Paid', value: stats?.paid_members || 0 },
    { name: 'Banned', value: stats?.banned_members || 0 },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">Dashboard</h1>
        <p className="text-sm text-surface-500 mt-1">Overview of matrimony platform statistics</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Total Members" value={stats?.total_members?.toLocaleString()} icon={Users} color="primary" />
        <StatsCard label="Active" value={stats?.active_members?.toLocaleString()} icon={UserCheck} color="green" />
        <StatsCard label="Paid" value={stats?.paid_members?.toLocaleString()} icon={CreditCard} color="blue" />
        <StatsCard label="Banned" value={stats?.banned_members?.toLocaleString()} icon={UserX} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-5">
          <h2 className="text-sm font-medium text-surface-300 mb-4">Gender Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={4} dataKey="value" label={({ name, value }) => `${name}: ${value?.toLocaleString()}`}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="text-sm font-medium text-surface-300 mb-4">Member Status</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#e2e8f0' }} />
                <Bar dataKey="value" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard label="Membership Plans" value={stats?.membership_plans} icon={Shield} color="purple" />
        <StatsCard label="Success Stories" value={stats?.success_stories} icon={Activity} color="amber" />
        <StatsCard label="Male / Female" value={`${stats?.male_members || 0} / ${stats?.female_members || 0}`} icon={Users} color="blue" />
      </div>
    </div>
  )
}
