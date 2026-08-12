import { Link } from 'react-router-dom'

export function ArqenBrand({ inverted = false }: { inverted?: boolean }) {
  return (
    <Link to="/" className="arqen-brand" aria-label="ARQEN — página inicial">
      <img
        src={inverted ? '/assets/arqen_logo_preta.png' : '/assets/arqen_logo_branca.png'}
        alt="ARQEN"
      />
    </Link>
  )
}
