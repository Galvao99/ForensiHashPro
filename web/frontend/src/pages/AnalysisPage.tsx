import { ChangeEvent, DragEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUp, FolderUp } from 'lucide-react'
import { Button } from '../components/ui'
import { MAX_WORKSPACE_FILES, useAnalysisSession } from '../context/AnalysisSessionContext'
import { useAuth } from '../context/AuthContext'

export function AnalysisPage() {
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { enqueueFiles, workspace } = useAnalysisSession()
  const { privacy, csrfToken } = useAuth()
  const [privateSession, setPrivateSession] = useState(privacy?.retention_mode === 'PRIVATE')

  function enqueue(files: File[]) {
    const result = enqueueFiles(files, {
      retentionMode: privacy?.retention_mode,
      privateSession,
      csrfToken,
    })
    setError(result.message ?? '')
    if (result.accepted > 0) navigate('/app/result')
  }

  function select(event: ChangeEvent<HTMLInputElement>) {
    enqueue(Array.from(event.target.files ?? []))
    event.target.value = ''
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    enqueue(Array.from(event.dataTransfer.files ?? []))
  }

  const directoryAttributes = { webkitdirectory: '', directory: '' }

  return (
    <div className="app-page">
      <div className="page-heading"><div><p className="eyebrow">NOVA ANÁLISE</p><h1>Analisar evidências</h1><p>Cada arquivo será adquirido e analisado individualmente pelo núcleo.</p></div></div>
      <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={drop}>
        <input ref={fileInput} type="file" onChange={select} aria-label="Selecionar arquivo" />
        <input ref={folderInput} type="file" multiple onChange={select} aria-label="Selecionar pasta" {...directoryAttributes} />
        <p>Arraste arquivos para esta área ou escolha uma origem.</p>
        <div className="analysis-source-actions">
          <Button type="button" className="button-secondary" onClick={() => fileInput.current?.click()}><FileUp size={16} />Selecionar arquivo</Button>
          <Button type="button" className="button-secondary" onClick={() => folderInput.current?.click()}><FolderUp size={16} />Selecionar pasta</Button>
        </div>
        <small>Até {MAX_WORKSPACE_FILES} arquivos por workspace; no máximo 2 análises simultâneas.</small>
      </div>
      <label className="private-session"><input type="checkbox" checked={privateSession} onChange={(event) => setPrivateSession(event.target.checked)} /><span><strong>Sessão privada</strong><small>Contratos concluídos não serão adicionados ao histórico.</small></span></label>
      {workspace.analyses.length > 0 && <p className="compact-message">{workspace.analyses.length} análise(s) aberta(s). Novas seleções serão adicionadas ao workspace atual.</p>}
      {error && <p role="alert" className="error-panel">{error}</p>}
    </div>
  )
}
