import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

// ── Types ────────────────────────────────────────────────────────────────────

export interface Target {
  id: number
  name: string
  sector: string | null
  is_recurring: boolean
  valuation_aggregate: string
  fund: string | null
  notes: string | null
  created_at: string
}

export interface Anchor {
  id: number
  target_id: number
  entry_date: string
  entry_round: string | null
  m_entry_aggregate: number
  m_market_entry: number
}

export interface Comp {
  id: number
  name: string
  ticker: string
  sector: string | null
  currency: string
  is_recurring: boolean
  recurring_basis_tag: string | null
}

export interface Snapshot {
  id: number
  comp_id: number
  snapshot_date: string
  market_cap: number | null
  net_debt: number | null
  cash: number | null
  revenue_ltm: number | null
  recurring_value: number | null
  ev: number | null
  ev_rev: number | null
  ev_recurring: number | null
  source_by_field: Record<string, string> | null
}

export interface RunComp {
  id: number
  comp_snapshot_id: number
  included: boolean
  exclusion_reason: string | null
  relevance_note: string | null
  snapshot: Snapshot
  comp: Comp
}

export interface Run {
  id: number
  target_id: number
  run_date: string
  mode: 'A' | 'B'
  aggregate: string
  median_now: number | null
  retention_factor: number | null
  m_final: number | null
  result_ev: number | null
  result_equity: number | null
  excel_path: string | null
  run_comps: RunComp[]
}

export interface Transaction {
  id: number
  target_company: string
  acquirer: string | null
  tx_date: string | null
  sector: string | null
  price_disclosed: boolean
  price: number | null
  implied_multiple: number | null
  source_doc_url: string | null
  notes: string | null
  created_at: string
}

// ── Targets ──────────────────────────────────────────────────────────────────

export const getTargets = () => http.get<Target[]>('/targets').then(r => r.data)
export const getTarget = (id: number) => http.get<Target>(`/targets/${id}`).then(r => r.data)
export const createTarget = (data: Omit<Target, 'id' | 'created_at'>) =>
  http.post<Target>('/targets', data).then(r => r.data)

export const getAnchors = (targetId: number) =>
  http.get<Anchor[]>(`/targets/${targetId}/anchors`).then(r => r.data)
export const createAnchor = (targetId: number, data: Omit<Anchor, 'id' | 'target_id'>) =>
  http.post<Anchor>(`/targets/${targetId}/anchors`, data).then(r => r.data)

// ── Comps ─────────────────────────────────────────────────────────────────────

export const getComps = () => http.get<Comp[]>('/comps').then(r => r.data)
export const createComp = (data: Omit<Comp, 'id'>) =>
  http.post<Comp>('/comps', data).then(r => r.data)
export const refreshSnapshot = (ticker: string) =>
  http.post<Snapshot>(`/comps/${ticker}/refresh`).then(r => r.data)

// ── Runs ──────────────────────────────────────────────────────────────────────

export const createPanel = (targetId: number, data: object) =>
  http.post<Run>(`/runs/panel?target_id=${targetId}`, data).then(r => r.data)
export const getRun = (runId: number) =>
  http.get<Run>(`/runs/${runId}`).then(r => r.data)
export const patchRunComps = (runId: number, comps: object[]) =>
  http.patch<Run>(`/runs/${runId}/comps`, { comps }).then(r => r.data)
export const executeRun = (runId: number, targetAggregateValue: number) =>
  http.post<Run>(`/runs/${runId}/execute`, { target_aggregate_value: targetAggregateValue }).then(r => r.data)

// ── Transactions ──────────────────────────────────────────────────────────────

export const getTransactions = () => http.get<Transaction[]>('/transactions').then(r => r.data)
export const createTransaction = (data: Omit<Transaction, 'id' | 'created_at'>) =>
  http.post<Transaction>('/transactions', data).then(r => r.data)
export const updateTransaction = (id: number, data: Partial<Transaction>) =>
  http.patch<Transaction>(`/transactions/${id}`, data).then(r => r.data)
export const deleteTransaction = (id: number) =>
  http.delete(`/transactions/${id}`)

// ── Helpers ───────────────────────────────────────────────────────────────────

export function fmtM(v: number | null): string {
  if (v == null) return '—'
  return `${v.toFixed(2)}x`
}

export function fmtBn(v: number | null): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return v.toFixed(0)
}
