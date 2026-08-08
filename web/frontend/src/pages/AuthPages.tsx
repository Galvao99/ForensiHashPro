import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Input } from '../components/ui'

function AuthFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="auth-page"><div className="auth-panel"><p className="eyebrow">ACESSO À PLATAFORMA</p><h1>{title}</h1>{children}</div></div>
}

export function LoginPage() {
  const [notice, setNotice] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice('A autenticação será integrada em uma fase posterior. Nenhuma credencial foi enviada ou armazenada.')
  }
  return <AuthFrame title="Entrar"><form onSubmit={submit}><label>E-mail<Input name="email" type="email" autoComplete="email" required /></label><label>Senha<Input name="password" type="password" autoComplete="current-password" required /></label><Button type="submit">Entrar</Button></form>{notice && <p role="status" className="form-notice">{notice}</p>}<p>Não possui conta? <Link to="/register">Criar conta</Link></p></AuthFrame>
}

export function RegisterPage() {
  const [notice, setNotice] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice('O cadastro ainda não está disponível. Nenhum dado foi enviado ou armazenado.')
  }
  return <AuthFrame title="Criar conta"><form onSubmit={submit}><label>Nome<Input name="name" autoComplete="name" required /></label><label>E-mail<Input name="email" type="email" autoComplete="email" required /></label><label>Senha<Input name="password" type="password" autoComplete="new-password" required /></label><label>Confirmar senha<Input name="confirmPassword" type="password" autoComplete="new-password" required /></label><Button type="submit">Criar conta</Button></form>{notice && <p role="status" className="form-notice">{notice}</p>}<p>Já possui conta? <Link to="/login">Entrar</Link></p></AuthFrame>
}
