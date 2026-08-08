import type { ProcessingStatus } from '../types/api'

const labels: Record<ProcessingStatus, string> = {
  success: 'Concluído',
  no_findings: 'Sem resultados',
  partial: 'Parcial',
  skipped: 'Não executado',
  unavailable: 'Indisponível',
  failed: 'Falhou',
  cancelled: 'Cancelado',
  limit_exceeded: 'Limite excedido',
}

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>
}

export function AvailabilityBadge({ available }: { available: boolean }) {
  return (
    <span className={`status-badge ${available ? 'status-success' : 'status-unavailable'}`}>
      {available ? 'Disponível' : 'Indisponível'}
    </span>
  )
}
