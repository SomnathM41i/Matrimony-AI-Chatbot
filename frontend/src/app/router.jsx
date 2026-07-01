import { createBrowserRouter, Navigate } from 'react-router-dom'
import AuthLayout from '../layouts/AuthLayout'
import ChatLayout from '../layouts/ChatLayout'
import Login from '../pages/Login'
import Chat from '../pages/Chat'
import History from '../pages/History'

function Guard({ children }) {
  const token = localStorage.getItem('access_token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return children
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout><Login /></AuthLayout>,
  },
  {
    path: '/',
    element: <Guard><ChatLayout /></Guard>,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: 'chat', element: <Chat /> },
      { path: 'chat/:conversationId', element: <Chat /> },
      { path: 'history', element: <History /> },
    ],
  },
])
