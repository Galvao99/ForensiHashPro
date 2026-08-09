import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  ChevronLeft,
  FileClock,
  FilePlus2,
  Fingerprint,
  LogOut,
  Menu,
  Moon,
  ShieldCheck,
  Sun,
  UserCog,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { Brand } from './Brand'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

type NavItem = readonly [LucideIcon, string, string, boolean]

const primary: NavItem[] = [
  [BarChart3, '/app', 'Overview', true],
  [FilePlus2, '/app/analysis', 'Nova análise', false],
  [FileClock, '/app/history', 'Histórico', false],
  [Fingerprint, '/app/ddna', 'DDNA', false],
]
const account: NavItem[] = [
  [UserCog, '/app/account', 'Conta', false],
  [ShieldCheck, '/app/account#privacy', 'Privacidade', false],
]

export function AppShell() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [showPrivacyNotice, setShowPrivacyNotice] = useState(
    () => Boolean(user?.last_login_at === null),
  )
  const { preferredTheme, resolvedTheme, setPreferredTheme } = useTheme()
  const navigate = useNavigate()

  async function signOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  const item = ([Icon, to, label, end]: NavItem) => (
    <NavLink
      key={to + label}
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      onClick={() => setMobile(false)}
    >
      <Icon size={18} aria-hidden="true" />
      <span>{label}</span>
    </NavLink>
  )

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <header className="app-mobile-header">
        <Brand />
        <button onClick={() => setMobile(!mobile)} aria-label="Abrir menu">
          {mobile ? <X /> : <Menu />}
        </button>
      </header>
      <aside className={`app-sidebar ${mobile ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <Brand />
          <button onClick={() => setCollapsed(!collapsed)} aria-label="Recolher sidebar">
            <ChevronLeft />
          </button>
        </div>
        <nav aria-label="Navegação da plataforma">
          {primary.map(item)}
          <div className="nav-separator" />
          {account.map(item)}
          <NavLink to="/app/assistant">
            <Bot size={18} />
            <span>Assistente <small>Em desenvolvimento</small></span>
          </NavLink>
          {user?.role === 'ADMIN' && (
            <>
              <div className="nav-separator" />
              <NavLink to="/admin/users">
                <Users size={18} />
                <span>Usuários</span>
              </NavLink>
            </>
          )}
        </nav>
        <footer className="sidebar-footer">
          <div className="user-identity">
            <strong>{user?.name}</strong>
            <small>{user?.role}</small>
          </div>
          <label className="theme-control" title="Tema">
            <span>{resolvedTheme === 'DARK' ? <Moon size={16} /> : <Sun size={16} />}</span>
            <select
              aria-label="Tema"
              value={preferredTheme}
              onChange={(event) => setPreferredTheme(event.target.value as 'LIGHT' | 'DARK' | 'SYSTEM')}
            >
              <option>LIGHT</option>
              <option>DARK</option>
              <option>SYSTEM</option>
            </select>
          </label>
          <button onClick={signOut} className="sidebar-action">
            <LogOut size={17} />
            <span>Sair</span>
          </button>
        </footer>
      </aside>
      <main className="app-content"><Outlet /></main>
      {showPrivacyNotice && (
        <div className="privacy-onboarding" role="dialog" aria-modal="true" aria-labelledby="privacy-title">
          <section>
            <p className="eyebrow">PRIMEIRO ACESSO</p>
            <h2 id="privacy-title">Como seus arquivos são tratados</h2>
            <p><strong>Seus arquivos, suas escolhas.</strong></p>
            <p>O upload é usado para a análise solicitada. O núcleo trabalha com uma cópia controlada e não modifica intencionalmente os bytes da evidência.</p>
            <p>Por padrão, o arquivo e o resultado técnico não são mantidos após o processamento. Você pode optar por manter somente resultados no histórico. Retenção do arquivo ainda não está disponível.</p>
            <p>Documentos não são usados para treinamento ou publicidade. Integrações externas permanecem sujeitas à sua preferência.</p>
            <button className="button button-primary" onClick={() => setShowPrivacyNotice(false)}>ENTENDI</button>
          </section>
        </div>
      )}
    </div>
  )
}
