import { useEffect, useState } from 'react'
import { ArrowRight, Building2, ChartNoAxesCombined, MessageCircleMore, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import type { User } from '../types'

export default function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [users, setUsers] = useState<User[]>([])
  const [selected, setSelected] = useState('')
  const [code, setCode] = useState('demo')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.users().then(r => { setUsers(r.items); setSelected(r.items[0]?.id ?? '') }).catch(e => setError(e.message)) }, [])
  const submit = async () => {
    setBusy(true); setError('')
    try { onLogin((await api.signIn(selected, code)).user) } catch (e) { setError(e instanceof Error ? e.message : 'Unable to sign in') } finally { setBusy(false) }
  }
  return <main className="login-shell">
    <section className="login-story">
      <div className="wordmark light"><span className="brand-mark small">A</span> ASTRA</div>
      <div className="story-copy"><p className="eyebrow">REAL ESTATE INTELLIGENCE</p><h1>Your portfolio,<br /><em>in conversation.</em></h1><p>Ask better questions. Model what-if scenarios. Make every property decision with clarity.</p></div>
      <div className="feature-row"><span><MessageCircleMore /> Natural conversations</span><span><ChartNoAxesCombined /> Exact analytics</span><span><ShieldCheck /> Safe scenarios</span></div>
      <div className="architectural-art" aria-hidden="true"><div /><div /><div /></div>
    </section>
    <section className="login-panel">
      <div className="login-card">
        <div className="login-icon"><Building2 /></div>
        <p className="eyebrow green">DEMO PORTFOLIO</p>
        <h2>Welcome to ASTRA</h2>
        <p className="muted">Choose a synthetic portfolio to explore the analyst.</p>
        <label>Portfolio owner<select value={selected} onChange={e => setSelected(e.target.value)}>{users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.city}</option>)}</select></label>
        <label>Access code<input value={code} onChange={e => setCode(e.target.value)} type="password" placeholder="Enter demo code" onKeyDown={e => e.key === 'Enter' && submit()} /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary wide" onClick={submit} disabled={!selected || busy}>{busy ? 'Opening portfolio…' : <>Open portfolio <ArrowRight size={17} /></>}</button>
        <p className="privacy"><ShieldCheck size={14} /> Synthetic data · Secure demo environment</p>
      </div>
    </section>
  </main>
}
