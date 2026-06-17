import type { RestrictionBufferMode } from '../components/MapLayerToolbar'

export type FeatureScope = 'property' | 'surroundings' | 'buffer'

export function getFeatureScope(props: Record<string, unknown> | null | undefined): FeatureScope {
  const scope = String(props?.scope ?? 'property')
  if (scope === 'surroundings' || scope === 'buffer') return scope
  return 'property'
}

export function filterLayerFeaturesForMap(
  collection: GeoJSON.FeatureCollection,
  carId: string | undefined,
  filterByCar: boolean,
  activeBuffer: RestrictionBufferMode | null,
): GeoJSON.FeatureCollection {
  if (!filterByCar || !carId) return collection

  const features = collection.features.filter(f => {
    const props = f.properties ?? {}
    if (String(props.car_id ?? '') !== carId) return false
    const scope = getFeatureScope(props as Record<string, unknown>)
    if (!activeBuffer) return scope === 'property'
    if (scope === 'property') return true
    return Number(props.buffer_m) === activeBuffer
  })

  return { type: 'FeatureCollection', features }
}

export function countLayerFeatures(
  collection: GeoJSON.FeatureCollection,
  carId: string | undefined,
  filterByCar: boolean,
  activeBuffer: RestrictionBufferMode | null,
): number {
  return filterLayerFeaturesForMap(collection, carId, filterByCar, activeBuffer).features.length
}
