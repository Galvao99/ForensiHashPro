import type { ReactNode } from 'react'

export function FlowDiagram({ label, nodes, compact = false }: { label: string; nodes: ReactNode[]; compact?: boolean }) {
  return <div className={`ddna-diagram ddna-flow${compact ? ' compact' : ''}`} role="img" aria-label={label}>
    {nodes.map((node, index) => <div className="ddna-flow-step" key={index}>
      <div className="ddna-node">{node}</div>
      {index < nodes.length - 1 && <span className="ddna-arrow" aria-hidden="true">↓</span>}
    </div>)}
  </div>
}

export function BranchDiagram({ label, leftTitle, left, rightTitle, right, footer }: {
  label: string; leftTitle: string; left: string[]; rightTitle: string; right: string[]; footer: ReactNode
}) {
  return <div className="ddna-diagram ddna-branch" role="img" aria-label={label}>
    <div className="ddna-node ddna-root">DDNA RECORD</div><span className="ddna-branch-line" aria-hidden="true">┌──────────┴──────────┐</span>
    <div className="ddna-branch-columns">
      <article><strong>{leftTitle}</strong>{left.map(item => <span key={item}>{item}</span>)}</article>
      <article><strong>{rightTitle}</strong>{right.map(item => <span key={item}>{item}</span>)}</article>
    </div><span className="ddna-arrow" aria-hidden="true">↓</span><div className="ddna-node">{footer}</div>
  </div>
}

export function LedgerDiagram() {
  const events = ['T0 ACQUIRED', 'T1 STORED', 'T2 ACCESSED', 'T3 EXPORTED', 'T4 TRANSFERRED', 'T5 VERIFIED', 'T6 PRESENTED']
  return <div className="ddna-diagram ddna-ledger" role="img" aria-label="Ledger de custódia do T0 à apresentação">
    {events.map((event, index) => <div key={event}><span>{event}</span>{index < events.length - 1 && <b aria-hidden="true">→</b>}</div>)}
  </div>
}
