import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Container({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`container ${className}`.trim()}>{children}</div>
}

export function Section({
  children,
  eyebrow,
  title,
  className = '',
  id,
  headingLevel = 'h2',
}: {
  children: ReactNode
  eyebrow?: string
  title?: string
  className?: string
  id?: string
  headingLevel?: 'h1' | 'h2'
}) {
  const Heading = headingLevel
  return (
    <section id={id} className={`section ${className}`.trim()}>
      <Container>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        {title && <Heading>{title}</Heading>}
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

export function TechnicalValue({ children, canCopy = false, copyValue }: { children: ReactNode; canCopy?: boolean; copyValue?: string }) {
  const value = typeof children === 'string' ? children : ''
  const copiedValue = copyValue ?? value
  return (
    <span className="technical-value">
      <code>{children}</code>
      {canCopy && copiedValue && (
        <button type="button" className="copy-button" aria-label="Copiar valor" onClick={() => navigator.clipboard?.writeText(copiedValue)}>
          Copiar
        </button>
      )}
    </span>
  )
}
