import { getReference } from '../content/references'

export function ReferenceLink({ id }: { id: string }) {
  const reference = getReference(id)
  if (!reference) return null
  return (
    <a className="source-link" href={reference.url} target="_blank" rel="noreferrer">
      Fonte: {reference.institution} · {reference.date}
    </a>
  )
}
