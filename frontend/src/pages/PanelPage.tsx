import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, RefreshCw } from 'lucide-react'
import { createPanel, getTarget, getAnchors } from '../api'
import { PageHeader, Card, Input, Select, Button, Spinner, ErrorBox, Badge } from '../components/ui'

interface CompRow { ticker: string; relevance_note: string }

export default function PanelPage() {
  const { targetId } = useParams<{ targetId: string }>()
  const id = Number(targetId)
  const nav = useNavigate()

  const { data: target } = useQuery({ queryKey: ['target', id], queryFn: () => getTarget(id) })
  const { data: anchors } = useQuery({ queryKey: ['anchors', id], queryFn: () => getAnchors(id) })

  const hasAnchor = anchors && anchors.length > 0

  // Panel rows
  const [comps, setComps] = useState<CompRow[]>([
    { ticker: '', relevance_note: '' },
    { ticker: '', relevance_note: '' },
  ])
  const addComp = () => setComps(c => [...c, { ticker: '', relevance_note: '' }])
  const removeComp = (i: number) => setComps(c => c.filter((_, idx) => idx !== i))
  const updateComp = (i: number, field: keyof CompRow, val: string) =>
    setComps(c => c.map((r, idx) => idx === i ? { ...r, [field]: val } : r))

  // Run settings
  const [mode, setMode] = useState<'A' | 'B'>('A')
  const [aggregate, setAggregate] = useState(target?.valuation_aggregate ?? 'revenue')
  const [retention, setRetention] = useState('1.0')
  const [targetAgg, setTargetAgg] = useState('')

  // Anchor fields (if none yet)
  const [anchorDate, setAnchorDate] = useState('')
  const [anchorRound, setAnchorRound] = useState('')
  const [mEntry, setMEntry] = useState('')
  const [mMarket, setMMarket] = useState('')

  const mut = useMutation({
    mutationFn: () => {
      const validComps = comps.filter(c => c.ticker.trim())
      const body: Record<string, unknown> = {
        comps: validComps.map(c => ({ ticker: c.ticker.trim().toUpperCase(), relevance_note: c.relevance_note || null })),
        mode,
        aggregate,
        retention_factor: parseFloat(retention) || 1.0,
        target_aggregate_value: parseFloat(targetAgg) * 1e6,
      }
      if (!hasAnchor) {
        body.anchor = {
          entry_date: anchorDate,
          entry_round: anchorRound || null,
          m_entry_aggregate: parseFloat(mEntry),
          m_market_entry: parseFloat(mMarket),
        }
      }
      return createPanel(id, body)
    },
    onSuccess: (run) => nav(`/runs/${run.id}`),
  })

  if (!target) return <Spinner />

  return (
    <div className="p-8 max-w-3xl">
      <PageHeader
        title={`Panel — ${target.name}`}
        sub="Saisissez les comparables cotés, puis lancez le run"
      />

      <div className="space-y-5">
        {/* Ancre (si aucune) */}
        {!hasAnchor && (
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Ancres d'entrée (tour de référence)</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Date du tour *" type="date" value={anchorDate} onChange={e => setAnchorDate(e.target.value)} />
              <Input label="Libellé tour" value={anchorRound} onChange={e => setAnchorRound(e.target.value)} placeholder="Série B" />
              <Input label={`M_entry EV/${aggregate} au tour *`} type="number" step="0.01" value={mEntry} onChange={e => setMEntry(e.target.value)} placeholder="8.0" />
              <Input label="Médiane marché au tour *" type="number" step="0.01" value={mMarket} onChange={e => setMMarket(e.target.value)} placeholder="9.5" />
            </div>
          </Card>
        )}
        {hasAnchor && (
          <Card className="p-4 flex items-center gap-3 bg-brand-light border-brand/20">
            <Badge variant="green">Ancre existante</Badge>
            <span className="text-sm text-slate-600">
              Tour {anchors[0].entry_round ?? '—'} · M_entry={anchors[0].m_entry_aggregate}x · Médiane={anchors[0].m_market_entry}x
            </span>
          </Card>
        )}

        {/* Comps */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">Comparables cotés</h3>
            <Button variant="secondary" onClick={addComp}><Plus size={13} /> Ajouter</Button>
          </div>
          <div className="space-y-2">
            {comps.map((c, i) => (
              <div key={i} className="flex gap-2 items-end">
                <div className="w-28">
                  <Input
                    label={i === 0 ? 'Ticker' : ''}
                    value={c.ticker}
                    onChange={e => updateComp(i, 'ticker', e.target.value)}
                    placeholder="WDAY"
                    className="uppercase"
                  />
                </div>
                <div className="flex-1">
                  <Input
                    label={i === 0 ? 'Note de pertinence' : ''}
                    value={c.relevance_note}
                    onChange={e => updateComp(i, 'relevance_note', e.target.value)}
                    placeholder="SaaS / HCM & Finance"
                  />
                </div>
                <button onClick={() => removeComp(i)} className="mb-0.5 p-1.5 text-slate-400 hover:text-red-500 transition-colors">
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* Paramètres run */}
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Paramètres du run</h3>
          <div className="grid grid-cols-2 gap-3">
            <Select label="Mode" value={mode} onChange={e => setMode(e.target.value as 'A' | 'B')}>
              <option value="A">MODE A — amorçage (gèle ancres)</option>
              <option value="B">MODE B — trimestriel (re-price médiane)</option>
            </Select>
            <Select label="Agrégat comps" value={aggregate} onChange={e => setAggregate(e.target.value)}>
              <option value="arr">ARR</option>
              <option value="revenue">Revenue</option>
              <option value="ebitda">EBITDA</option>
            </Select>
            <Input label="Facteur rétention" type="number" step="0.01" value={retention} onChange={e => setRetention(e.target.value)} />
            <Input
              label={`Agrégat cible (${aggregate.toUpperCase()}) en M€ *`}
              type="number"
              step="0.1"
              value={targetAgg}
              onChange={e => setTargetAgg(e.target.value)}
              placeholder="8.0"
            />
          </div>
        </Card>

        {mut.error && <ErrorBox message="Erreur lors de la création du run. Vérifiez les données saisies." />}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => nav('/')}>Annuler</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
            <RefreshCw size={14} className={mut.isPending ? 'animate-spin' : ''} />
            {mut.isPending ? 'Acquisition en cours…' : 'Lancer le run →'}
          </Button>
        </div>
      </div>
    </div>
  )
}
