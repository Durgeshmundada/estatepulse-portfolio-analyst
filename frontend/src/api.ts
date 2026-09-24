import type { AdminOverview, Conversation, Message, Portfolio, User } from './types'

type StreamHandlers = {
  onStatus?: (text: string) => void
  onDelta?: (text: string) => void
}

type StreamResult = { message: Message; server_ms: number }

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

async function streamRequest(path: string, body: object, handlers: StreamHandlers): Promise<StreamResult> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let message = 'Something went wrong'
    try { message = (await response.json()).detail ?? message } catch { /* keep safe message */ }
    throw new Error(message)
  }
  if (!response.body) throw new Error('Streaming is unavailable in this browser')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed: StreamResult | null = null
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      const event = JSON.parse(line) as { type: string; text?: string; detail?: string; message?: Message; server_ms?: number }
      if (event.type === 'status' && event.text) handlers.onStatus?.(event.text)
      if (event.type === 'delta' && event.text) handlers.onDelta?.(event.text)
      if (event.type === 'error') throw new Error(event.detail ?? 'Analysis temporarily unavailable')
      if (event.type === 'done' && event.message && event.server_ms !== undefined) completed = { message: event.message, server_ms: event.server_ms }
    }
    if (done) break
  }
  if (!completed) throw new Error('The response stream ended before completion')
  return completed
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
  deleteConversation: (id: string) => request<void>(`/api/conversations/${id}`, { method: 'DELETE' }),
  send: (id: string, text: string, request_id = crypto.randomUUID()) => request<{ message: Message; server_ms: number }>(`/api/conversations/${id}/messages`, { method: 'POST', body: JSON.stringify({ text, request_id }) }),
  sendStream: (id: string, text: string, handlers: StreamHandlers, request_id = crypto.randomUUID()) => streamRequest(`/api/conversations/${id}/messages/stream`, { text, request_id }, handlers),
  confirm: (id: string) => request<{ message: Message }>(`/api/changes/${id}/confirm`, { method: 'POST', body: JSON.stringify({ request_id: crypto.randomUUID() }) }),
  cancel: (id: string) => request<{ status: string }>(`/api/changes/${id}/cancel`, { method: 'POST', body: '{}' }),
  adminOverview: () => request<AdminOverview>('/api/admin/overview', {}, true),
  adminConversation: (id: string) => request<{ conversation: Conversation; messages: Message[]; events: AgentEvent[] }>(`/api/admin/conversations/${id}`, {}, true),
  resolveFlag: (id: string) => request<{ resolved: boolean }>(`/api/admin/flags/${id}/resolve`, { method: 'POST', body: '{}' }, true),
}

export type AgentEvent = { id: string; request_id: string; kind: string; name: string; duration_ms: number; success: boolean; input: Record<string, unknown>; output: Record<string, unknown>; error?: string; created_at: string }
