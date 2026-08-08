import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`container ${className}`.trim()}>{children}</div>
}

export function Section({
  children,
  eyebrow,
  title,
  className = '',
}: {
  children: ReactNode
  eyebrow?: string
  title?: string
  className?: string
}) {
  return (
    <section className={`section ${className}`.trim()}>
      <Container>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        {title && <h2>{title}</h2>}
        {children}
      </Container>
    </section>
  )
}

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`.trim()} {...props} />
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`.trim()} {...props} />
}

export function Divider() {
  return <hr className="divider" />
}

export function TechnicalValue({ children, canCopy = false }: { children: ReactNode; canCopy?: boolean }) {
  const value = typeof children === 'string' ? children : ''
  return (
    <span className="technical-value">
      <code>{children}</code>
      {canCopy && value && (
        <button type="button" className="copy-button" onClick={() => navigator.clipboard?.writeText(value)}>
          Copiar
        </button>
      )}
    </span>
  )
}
