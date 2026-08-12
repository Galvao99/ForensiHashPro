import { Link } from 'react-router-dom'

interface ArqenBrandProps {
  theme: 'dark' | 'light'
}

export function ArqenBrand({ theme }: ArqenBrandProps) {
  return (
    <Link to="/" className="arqen-brand" aria-label="ARQEN — página inicial">
      <img
        src={theme === 'dark' ? '/assets/arqen_logo_branca.png' : '/assets/arqen_logo_preta.png'}
        alt="ARQEN"
      />
    </Link>
  )
}
