import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, Download, Check, X, Anchor as AnchorIcon } from 'lucide-react'
import {
  getRun, getTarget, getAnchors, patchRunComps, computeAnchor, executeRun,
  fmtM, fmtBn, type RunComp, type AnchorProposal,
} from '../api'
import { PageHeader, Card, Button, Spinner, ErrorBox, Badge } from '../components/ui'

export default function RunResult() {
  const { runId } = useParams<{ runId: string }>()
  const id = Number(runId)
  const nav = useNavigate()
  const qc = useQueryClient()

  const { data: run, isLoading, error } = useQuery({ queryKey: ['run', id], queryFn: () => getRun(id) })
  const { data: target } = useQuery({ queryKey: ['target', run?.target_id], queryFn: () => getTarget(run!.target_id), enabled: !!run })
  const { data: anchors } = useQuery({ queryKey: ['anchors', run?.target_id], queryFn: () => getAnchors(run!.target_id), enabled: !!run })

  const anchor = anchors?.[anchors.length - 1]
  const anchored = anchor?.m_market_entry != null

  const [exclusions, setExclusions] = useState<Record<number, boolean>>({})
  const [proposal, setProposal] = useState<AnchorProposal | null>(null)
  const [manualAnchor, setManualAnchor] = useState('')
  const [targetAgg, setTargetAgg] = useState('')

  const patchMut = useMutation({
    mutationFn: () => patchRunComps(id, run!.run_comps.map(rc => ({
      run_comp_id: rc.id,
      included: exclusions[rc.id] ?? rc.included,
      exclusion_reason: rc.exclusion_reason,
      relevance_note: rc.relevance_note,
    }))),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['run', id] }),
  })

  const anchorMut = useMutation({
    mutationFn: (manual?: number) => computeAnchor(id, manual != null ? { manual_value: manual, basis: run!.aggregate } : {}),
    onSuccess: (p) => {
      setProposal(p)
      qc.invalidateQueries({ queryKey: ['anchors', run?.target_id] })
    },
  })

  const execMut = useMutation({
    mutationFn: () => executeRun(id, targetAgg ? parseFloat(targetAgg) * 1e6 : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['run', id] }),
  })

  if (isLoading) return <Spinner />
  if (error || !run) return <ErrorBox message="Run introuvable." />
  const hasResult = run.m_final != null

  return (
    <div className="p-8 max-w-4xl">
      <PageHeader title={`Run #${run.id} · MODE ${run.mode} · ${run.aggregate.toUpperCase()}`}
        sub={new Date(run.run_date).toLocaleString('fr-FR')} />

      {/* Résultat */}
      {hasResult && (
        <Card className="p-5 mb-5 bg-brand-light border-brand/20">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">Résultat</h3>
          <div className="grid grid-cols-4 gap-4">
            <Metric label="Médiane now" value={fmtM(run.median_now)} />
            <Metric label="M_final" value={fmtM(run.m_final)} highlight />
            <Metric label="EV cible" value={fmtBn(run.result_ev) + ' €'} highlight />
            <Metric label="Rétention" value={fmtM(run.retention_factor)} />
          </div>
          {run.excel_path && (
            <p className="mt-3 text-xs text-slate-500 flex items-center gap-1">
              <Download size={12} /> Excel : {run.excel_path}
            </p>
          )}
        </Card>
      )}

      {/* Panel */}
      <Card className="mb-5">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Panel de comparables</h3>
          {!hasResult && (
            <Button variant="secondary" onClick={() => patchMut.mutate()}
              disabled={patchMut.isPending || Object.keys(exclusions).length === 0}>
              {patchMut.isPending ? 'Sauvegarde…' : 'Enregistrer sélection'}
            </Button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
            <tr>
              <th className="px-5 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right">Market Cap</th>
              <th className="px-4 py-2 text-right">EV</th>
              <th className="px-4 py-2 text-right">EV/{run.aggregate}</th>
              <th className="px-4 py-2 text-left">Note</th>
              <th className="px-4 py-2 text-center">Inclus</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {run.run_comps.map((rc: RunComp) => {
              const included = exclusions[rc.id] ?? rc.included
              return (
                <tr key={rc.id} className={included ? '' : 'opacity-50'}>
                  <td className="px-5 py-3 font-mono font-semibold">{rc.comp.ticker}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{fmtBn(rc.snapshot?.market_cap ?? null)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{fmtBn(rc.snapshot?.ev ?? null)}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmtM(rc.snapshot?.ev_rev ?? null)}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-[200px] truncate">{rc.relevance_note ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    {hasResult
                      ? (rc.included ? <Check size={16} className="text-green-600 mx-auto" /> : <X size={16} className="text-red-400 mx-auto" />)
                      : <button onClick={() => setExclusions(e => ({ ...e, [rc.id]: !(e[rc.id] ?? rc.included) }))}>
                          {included ? <Check size={16} className="text-green-600 mx-auto" /> : <X size={16} className="text-red-400 mx-auto" />}
                        </button>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="px-5 py-2 text-xs text-slate-400">Les snapshots financiers sont gelés au calcul de la valo (recherche financière).</p>
      </Card>

      {/* Ancre marché */}
      {!hasResult && (
        <Card className="p-5 mb-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
            <AnchorIcon size={15} className="text-brand" /> Ancre marché (m_market_entry)
          </h3>
          {anchored && (
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="green">Ancré</Badge>
              <span className="text-sm text-slate-600">
                {fmtM(anchor!.m_market_entry)} · basis={anchor!.market_anchor_basis} · {anchor!.m_market_entry_source}
              </span>
            </div>
          )}
          <div className="flex items-end gap-3 flex-wrap">
            <Button variant="secondary" onClick={() => anchorMut.mutate(undefined)} disabled={anchorMut.isPending}>
              {anchorMut.isPending ? 'Calcul historique…' : 'Calculer auto (EV/Revenue historique)'}
            </Button>
            <span className="text-sm text-slate-400">ou</span>
            <label className="block">
              <span className="text-xs text-slate-500">Multiple manuel (cas ARR)</span>
              <div className="flex gap-2 mt-0.5">
                <input type="number" step="0.01" value={manualAnchor} onChange={e => setManualAnchor(e.target.value)}
                  placeholder="9.5" className="w-24 rounded-md border border-slate-300 px-2 py-1.5 text-sm" />
                <Button variant="secondary" onClick={() => anchorMut.mutate(parseFloat(manualAnchor))} disabled={!manualAnchor}>
                  Fixer
                </Button>
              </div>
            </label>
          </div>

          {proposal && (
            <div className="mt-3 text-sm">
              {proposal.m_market_entry != null
                ? <p className="text-slate-700">Ancre = <b>{fmtM(proposal.m_market_entry)}</b> ({proposal.source}, {proposal.n_available} comps dispo, basis {proposal.basis})</p>
                : <ErrorBox message="Aucune donnée historique exploitable — saisissez un multiple manuel." />}
              {proposal.details.length > 0 && (
                <ul className="mt-2 text-xs text-slate-500 space-y-0.5">
                  {proposal.details.map(d => (
                    <li key={d.ticker}>
                      {d.ticker} : {d.available ? fmtM(d.multiple) : `indispo — ${d.note}`}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Execute */}
      {!hasResult && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Calculer la valo (recherche financière + Excel)</h3>
          <div className="flex items-end gap-3">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Agrégat cible ({run.aggregate.toUpperCase()}) M€</span>
              <input type="number" step="0.1" value={targetAgg} onChange={e => setTargetAgg(e.target.value)}
                placeholder={target?.aggregate_value ? String(target.aggregate_value / 1e6) : '8.0'}
                className="mt-1 block w-36 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
            </label>
            <Button onClick={() => execMut.mutate()} disabled={execMut.isPending || !anchored}>
              <Play size={14} /> {execMut.isPending ? 'Calcul…' : 'Calculer la valo'}
            </Button>
          </div>
          {!anchored && <p className="text-xs text-amber-600 mt-2">Ancrez d'abord la médiane marché ci-dessus.</p>}
          {execMut.error && <ErrorBox message="Erreur au calcul. Vérifiez l'ancre et le panel." />}
        </Card>
      )}

      {hasResult && (
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={() => nav('/')}>Retour au tableau de bord</Button>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? 'bg-white border border-brand/30' : 'bg-white/60'}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xl font-bold mt-0.5 ${highlight ? 'text-brand' : 'text-slate-700'}`}>{value}</p>
    </div>
  )
}
