import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, Clock3, MessageSquareText, Search, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, setAdminToken, type AgentEvent } from '../api'
import ResultCard from '../components/ResultCard'
import type { AdminOverview, Message } from '../types'

export default function AdminPage() {
  const [token, setToken] = useState('admin-demo')
  const [data, setData] = useState<AdminOverview | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<{ messages: Message[]; events: AgentEvent[] } | null>(null)
  const [error, setError] = useState('')
  const load = async () => { setAdminToken(token); setError(''); try { setData(await api.adminOverview()) } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load dashboard') } }
  useEffect(() => {
    setAdminToken('admin-demo')
    api.adminOverview().then(setData).catch(e => setError(e instanceof Error ? e.message : 'Unable to load dashboard'))
  }, [])
  const inspect = async (id: string) => { setSelected(id); setDetail(await api.adminConversation(id)) }
  return <main className="admin-shell">
    <header className="admin-header"><Link to="/chat" className="wordmark"><span className="brand-mark small">E</span> EstatePulse <span className="admin-tag">BUSINESS</span></Link><div className="admin-auth"><input value={token} onChange={e => setToken(e.target.value)} type="password" placeholder="Admin token" /><button className="secondary" onClick={load}>Connect</button></div></header>
    <section className="admin-content">
      <div className="page-heading"><div><p className="eyebrow green">OPERATIONS OVERVIEW</p><h1>Conversation intelligence</h1><p>Monitor portfolio conversations, agent activity, and requests that need attention.</p></div><div className="last-updated"><span className="status-dot" /> Live system</div></div>
      {error && <div className="inline-error">{error}</div>}
      {data && <><div className="metric-cards"><article><Users /><span>Demo users</span><strong>{data.metrics.users}</strong></article><article><MessageSquareText /><span>Conversations</span><strong>{data.metrics.conversations}</strong></article><article className={data.metrics.open_flags ? 'warning' : ''}><AlertTriangle /><span>Needs attention</span><strong>{data.metrics.open_flags}</strong></article><article><Clock3 /><span>Model median</span><strong>{data.metrics.model_p50_ms ?? '—'}<small> ms</small></strong></article></div>
      <div className="admin-grid"><section className="admin-card conversation-table"><header><div><h2>Recent conversations</h2><p>Latest customer interactions and status</p></div><Search size={18} /></header><div className="table-head"><span>User</span><span>Conversation</span><span>Status</span><span>Updated</span></div>{data.conversations.length ? data.conversations.map(c => <button key={c.id} onClick={() => inspect(c.id)} className={selected === c.id ? 'selected' : ''}><span><strong>{c.user_name}</strong><small>{c.user_id}</small></span><span>{c.title}</span><span className={c.needs_attention ? 'status warning-text' : 'status'}>{c.needs_attention ? <><AlertTriangle size={13} /> Attention</> : <><CheckCircle2 size={13} /> Healthy</>}</span><time>{new Date(c.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time></button>) : <div className="empty-admin">No conversations yet. Start in the chat view.</div>}</section>
      <section className="admin-card attention-panel"><header><div><h2>Attention queue</h2><p>Items requiring review</p></div><span className="count-chip">{data.flags.length}</span></header>{data.flags.length ? data.flags.map(f => <article key={f.id}><AlertTriangle /><div><strong>{f.reason.replaceAll('_', ' ')}</strong><p>{f.detail}</p><small>{new Date(f.created_at).toLocaleString()}</small></div><button onClick={async () => { await api.resolveFlag(f.id); await load() }}>Resolve</button></article>) : <div className="all-clear"><CheckCircle2 /><strong>All clear</strong><span>No conversations need attention.</span></div>}</section></div></>}
      {detail && <section className="inspector"><header><button className="icon-button" onClick={() => { setDetail(null); setSelected(null) }}><ArrowLeft /></button><div><p className="eyebrow green">CONVERSATION INSPECTOR</p><h2>Messages & agent activity</h2></div></header><div className="inspector-grid"><div className="transcript">{detail.messages.map(m => <div className={`inspect-message ${m.role}`} key={m.id}><strong>{m.role === 'assistant' ? 'EstatePulse' : 'User'}</strong><p>{m.text}</p>{m.cards.map((c, i) => <ResultCard key={i} card={c} readonly />)}</div>)}</div><div className="event-timeline"><h3><Activity size={17} /> Agent timeline</h3>{detail.events.map(e => <article key={e.id}><div className={`event-dot ${e.success ? '' : 'failed'}`} /><div><strong>{e.kind} · {e.name}</strong><span>{e.duration_ms} ms · {e.success ? 'Succeeded' : 'Fallback used'}</span><details><summary>Inspect payload</summary><pre>{JSON.stringify({ input: e.input, output: e.output, error: e.error }, null, 2)}</pre></details></div></article>)}</div></div></section>}
    </section>
  </main>
}
