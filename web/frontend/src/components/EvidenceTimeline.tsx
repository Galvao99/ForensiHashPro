import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { TechnicalTree } from './TechnicalTree'

export type TimelineRecord = Record<string, unknown>

export interface PositionedTimelineEvent {
  event: TimelineRecord
  milliseconds: number
  position: number
  lane: number
}

export function timestampMilliseconds(event: TimelineRecord): number | null {
  if (event.temporal_status === 'structural_only' || typeof event.timestamp !== 'string') return null
  const value = Date.parse(event.timestamp)
  return Number.isFinite(value) ? value : null
}

export function positionTimelineEvents(events: TimelineRecord[], scaleEvents: TimelineRecord[] = events): PositionedTimelineEvent[] {
  const scaleTimes = scaleEvents.map(timestampMilliseconds).filter((value): value is number => value !== null)
  const earliest = scaleTimes.length ? Math.min(...scaleTimes) : 0
  const latest = scaleTimes.length ? Math.max(...scaleTimes) : earliest
  const span = latest - earliest
  const lanePositions: number[] = []
  return events.map((event) => ({ event, milliseconds: timestampMilliseconds(event) }))
    .filter((item): item is { event: TimelineRecord; milliseconds: number } => item.milliseconds !== null)
    .sort((left, right) => left.milliseconds - right.milliseconds)
    .map((item) => {
      const position = span === 0 ? 50 : ((item.milliseconds - earliest) / span) * 100
      let lane = lanePositions.findIndex((previous) => Math.abs(position - previous) >= 8)
      if (lane < 0) lane = lanePositions.length
      lanePositions[lane] = position
      return { ...item, position, lane }
    })
}

function eventName(event: TimelineRecord): string {
  return String(event.title ?? event.event_type ?? 'Evento técnico')
}

function eventTimestamp(event: TimelineRecord): string {
  return String(event.raw_timestamp ?? event.timestamp ?? 'Data não determinada')
}

function EventDetails({ event, onClose }: { event: TimelineRecord; onClose?: () => void }) {
  const provenance = [
    ['Artefato', event.filename], ['Origem', event.source_type], ['Engine', event.source_engine], ['Campo', event.field_path],
    ['Evidência', event.evidence_ref], ['Precisão', event.precision], ['Timezone', event.timezone], ['Status do timezone', event.timezone_status], ['Limitação', event.limitations],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length > 0))
  return <aside className="timeline-detail-panel" aria-label={`Detalhes do evento ${eventName(event)}`}>
    <header><div><p className="eyebrow">EVENTO</p><h4>{eventName(event)}</h4></div>{onClose && <button type="button" onClick={onClose} aria-label="Fechar detalhes do evento">×</button>}</header>
    {event.temporal_status === 'structural_only' ? <p className="timeline-undated-note">Data não determinável pelo contrato.</p> : <p className="timeline-detail-time"><span>Timestamp</span><strong>{eventTimestamp(event)}</strong></p>}
    {provenance.length > 0 && <dl className="timeline-provenance">{provenance.map(([name, value]) => <div key={String(name)}><dt>{String(name)}</dt><dd>{Array.isArray(value) ? value.join(' · ') : String(value)}</dd></div>)}</dl>}
    <details className="technical-details"><summary>Ver registro técnico completo</summary><TechnicalTree value={event} showActions={false} /></details>
  </aside>
}

export function EvidenceTimeline({ visibleEvents, scaleEvents, heading = 'Eventos com data conhecida' }: { visibleEvents: TimelineRecord[]; scaleEvents: TimelineRecord[]; heading?: string }) {
  const [selected, setSelected] = useState<TimelineRecord | null>(null)
  const positioned = useMemo(() => positionTimelineEvents(visibleEvents, scaleEvents), [visibleEvents, scaleEvents])
  const undated = visibleEvents.filter((event) => timestampMilliseconds(event) === null)
  const scalePositioned = useMemo(() => positionTimelineEvents(scaleEvents, scaleEvents), [scaleEvents])
  const earliest = scalePositioned[0]?.event
  const latest = scalePositioned.at(-1)?.event
  const laneCount = Math.max(1, ...positioned.map((item) => item.lane + 1))

  return <div className="evidence-timeline">
    {positioned.length > 0 && <section aria-labelledby="dated-events-title">
      <h3 id="dated-events-title" className="timeline-group-title">{heading}</h3>
      <div className="timeline-range" aria-label="Intervalo temporal"><time>{earliest ? eventTimestamp(earliest) : ''}</time><span aria-hidden="true" /><time>{latest ? eventTimestamp(latest) : ''}</time></div>
      <div className="timeline-scroll" tabIndex={0} aria-label="Linha cronológica; use rolagem horizontal quando necessário">
        <div className="timeline-axis" style={{ '--timeline-lanes': laneCount } as CSSProperties}>
          <div className="timeline-axis-line" aria-hidden="true" />
          {positioned.map(({ event, position, lane }, index) => <button
            type="button"
            key={String(event.event_id ?? `${eventTimestamp(event)}-${index}`)}
            className={`timeline-event-marker ${selected === event ? 'selected' : ''}`}
            style={{ left: `${position}%`, '--event-lane': lane } as CSSProperties}
            data-position={position.toFixed(6)}
            aria-label={`${eventName(event)}, ${eventTimestamp(event)}`}
            aria-pressed={selected === event}
            onClick={() => setSelected(event)}
          ><span className="timeline-event-dot" aria-hidden="true" /><span className="timeline-event-label"><strong>{eventName(event)}</strong><time>{eventTimestamp(event)}</time></span></button>)}
        </div>
      </div>
    </section>}
    {undated.length > 0 && <section className="undated-events" aria-labelledby="undated-events-title"><h3 id="undated-events-title" className="timeline-group-title">Eventos sem data determinável</h3><div className="undated-event-grid">{undated.map((event, index) => <button type="button" key={String(event.event_id ?? index)} onClick={() => setSelected(event)} aria-label={`Ver detalhes: ${eventName(event)}`}><span aria-hidden="true">◆</span><strong>{eventName(event)}</strong><small>{String(event.source_type ?? event.category ?? 'Evento estrutural')}</small></button>)}</div></section>}
    {selected && <EventDetails event={selected} onClose={() => setSelected(null)} />}
  </div>
}
