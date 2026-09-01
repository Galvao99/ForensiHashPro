import type { ReactNode } from 'react'
import { ArqenBrand } from './ArqenBrand'

interface AuthLayoutProps {
  title: string
  children: ReactNode
}

export function ForensiHashLogo({ className = '' }: { className?: string }) {
  return (
    <img
      className={`forensihash-logo ${className}`.trim()}
      src="/assets/forensihash_logo_branco.png"
      alt="ForensiHash"
    />
  )
}

export function AuthLayout({ title, children }: AuthLayoutProps) {
  return (
    <div className="customer-auth-page">
      <section className="customer-auth-brand" aria-label="ForensiHash — Área do Cliente">
        <div className="auth-brand-parent"><span>Um produto</span><ArqenBrand theme="dark" /></div>
        <div className="auth-brand-product">
          <ForensiHashLogo />
          <p>Área do Cliente</p>
          <small>Conta e acesso ao produto</small>
        </div>
        <div className="auth-brand-geometry" aria-hidden="true" />
      </section>
      <section className="customer-auth-surface">
        <div className="customer-auth-panel">
          <p className="eyebrow">ÁREA DO CLIENTE</p>
          <h1>{title}</h1>
          {title === 'Entrar' && <p className="auth-introduction">Acesse sua conta para continuar.</p>}
          {children}
        </div>
      </section>
    </div>
  )
}
