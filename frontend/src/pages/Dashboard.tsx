import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, ChevronRight } from 'lucide-react'
import { getTargets, type Target } from '../api'
import { PageHeader, Card, Badge, Button, Spinner, ErrorBox } from '../components/ui'

export default function Dashboard() {
  const { data: targets, isLoading, error } = useQuery({
    queryKey: ['targets'],
    queryFn: getTargets,
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="Tableau de bord" sub="Cibles et runs de valorisation" />
        <Link to="/targets/new">
          <Button><Plus size={14} /> Nouvelle cible</Button>
        </Link>
      </div>

      {isLoading && <Spinner />}
      {error && <ErrorBox message="Impossible de charger les cibles. L'API est-elle démarrée ?" />}

      {targets && targets.length === 0 && (
        <Card className="p-10 text-center text-slate-400">
          <p className="text-base font-medium">Aucune cible pour l'instant.</p>
          <p className="text-sm mt-1">Créez votre première cible pour démarrer un run de valo.</p>
          <Link to="/targets/new" className="mt-4 inline-block">
            <Button><Plus size={14} /> Nouvelle cible</Button>
          </Link>
        </Card>
      )}

      {targets && targets.length > 0 && (
        <div className="space-y-3">
          {targets.map(t => <TargetRow key={t.id} target={t} />)}
        </div>
      )}
    </div>
  )
}

function TargetRow({ target }: { target: Target }) {
  return (
    <Card className="flex items-center justify-between px-5 py-4 hover:border-brand/40 transition-colors">
      <div className="flex items-center gap-4">
        <div>
          <p className="font-semibold text-slate-800">{target.name}</p>
          <p className="text-xs text-slate-500 mt-0.5">
            {target.sector ?? '—'} · {target.fund ?? '—'}
          </p>
        </div>
        <div className="flex gap-1.5">
          <Badge variant={target.is_recurring ? 'green' : 'gray'}>
            {target.is_recurring ? 'Récurrent' : 'Non récurrent'}
          </Badge>
          <Badge>{target.valuation_aggregate.toUpperCase()}</Badge>
        </div>
      </div>
      <Link to={`/targets/${target.id}/panel`}>
        <Button variant="secondary">
          Nouveau run <ChevronRight size={14} />
        </Button>
      </Link>
    </Card>
  )
}
