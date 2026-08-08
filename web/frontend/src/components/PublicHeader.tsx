import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Brand } from './Brand'
import { Container } from './ui'

const links = [
  ['/forensihash', 'Produto'],
  ['/ddna', 'DDNA'],
  ['/technology', 'Tecnologia'],
  ['/references', 'Referências'],
]

export function PublicHeader() {
  const [open, setOpen] = useState(false)
  return (
    <header className="public-header">
      <Container className="header-inner">
        <Brand />
        <button className="menu-button" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
          Menu
        </button>
        <nav className={open ? 'public-nav open' : 'public-nav'} aria-label="Navegação principal">
          {links.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          <Link to="/login">Entrar</Link>
          <Link className="button-link" to="/app/analysis">Começar análise</Link>
        </nav>
      </Container>
    </header>
  )
}
