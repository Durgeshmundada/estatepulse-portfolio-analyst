export type User = { id: string; name: string; city: string; preferences: string }
export type Conversation = { id: string; title: string; user_id: string; created_at: string; updated_at: string; needs_attention: boolean; user_name?: string }
export type Metric = { label: string; value: string }
export type Card = {
  type: 'summary' | 'properties' | 'comparison' | 'scenario' | 'change_review' | 'change_receipt'
  title: string
  [key: string]: unknown
}
export type Message = { id: string; role: 'user' | 'assistant'; text: string; cards: Card[]; created_at: string; request_id?: string }
export type Portfolio = { portfolio_version: number; card: Card; summary: Record<string, unknown>; properties: Record<string, unknown>[] }
export type AdminOverview = {
  metrics: { users: number; conversations: number; open_flags: number; model_p50_ms: number | null }
  users: Array<User & { property_count: number; conversation_count: number }>
  conversations: Conversation[]
  flags: Array<{ id: string; conversation_id: string; reason: string; detail: string; created_at: string }>
}
