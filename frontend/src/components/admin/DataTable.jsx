import { useState } from 'react'
import { ChevronLeft, ChevronRight, Search, Loader2 } from 'lucide-react'

export default function DataTable({
  columns,       // [{key, label, render?: (value, row) => JSX}]
  data,
  total,
  page,
  perPage,
  onPageChange,
  search,
  onSearch,
  loading,
  searchPlaceholder = 'Search...',
}) {
  const [searchInput, setSearchInput] = useState(search || '')

  const totalPages = Math.max(1, Math.ceil(total / perPage))

  const handleSearch = (e) => {
    e.preventDefault()
    onSearch?.(searchInput)
  }

  return (
    <div className="space-y-4">
      {onSearch && (
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={searchPlaceholder}
              className="input pl-10"
            />
          </div>
          <button type="submit" className="btn-primary text-sm px-4 py-2">Search</button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearchInput(''); onSearch?.('') }}
              className="btn-ghost text-sm"
            >
              Clear
            </button>
          )}
        </form>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-800 bg-surface-900/50">
                {columns.map((col) => (
                  <th key={col.key} className="text-left px-4 py-3 text-xs font-medium text-surface-400 uppercase tracking-wider whitespace-nowrap">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-surface-500" />
                  </td>
                </tr>
              ) : data.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-12 text-center text-surface-500">
                    No data found
                  </td>
                </tr>
              ) : (
                data.map((row, i) => (
                  <tr key={row.id ?? i} className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors">
                    {columns.map((col) => (
                      <td key={col.key} className="px-4 py-3 text-surface-200 whitespace-nowrap">
                        {col.render ? col.render(row[col.key], row) : row[col.key] ?? '—'}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-surface-400">
        <span>
          Showing {Math.min((page - 1) * perPage + 1, total)}–{Math.min(page * perPage, total)} of {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange?.(page - 1)}
            disabled={page <= 1}
            className="btn-ghost p-1.5 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="tabular-nums">{page} / {totalPages}</span>
          <button
            onClick={() => onPageChange?.(page + 1)}
            disabled={page >= totalPages}
            className="btn-ghost p-1.5 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
