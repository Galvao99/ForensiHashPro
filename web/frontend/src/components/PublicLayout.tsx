import { Outlet } from 'react-router-dom'
import { PublicHeader } from './PublicHeader'
import { Container } from './ui'

export function PublicLayout() {
  return (
    <>
      <PublicHeader />
      <main><Outlet /></main>
      <footer className="public-footer">
        <Container>
          <p>ForensiHash Pro · apoio à análise técnica de evidências digitais.</p>
          <p>Os resultados exigem interpretação conjunta com os demais elementos do caso.</p>
        </Container>
      </footer>
    </>
  )
}
