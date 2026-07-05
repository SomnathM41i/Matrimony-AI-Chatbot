export default function StatsCard({ label, value, icon: Icon, color = 'primary' }) {
  const colorMap = {
    primary: 'from-primary-600/20 to-primary-600/5 text-primary-300 border-primary-500/20',
    green: 'from-green-600/20 to-green-600/5 text-green-300 border-green-500/20',
    blue: 'from-blue-600/20 to-blue-600/5 text-blue-300 border-blue-500/20',
    purple: 'from-purple-600/20 to-purple-600/5 text-purple-300 border-purple-500/20',
    amber: 'from-amber-600/20 to-amber-600/5 text-amber-300 border-amber-500/20',
    red: 'from-red-600/20 to-red-600/5 text-red-300 border-red-500/20',
  }

  return (
    <div className={`card p-5 bg-gradient-to-br ${colorMap[color] || colorMap.primary}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider opacity-70">{label}</p>
          <p className="text-2xl font-bold mt-1 tabular-nums">{value ?? '—'}</p>
        </div>
        {Icon && <Icon className="w-8 h-8 opacity-50" />}
      </div>
    </div>
  )
}
