import { useEffect } from 'react'

const DEFAULT_DESCRIPTION = 'Tecnologia para proveniência, integridade, custódia e análise de artefatos digitais.'

interface DocumentMetadataProps {
  title: string
  description?: string
}

function setMeta(selector: string, content: string) {
  const element = document.querySelector<HTMLMetaElement>(selector)
  if (element) element.content = content
}

export function DocumentMetadata({ title, description = DEFAULT_DESCRIPTION }: DocumentMetadataProps) {
  useEffect(() => {
    document.title = title
    setMeta('meta[name="description"]', description)
    setMeta('meta[property="og:title"]', title)
    setMeta('meta[property="og:description"]', description)
    setMeta('meta[property="og:site_name"]', 'ARQEN')
  }, [description, title])

  return null
}
