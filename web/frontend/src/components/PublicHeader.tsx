import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { ArqenBrand } from './ArqenBrand'
import { Container } from './ui'

const links = [
  ['/#solutions', 'Soluções'],
  ['/ddna', 'DDNA'],
  ['/forensihash', 'ForensiHash'],
  ['/references', 'Recursos'],
]

export function PublicHeader() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const { pathname } = useLocation()
  const hasDarkHero = pathname === '/' || pathname === '/ddna'
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return (
    <header className={`public-header ${hasDarkHero ? 'on-dark-hero' : ''} ${scrolled ? 'is-scrolled' : ''}`}>
      <Container className="header-inner">
        <ArqenBrand theme="dark" />
        <button className="menu-button" type="button" aria-expanded={open} aria-controls="public-navigation" aria-label={open ? 'Fechar menu' : 'Abrir menu'} onClick={() => setOpen(!open)}>
          <span aria-hidden="true">{open ? '×' : '☰'}</span><span>Menu</span>
        </button>
        <nav id="public-navigation" className={open ? 'public-nav open' : 'public-nav'} aria-label="Navegação principal">
          {links.map(([to, label]) => to.includes('#') ? <Link key={to} to={to} onClick={() => setOpen(false)}>{label}</Link> : <NavLink key={to} to={to} onClick={() => setOpen(false)}>{label}</NavLink>)}
          <Link className="header-cta" to="/app/analysis" onClick={() => setOpen(false)}>Acessar plataforma</Link>
        </nav>
      </Container>
    </header>
  )
}
