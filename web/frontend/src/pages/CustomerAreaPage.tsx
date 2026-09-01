import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const groups = [
  { label: 'CONTA', items: ['Minha conta', 'Segurança'] },
  { label: 'PRODUTO', items: ['Meu plano', 'Licença', 'Dispositivos', 'Downloads'] },
  { label: 'FINANCEIRO', items: ['Cobrança'] },
  { label: 'AJUDA', items: ['Suporte', 'Minhas solicitações', 'Documentação'] },
]

export function CustomerAreaPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function signOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  return <main className="customer-area">
    <aside className="customer-sidebar">
      <div><span className="customer-mark">FH</span><strong>ForensiHash</strong><small>Área do Cliente</small></div>
      <nav aria-label="Área do Cliente">
        <NavLink to="/customer" end>Visão Geral</NavLink>
        {groups.map((group) => <section key={group.label} className="customer-nav-group">
          <h2>{group.label}</h2>
          {group.items.map((label) => <span key={label} aria-disabled="true">{label}<small>Em breve</small></span>)}
        </section>)}
      </nav>
      <button type="button" className="customer-logout" onClick={signOut}>Sair</button>
    </aside>
    <section className="customer-content">
      <p className="eyebrow">FORENSIHASH · ÁREA DO CLIENTE</p>
      <h1>Visão Geral</h1>
      <article className="customer-card">
        <small>CONTA AUTENTICADA</small>
        <strong>{user?.email}</strong>
        <dl className="customer-auth-facts">
          <div><dt>Status</dt><dd>{user?.status === 'ACTIVE' ? 'Ativa' : user?.status}</dd></div>
          <div><dt>E-mail</dt><dd>{user?.email_verified ? 'Verificado' : 'Ainda não verificado'}</dd></div>
        </dl>
      </article>
      <section className="customer-next-actions" aria-labelledby="available-soon">
        <h2 id="available-soon">Recursos da conta</h2>
        <p>Perfil, plano, licença, dispositivos, downloads, cobrança e suporte serão disponibilizados em etapas futuras.</p>
      </section>
      <p className="customer-boundary">Arquivos, casos e análises periciais permanecem locais no ForensiHash Desktop. Esta área não recebe evidências automaticamente.</p>
    </section>
  </main>
}
