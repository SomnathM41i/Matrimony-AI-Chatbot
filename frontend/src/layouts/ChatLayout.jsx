import { Outlet } from 'react-router-dom'
import Sidebar from '../components/ui/Sidebar'

export default function ChatLayout() {
  return (
    <div className="h-screen flex bg-surface-950 overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
