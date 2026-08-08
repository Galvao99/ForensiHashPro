import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AvailabilityBadge } from '../components/StatusBadge'
import { getCapabilities } from '../lib/api'
import type { Capabilities } from '../types/api'

const labels: Record<string, string> = { hashes: 'Hashes', metadata: 'Metadados', ocr: 'OCR', pdf_structure: 'Estrutura PDF', binary_structure: 'Estrutura binária', signature: 'Assinaturas', rust_json: 'JSON / Rust', biometrics: 'Biometria' }

export function DashboardPage() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { getCapabilities().then(setCapabilities).catch(() => setError('Não foi possível consultar as capacidades do backend.')) }, [])
  return <div className="app-page"><div className="page-heading"><div><p className="eyebrow">OVERVIEW</p><h1>Ambiente de análise</h1><p>Estado operacional informado diretamente pelo backend.</p></div><Link className="button-link" to="/app/analysis">Nova análise</Link></div>{error && <p role="alert" className="error-panel">{error}</p>}<section className="app-panel"><h2>Capacidades</h2>{!capabilities ? <p>Consultando ambiente…</p> : <div className="capability-table">{Object.entries(labels).map(([key, label]) => <div key={key}><span>{label}</span><AvailabilityBadge available={Boolean(capabilities[key]?.available)} /></div>)}</div>}</section></div>
}
