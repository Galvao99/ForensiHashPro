import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { StructureResultView } from '../components/ResultPresentation'

const structure = {
  version: '1.7',
  binary: {
    strings: [
      { value: 'first hidden value', length: 18, offset: 514, category: 'generic', encoding: 'utf-16-be' },
      { value: 'second hidden value', length: 19, offset: 820, category: 'generic', encoding: 'ascii' },
    ],
    regions: [{ type: 'pdf', offset: 0 }],
    ignored: null,
  },
}

describe('árvore técnica colapsável', () => {
  it('mantém branches e arrays complexos colapsados e só monta descendants ao expandir', async () => {
    render(<StructureResultView structure={structure} />)
    expect(screen.getByText('1.7')).toBeInTheDocument()
    expect(screen.queryByText('first hidden value')).not.toBeInTheDocument()
    const binary = screen.getByRole('button', { name: /binary.*2 campos/i })
    expect(binary).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(binary)
    const strings = screen.getByRole('button', { name: /strings.*2/i })
    expect(strings).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(strings)
    expect(screen.queryByText('first hidden value')).not.toBeInTheDocument()
    const first = screen.getByRole('button', { name: /string 1.*utf 16 be/i })
    await userEvent.click(first)
    expect(screen.getByText('first hidden value')).toBeInTheDocument()
    expect(screen.queryByText('Ignored')).not.toBeInTheDocument()
    await userEvent.click(first)
    expect(screen.queryByText('first hidden value')).not.toBeInTheDocument()
  })

  it('reseta expansão quando o arquivo ativo fornece outra estrutura', async () => {
    const view = render(<StructureResultView structure={structure} />)
    await userEvent.click(screen.getByRole('button', { name: /binary.*2 campos/i }))
    expect(screen.getByRole('button', { name: /strings.*2/i })).toBeInTheDocument()
    view.rerender(<StructureResultView structure={{ binary: { strings: [{ value: 'other file' }] } }} />)
    expect(screen.queryByText('other file')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /strings.*1/i })).not.toBeInTheDocument()
  })
})
