import { useLocation, Link, useParams } from 'react-router-dom'
import { JsonView } from '../components/JsonView'
import { StatusBadge } from '../components/StatusBadge'
import { TechnicalValue } from '../components/ui'
import type { AnalysisContract, ProcessingStep } from '../types/api'
import { useAnalysisSession } from '../context/AnalysisSessionContext'

function ResultSection({ title, value, step }: { title: string; value: unknown; step?: ProcessingStep }) {
  if (value === undefined) return null
  return <section className="result-section"><header><h2>{title}</h2>{step && <StatusBadge status={step.status} />}</header><JsonView value={value} /></section>
}

export function ResultView({ result }: { result: AnalysisContract }) {
  const step = (code: string) => result.processing_steps.find((item) => item.code === code || item.component === code)
  return <div className="app-page result-page"><div className="page-heading"><div><p className="eyebrow">RESULTADO TÉCNICO</p><h1>{String(result.file.name ?? 'Evidência')}</h1><p><TechnicalValue canCopy>{result.analysis_id}</TechnicalValue></p></div><StatusBadge status={result.state === 'completed' ? 'success' : result.state === 'partial' ? 'partial' : 'failed'} /></div><section className="result-summary"><div><span>Schema</span><TechnicalValue>{result.schema_version}</TechnicalValue></div><div><span>Tipo declarado</span><TechnicalValue>{result.declared_type ?? 'não informado'}</TechnicalValue></div><div><span>Tipo detectado</span><TechnicalValue>{result.detected_type ?? 'não identificado'}</TechnicalValue></div></section><section className="result-section"><header><h2>Hashes</h2></header><div className="hash-list">{Object.entries(result.hashes).map(([name, value]) => <div key={name}><span>{name.toUpperCase()}</span><TechnicalValue canCopy>{value}</TechnicalValue></div>)}</div></section><ResultSection title="Metadados" value={result.metadata} step={step('metadata')} /><ResultSection title="Estrutura" value={result.technical_structure} step={step('pdf_structure')} /><ResultSection title="Assinaturas" value={result.signatures} /><ResultSection title="Texto nativo" value={result.native_text} step={step('text_extraction')} /><ResultSection title="OCR" value={result.ocr} step={step('text_extraction')} /><ResultSection title="Timeline" value={result.timeline} step={step('timeline')} /><ResultSection title="Biometria" value={result.biometrics} step={step('biometric')} /><ResultSection title="IP" value={result.ip_addresses} step={step('ip_context')} /><ResultSection title="Vestígios" value={result.findings} /><ResultSection title="Fatos" value={result.facts} /><ResultSection title="Limitações" value={result.limitations} /><ResultSection title="Erros" value={result.errors} /><section className="result-section"><header><h2>Processamento</h2></header><div className="steps-list">{result.processing_steps.map((item, index) => <div key={item.step_id ?? `${item.code}-${index}`}><span>{item.code}</span><StatusBadge status={item.status} /><small>{item.user_message}</small></div>)}</div></section><ResultSection title="Execução" value={result.execution} /></div>
}

export function ResultPage() {
  const location = useLocation()
  const { analysisId } = useParams()
  const { getAnalysis } = useAnalysisSession()
  const routedResult = (location.state as { result?: AnalysisContract } | null)?.result
  const result = routedResult ?? (analysisId ? getAnalysis(analysisId) : undefined)
  if (!result) return <div className="app-page"><h1>Nenhum resultado nesta sessão</h1><p>As análises ainda não são persistidas.</p><Link className="button-link" to="/app/analysis">Iniciar análise</Link></div>
  return <ResultView result={result} />
}
