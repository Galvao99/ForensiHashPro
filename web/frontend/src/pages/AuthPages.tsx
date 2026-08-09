import { FormEvent, ReactNode, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'

function AuthFrame({ title, children }: { title: string; children: ReactNode }) {
  return <div className="auth-page"><div className="auth-panel"><p className="eyebrow">ACESSO À PLATAFORMA</p><h1>{title}</h1>{children}</div></div>
}

export function LoginPage() {
  const { login, authStage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    setSubmitting(true)
    try {
      await login(String(data.get('email')), String(data.get('password')))
      const from = (location.state as { from?: string } | null)?.from
      navigate(from?.startsWith('/app') || from?.startsWith('/admin') ? from : '/app', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível entrar.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthFrame title="Entrar">
      <form onSubmit={submit} aria-busy={submitting}>
        <label>E-mail<Input name="email" type="email" autoComplete="email" required /></label>
        <label>Senha<Input name="password" type="password" autoComplete="current-password" required /></label>
        <Button type="submit" disabled={submitting}>{submitting ? 'Entrando…' : 'Entrar'}</Button>
      </form>
      {submitting && <p role="status" className="processing-note">{authStage === 'VALIDATING' ? 'VALIDANDO SESSÃO…' : 'ENVIANDO CREDENCIAIS…'}</p>}
      {error && <p role="alert" className="error-panel">{error}</p>}
      <p>Não possui conta? <Link to="/register">Criar conta</Link></p>
    </AuthFrame>
  )
}

export function RegisterPage() {
  const { register, authStage } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    if (data.get('password') !== data.get('confirmPassword')) {
      setError('As senhas não coincidem.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await register({
        name: String(data.get('name')),
        email: String(data.get('email')),
        password: String(data.get('password')),
        accept_terms: data.get('terms') === 'on',
        accept_privacy: data.get('privacy') === 'on',
      })
      navigate('/app', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível criar a conta.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthFrame title="Criar conta">
      <form onSubmit={submit} aria-busy={submitting}>
        <label>Nome<Input name="name" autoComplete="name" required /></label>
        <label>E-mail<Input name="email" type="email" autoComplete="email" required /></label>
        <label>Senha<Input name="password" type="password" autoComplete="new-password" minLength={12} required /></label>
        <label>Confirmar senha<Input name="confirmPassword" type="password" autoComplete="new-password" required /></label>
        <label className="check-line"><input name="terms" type="checkbox" required /> Li e aceito os <Link to="/terms">Termos de Uso</Link>.</label>
        <label className="check-line"><input name="privacy" type="checkbox" required /> Li e aceito a <Link to="/privacy">Política de Privacidade</Link>.</label>
        <Button type="submit" disabled={submitting}>{submitting ? 'Criando conta…' : 'Criar conta'}</Button>
      </form>
      {submitting && <p role="status" className="processing-note">{authStage === 'VALIDATING' ? 'VALIDANDO SESSÃO…' : 'ENVIANDO CADASTRO…'}</p>}
      {error && <p role="alert" className="error-panel">{error}</p>}
      <p>Já possui conta? <Link to="/login">Entrar</Link></p>
    </AuthFrame>
  )
}
