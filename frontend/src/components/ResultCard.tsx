import { ArrowDownRight, ArrowRight, CheckCircle2, MapPin, SquareStack, TrendingUp } from 'lucide-react'
import type { Card } from '../types'

export default function ResultCard({ card, onConfirm, onCancel, readonly = false }: { card: Card; onConfirm?: (id: string) => void; onCancel?: (id: string) => void; readonly?: boolean }) {
  if (card.type === 'summary') {
    const metrics = card.metrics as Array<{ label: string; value: string }>
    return <section className="result-card summary-card"><header><div><span className="card-kicker">PORTFOLIO SNAPSHOT</span><h3>{card.title}</h3></div><span className="live-chip">Live</span></header><div className="metrics-grid">{metrics.map((m, i) => <div key={m.label} className={i === 0 ? 'featured-metric' : ''}><span>{m.label}</span><strong>{m.value}</strong>{i === 0 && <small><TrendingUp size={13} /> ownership-adjusted</small>}</div>)}</div>{card.rent_complete === false && <p className="data-note">Yield is unavailable because rent is unknown for part of this portfolio.</p>}</section>
  }
  if (card.type === 'properties') {
    const items = card.items as Array<Record<string, string>>
    return <section className="result-card"><header><div><span className="card-kicker">MATCHES</span><h3>{card.title}</h3></div><span className="count-chip">{items.length}</span></header><div className="property-list">{items.map(item => <article key={item.id}><div className="property-icon"><SquareStack size={18} /></div><div className="property-main"><strong>{item.location}</strong><span><MapPin size={12} /> {item.type} · {item.area}</span></div><div className="property-numbers"><strong>{item.value}</strong><span>{item.rent} rent</span></div></article>)}</div></section>
  }
  if (card.type === 'comparison') {
    const groups = card.groups as Array<Record<string, string | number>>
    const max = Math.max(...groups.map(g => typeof g.share === 'number' ? g.share : 100), 1)
    return <section className="result-card"><header><div><span className="card-kicker">COMPARISON</span><h3>{card.title}</h3></div></header><div className="comparison-list">{groups.map((group, i) => <div key={String(group.label)} className="comparison-row"><div><strong>{group.label}</strong><span>{group.value}</span></div>{typeof group.share === 'number' && <div className="bar-track"><div style={{ width: `${Number(group.share) / max * 100}%` }} className={i === 0 ? 'bar primary-bar' : 'bar'} /></div>}<div className="compare-foot"><span>{group.share !== undefined ? `${group.share}%` : String(group.rent ?? '')}</span>{group.yield && <span>{group.yield} yield</span>}</div></div>)}</div></section>
  }
  if (card.type === 'scenario') return <section className="result-card scenario-card"><header><div><span className="card-kicker">WHAT-IF MODEL</span><h3>{card.title}</h3></div><span className="scenario-chip">Hypothetical</span></header><div className="scenario-flow"><div><span>Actual baseline</span><strong>{String(card.baseline)}</strong></div><ArrowRight /><div><span>Scenario value</span><strong>{String(card.scenario)}</strong></div></div><div className="delta"><ArrowDownRight size={16} /> Change: {String(card.delta)}</div><p className="data-note">Your actual portfolio has not been modified.</p></section>
  if (card.type === 'change_review') {
    const after = card.after as Record<string, unknown>
    const changeId = String(card.change_id)
    const pending = card.status === 'PENDING'
    return <section className="result-card review-card"><header><div><span className="card-kicker">{pending ? 'CONFIRMATION REQUIRED' : 'CHANGE REVIEWED'}</span><h3>{card.title}</h3></div><span className="review-chip">{String(card.status)}</span></header><div className="review-fields"><div><span>Operation</span><strong>{String(card.operation)}</strong></div><div><span>Property</span><strong>{String(after.location ?? after.id ?? 'New property')}</strong></div><div><span>New value</span><strong>{after.current_value_inr ? `₹${Number(after.current_value_inr).toLocaleString('en-IN')}` : '—'}</strong></div><div><span>Ownership</span><strong>{String(after.ownership_percent ?? 100)}%</strong></div></div>{!readonly && pending && <div className="review-actions"><button className="secondary" onClick={() => onCancel?.(changeId)}>Cancel</button><button className="primary" onClick={() => onConfirm?.(changeId)}>Confirm & save</button></div>}<p className="data-note">{pending ? 'No actual data changes until you confirm.' : 'This review is complete.'}</p></section>
  }
  return <section className="result-card receipt-card"><CheckCircle2 /><div><span className="card-kicker">CHANGE SAVED</span><h3>{card.title}</h3><p>Portfolio value: <strong>{String(card.portfolio_value ?? '')}</strong></p></div></section>
}
