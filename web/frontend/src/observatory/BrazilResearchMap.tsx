import type { KeyboardEvent } from 'react'
import type { StateResearch } from './models'

export type MapMode = 'DIGITAL' | 'GENERAL'

const positions: Record<string,[number,number]> = {
  RR:[2,0],AP:[6,0],AM:[1,1],PA:[5,1],MA:[7,2],CE:[9,2],RN:[11,2],PB:[10,3],PE:[9,4],AL:[10,5],SE:[9,6],
  AC:[0,3],RO:[2,3],TO:[6,3],PI:[8,3],BA:[7,5],MT:[3,4],GO:[5,5],DF:[5,6],MS:[3,6],MG:[6,7],ES:[8,7],
  SP:[5,8],RJ:[7,8],PR:[4,9],SC:[4,10],RS:[3,11],
}

function displayedValue(state: StateResearch, mode: MapMode) {
  return mode === 'DIGITAL' ? state.digitalCoreCount : state.uniqueProfessionalsCount
}

function intensity(value: number | undefined) {
  if (value === undefined) return 'no-data'
  if (value === 0) return 'zero'
  if (value < 20) return 'low'
  if (value < 75) return 'medium'
  return 'high'
}

export function BrazilResearchMap({ states, mode, selectedUf, onSelect }: { states: StateResearch[]; mode: MapMode; selectedUf: string; onSelect: (state: StateResearch) => void }) {
  const selectFromKey = (event: KeyboardEvent<SVGGElement>, state: StateResearch) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(state) }
  }
  return <svg className="brazil-research-map" viewBox="0 0 600 600" role="group" aria-label="Mapa esquemático interativo do Brasil com 27 unidades federativas">
    {states.map(state => {
      const [column,row] = positions[state.uf]
      const value = displayedValue(state,mode)
      const x = 28 + column * 45
      const y = 20 + row * 45
      const label = `${state.stateName}, ${state.uf}. ${value === undefined ? 'Sem quantitativo consolidado' : `${value} ${mode === 'DIGITAL' ? 'profissionais do núcleo digital/TI' : 'profissionais únicos no cadastro consultado'}`}.`
      return <g key={state.uf} className={`map-state map-state--${intensity(value)} ${selectedUf === state.uf ? 'is-selected' : ''}`} role="button" tabIndex={0} aria-label={label} onClick={() => onSelect(state)} onKeyDown={event => selectFromKey(event,state)}>
        <rect x={x} y={y} width="40" height="40" rx="3" /><text x={x+20} y={y+24} textAnchor="middle">{state.uf}</text>
      </g>
    })}
  </svg>
}
