import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { createTarget } from '../api'
import { PageHeader, Card, Input, Select, Button, ErrorBox } from '../components/ui'

interface Form {
  name: string
  sector: string
  is_recurring: string
  valuation_aggregate: string
  fund: string
  aggregate_value: string
  net_debt: string
  growth_now: string
  description: string
  notes: string
}

export default function TargetNew() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { register, handleSubmit, watch, formState: { errors } } = useForm<Form>({
    defaultValues: { is_recurring: 'true', valuation_aggregate: 'arr', fund: '' },
  })
  const agg = watch('valuation_aggregate')

  const mut = useMutation({
    mutationFn: (data: Form) =>
      createTarget({
        name: data.name,
        sector: data.sector || null,
        is_recurring: data.is_recurring === 'true',
        valuation_aggregate: data.valuation_aggregate,
        fund: data.fund || null,
        aggregate_value: data.aggregate_value ? parseFloat(data.aggregate_value) * 1e6 : null,
        net_debt: data.net_debt ? parseFloat(data.net_debt) * 1e6 : null,
        growth_now: data.growth_now ? parseFloat(data.growth_now) / 100 : null,
        description: data.description || null,
        notes: data.notes || null,
      }),
    onSuccess: (target) => {
      qc.invalidateQueries({ queryKey: ['targets'] })
      nav(`/targets/${target.id}/panel`)
    },
  })

  return (
    <div className="p-8 max-w-xl">
      <PageHeader title="Nouvelle cible" sub="Nom + chiffres clés. La découverte des comparables est automatique à l'étape suivante." />

      <Card className="p-6">
        <form onSubmit={handleSubmit(d => mut.mutate(d))} className="space-y-4">
          <Input label="Nom de la cible *" {...register('name', { required: 'Champ requis' })}
            error={errors.name?.message} placeholder="ex. Syroco" />
          <Input label="Secteur" {...register('sector')} placeholder="ex. SaaS / Maritime" />

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Description (pitch — utilisée pour la découverte)</span>
            <textarea {...register('description')} rows={2}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40"
              placeholder="Logiciel SaaS de décarbonation maritime, ARR récurrent…" />
          </label>

          <div className="grid grid-cols-2 gap-4">
            <Select label="Modèle récurrent" {...register('is_recurring')}>
              <option value="true">Récurrent</option>
              <option value="false">Non récurrent</option>
            </Select>
            <Select label="Agrégat de valo *" {...register('valuation_aggregate')}>
              <option value="arr">ARR</option>
              <option value="revenue">Revenue</option>
              <option value="ebitda">EBITDA</option>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input label={`${agg?.toUpperCase() ?? 'Agrégat'} courant (M€)`} type="number" step="any"
              {...register('aggregate_value')} placeholder="1.437" />
            <Input label="Dette nette (M€)" type="number" step="any"
              {...register('net_debt')} placeholder="0.3" />
          </div>

          <Input label="Croissance actuelle (% YoY)" type="number" step="any"
            {...register('growth_now')} placeholder="45" />

          <Select label="Fonds" {...register('fund')}>
            <option value="">—</option>
            <option value="FR FII">FR Fonds II</option>
            <option value="EN FIII">EN Fonds III</option>
          </Select>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Notes</span>
            <textarea {...register('notes')} rows={2}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40" />
          </label>

          {mut.error && <ErrorBox message="Erreur lors de la création. Vérifiez que l'API est démarrée." />}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => nav('/')}>Annuler</Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending ? 'Création…' : 'Créer → découvrir les comparables'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
