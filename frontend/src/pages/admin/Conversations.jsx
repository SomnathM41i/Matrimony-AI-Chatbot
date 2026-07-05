import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, User, ChevronDown, ChevronUp } from 'lucide-react'
import DataTable from '../../components/admin/DataTable'
import { getConversations, getConversationDetail } from '../../services/adminService'

export default function AdminConversations() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [selectedConv, setSelectedConv] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-conversations', page, search],
    queryFn: () => getConversations(page, search),
  })

  const { data: convDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['admin-conversation', selectedConv],
    queryFn: () => getConversationDetail(selectedConv),
    enabled: !!selectedConv,
  })

  const columns = [
    { key: 'id', label: 'ID' },
    {
      key: 'title',
      label: 'Title',
      render: (val) => (
        <span className="flex items-center gap-2">
          <MessageSquare className="w-3.5 h-3.5 text-surface-500 shrink-0" />
          {val || 'Untitled'}
        </span>
      ),
    },
    { key: 'user_name', label: 'User' },
    { key: 'user_email', label: 'Email' },
    { key: 'message_count', label: 'Messages' },
    {
      key: 'updated_at',
      label: 'Last Active',
      render: (val) => val ? new Date(val).toLocaleString() : '—',
    },
    {
      key: 'id',
      label: '',
      render: (_, row) => (
        <button
          onClick={() => setSelectedConv(selectedConv === row.id ? null : row.id)}
          className="btn-ghost p-1"
        >
          {selectedConv === row.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-surface-100">Chat Monitoring</h1>
        <p className="text-sm text-surface-500 mt-1">View all user conversations</p>
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
        searchPlaceholder="Search by user name, email, or conversation title..."
      />

      {selectedConv && (
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-surface-300 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Conversation #{selectedConv}
            </h2>
            <button onClick={() => setSelectedConv(null)} className="text-xs text-surface-500 hover:text-surface-300 cursor-pointer">
              Close
            </button>
          </div>

          {detailLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {convDetail?.messages?.map((msg) => (
                <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? '' : 'flex-row-reverse'}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                    msg.role === 'user' ? 'bg-primary-600/20' : 'bg-green-600/20'
                  }`}>
                    <User className={`w-3.5 h-3.5 ${msg.role === 'user' ? 'text-primary-300' : 'text-green-300'}`} />
                  </div>
                  <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
                    msg.role === 'user'
                      ? 'bg-primary-600/10 text-surface-200'
                      : 'bg-surface-800 text-surface-200'
                  }`}>
                    <p className="text-xs text-surface-500 mb-1">{msg.role}</p>
                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                    <p className="text-xs text-surface-500 mt-1">
                      {msg.created_at ? new Date(msg.created_at).toLocaleString() : ''}
                    </p>
                  </div>
                </div>
              ))}
              {(!convDetail?.messages || convDetail.messages.length === 0) && (
                <p className="text-center text-surface-500 py-4">No messages in this conversation</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
