import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { getTransactions, createTransaction, deleteTransaction, type Transaction } from '../api'
import { PageHeader, Card, Button, Input, Spinner, ErrorBox, Badge } from '../components/ui'

export default function TransactionsPage() {
  const qc = useQueryClient()
  const { data: txs, isLoading, error } = useQuery({
    queryKey: ['transactions'],
    queryFn: getTransactions,
  })

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    target_company: '', acquirer: '', tx_date: '', sector: '',
    price_disclosed: false, price: '', implied_multiple: '',
    source_doc_url: '', notes: '',
  })

  const createMut = useMutation({
    mutationFn: () => createTransaction({
      ...form,
      price_disclosed: form.price_disclosed,
      price: form.price ? parseFloat(form.price) : null,
      implied_multiple: form.implied_multiple ? parseFloat(form.implied_multiple) : null,
      tx_date: form.tx_date || null,
      acquirer: form.acquirer || null,
      sector: form.sector || null,
      source_doc_url: form.source_doc_url || null,
      notes: form.notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      setShowForm(false)
      setForm({ target_company: '', acquirer: '', tx_date: '', sector: '', price_disclosed: false, price: '', implied_multiple: '', source_doc_url: '', notes: '' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['transactions'] }),
  })

  const f = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }))

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <PageHeader
          title="Transactions M&A"
          sub="Cross-check qualitatif — hors médiane"
        />
        <Button onClick={() => setShowForm(s => !s)}>
          <Plus size={14} /> Ajouter
        </Button>
      </div>

      {showForm && (
        <Card className="p-5 mb-5">
          <h3 className="text-sm font-semibold mb-3">Nouvelle transaction</h3>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Société cible *" value={form.target_company} onChange={f('target_company')} />
            <Input label="Acquéreur" value={form.acquirer} onChange={f('acquirer')} />
            <Input label="Date" type="date" value={form.tx_date} onChange={f('tx_date')} />
            <Input label="Secteur" value={form.sector} onChange={f('sector')} />
            <Input label="Prix (M€)" type="number" step="0.1" value={form.price} onChange={f('price')} />
            <Input label="Multiple implicite (x)" type="number" step="0.1" value={form.implied_multiple} onChange={f('implied_multiple')} />
            <Input label="Source (URL)" value={form.source_doc_url} onChange={f('source_doc_url')} className="col-span-2" />
          </div>
          <label className="flex items-center gap-2 mt-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.price_disclosed} onChange={e => setForm(p => ({ ...p, price_disclosed: e.target.checked }))} />
            Prix divulgué
          </label>
          <div className="flex gap-2 justify-end mt-3">
            <Button variant="secondary" onClick={() => setShowForm(false)}>Annuler</Button>
            <Button onClick={() => createMut.mutate()} disabled={!form.target_company || createMut.isPending}>
              {createMut.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </Card>
      )}

      {isLoading && <Spinner />}
      {error && <ErrorBox message="Impossible de charger les transactions." />}

      {txs && txs.length === 0 && !showForm && (
        <Card className="p-10 text-center text-slate-400">
          <p>Aucune transaction enregistrée.</p>
          <p className="text-sm mt-1">Les transactions M&A servent de cross-check qualitatif, jamais de médiane.</p>
        </Card>
      )}

      {txs && txs.length > 0 && (
        <Card>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
              <tr>
                <th className="px-5 py-2 text-left">Cible</th>
                <th className="px-4 py-2 text-left">Acquéreur</th>
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-left">Secteur</th>
                <th className="px-4 py-2 text-right">Multiple</th>
                <th className="px-4 py-2 text-center">Prix divulgué</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {txs.map((tx: Transaction) => (
                <tr key={tx.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 font-medium">{tx.target_company}</td>
                  <td className="px-4 py-3 text-slate-600">{tx.acquirer ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{tx.tx_date ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{tx.sector ?? '—'}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {tx.implied_multiple ? `${tx.implied_multiple.toFixed(1)}x` : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge variant={tx.price_disclosed ? 'green' : 'gray'}>
                      {tx.price_disclosed ? 'Oui' : 'Non'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => deleteMut.mutate(tx.id)} className="text-slate-300 hover:text-red-500 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
