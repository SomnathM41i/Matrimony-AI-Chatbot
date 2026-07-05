import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../../app/store'

export default function AdminGuard({ children }) {
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (!user || user.role !== 'admin') {
    return <Navigate to="/app/chat" replace />
  }

  return children
}
