import { Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Target, TrendingUp, ArrowLeftRight } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import TargetNew from './pages/TargetNew'
import PanelPage from './pages/PanelPage'
import RunResult from './pages/RunResult'
import TransactionsPage from './pages/TransactionsPage'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: '/targets/new', icon: Target, label: 'Nouvelle cible' },
  { to: '/transactions', icon: ArrowLeftRight, label: 'Transactions M&A' },
]

export default function App() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-brand text-white flex flex-col shrink-0">
        <div className="px-5 py-4 border-b border-blue-900">
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-300">Alter Equity</p>
          <h1 className="text-base font-bold leading-tight mt-0.5">Valo Comparables</h1>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-3">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? 'bg-blue-900 text-white' : 'text-blue-200 hover:bg-blue-800 hover:text-white'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-blue-900 text-xs text-blue-400">
          IPEV déc. 2022 · V1 local
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/targets/new" element={<TargetNew />} />
          <Route path="/targets/:targetId/panel" element={<PanelPage />} />
          <Route path="/runs/:runId" element={<RunResult />} />
          <Route path="/transactions" element={<TransactionsPage />} />
        </Routes>
      </main>
    </div>
  )
}
