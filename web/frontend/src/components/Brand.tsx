import { Link } from 'react-router-dom'

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="ForensiHash Pro — página inicial">
      <span className="brand-mark" aria-hidden="true">FH</span>
      <span>
        <strong>FORENSIHASH</strong>
        <small>PRO</small>
      </span>
    </Link>
  )
}
