import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ResultView } from '../pages/ResultPage'
import { analysisFixture } from './fixtures'

describe('resultado técnico', () => {
  it('formata hashes e copia o valor integral sem recalculá-lo', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    render(<ResultView result={analysisFixture} />)
    const hashes = document.querySelector<HTMLElement>('#hashes')!
    expect(within(hashes).getByRole('columnheader', { name: 'Algoritmo' })).toBeInTheDocument()
    expect(within(hashes).getByText('abc123')).toBeInTheDocument()
    expect(within(hashes).getByText('def456')).toBeInTheDocument()
    const shaRow = within(hashes).getByText('SHA256').closest('tr')!
    await userEvent.click(within(shaRow).getByRole('button', { name: 'Copiar valor' }))
    expect(writeText).toHaveBeenCalledWith('abc123')
  })

  it('preserva diferenças entre processing statuses', () => {
    render(<ResultView result={analysisFixture} />)
    expect(screen.getAllByText('Concluído').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sem resultados').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Não executado').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Indisponível').length).toBeGreaterThan(0)
  })

  it('distingue null de coleção vazia', () => {
    render(<ResultView result={analysisFixture} />)
    expect(screen.getByText(/não executado ou indisponível; consulte as etapas/i)).toBeInTheDocument()
    expect(screen.getByText(/nenhuma assinatura digital incorporada foi identificada/i)).toBeInTheDocument()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('apresenta metadados e execução sem JSON cru nas seções principais', () => {
    render(<ResultView result={analysisFixture} />)
    const metadata = screen.getByRole('heading', { name: 'Metadados' }).closest('section')!
    expect(within(metadata).getByText('Documento')).toBeInTheDocument()
    expect(within(metadata).getAllByText('Synthetic')).not.toHaveLength(0)
    expect(metadata.querySelector('.json-view')).not.toBeInTheDocument()
    const execution = screen.getByRole('heading', { name: 'Execução' }).closest('section')!
    expect(within(execution).getByRole('columnheader', { name: 'Etapa' })).toBeInTheDocument()
    expect(within(execution).getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()
  })

  it('mantém um único JSON técnico completo como seção secundária', async () => {
    render(<ResultView result={analysisFixture} />)
    expect(document.querySelectorAll('.json-view')).toHaveLength(1)
    await userEvent.click(screen.getByText('Expandir JSON'))
    const raw = document.querySelector('.json-view')!
    expect(raw).toHaveTextContent('"schema_version": "1.0.0"')
  })

  it('mantém o contrato imutável e as tabs superiores acessíveis', () => {
    const original = structuredClone(analysisFixture)
    render(<ResultView result={analysisFixture} />)
    const navigation = screen.getByRole('navigation', { name: 'Seções do resultado' })
    expect(navigation).toHaveClass('result-nav')
    expect(within(navigation).getAllByRole('link')).toHaveLength(11)
    expect(analysisFixture).toEqual(original)
  })
})
