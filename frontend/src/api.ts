import type { AdminOverview, Conversation, Message, Portfolio, User } from './types'

let adminToken = ''
export const setAdminToken = (value: string) => { adminToken = value }

async function request<T>(path: string, options: RequestInit = {}, admin = false): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    ...options,
    headers: { 'Content-Type': 'application/json', ...(admin && adminToken ? { 'X-Admin-Token': adminToken } : {}), ...options.headers },
  })
  if (!response.ok) {
    let message = 'Something went wrong'
    try { message = (await response.json()).detail ?? message } catch { /* keep safe message */ }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  users: () => request<{ items: User[] }>('/api/demo/users'),
  session: () => request<{ user: User }>('/api/session'),
  signIn: (user_id: string, access_code: string) => request<{ user: User }>('/api/session', { method: 'POST', body: JSON.stringify({ user_id, access_code }) }),
  signOut: () => request<void>('/api/session', { method: 'DELETE' }),
  portfolio: () => request<Portfolio>('/api/portfolio'),
  conversations: () => request<{ items: Conversation[] }>('/api/conversations'),
  createConversation: () => request<Conversation>('/api/conversations', { method: 'POST', body: '{}' }),
  conversation: (id: string) => request<Conversation & { messages: Message[]; context: Record<string, unknown>; pending_change: string | null }>(`/api/conversations/${id}`),
  send: (id: string, text: string, request_id = crypto.randomUUID()) => request<{ message: Message; server_ms: number }>(`/api/conversations/${id}/messages`, { method: 'POST', body: JSON.stringify({ text, request_id }) }),
  confirm: (id: string) => request<{ message: Message }>(`/api/changes/${id}/confirm`, { method: 'POST', body: JSON.stringify({ request_id: crypto.randomUUID() }) }),
  cancel: (id: string) => request<{ status: string }>(`/api/changes/${id}/cancel`, { method: 'POST', body: '{}' }),
  adminOverview: () => request<AdminOverview>('/api/admin/overview', {}, true),
  adminConversation: (id: string) => request<{ conversation: Conversation; messages: Message[]; events: AgentEvent[] }>(`/api/admin/conversations/${id}`, {}, true),
  resolveFlag: (id: string) => request<{ resolved: boolean }>(`/api/admin/flags/${id}/resolve`, { method: 'POST', body: '{}' }, true),
}

export type AgentEvent = { id: string; request_id: string; kind: string; name: string; duration_ms: number; success: boolean; input: Record<string, unknown>; output: Record<string, unknown>; error?: string; created_at: string }
