import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, TechnicalValue } from '../components/ui'
import { ApiError, submitAnalysis } from '../lib/api'

export function AnalysisPage() {
  const [file, setFile] = useState<File | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  function select(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); setError('') }
  function drop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setFile(event.dataTransfer.files?.[0] ?? null); setError('') }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) { setError('Selecione uma evidência para análise.'); return }
    setProcessing(true); setError('')
    try {
      const result = await submitAnalysis(file)
      navigate('/app/result', { state: { result } })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Não foi possível concluir a análise.')
    } finally { setProcessing(false) }
  }

  return <div className="app-page"><div className="page-heading"><div><p className="eyebrow">NOVA ANÁLISE</p><h1>Analisar evidência</h1><p>O arquivo será enviado ao backend e adquirido pelo núcleo em cópia controlada.</p></div></div><form onSubmit={submit}><div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={drop}><input ref={inputRef} type="file" onChange={select} aria-label="Selecionar arquivo" /><p>Arraste um arquivo para esta área ou</p><Button type="button" className="button-secondary" onClick={() => inputRef.current?.click()}>Selecionar arquivo</Button></div>{file && <dl className="selected-file"><div><dt>Nome</dt><dd>{file.name}</dd></div><div><dt>Tamanho</dt><dd><TechnicalValue>{file.size.toLocaleString('pt-BR')} bytes</TechnicalValue></dd></div><div><dt>Tipo declarado</dt><dd><TechnicalValue>{file.type || 'não informado'}</TechnicalValue></dd></div></dl>}{error && <p role="alert" className="error-panel">{error}</p>}<Button type="submit" disabled={processing}>{processing ? 'Analisando evidência…' : 'Analisar'}</Button>{processing && <p role="status" className="processing-note">PROCESSING · aguardando resposta síncrona do núcleo, sem percentual estimado.</p>}</form></div>
}
