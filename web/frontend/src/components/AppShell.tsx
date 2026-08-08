import { NavLink, Outlet } from 'react-router-dom'
import { Brand } from './Brand'

const items = [
  ['/app', 'Overview', true],
  ['/app/analysis', 'Nova análise', false],
  ['/app/history', 'Histórico', false],
  ['/app/ddna', 'DDNA', false],
  ['/app/account', 'Conta', false],
] as const

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="app-header"><Brand /><span className="environment-label">AMBIENTE LOCAL</span></header>
      <aside className="app-sidebar">
        <nav aria-label="Navegação da plataforma">
          {items.map(([to, label, end]) => <NavLink key={to} to={to} end={end}>{label}</NavLink>)}
        </nav>
      </aside>
      <main className="app-content"><Outlet /></main>
    </div>
  )
}
