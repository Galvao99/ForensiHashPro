import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navigation = ['Visão Geral', 'Minha Conta', 'Meu Plano', 'Licença', 'Dispositivos', 'Downloads', 'Suporte']

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
        {navigation.map((label, index) => index === 0
          ? <NavLink key={label} to="/customer" end>{label}</NavLink>
          : <span key={label} aria-disabled="true">{label}<small>Em breve</small></span>)}
      </nav>
      <button type="button" className="customer-logout" onClick={signOut}>Sair</button>
    </aside>
    <section className="customer-content">
      <p className="eyebrow">ÁREA DO CLIENTE</p>
      <h1>Visão Geral</h1>
      <article className="customer-card">
        <small>CONTA AUTENTICADA</small>
        <strong>{user?.email}</strong>
        <span className="customer-status">{user?.status === 'ACTIVE' ? 'Ativa' : user?.status}</span>
      </article>
      <p className="customer-boundary">Seus arquivos e análises periciais permanecem no ForensiHash Desktop. Esta área não recebe evidências automaticamente.</p>
    </section>
  </main>
}
