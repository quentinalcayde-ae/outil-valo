import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, Download, Check, X, Anchor as AnchorIcon } from 'lucide-react'
import {
  getRun, getTarget, getAnchors, getSuggestions, patchRunComps, computeAnchor, executeRun,
  fmtM, fmtBn, apiError, type RunComp, type AnchorProposal, type TransactionSuggestion,
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
  const { data: suggestions } = useQuery({ queryKey: ['suggestions', run?.target_id], queryFn: () => getSuggestions(run!.target_id), enabled: !!run })

  const anchor = anchors?.[anchors.length - 1]
  const hasAnchorRow = !!anchor
  const anchored = anchor?.m_market_entry != null

  const [exclusions, setExclusions] = useState<Record<number, boolean>>({})
  const [proposal, setProposal] = useState<AnchorProposal | null>(null)
  const [manualAnchor, setManualAnchor] = useState('')
  const [targetAgg, setTargetAgg] = useState('')
  const [growthNow, setGrowthNow] = useState('')
  const [otherDeltas, setOtherDeltas] = useState('')

  useEffect(() => {
    if (target?.growth_now != null) setGrowthNow(String(target.growth_now * 100))
  }, [target?.growth_now])
  useEffect(() => {
    if (run?.other_deltas != null) setOtherDeltas(String(run.other_deltas))
  }, [run?.other_deltas])

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
    mutationFn: () => executeRun(
      id,
      targetAgg ? parseFloat(targetAgg) * 1e6 : undefined,
      growthNow !== '' ? parseFloat(growthNow) / 100 : undefined,
      otherDeltas !== '' ? parseFloat(otherDeltas) : undefined,
    ),
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
            <Metric label="EV cible" value={fmtBn(run.result_ev) + ' €'} />
            <Metric label="Equity (− dette nette)" value={fmtBn(run.result_equity) + ' €'} highlight />
          </div>
          {/* Décomposition : médiane + winsor + deltas société */}
          <div className="mt-3 text-xs text-slate-600 bg-white/60 rounded-md px-3 py-2">
            Médiane priced <b>{fmtM(run.median_now)}</b> · moy. winsorisée {fmtM(run.winsor_mean)}
            {' · '}delta croissance {run.growth_delta ? `${run.growth_delta > 0 ? '+' : ''}${run.growth_delta.toFixed(2)}x` : '0'}
            {' · '}autres deltas {run.other_deltas ? `${run.other_deltas > 0 ? '+' : ''}${run.other_deltas.toFixed(2)}x` : '0'}
          </div>
          {run.flags && run.flags.length > 0 && (
            <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
              {run.flags.map((f, i) => <div key={i}>⚠ {f}</div>)}
            </div>
          )}
          {run.excel_path && (
            <a href={`/api/runs/${run.id}/excel`}
               className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-900">
              <Download size={14} /> Télécharger l'Excel (Synthèse + Comparables)
            </a>
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

      {/* Transactions M&A comparables — cross-check, hors médiane */}
      {suggestions && suggestions.transactions.length > 0 && (
        <Card className="mb-5">
          <div className="px-5 py-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">Transactions M&A comparables
              <span className="ml-2 text-xs font-normal text-slate-400">cross-check qualitatif · hors médiane</span>
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
              <tr>
                <th className="px-5 py-2 text-left">Cible ← Acquéreur</th>
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-right">Multiple</th>
                <th className="px-4 py-2 text-left">Source</th>
                <th className="px-4 py-2 text-left">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {suggestions.transactions.map((t: TransactionSuggestion, i: number) => (
                <tr key={i}>
                  <td className="px-5 py-3 font-medium">
                    {t.target_company} <span className="text-slate-400">←</span> {t.acquirer ?? 'nc.'}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{t.tx_date ?? 'nc.'}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {t.implied_multiple != null ? `${t.implied_multiple.toFixed(1)}x` : 'nc.'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {t.source_doc_url
                      ? <a href={t.source_doc_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">source</a>
                      : <span className="text-slate-400">nc.</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-[220px] truncate">{t.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-5 py-2 text-xs text-slate-400">
            Proposées par l'IA à titre de repère qualitatif — les chiffres (prix, multiple) sont à vérifier manuellement et n'entrent jamais dans la médiane.
          </p>
        </Card>
      )}

      {/* Ancre marché — uniquement si la cible a une ancre de tour (sinon valo directe) */}
      {!hasResult && hasAnchorRow && (
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
              <input type="number" step="any" value={targetAgg} onChange={e => setTargetAgg(e.target.value)}
                placeholder={target?.aggregate_value ? String(target.aggregate_value / 1e6) : '1.437'}
                className="mt-1 block w-36 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Croissance actuelle (% YoY)</span>
              <input type="number" step="any" value={growthNow} onChange={e => setGrowthNow(e.target.value)}
                placeholder="45"
                className="mt-1 block w-32 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Autres deltas (tours)</span>
              <input type="number" step="any" value={otherDeltas} onChange={e => setOtherDeltas(e.target.value)}
                placeholder="0"
                className="mt-1 block w-32 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
            </label>
            <Button onClick={() => execMut.mutate()} disabled={execMut.isPending || (hasAnchorRow && !anchored)}>
              <Play size={14} /> {execMut.isPending ? 'Calcul…' : 'Calculer la valo'}
            </Button>
          </div>
          <div className="text-xs text-slate-500 mt-1 space-y-0.5">
            <p><b>Croissance actuelle</b> : tu saisis le % de croissance de la cible → le <b>delta croissance est calculé automatiquement</b> (prix d'un point de croissance dans le panel × écart vs médiane du panel, plafonné).</p>
            <p><b>Autres deltas</b> (en tours de multiple) : marge, rétention (NRR), taille — manuels, faute de données panel fiables pour les automatiser. Laisse 0 sinon.</p>
          </div>
          {hasAnchorRow && !anchored && <p className="text-xs text-amber-600 mt-2">Ancrez d'abord la médiane marché ci-dessus.</p>}
          {!hasAnchorRow && <p className="text-xs text-slate-500 mt-2">Valorisation directe (sans ancre) : la médiane des comparables sera appliquée telle quelle.</p>}
          {execMut.error && <ErrorBox message={apiError(execMut.error, "Erreur au calcul. Vérifiez l'ancre et le panel.")} />}
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
