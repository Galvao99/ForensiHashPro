import { useState, type KeyboardEvent } from 'react'
import { BRAZIL_MAP_VIEW_BOX, BRAZIL_STATE_GEOMETRY } from './brazilMapData'
import type { ResearchMetricId, StateResearch } from './models'
import { STATUS_LABELS, UNIT_LABELS, metricFor } from './models'

export type MapMode = 'DIGITAL' | 'GENERAL' | 'OTHER'

export const MAP_MODE_LABELS: Record<MapMode, string> = {
  DIGITAL: 'Núcleo Digital',
  GENERAL: 'Cadastro Geral',
  OTHER: 'Outras especialidades',
}

export function bubbleRadius(value: number, maximum: number): number {
  if (value < 0 || maximum <= 0) return 0
  return Math.sqrt(value / maximum) * 34
}

function metricIdFor(mode: MapMode): ResearchMetricId | undefined {
  return mode === 'OTHER' ? undefined : mode
}

export function BrazilResearchMap({
  states, mode, selectedUf, onSelect,
}: {
  states: StateResearch[]
  mode: MapMode
  selectedUf: string
  onSelect: (state: StateResearch) => void
}) {
  const [hoveredUf, setHoveredUf] = useState<string>()
  const metricId = metricIdFor(mode)
  const values = metricId ? states.flatMap(state => {
    const value = metricFor(state, metricId)?.value
    return value === undefined ? [] : [value]
  }) : []
  const maximum = Math.max(...values, 0)
  const active = states.find(state => state.uf === (hoveredUf ?? selectedUf))
  const activeMetric = active && metricId ? metricFor(active, metricId) : undefined

  const selectFromKey = (event: KeyboardEvent<SVGGElement>, state: StateResearch) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(state)
    }
  }

  return (
    <svg
      className="brazil-research-map"
      viewBox={BRAZIL_MAP_VIEW_BOX}
      role="group"
      aria-label="Mapa geográfico interativo do Brasil com 27 unidades federativas"
    >
      <g className="map-geography">
        {states.map(state => {
          const geometry = BRAZIL_STATE_GEOMETRY[state.uf]
          const metric = metricId ? metricFor(state, metricId) : undefined
          const detail = metric
            ? `${metric.value.toLocaleString('pt-BR')} — ${UNIT_LABELS[metric.unit]}`
            : mode === 'OTHER' ? 'Outras especialidades em levantamento' : 'Sem quantitativo consolidado'
          const label = `${state.stateName}, ${state.uf}. ${MAP_MODE_LABELS[mode]}. ${detail}. ${STATUS_LABELS[state.status]}.`
          return (
            <g
              key={state.uf}
              className={`map-state ${selectedUf === state.uf ? 'is-selected' : ''}`}
              data-uf={state.uf}
              data-status={state.status}
              role="button"
              tabIndex={0}
              aria-label={label}
              onClick={() => onSelect(state)}
              onKeyDown={event => selectFromKey(event, state)}
              onMouseEnter={() => setHoveredUf(state.uf)}
              onMouseLeave={() => setHoveredUf(undefined)}
              onFocus={() => setHoveredUf(state.uf)}
              onBlur={() => setHoveredUf(undefined)}
            >
              <path d={geometry.path} />
              {metric && (
                <circle
                  className={`map-bubble map-bubble--${state.status.toLowerCase()}`}
                  cx={geometry.center[0]}
                  cy={geometry.center[1]}
                  r={bubbleRadius(metric.value, maximum)}
                  data-value={metric.value}
                  data-count-type={metric.countType}
                  aria-hidden="true"
                />
              )}
            </g>
          )
        })}
      </g>
      {active && (() => {
        const [centerX, centerY] = BRAZIL_STATE_GEOMETRY[active.uf].center
        const x = Math.min(510, Math.max(90, centerX))
        const y = centerY < 105 ? centerY + 72 : centerY - 62
        return (
          <g className="map-tooltip" role="tooltip" transform={`translate(${x} ${y})`} pointerEvents="none">
            <rect x="-82" y="-38" width="164" height="76" rx="3" />
            <text textAnchor="middle">
              <tspan x="0" y="-19">{active.uf} · {MAP_MODE_LABELS[mode]}</tspan>
              <tspan className="map-tooltip__value" x="0" y="3">{activeMetric?.value.toLocaleString('pt-BR') ?? (mode === 'OTHER' ? 'Em levantamento' : 'Sem quantitativo')}</tspan>
              <tspan x="0" y="23">{STATUS_LABELS[active.status]}</tspan>
            </text>
          </g>
        )
      })()}
    </svg>
  )
}
