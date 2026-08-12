import { useState, type CSSProperties, type PointerEvent } from 'react'

const nodes = [
  { id: 'hash', label: 'HASH', x: 17, y: 27 },
  { id: 'metadata', label: 'METADATA', x: 12, y: 67 },
  { id: 'context', label: 'CONTEXT', x: 50, y: 10 },
  { id: 'events', label: 'EVENTS', x: 83, y: 27 },
  { id: 'timeline', label: 'TIMELINE', x: 88, y: 67 },
  { id: 'custody', label: 'CUSTODY', x: 50, y: 90 },
]

export function ArtifactGraph() {
  const [active, setActive] = useState('context')
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  function move(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    setOffset({ x: ((event.clientX - bounds.left) / bounds.width - 0.5) * 8, y: ((event.clientY - bounds.top) / bounds.height - 0.5) * 8 })
  }

  return (
    <div className="artifact-graph" onPointerMove={move} onPointerLeave={() => setOffset({ x: 0, y: 0 })}>
      <div className="artifact-graph__frame" style={{ '--graph-x': `${offset.x}px`, '--graph-y': `${offset.y}px` } as CSSProperties}>
        <svg className="artifact-graph__lines" viewBox="0 0 100 100" role="img" aria-labelledby="artifact-graph-title artifact-graph-description">
          <title id="artifact-graph-title">Digital Artifact Graph</title>
          <desc id="artifact-graph-description">Um artefato digital relacionado a hash, metadados, contexto, eventos, timeline e custódia.</desc>
          {nodes.map(node => <line key={node.id} className={active === node.id ? 'is-active' : ''} x1="50" y1="50" x2={node.x} y2={node.y} />)}
          <circle cx="50" cy="50" r="13" />
        </svg>
        <div className="artifact-core"><span>01</span><strong>ARTIFACT</strong><small>digital object</small></div>
        {nodes.map(node => (
          <button key={node.id} type="button" className={`artifact-node ${active === node.id ? 'is-active' : ''}`} style={{ left: `${node.x}%`, top: `${node.y}%` }} onMouseEnter={() => setActive(node.id)} onFocus={() => setActive(node.id)} onClick={() => setActive(node.id)} aria-pressed={active === node.id}>
            <i aria-hidden="true" />{node.label}
          </button>
        ))}
        <p className="artifact-graph__status" aria-live="polite">RELATION / {active.toUpperCase()}</p>
      </div>
    </div>
  )
}
