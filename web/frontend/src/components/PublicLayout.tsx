import { Link, Outlet } from 'react-router-dom'
import { PublicHeader } from './PublicHeader'
import { ArqenBrand } from './ArqenBrand'
import { Container } from './ui'

export function PublicLayout() {
  return (
    <>
      <PublicHeader />
      <main><Outlet /></main>
      <footer className="public-footer">
        <Container className="footer-grid">
          <div className="footer-brand"><ArqenBrand inverted /><p>Infraestrutura tecnológica para proveniência, integridade, custódia e análise de artefatos digitais.</p></div>
          <div><strong>Soluções</strong><Link to="/ddna">DDNA</Link><Link to="/forensihash">ForensiHash</Link></div>
          <div><strong>Recursos</strong><Link to="/technology">Tecnologia</Link><Link to="/references">Referências</Link></div>
          <div><strong>Legal</strong><Link to="/terms">Termos de Uso</Link><Link to="/privacy">Privacidade</Link></div>
          <p className="footer-note">© {new Date().getFullYear()} ARQEN. Os resultados técnicos exigem interpretação conjunta com os demais elementos disponíveis.</p>
        </Container>
      </footer>
    </>
  )
}
