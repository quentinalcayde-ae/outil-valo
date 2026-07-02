import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, Sparkles, ArrowRight, CheckCircle2, AlertTriangle } from 'lucide-react'
import { getTarget, suggest, getSuggestions, getAnchors, createPanel, resolveTickers, type SuggestResponse, type ResolveItem } from '../api'
import { PageHeader, Card, Input, Select, Button, Spinner, ErrorBox } from '../components/ui'

interface Row { ticker: string; name: string; relevance_note: string; included: boolean }

export default function PanelPage() {
  const { targetId } = useParams<{ targetId: string }>()
  const id = Number(targetId)
  const nav = useNavigate()

  const { data: target } = useQuery({ queryKey: ['target', id], queryFn: () => getTarget(id) })

  const [rows, setRows] = useState<Row[]>([])
  const [txs, setTxs] = useState<{ label: string; note: string; keep: boolean }[]>([])
  // Résolution yfinance : ticker (majuscules) -> {valid, name}
  const [resolved, setResolved] = useState<Record<string, { valid: boolean; name: string | null }>>({})

  const resolveMut = useMutation({
    mutationFn: (tickers: string[]) => resolveTickers(tickers),
    onSuccess: (items: ResolveItem[]) => {
      setResolved(prev => {
        const next = { ...prev }
        items.forEach(i => { next[i.ticker.toUpperCase()] = { valid: i.valid, name: i.name } })
        return next
      })
    },
  })

  const [fromCache, setFromCache] = useState(false)

  const populate = (data: SuggestResponse) => {
    setRows(data.comps.map(c => ({
      ticker: c.ticker, name: c.name, relevance_note: c.rationale, included: true,
    })))
    setTxs(data.transactions.map(t => ({
      label: `${t.target_company}${t.acquirer ? ` ← ${t.acquirer}` : ''}`,
      note: t.rationale, keep: true,
    })))
    const tickers = data.comps.map(c => c.ticker).filter(Boolean)
    if (tickers.length) resolveMut.mutate(tickers)
  }

  // Découverte LLM (forcée) — ré-appelle le modèle et écrase le cache
  const suggestMut = useMutation({
    mutationFn: () => suggest(id, { n_comps: 8, n_transactions: 5 }),
    onSuccess: (data) => { setFromCache(false); populate(data) },
  })

  // À l'arrivée : réutilise la découverte mémorisée si elle existe (aucun appel LLM),
  // sinon lance la découverte une première fois.
  useEffect(() => {
    if (!target) return
    let cancelled = false
    getSuggestions(id).then(cached => {
      if (cancelled) return
      if (cached.comps.length > 0) { setFromCache(true); populate(cached) }
      else suggestMut.mutate()
    })
    return () => { cancelled = true }
  }, [target?.id]) // eslint-disable-line

  const [mode, setMode] = useState<'A' | 'B'>('A')
  const [otherDeltas, setOtherDeltas] = useState('0')
  const [useAnchor, setUseAnchor] = useState(true)
  const [entryDate, setEntryDate] = useState('')
  const [entryRound, setEntryRound] = useState('')
  const [mEntry, setMEntry] = useState('')
  const [entryGrowth, setEntryGrowth] = useState('')  // croissance cible au tour (%)

  // Pré-remplit l'ancre depuis la cible si elle a déjà été saisie (pas de re-saisie à chaque run)
  useEffect(() => {
    if (!target) return
    getAnchors(id).then(anchors => {
      const a = anchors[anchors.length - 1]
      if (a) {
        setEntryDate(a.entry_date ?? '')
        setEntryRound(a.entry_round ?? '')
        setMEntry(a.m_entry_aggregate != null ? String(a.m_entry_aggregate) : '')
        setEntryGrowth(a.entry_growth != null ? String(a.entry_growth * 100) : '')
        setUseAnchor(true)
      }
    })
  }, [target?.id]) // eslint-disable-line

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
      other_deltas: parseFloat(otherDeltas) || 0,
      anchor: useAnchor && entryDate && mEntry
        ? {
            entry_date: entryDate, entry_round: entryRound || null,
            m_entry_aggregate: parseFloat(mEntry),
            entry_growth: entryGrowth ? parseFloat(entryGrowth) / 100 : null,
          }
        : null,
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
            {fromCache && (
              <span className="ml-1 rounded bg-green-100 text-green-700 text-[11px] font-medium px-1.5 py-0.5">
                panel réutilisé (dernière découverte)
              </span>
            )}
          </h3>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => resolveMut.mutate(rows.map(r => r.ticker).filter(Boolean))}
              disabled={resolveMut.isPending || rows.length === 0}>
              {resolveMut.isPending ? 'Vérif…' : 'Vérifier les tickers'}
            </Button>
            <Button variant="secondary" onClick={() => suggestMut.mutate()} disabled={suggestMut.isPending}>
              {suggestMut.isPending ? 'Recherche…' : 'Re-découvrir (LLM)'}
            </Button>
            <Button variant="secondary" onClick={addRow}><Plus size={13} /> Ajouter</Button>
          </div>
        </div>

        {suggestMut.isPending && <Spinner />}
        {suggestMut.error && <div className="p-4"><ErrorBox message="Échec de la découverte (LLM). Réessayez." /></div>}

        {!suggestMut.isPending && rows.length > 0 && (
          <div className="divide-y divide-slate-100">
            <div className="grid grid-cols-[auto_120px_1fr_auto] gap-3 px-5 py-2 text-xs font-medium text-slate-400 uppercase">
              <span>Inclus</span><span>Ticker</span><span>Pourquoi pertinent</span><span></span>
            </div>
            {rows.map((r, i) => {
              const res = resolved[r.ticker.trim().toUpperCase()]
              return (
                <div key={i} className="grid grid-cols-[auto_120px_1fr_auto] gap-3 px-5 py-2 items-start">
                  <input type="checkbox" className="mt-2" checked={r.included} onChange={e => upd(i, 'included', e.target.checked)} />
                  <div>
                    <input value={r.ticker}
                      onChange={e => upd(i, 'ticker', e.target.value)}
                      onBlur={() => r.ticker.trim() && resolveMut.mutate([r.ticker.trim()])}
                      className="w-full rounded border border-slate-300 px-2 py-1 text-sm font-mono uppercase" placeholder="WDAY" />
                    {res && (
                      <p className={`mt-0.5 text-[11px] flex items-center gap-1 ${res.valid ? 'text-green-600' : 'text-amber-600'}`}>
                        {res.valid ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
                        {res.valid ? res.name : 'ticker introuvable / à corriger'}
                      </p>
                    )}
                  </div>
                  <input value={r.relevance_note} onChange={e => upd(i, 'relevance_note', e.target.value)}
                    className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-600 mt-0.5" />
                  <button onClick={() => rmRow(i)} className="mt-1.5 text-slate-300 hover:text-red-500"><Trash2 size={15} /></button>
                </div>
              )
            })}
            <p className="px-5 py-2 text-[11px] text-slate-400">
              Le nom affiché est celui réellement résolu par Yahoo Finance — vérifiez qu'il correspond bien à la société visée
              (ex. un ticker peut pointer vers une autre société que celle proposée).
            </p>
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

      {/* Ancres d'entrée (optionnelles) */}
      <Card className="mb-5 p-5">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-3">
          <input type="checkbox" checked={useAnchor} onChange={e => setUseAnchor(e.target.checked)} />
          Utiliser une ancre de tour (calibration IPEV par delta)
        </label>

        {useAnchor ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Date du tour *" type="date" value={entryDate} onChange={e => setEntryDate(e.target.value)} />
              <Input label="Libellé tour" value={entryRound} onChange={e => setEntryRound(e.target.value)} placeholder="Série B" />
              <Input label={`M_entry (EV/${target.valuation_aggregate} au tour) *`} type="number" step="any"
                value={mEntry} onChange={e => setMEntry(e.target.value)} placeholder="8.0" />
              <Input label="Croissance cible au tour (% YoY)" type="number" step="any"
                value={entryGrowth} onChange={e => setEntryGrowth(e.target.value)} placeholder="45" />
            </div>
            <p className="text-xs text-slate-400 mt-2">
              La médiane marché au tour (m_market_entry) et la croissance du panel au tour seront
              calculées automatiquement à l'étape suivante (base trailing yfinance).
            </p>
          </>
        ) : (
          <p className="text-xs text-amber-600">
            Valorisation directe : la médiane des comparables est appliquée telle quelle, avec
            ajustement de croissance vs le panel (si dispo), sans référence à un tour d'entrée.
          </p>
        )}
        <div className="grid grid-cols-2 gap-3 mt-3">
          <Select label="Mode" value={mode} onChange={e => setMode(e.target.value as 'A' | 'B')}>
            <option value="A">MODE A — amorçage</option>
            <option value="B">MODE B — trimestriel</option>
          </Select>
          <Input label="Autres deltas société (tours : marge/NRR/taille)" type="number" step="any"
            value={otherDeltas} onChange={e => setOtherDeltas(e.target.value)} placeholder="0" />
        </div>
      </Card>

      {panelMut.error && <ErrorBox message="Erreur lors de la création du panel. Vérifiez qu'au moins un comparable est inclus (et l'ancre si activée)." />}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => nav('/')}>Annuler</Button>
        <Button onClick={() => panelMut.mutate()}
          disabled={panelMut.isPending
            || (useAnchor && (!entryDate || !mEntry))
            || rows.filter(r => r.included && r.ticker).length === 0}>
          {panelMut.isPending ? 'Création…' : 'Valider le panel'} <ArrowRight size={14} />
        </Button>
      </div>
    </div>
  )
}
