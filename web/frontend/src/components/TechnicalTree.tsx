import { useEffect, useId, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { TechnicalValue } from './ui'

type TreeValue = Record<string, unknown> | unknown[]

function present(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return false
  if (Array.isArray(value)) return value.some(present)
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some(present)
  return true
}

function complex(value: unknown): value is TreeValue {
  return present(value) && typeof value === 'object'
}

function displayLabel(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

function countLabel(value: TreeValue): string {
  if (Array.isArray(value)) return String(value.filter(present).length)
  const count = Object.entries(value).filter(([, child]) => present(child)).length
  return `${count} ${count === 1 ? 'campo' : 'campos'}`
}

function itemLabel(parent: string, item: unknown, index: number): string {
  const singular = parent.replace(/s$/i, '') || 'Item'
  if (item && typeof item === 'object' && !Array.isArray(item)) {
    const record = item as Record<string, unknown>
    const descriptor = ['type', 'kind', 'encoding', 'category', 'format', 'name']
      .map((key) => record[key])
      .find((value) => typeof value === 'string' && value.length <= 40)
    return `${displayLabel(singular)} ${index + 1}${descriptor ? ` — ${descriptor}` : ''}`
  }
  return `Item ${index + 1}`
}

function pathId(base: string, path: string): string {
  return `${base}-${path.replace(/[^a-zA-Z0-9_-]/g, '-')}`
}

function TreeNode({ label, value, path, expanded, setExpanded, baseId }: {
  label: string
  value: TreeValue
  path: string
  expanded: Set<string>
  setExpanded: (next: Set<string>) => void
  baseId: string
}) {
  const open = expanded.has(path)
  const contentId = pathId(baseId, path)
  const toggle = () => {
    const next = new Set(expanded)
    if (open) next.delete(path); else next.add(path)
    setExpanded(next)
  }
  return <div className="technical-tree-node">
    <button type="button" className="technical-tree-toggle" aria-expanded={open} aria-controls={contentId} onClick={toggle}>
      {open ? <ChevronDown aria-hidden="true" size={15} /> : <ChevronRight aria-hidden="true" size={15} />}
      <span>{displayLabel(label)}</span><small>{countLabel(value)}</small>
    </button>
    {open && <div id={contentId} className="technical-tree-children">
      <TreeChildren value={value} parent={label} path={path} expanded={expanded} setExpanded={setExpanded} baseId={baseId} />
    </div>}
  </div>
}

function TreeChildren({ value, parent, path, expanded, setExpanded, baseId }: {
  value: TreeValue
  parent: string
  path: string
  expanded: Set<string>
  setExpanded: (next: Set<string>) => void
  baseId: string
}) {
  const entries: Array<[string, unknown]> = Array.isArray(value)
    ? value.filter(present).map((item, index) => [itemLabel(parent, item, index), item])
    : Object.entries(value).filter(([, child]) => present(child))
  const leaves = entries.filter(([, child]) => !complex(child))
  const branches = entries.filter(([, child]) => complex(child))
  return <>
    {leaves.length > 0 && <dl className="technical-tree-leaves">{leaves.map(([key, child]) => <div key={key}><dt>{displayLabel(key)}</dt><dd><TechnicalValue>{typeof child === 'boolean' ? (child ? 'Sim' : 'Não') : String(child)}</TechnicalValue></dd></div>)}</dl>}
    {branches.map(([key, child], index) => <TreeNode key={`${key}-${index}`} label={key} value={child as TreeValue} path={`${path}.${key}.${index}`} expanded={expanded} setExpanded={setExpanded} baseId={baseId} />)}
  </>
}

export function TechnicalTree({ value, showActions = true }: { value: TreeValue; showActions?: boolean }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const baseId = useId().replace(/:/g, '')
  useEffect(() => setExpanded(new Set()), [value])
  const topEntries = Array.isArray(value)
    ? value.filter(present).map((item, index) => [itemLabel('Items', item, index), item] as [string, unknown])
    : Object.entries(value).filter(([, child]) => present(child))
  const topBranches = topEntries.filter(([, child]) => complex(child))
  return <div className="technical-tree">
    {showActions && topBranches.length > 0 && <div className="technical-tree-actions">
      <button type="button" onClick={() => setExpanded(new Set(topBranches.map(([key], index) => `root.${key}.${index}`)))}>Expandir primeiro nível</button>
      <button type="button" onClick={() => setExpanded(new Set())}>Recolher tudo</button>
    </div>}
    <TreeChildren value={value} parent="Items" path="root" expanded={expanded} setExpanded={setExpanded} baseId={baseId} />
  </div>
}
