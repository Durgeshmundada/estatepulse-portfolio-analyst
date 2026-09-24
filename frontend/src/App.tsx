import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api'
import type { User } from './types'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'
import LoginPage from './pages/LoginPage'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.session().then(r => setUser(r.user)).catch(() => setUser(null)).finally(() => setLoading(false)) }, [])
  if (loading) return <div className="splash"><div className="brand-mark">A</div><span>Preparing your portfolio…</span></div>
  return <Routes>
    <Route path="/login" element={user ? <Navigate to="/chat" /> : <LoginPage onLogin={setUser} />} />
    <Route path="/chat" element={user ? <ChatPage user={user} onLogout={() => setUser(null)} /> : <Navigate to="/login" />} />
    <Route path="/admin" element={<AdminPage />} />
    <Route path="*" element={<Navigate to={user ? '/chat' : '/login'} />} />
  </Routes>
}
