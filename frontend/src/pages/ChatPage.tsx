import { useEffect, useRef, useState } from 'react'
import { BarChart3, Building2, ChevronDown, LogOut, Menu, MessageSquarePlus, MoreHorizontal, PanelLeftClose, Send, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import ResultCard from '../components/ResultCard'
import type { Conversation, Message, Portfolio, User } from '../types'

const starters = ['What does my portfolio look like?', 'How much of my portfolio is retail?', 'Which property has the highest rental yield?', 'What if I exclude my Bandra property?']

function ChatBubble({ message, onConfirm, onCancel }: { message: Message; onConfirm: (id: string) => void; onCancel: (id: string) => void }) {
  return <div className={`message-row ${message.role}`}>
    {message.role === 'assistant' && <div className="avatar">A</div>}
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
  const [error, setError] = useState('')
  const [sidebar, setSidebar] = useState(true)
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
    try {
      let id = active
      if (!id) { const created = await api.createConversation(); id = created.id; setActive(id) }
      const optimistic: Message = { id: crypto.randomUUID(), role: 'user', text: value, cards: [], created_at: new Date().toISOString() }
      setMessages(old => [...old, optimistic])
      const result = await api.send(id, value)
      setMessages(old => [...old, result.message])
      await Promise.all([refreshList(), api.portfolio().then(setPortfolio)])
    } catch (e) { setError(e instanceof Error ? e.message : 'Message failed') } finally { setBusy(false) }
  }
  const confirm = async (id: string) => { setBusy(true); try { const r = await api.confirm(id); setMessages(old => [...old.map(message => ({ ...message, cards: message.cards.map(card => card.type === 'change_review' && card.change_id === id ? { ...card, status: 'CONFIRMED' } : card) })), { id: crypto.randomUUID(), role: 'user', text: 'Confirm change', cards: [], created_at: new Date().toISOString() }, r.message]); setPortfolio(await api.portfolio()) } catch (e) { setError(e instanceof Error ? e.message : 'Confirmation failed') } finally { setBusy(false) } }
  const cancel = async (id: string) => { try { await api.cancel(id); setMessages(old => [...old, { id: crypto.randomUUID(), role: 'assistant', text: 'Change cancelled. Your actual portfolio remains unchanged.', cards: [], created_at: new Date().toISOString() }]) } catch (e) { setError(e instanceof Error ? e.message : 'Cancellation failed') } }

  return <main className="app-shell">
    <aside className={`sidebar ${sidebar ? '' : 'collapsed'}`}>
      <div className="sidebar-head"><div className="wordmark"><span className="brand-mark small">A</span><span>ASTRA</span></div><button className="icon-button" onClick={() => setSidebar(false)} aria-label="Close sidebar"><PanelLeftClose size={18} /></button></div>
      <button className="new-chat" onClick={newConversation}><MessageSquarePlus size={17} /> New analysis</button>
      <div className="nav-label">CONVERSATIONS</div>
      <nav className="conversation-list">{conversations.map(item => <button key={item.id} className={active === item.id ? 'active' : ''} onClick={() => loadConversation(item.id)}><span>{item.title}</span><small>{new Date(item.updated_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</small></button>)}</nav>
      <div className="sidebar-bottom"><Link to="/admin"><BarChart3 size={17} /> Business dashboard</Link><button onClick={onLogout}><LogOut size={17} /> Switch portfolio</button></div>
    </aside>
    <section className="chat-workspace">
      <header className="chat-header"><div className="header-left">{!sidebar && <button className="icon-button" onClick={() => setSidebar(true)}><Menu size={20} /></button>}<div><div className="agent-title"><span className="status-dot" /> ASTRA <span>Portfolio Analyst</span></div><small>Grounded in your portfolio data</small></div></div><div className="user-pill"><div className="user-initials">{user.name.split(' ').map(x => x[0]).join('')}</div><div><strong>{user.name}</strong><span>{user.city}</span></div><ChevronDown size={15} /></div></header>
      <div className="actual-strip"><div><Building2 size={17} /><span>Actual portfolio</span></div><strong>{portfolio ? String((portfolio.card.metrics as Array<{ value: string }>)[0]?.value) : '—'}</strong><span>{portfolio ? `${String(portfolio.summary.property_count)} properties` : ''}</span></div>
      <div className="chat-scroll">
        {!messages.length && <div className="welcome"><div className="welcome-orbit"><span className="brand-mark">A</span></div><p className="eyebrow green">YOUR PORTFOLIO ANALYST</p><h1>Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, {user.name.split(' ')[0]}.</h1><p>I can analyse your holdings, compare exposure, model scenarios, or prepare property updates.</p><div className="starter-grid">{starters.map(item => <button key={item} onClick={() => send(item)}><Sparkles size={15} /><span>{item}</span><MoreHorizontal size={15} /></button>)}</div></div>}
        <div className="messages">{messages.map(m => <ChatBubble key={m.id} message={m} onConfirm={confirm} onCancel={cancel} />)}{busy && <div className="message-row assistant"><div className="avatar">A</div><div className="typing"><i /><i /><i /></div></div>}{error && <div className="inline-error">{error}</div>}<div ref={bottom} /></div>
      </div>
      <footer className="composer-wrap"><div className="composer"><textarea value={text} onChange={e => setText(e.target.value)} placeholder="Ask about your portfolio…" rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} /><button onClick={() => send()} disabled={!text.trim() || busy} aria-label="Send"><Send size={18} /></button></div><small>ASTRA uses your recorded portfolio data. Financial outputs are descriptive, not investment advice.</small></footer>
    </section>
  </main>
}
