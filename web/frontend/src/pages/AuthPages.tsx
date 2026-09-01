import { FormEvent, ReactNode, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../lib/api'
import { DocumentMetadata } from '../components/DocumentMetadata'

export function publicRegistrationEnabled() {
  return import.meta.env.VITE_REGISTRATION_ENABLED?.toLowerCase() !== 'false'
}

function AuthFrame({ title, children }: { title: string; children: ReactNode }) {
  const { user, loading } = useAuth()
  if (!loading && user) return <Navigate to="/customer" replace />
  return <div className="customer-auth-page"><div className="customer-auth-brand"><span>FH</span><strong>ForensiHash</strong><small>Área do Cliente · ARQEN</small></div><div className="customer-auth-panel auth-panel"><p className="eyebrow">ACESSO SEGURO</p><h1>{title}</h1>{children}</div></div>
}

function PasswordField({ name, label, autoComplete }: { name: string; label: string; autoComplete: string }) {
  const [visible, setVisible] = useState(false)
  return <label>{label}<span className="password-field"><Input name={name} type={visible ? 'text' : 'password'} autoComplete={autoComplete} minLength={12} required /><button type="button" onClick={() => setVisible(!visible)} aria-label={`${visible ? 'Ocultar' : 'Mostrar'} ${label.toLowerCase()}`}>{visible ? 'Ocultar' : 'Mostrar'}</button></span></label>
}

export function LoginPage() {
  const { login, authStage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setError(''); setSubmitting(true)
    try { await login(String(data.get('email')), String(data.get('password'))); const from = (location.state as { from?: string } | null)?.from; navigate(from?.startsWith('/customer') ? from : '/customer', { replace: true }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Não foi possível entrar.') }
    finally { setSubmitting(false) }
  }
  return <><DocumentMetadata title="Acessar plataforma | ARQEN" /><AuthFrame title="Entrar"><form onSubmit={submit} aria-busy={submitting}><label>E-mail<Input name="email" type="email" autoComplete="email" required autoFocus /></label><PasswordField name="password" label="Senha" autoComplete="current-password" /><div className="auth-assistance"><Link to="/forgot-password">Esqueci minha senha</Link></div><Button type="submit" disabled={submitting}>{submitting ? 'Entrando…' : 'Entrar'}</Button></form>{submitting && <p role="status">{authStage === 'VALIDATING' ? 'Validando sessão…' : 'Enviando credenciais…'}</p>}{error && <p role="alert" className="error-panel">{error}</p>}{publicRegistrationEnabled() ? <p>Não possui conta? <Link to="/register">Criar conta</Link></p> : <p>Acesso restrito. Solicite uma conta ao administrador.</p>}</AuthFrame></>
}

export function RegisterPage() {
  const { register } = useAuth(); const navigate = useNavigate(); const [error, setError] = useState(''); const [submitting, setSubmitting] = useState(false)
  if (!publicRegistrationEnabled()) return <AuthFrame title="Acesso restrito"><p>O cadastro público está desabilitado neste ambiente.</p><Link to="/login">Voltar para o login</Link></AuthFrame>
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); const password = String(data.get('password')); const confirmation = String(data.get('password_confirmation'))
    if (password !== confirmation) { setError('As senhas não coincidem.'); return }
    setError(''); setSubmitting(true)
    try { await register({ email: String(data.get('email')), password, password_confirmation: confirmation }); navigate('/customer', { replace: true }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Não foi possível criar a conta.') }
    finally { setSubmitting(false) }
  }
  return <><DocumentMetadata title="Criar conta | ForensiHash" /><AuthFrame title="Criar conta"><form onSubmit={submit} aria-busy={submitting}><label>E-mail<Input name="email" type="email" autoComplete="email" required autoFocus /></label><PasswordField name="password" label="Senha" autoComplete="new-password" /><PasswordField name="password_confirmation" label="Confirmar senha" autoComplete="new-password" /><small>A senha deve ter ao menos 12 caracteres, letras e números.</small><Button type="submit" disabled={submitting}>{submitting ? 'Criando conta…' : 'Criar conta'}</Button></form>{error && <p role="alert" className="error-panel">{error}</p>}<p>Já possui conta? <Link to="/login">Entrar</Link></p></AuthFrame></>
}

export function ForgotPasswordPage() {
  const [notice, setNotice] = useState(''); const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSubmitting(true); const data = new FormData(event.currentTarget); try { const result = await authApi.forgotPassword(String(data.get('email'))); setNotice(result.message) } catch { setNotice('Não foi possível concluir agora. Tente novamente mais tarde.') } finally { setSubmitting(false) } }
  return <AuthFrame title="Recuperar senha"><p>Informe seu e-mail para receber as instruções de recuperação.</p><form onSubmit={submit}><label>E-mail<Input name="email" type="email" autoComplete="email" required autoFocus /></label><Button disabled={submitting}>{submitting ? 'Enviando…' : 'Enviar instruções'}</Button></form>{notice && <p role="status" className="success-panel">{notice}</p>}<Link to="/login">Voltar para o login</Link></AuthFrame>
}

export function ResetPasswordPage() {
  const [params] = useSearchParams(); const navigate = useNavigate(); const [error, setError] = useState(''); const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); const password = String(data.get('password')); const confirmation = String(data.get('password_confirmation')); if (password !== confirmation) { setError('As senhas não coincidem.'); return } setSubmitting(true); setError(''); try { await authApi.resetPassword(params.get('token') ?? '', password, confirmation); navigate('/login', { replace: true, state: { passwordReset: true } }) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Não foi possível alterar a senha.') } finally { setSubmitting(false) } }
  return <AuthFrame title="Definir nova senha"><form onSubmit={submit}><PasswordField name="password" label="Nova senha" autoComplete="new-password" /><PasswordField name="password_confirmation" label="Confirmar nova senha" autoComplete="new-password" /><Button disabled={submitting}>{submitting ? 'Alterando…' : 'Alterar senha'}</Button></form>{error && <p role="alert" className="error-panel">{error}</p>}</AuthFrame>
}
