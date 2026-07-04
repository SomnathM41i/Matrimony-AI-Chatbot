import { createBrowserRouter, Navigate, useParams } from 'react-router-dom'
import AuthLayout from '../layouts/AuthLayout'
import ChatLayout from '../layouts/ChatLayout'
import Login from '../pages/Login'
import Landing from '../pages/Landing'
import Chat from '../pages/Chat'
import History from '../pages/History'

function Guard({ children }) {
  const token = localStorage.getItem('access_token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return children
}

function RedirectToAppChat() {
  const { conversationId } = useParams()
  const path = conversationId ? `/app/chat/${conversationId}` : '/app/chat'
  return <Navigate to={path} replace />
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout><Login /></AuthLayout>,
  },
  {
    path: '/',
    element: <Landing />,
  },
  {
    path: '/chat',
    element: <RedirectToAppChat />,
  },
  {
    path: '/chat/:conversationId',
    element: <RedirectToAppChat />,
  },
  {
    path: '/history',
    element: <Navigate to="/app/history" replace />,
  },
  {
    path: '/app',
    element: <Guard><ChatLayout /></Guard>,
    children: [
      { index: true, element: <Navigate to="/app/chat" replace /> },
      { path: 'chat', element: <Chat /> },
      { path: 'chat/:conversationId', element: <Chat /> },
      { path: 'history', element: <History /> },
    ],
  },
])
