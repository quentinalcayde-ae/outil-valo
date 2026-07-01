import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, Download, Check, X } from 'lucide-react'
import { getRun, patchRunComps, executeRun, fmtM, fmtBn, type RunComp } from '../api'
import { PageHeader, Card, Badge, Button, Spinner, ErrorBox } from '../components/ui'

export default function RunResult() {
  const { runId } = useParams<{ runId: string }>()
  const id = Number(runId)
  const nav = useNavigate()
  const qc = useQueryClient()

  const { data: run, isLoading, error } = useQuery({
    queryKey: ['run', id],
    queryFn: () => getRun(id),
  })

  const [targetAgg, setTargetAgg] = useState('')
  const [exclusions, setExclusions] = useState<Record<number, { included: boolean; reason: string }>>({})

  const patchMut = useMutation({
    mutationFn: () => {
      const comps = run!.run_comps.map(rc => ({
        comp_snapshot_id: rc.comp_snapshot_id,
        included: exclusions[rc.comp_snapshot_id]?.included ?? rc.included,
        exclusion_reason: exclusions[rc.comp_snapshot_id]?.reason ?? rc.exclusion_reason,
        relevance_note: rc.relevance_note,
      }))
      return patchRunComps(id, comps)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['run', id] }),
  })

  const execMut = useMutation({
    mutationFn: () => executeRun(id, parseFloat(targetAgg) * 1e6),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['run', id] }),
  })

  const toggleComp = (rc: RunComp) => {
    setExclusions(e => ({
      ...e,
      [rc.comp_snapshot_id]: {
        included: !(e[rc.comp_snapshot_id]?.included ?? rc.included),
        reason: e[rc.comp_snapshot_id]?.reason ?? '',
      },
    }))
  }

  if (isLoading) return <Spinner />
  if (error || !run) return <ErrorBox message="Run introuvable." />

  const hasResult = run.m_final != null

  return (
    <div className="p-8 max-w-4xl">
      <PageHeader
        title={`Run #${run.id} · MODE ${run.mode} · ${run.aggregate.toUpperCase()}`}
        sub={new Date(run.run_date).toLocaleString('fr-FR')}
      />

      {/* Résultat (si calculé) */}
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
          <Button variant="secondary" onClick={() => patchMut.mutate()} disabled={patchMut.isPending || Object.keys(exclusions).length === 0}>
            {patchMut.isPending ? 'Sauvegarde…' : 'Enregistrer sélection'}
          </Button>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
            <tr>
              <th className="px-5 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right">Market Cap</th>
              <th className="px-4 py-2 text-right">EV</th>
              <th className="px-4 py-2 text-right">EV/Rev</th>
              <th className="px-4 py-2 text-left">Note</th>
              <th className="px-4 py-2 text-center">Inclus</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {run.run_comps.map(rc => {
              const override = exclusions[rc.comp_snapshot_id]
              const included = override?.included ?? rc.included
              return (
                <tr key={rc.id} className={included ? '' : 'opacity-50'}>
                  <td className="px-5 py-3 font-mono font-semibold">{rc.comp.ticker}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{fmtBn(rc.snapshot.market_cap)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{fmtBn(rc.snapshot.ev)}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmtM(rc.snapshot.ev_rev)}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-[180px] truncate">{rc.relevance_note ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleComp(rc)} className="transition-colors">
                      {included
                        ? <Check size={16} className="text-green-600 mx-auto" />
                        : <X size={16} className="text-red-400 mx-auto" />
                      }
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      {/* Exécuter */}
      {!hasResult && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Lancer le calcul</h3>
          <div className="flex items-end gap-3">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">
                Agrégat cible ({run.aggregate.toUpperCase()}) en M€
              </span>
              <input
                type="number"
                step="0.1"
                value={targetAgg}
                onChange={e => setTargetAgg(e.target.value)}
                placeholder="8.0"
                className="mt-1 block w-36 rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40"
              />
            </label>
            <Button onClick={() => execMut.mutate()} disabled={execMut.isPending || !targetAgg}>
              <Play size={14} className={execMut.isPending ? 'animate-pulse' : ''} />
              {execMut.isPending ? 'Calcul…' : 'Calculer la valo'}
            </Button>
          </div>
          {execMut.error && <ErrorBox message="Erreur lors du calcul. Vérifiez le panel et les ancres." />}
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
