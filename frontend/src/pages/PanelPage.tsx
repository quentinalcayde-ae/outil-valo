import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, Sparkles, ArrowRight } from 'lucide-react'
import { getTarget, suggest, createPanel, type CompSuggestion } from '../api'
import { PageHeader, Card, Input, Select, Button, Spinner, ErrorBox } from '../components/ui'

interface Row { ticker: string; name: string; relevance_note: string; included: boolean }

export default function PanelPage() {
  const { targetId } = useParams<{ targetId: string }>()
  const id = Number(targetId)
  const nav = useNavigate()

  const { data: target } = useQuery({ queryKey: ['target', id], queryFn: () => getTarget(id) })

  const [rows, setRows] = useState<Row[]>([])
  const [txs, setTxs] = useState<{ label: string; note: string; keep: boolean }[]>([])

  const suggestMut = useMutation({
    mutationFn: () => suggest(id, { n_comps: 8, n_transactions: 5 }),
    onSuccess: (data) => {
      setRows(data.comps.map((c: CompSuggestion) => ({
        ticker: c.ticker, name: c.name, relevance_note: c.rationale, included: true,
      })))
      setTxs(data.transactions.map(t => ({
        label: `${t.target_company}${t.acquirer ? ` ← ${t.acquirer}` : ''}`,
        note: t.rationale, keep: true,
      })))
    },
  })

  // Lance la découverte automatiquement à l'arrivée
  useEffect(() => { if (target) suggestMut.mutate() }, [target?.id]) // eslint-disable-line

  const [mode, setMode] = useState<'A' | 'B'>('A')
  const [retention, setRetention] = useState('1.0')
  const [entryDate, setEntryDate] = useState('')
  const [entryRound, setEntryRound] = useState('')
  const [mEntry, setMEntry] = useState('')

  const addRow = () => setRows(r => [...r, { ticker: '', name: '', relevance_note: '', included: true }])
  const rmRow = (i: number) => setRows(r => r.filter((_, idx) => idx !== i))
  const upd = (i: number, f: keyof Row, v: string | boolean) =>
    setRows(r => r.map((row, idx) => idx === i ? { ...row, [f]: v } : row))

  const panelMut = useMutation({
    mutationFn: () => createPanel(id, {
      comps: rows.filter(r => r.included && r.ticker.trim()).map(r => ({
        ticker: r.ticker.trim().toUpperCase(), name: r.name || undefined,
        relevance_note: r.relevance_note || null,
      })),
      mode,
      aggregate: target!.valuation_aggregate,
      retention_factor: parseFloat(retention) || 1.0,
      anchor: { entry_date: entryDate, entry_round: entryRound || null, m_entry_aggregate: parseFloat(mEntry) },
    }),
    onSuccess: (run) => nav(`/runs/${run.id}`),
  })

  if (!target) return <Spinner />

  return (
    <div className="p-8 max-w-3xl">
      <PageHeader title={`Découverte — ${target.name}`}
        sub="Comparables et transactions proposés automatiquement. Corrigez les tickers, sélectionnez, puis ancrez." />

      {/* Comps */}
      <Card className="mb-5">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
            <Sparkles size={15} className="text-brand" /> Comparables cotés proposés
          </h3>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => suggestMut.mutate()} disabled={suggestMut.isPending}>
              {suggestMut.isPending ? 'Recherche…' : 'Re-proposer'}
            </Button>
            <Button variant="secondary" onClick={addRow}><Plus size={13} /> Ajouter</Button>
          </div>
        </div>

        {suggestMut.isPending && <Spinner />}
        {suggestMut.error && <div className="p-4"><ErrorBox message="Échec de la découverte (LLM). Réessayez." /></div>}

        {!suggestMut.isPending && rows.length > 0 && (
          <div className="divide-y divide-slate-100">
            <div className="grid grid-cols-[auto_90px_1fr_auto] gap-3 px-5 py-2 text-xs font-medium text-slate-400 uppercase">
              <span>Inclus</span><span>Ticker</span><span>Pourquoi pertinent</span><span></span>
            </div>
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[auto_90px_1fr_auto] gap-3 px-5 py-2 items-center">
                <input type="checkbox" checked={r.included} onChange={e => upd(i, 'included', e.target.checked)} />
                <input value={r.ticker} onChange={e => upd(i, 'ticker', e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm font-mono uppercase" placeholder="WDAY" />
                <input value={r.relevance_note} onChange={e => upd(i, 'relevance_note', e.target.value)}
                  className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-600" />
                <button onClick={() => rmRow(i)} className="text-slate-300 hover:text-red-500"><Trash2 size={15} /></button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Transactions proposées (cross-check, hors médiane) */}
      {txs.length > 0 && (
        <Card className="mb-5 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Transactions M&A proposées
            <span className="ml-2 text-xs font-normal text-slate-400">cross-check · hors médiane · chiffres à vérifier</span>
          </h3>
          <div className="space-y-1.5">
            {txs.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={t.keep}
                  onChange={e => setTxs(prev => prev.map((x, idx) => idx === i ? { ...x, keep: e.target.checked } : x))} />
                <span className="font-medium">{t.label}</span>
                <span className="text-slate-400 text-xs">— {t.note}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">Les transactions retenues se saisissent/valident dans l'onglet Transactions M&A.</p>
        </Card>
      )}

      {/* Ancres d'entrée */}
      <Card className="mb-5 p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Ancres du tour d'entrée</h3>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Date du tour *" type="date" value={entryDate} onChange={e => setEntryDate(e.target.value)} />
          <Input label="Libellé tour" value={entryRound} onChange={e => setEntryRound(e.target.value)} placeholder="Série B" />
          <Input label={`M_entry (EV/${target.valuation_aggregate} au tour) *`} type="number" step="0.01"
            value={mEntry} onChange={e => setMEntry(e.target.value)} placeholder="8.0" />
          <Select label="Mode" value={mode} onChange={e => setMode(e.target.value as 'A' | 'B')}>
            <option value="A">MODE A — amorçage</option>
            <option value="B">MODE B — trimestriel</option>
          </Select>
          <Input label="Facteur rétention" type="number" step="0.01" value={retention} onChange={e => setRetention(e.target.value)} />
        </div>
        <p className="text-xs text-slate-400 mt-2">
          La médiane marché au tour (m_market_entry) sera calculée automatiquement à l'étape suivante.
        </p>
      </Card>

      {panelMut.error && <ErrorBox message="Erreur lors de la création du panel. Vérifiez les ancres et au moins un comp inclus." />}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => nav('/')}>Annuler</Button>
        <Button onClick={() => panelMut.mutate()}
          disabled={panelMut.isPending || !entryDate || !mEntry || rows.filter(r => r.included && r.ticker).length === 0}>
          {panelMut.isPending ? 'Création…' : 'Valider le panel'} <ArrowRight size={14} />
        </Button>
      </div>
    </div>
  )
}
