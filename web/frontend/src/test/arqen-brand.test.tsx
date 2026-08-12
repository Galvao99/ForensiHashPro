import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ArqenBrand } from '../components/ArqenBrand'

describe('seleção do logo ARQEN pelo fundo', () => {
  it('usa o logo branco sobre fundo escuro', () => {
    render(<MemoryRouter><ArqenBrand theme="dark" /></MemoryRouter>)
    expect(screen.getByAltText('ARQEN')).toHaveAttribute('src', '/assets/arqen_logo_branca.png')
  })

  it('usa o logo preto sobre fundo claro', () => {
    render(<MemoryRouter><ArqenBrand theme="light" /></MemoryRouter>)
    expect(screen.getByAltText('ARQEN')).toHaveAttribute('src', '/assets/arqen_logo_preta.png')
  })
})
