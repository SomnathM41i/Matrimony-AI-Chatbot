import { lazy, Suspense, useEffect } from 'react'
import { createBrowserRouter, Navigate, useParams, useNavigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { setNavigate } from '../services/navigate'
import ErrorBoundary from '../components/ErrorBoundary'
import AuthLayout from '../layouts/AuthLayout'
import ChatLayout from '../layouts/ChatLayout'
import AdminLayout from '../layouts/AdminLayout'
import AdminGuard from '../components/admin/AdminGuard'
import { useAuthStore } from './store'

const Login = lazy(() => import('../pages/Login'))
const Landing = lazy(() => import('../pages/Landing'))
const Chat = lazy(() => import('../pages/Chat'))
const History = lazy(() => import('../pages/History'))
const PartnerPreferences = lazy(() => import('../pages/PartnerPreferences'))
const Plans = lazy(() => import('../pages/Plans'))
const AdminDashboard = lazy(() => import('../pages/admin/Dashboard'))
const AdminUsers = lazy(() => import('../pages/admin/Users'))
const AdminProfiles = lazy(() => import('../pages/admin/Profiles'))
const AdminConversations = lazy(() => import('../pages/admin/Conversations'))
const CommercialAI = lazy(() => import('../pages/admin/CommercialAI'))

function loadPage(element) {
  return <Suspense fallback={<div className="min-h-[12rem] flex items-center justify-center text-surface-400">Loading…</div>}>{element}</Suspense>
}


function NavigateSetter() {
  const navigate = useNavigate()
  useEffect(() => { setNavigate(navigate) }, [navigate])
  return <Outlet />
}

function Guard({ children }) {
  const token = useAuthStore.getState().token
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
    element: <><Toaster position="top-right" toastOptions={{ className: '!bg-surface-800 !text-surface-200 !border !border-surface-700 !text-sm' }} /><ErrorBoundary><NavigateSetter /></ErrorBoundary></>,
    children: [
      {
        path: '/login',
        element: <AuthLayout>{loadPage(<Login />)}</AuthLayout>,
      },
      {
        path: '/register',
        element: <Navigate to="/login" replace />,
      },
      {
        path: '/',
        element: loadPage(<Landing />),
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
          { path: 'chat', element: loadPage(<Chat />) },
          { path: 'chat/:conversationId', element: loadPage(<Chat />) },
          { path: 'history', element: loadPage(<History />) },
          { path: 'partner-preferences', element: loadPage(<PartnerPreferences />) },
          { path: 'plans', element: loadPage(<Plans />) },
        ],
      },
      {
        path: '/admin',
        element: <AdminGuard><AdminLayout /></AdminGuard>,
        children: [
          { index: true, element: loadPage(<AdminDashboard />) },
          { path: 'users', element: loadPage(<AdminUsers />) },
          { path: 'profiles', element: loadPage(<AdminProfiles />) },
          { path: 'conversations', element: loadPage(<AdminConversations />) },
          { path: 'commercial-ai', element: loadPage(<CommercialAI />) },
        ],
      },
    ],
  },
])
