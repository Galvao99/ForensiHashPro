import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResultView } from '../pages/ResultPage'
import { analysisFixture } from './fixtures'

describe('resultado técnico', () => {
  it('preserva hashes sem recalcular valores', () => {
    render(<ResultView result={analysisFixture} />)
    const hashes = screen.getByRole('heading', { name: 'Hashes' }).closest('section')!
    expect(within(hashes).getByText('abc123')).toBeInTheDocument()
    expect(within(hashes).getByText('def456')).toBeInTheDocument()
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
    const ip = screen.getByRole('heading', { name: 'IP' }).closest('section')!
    const timeline = screen.getByRole('heading', { name: 'Timeline' }).closest('section')!
    expect(within(ip).getByText(/não executada ou fora do escopo/i)).toBeInTheDocument()
    expect(within(timeline).getByText(/executada sem itens/i)).toBeInTheDocument()
  })
})
