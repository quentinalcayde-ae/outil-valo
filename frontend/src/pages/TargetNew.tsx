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
  notes: string
}

export default function TargetNew() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({
    defaultValues: { is_recurring: 'true', valuation_aggregate: 'arr', fund: '' },
  })

  const mut = useMutation({
    mutationFn: (data: Form) =>
      createTarget({
        ...data,
        is_recurring: data.is_recurring === 'true',
        sector: data.sector || null,
        fund: data.fund || null,
        notes: data.notes || null,
      }),
    onSuccess: (target) => {
      qc.invalidateQueries({ queryKey: ['targets'] })
      nav(`/targets/${target.id}/panel`)
    },
  })

  return (
    <div className="p-8 max-w-xl">
      <PageHeader title="Nouvelle cible" sub="Saisissez les attributs de la société à valoriser" />

      <Card className="p-6">
        <form onSubmit={handleSubmit(d => mut.mutate(d))} className="space-y-4">
          <Input
            label="Nom de la cible *"
            {...register('name', { required: 'Champ requis' })}
            error={errors.name?.message}
            placeholder="ex. Syroco"
          />
          <Input label="Secteur" {...register('sector')} placeholder="ex. SaaS / Maritime" />
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
          <Select label="Fonds" {...register('fund')}>
            <option value="">—</option>
            <option value="FR FII">FR Fonds II</option>
            <option value="EN FIII">EN Fonds III</option>
          </Select>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Notes</span>
            <textarea
              {...register('notes')}
              rows={3}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40"
              placeholder="Contexte, particularités…"
            />
          </label>

          {mut.error && <ErrorBox message="Erreur lors de la création. Vérifiez que l'API est démarrée." />}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => nav('/')}>Annuler</Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending ? 'Création…' : 'Créer et configurer le panel →'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
