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
  aggregate_value: number | null
  net_debt: number | null
  description: string | null
  notes: string | null
  created_at: string
}

export interface CompSuggestion {
  name: string
  ticker: string
  rationale: string
  sector: string | null
  confidence: string
}

export interface TransactionSuggestion {
  target_company: string
  acquirer: string | null
  tx_date: string | null
  rationale: string
  source_doc_url: string | null
  implied_multiple: number | null
  sector: string | null
}

export interface SuggestResponse {
  comps: CompSuggestion[]
  transactions: TransactionSuggestion[]
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
  comp_id: number
  comp_snapshot_id: number | null
  included: boolean
  exclusion_reason: string | null
  relevance_note: string | null
  comp: Comp
  snapshot: Snapshot | null
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

export interface AnchorCompDetail {
  ticker: string
  ev: number | null
  revenue_ltm: number | null
  multiple: number | null
  available: boolean
  note: string
}

export interface AnchorProposal {
  basis: string
  entry_date: string
  m_market_entry: number | null
  n_available: number
  details: AnchorCompDetail[]
  source: string // computed / manual / pending
}

export interface Transaction {
  id: number
  target_id: number | null
  target_company: string
  acquirer: string | null
  tx_date: string | null
  sector: string | null
  price_disclosed: boolean
  price: number | null
  implied_multiple: number | null
  source_doc_url: string | null
  origin: string
  status: string
  notes: string | null
  created_at: string
}

// ── Targets & découverte ──────────────────────────────────────────────────────

export const getTargets = () => http.get<Target[]>('/targets').then(r => r.data)
export const getTarget = (id: number) => http.get<Target>(`/targets/${id}`).then(r => r.data)
export const createTarget = (data: Partial<Target>) =>
  http.post<Target>('/targets', data).then(r => r.data)
export const deleteTarget = (id: number) => http.delete(`/targets/${id}`)

/** Extrait le message d'erreur métier renvoyé par l'API (FastAPI `detail`). */
export function apiError(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export const suggest = (targetId: number, body: { extra_tickers?: string[]; n_comps?: number; n_transactions?: number }) =>
  http.post<SuggestResponse>(`/targets/${targetId}/suggest`, body).then(r => r.data)

export interface ResolveItem { ticker: string; valid: boolean; name: string | null }
export const resolveTickers = (tickers: string[]) =>
  http.post<ResolveItem[]>('/comps/resolve', { tickers }).then(r => r.data)

export interface Anchor {
  id: number
  target_id: number
  entry_date: string
  entry_round: string | null
  m_entry_aggregate: number
  m_market_entry: number | null
  market_anchor_basis: string | null
  m_market_entry_source: string
}
export const getAnchors = (targetId: number) =>
  http.get<Anchor[]>(`/targets/${targetId}/anchors`).then(r => r.data)

// ── Runs : panel → anchor → execute ─────────────────────────────────────────────

export interface PanelBody {
  comps: { ticker: string; name?: string; relevance_note?: string | null }[]
  mode: 'A' | 'B'
  aggregate: string
  retention_factor: number
  anchor: { entry_date: string; entry_round?: string | null; m_entry_aggregate: number }
}

export const createPanel = (targetId: number, body: PanelBody) =>
  http.post<Run>(`/runs/panel?target_id=${targetId}`, body).then(r => r.data)
export const getRun = (runId: number) => http.get<Run>(`/runs/${runId}`).then(r => r.data)
export const patchRunComps = (runId: number, comps: object[]) =>
  http.patch<Run>(`/runs/${runId}/comps`, { comps }).then(r => r.data)
export const computeAnchor = (runId: number, body: { manual_value?: number; basis?: string }) =>
  http.post<AnchorProposal>(`/runs/${runId}/anchor`, body).then(r => r.data)
export const executeRun = (runId: number, targetAggregateValue?: number) =>
  http.post<Run>(`/runs/${runId}/execute`, { target_aggregate_value: targetAggregateValue ?? null }).then(r => r.data)

// ── Transactions ──────────────────────────────────────────────────────────────

export const getTransactions = () => http.get<Transaction[]>('/transactions').then(r => r.data)
export const createTransaction = (data: Partial<Transaction>) =>
  http.post<Transaction>('/transactions', data).then(r => r.data)
export const updateTransaction = (id: number, data: Partial<Transaction>) =>
  http.patch<Transaction>(`/transactions/${id}`, data).then(r => r.data)
export const deleteTransaction = (id: number) => http.delete(`/transactions/${id}`)

// ── Helpers ───────────────────────────────────────────────────────────────────

export function fmtM(v: number | null): string {
  return v == null ? '—' : `${v.toFixed(2)}x`
}
export function fmtBn(v: number | null): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return v.toFixed(0)
}
