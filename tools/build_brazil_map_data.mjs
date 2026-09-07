import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const ufs = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']
const features = ufs.map(uf => {
  const source = JSON.parse(readFileSync(resolve(root, `.review_tmp/ibge-${uf.toLowerCase()}.geojson`), 'utf8'))
  return { uf, geometry: source.features[0].geometry }
})

function rings(geometry) {
  return geometry.type === 'Polygon' ? geometry.coordinates : geometry.coordinates.flat()
}

const points = features.flatMap(({ geometry }) => rings(geometry).flat())
const longitudes = points.map(([longitude]) => longitude)
const latitudes = points.map(([, latitude]) => latitude)
const bounds = {
  minLongitude: Math.min(...longitudes), maxLongitude: Math.max(...longitudes),
  minLatitude: Math.min(...latitudes), maxLatitude: Math.max(...latitudes),
}
const padding = 24
const width = 600
const height = 600
const scale = Math.min(
  (width - padding * 2) / (bounds.maxLongitude - bounds.minLongitude),
  (height - padding * 2) / (bounds.maxLatitude - bounds.minLatitude),
)
const projectedWidth = (bounds.maxLongitude - bounds.minLongitude) * scale
const projectedHeight = (bounds.maxLatitude - bounds.minLatitude) * scale
const offsetX = (width - projectedWidth) / 2
const offsetY = (height - projectedHeight) / 2
const project = ([longitude, latitude]) => [
  offsetX + (longitude - bounds.minLongitude) * scale,
  offsetY + (bounds.maxLatitude - latitude) * scale,
]
const round = value => Number(value.toFixed(1))

function pathFor(geometry) {
  return rings(geometry).map(ring => ring.map((point, index) => {
    const [x, y] = project(point)
    return `${index ? 'L' : 'M'}${round(x)},${round(y)}`
  }).join('') + 'Z').join('')
}

function polygonCentroid(ring) {
  let twiceArea = 0
  let x = 0
  let y = 0
  for (let index = 0; index < ring.length - 1; index += 1) {
    const [x1, y1] = project(ring[index])
    const [x2, y2] = project(ring[index + 1])
    const cross = x1 * y2 - x2 * y1
    twiceArea += cross
    x += (x1 + x2) * cross
    y += (y1 + y2) * cross
  }
  return { area: Math.abs(twiceArea / 2), x: x / (3 * twiceArea), y: y / (3 * twiceArea) }
}

function centroidFor(geometry) {
  const candidates = rings(geometry).map(polygonCentroid).filter(item => Number.isFinite(item.x) && item.area > 0)
  const largest = candidates.sort((left, right) => right.area - left.area)[0]
  return [round(largest.x), round(largest.y)]
}

const records = features.map(({ uf, geometry }) => `  ${uf}: { path: ${JSON.stringify(pathFor(geometry))}, center: ${JSON.stringify(centroidFor(geometry))} },`)
const output = `// Generated from IBGE Geographic Meshes API (quality=minima), accessed 2026-09-07.
// Source pattern: https://servicodados.ibge.gov.br/api/v3/malhas/estados/{UF}
export interface BrazilStateGeometry { path: string; center: readonly [number, number] }

export const BRAZIL_MAP_VIEW_BOX = '0 0 600 600'
export const BRAZIL_STATE_GEOMETRY: Record<string, BrazilStateGeometry> = {
${records.join('\n')}
}
`

writeFileSync(resolve(root, 'web/frontend/src/observatory/brazilMapData.ts'), output)
