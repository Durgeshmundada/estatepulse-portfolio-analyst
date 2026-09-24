import { useEffect, useRef, useState } from 'react'
import { BarChart3, Building2, ChevronDown, LogOut, Menu, MessageSquarePlus, MoreHorizontal, PanelLeftClose, Send, Sparkles, Trash2, UserRoundCog, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import ResultCard from '../components/ResultCard'
import type { Conversation, Message, Portfolio, User } from '../types'

const starters = ['What does my portfolio look like?', 'How much of my portfolio is retail?', 'Which property has the highest rental yield?', 'What if I exclude my Bandra property?']

function ChatBubble({ message, onConfirm, onCancel }: { message: Message; onConfirm: (id: string) => void; onCancel: (id: string) => void }) {
  return <div className={`message-row ${message.role}`}>
    {message.role === 'assistant' && <div className="avatar">E</div>}
    <div className="message-stack"><div className="bubble">{message.text}</div>{message.cards.map((card, i) => <ResultCard key={`${message.id}-${i}`} card={card} onConfirm={onConfirm} onCancel={onCancel} />)}<time>{new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div>
  </div>
}

export default function ChatPage({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [active, setActive] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')
  const [error, setError] = useState('')
  const [sidebar, setSidebar] = useState(true)
  const [profileMenu, setProfileMenu] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  const refreshList = async () => { const list = (await api.conversations()).items; setConversations(list); return list }
  const loadConversation = async (id: string) => { setActive(id); setError(''); setMessages((await api.conversation(id)).messages) }
  const newConversation = async () => { const created = await api.createConversation(); await refreshList(); await loadConversation(created.id) }
  useEffect(() => {
    Promise.all([refreshList(), api.portfolio()]).then(async ([list, data]) => { setPortfolio(data); if (list[0]) await loadConversation(list[0].id) }).catch(e => setError(e.message))
  }, [])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])

  const send = async (preset?: string) => {
    const value = (preset ?? text).trim(); if (!value || busy) return
    setBusy(true); setError(''); setText('')
    setStreaming(false); setStreamStatus('Reading your portfolio…')
    try {
      let id = active
      if (!id) { const created = await api.createConversation(); id = created.id; setActive(id) }
      const optimistic: Message = { id: crypto.randomUUID(), role: 'user', text: value, cards: [], created_at: new Date().toISOString() }
      setMessages(old => [...old, optimistic])
      const draftId = crypto.randomUUID()
      let receivedDelta = false
      const result = await api.sendStream(id, value, {
        onStatus: setStreamStatus,
        onDelta: delta => {
          if (!receivedDelta) {
            receivedDelta = true
            setStreaming(true)
            setMessages(old => [...old, { id: draftId, role: 'assistant', text: delta, cards: [], created_at: new Date().toISOString() }])
          } else {
            setMessages(old => old.map(message => message.id === draftId ? { ...message, text: message.text + delta } : message))
          }
        },
      })
      setMessages(old => receivedDelta ? old.map(message => message.id === draftId ? result.message : message) : [...old, result.message])
      void refreshList().catch(e => setError(e instanceof Error ? e.message : 'Unable to refresh conversations'))
    } catch (e) { setError(e instanceof Error ? e.message : 'Message failed') } finally { setBusy(false); setStreaming(false); setStreamStatus('') }
  }
  const confirm = async (id: string) => { setBusy(true); try { const r = await api.confirm(id); setMessages(old => [...old.map(message => ({ ...message, cards: message.cards.map(card => card.type === 'change_review' && card.change_id === id ? { ...card, status: 'CONFIRMED' } : card) })), { id: crypto.randomUUID(), role: 'user', text: 'Confirm change', cards: [], created_at: new Date().toISOString() }, r.message]); setPortfolio(await api.portfolio()) } catch (e) { setError(e instanceof Error ? e.message : 'Confirmation failed') } finally { setBusy(false) } }
  const cancel = async (id: string) => { try { await api.cancel(id); setMessages(old => [...old, { id: crypto.randomUUID(), role: 'assistant', text: 'Change cancelled. Your actual portfolio remains unchanged.', cards: [], created_at: new Date().toISOString() }]) } catch (e) { setError(e instanceof Error ? e.message : 'Cancellation failed') } }
  const switchPortfolio = () => { setProfileMenu(false); api.signOut().finally(onLogout) }
  const deleteConversation = async () => {
    if (!deleteTarget || deleting) return
    setDeleting(true); setError('')
    try {
      await api.deleteConversation(deleteTarget.id)
      const removedActive = active === deleteTarget.id
      const list = await refreshList()
      if (removedActive) {
        setActive(null); setMessages([])
        if (list[0]) await loadConversation(list[0].id)
      }
      setDeleteTarget(null)
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to delete conversation') } finally { setDeleting(false) }
  }

  return <main className="app-shell">
    <aside className={`sidebar ${sidebar ? '' : 'collapsed'}`}>
      <div className="sidebar-head"><div className="wordmark"><span className="brand-mark small">E</span><span>EstatePulse</span></div><button className="icon-button" onClick={() => setSidebar(false)} aria-label="Close sidebar"><PanelLeftClose size={18} /></button></div>
      <button className="new-chat" onClick={newConversation}><MessageSquarePlus size={17} /> New analysis</button>
      <div className="nav-label">CONVERSATIONS</div>
      <nav className="conversation-list">{conversations.map(item => <div key={item.id} className={`conversation-row ${active === item.id ? 'active' : ''}`}><button className="conversation-open" onClick={() => loadConversation(item.id)}><span>{item.title}</span><small>{new Date(item.updated_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</small></button><button className="delete-chat" onClick={() => setDeleteTarget(item)} aria-label={`Delete ${item.title}`} title="Delete conversation" disabled={busy}><Trash2 size={14} /></button></div>)}</nav>
      <div className="sidebar-bottom"><Link to="/admin"><BarChart3 size={17} /> Business dashboard</Link><button onClick={switchPortfolio}><LogOut size={17} /> Switch portfolio</button></div>
    </aside>
    <section className="chat-workspace">
      <header className="chat-header"><div className="header-left">{!sidebar && <button className="icon-button" onClick={() => setSidebar(true)}><Menu size={20} /></button>}<div><div className="agent-title"><span className="status-dot" /> EstatePulse <span>Portfolio Analyst</span></div><small>Grounded in your portfolio data</small></div></div><div className="profile-menu-wrap"><button className="user-pill" onClick={() => setProfileMenu(open => !open)} aria-expanded={profileMenu} aria-haspopup="menu"><div className="user-initials">{user.name.split(' ').map(x => x[0]).join('')}</div><div><strong>{user.name}</strong><span>{user.city}</span></div><ChevronDown size={15} className={profileMenu ? 'rotated' : ''} /></button>{profileMenu && <div className="profile-menu" role="menu"><div><UserRoundCog size={16} /><span><strong>Demo portfolio</strong><small>{user.name} · {user.id}</small></span></div><button onClick={switchPortfolio} role="menuitem"><LogOut size={16} /> Switch portfolio</button></div>}</div></header>
      <div className="actual-strip"><div><Building2 size={17} /><span>Actual portfolio</span></div><strong>{portfolio ? String((portfolio.card.metrics as Array<{ value: string }>)[0]?.value) : '—'}</strong><span>{portfolio ? `${String(portfolio.summary.property_count)} properties` : ''}</span></div>
      <div className="chat-scroll">
        {!messages.length && <div className="welcome"><div className="welcome-orbit"><span className="brand-mark">E</span></div><p className="eyebrow green">YOUR PORTFOLIO ANALYST</p><h1>Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, {user.name.split(' ')[0]}.</h1><p>I can analyse your holdings, compare exposure, model scenarios, or prepare property updates.</p><div className="starter-grid">{starters.map(item => <button key={item} onClick={() => send(item)}><Sparkles size={15} /><span>{item}</span><MoreHorizontal size={15} /></button>)}</div></div>}
        <div className="messages">{messages.map(m => <ChatBubble key={m.id} message={m} onConfirm={confirm} onCancel={cancel} />)}{busy && !streaming && <div className="message-row assistant"><div className="avatar">E</div><div className="typing"><i /><i /><i />{streamStatus && <span>{streamStatus}</span>}</div></div>}{error && <div className="inline-error">{error}</div>}<div ref={bottom} /></div>
      </div>
      <footer className="composer-wrap"><div className="composer"><textarea value={text} onChange={e => setText(e.target.value)} placeholder="Ask about your portfolio…" rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} /><button onClick={() => send()} disabled={!text.trim() || busy} aria-label="Send"><Send size={18} /></button></div><small>EstatePulse uses your recorded portfolio data. Financial outputs are descriptive, not investment advice.</small></footer>
    </section>
    {deleteTarget && <div className="modal-backdrop" role="presentation" onMouseDown={event => event.target === event.currentTarget && setDeleteTarget(null)}><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title"><button className="dialog-close" onClick={() => setDeleteTarget(null)} aria-label="Close"><X size={18} /></button><div className="danger-icon"><Trash2 size={20} /></div><p className="eyebrow danger">DELETE CONVERSATION</p><h2 id="delete-title">Delete this analysis?</h2><p>“{deleteTarget.title}” and its messages will be permanently removed. Your property portfolio will not be changed.</p><div><button className="secondary" onClick={() => setDeleteTarget(null)} disabled={deleting}>Keep conversation</button><button className="danger-button" onClick={deleteConversation} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete conversation'}</button></div></section></div>}
  </main>
}
