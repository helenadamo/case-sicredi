import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import type { Layer, PathOptions } from 'leaflet'
import type { Property } from '../types'
import MapLayerToolbar, { type RestrictionBufferMode, type RestrictionMenuItem, type ClimateMenuItem } from './MapLayerToolbar'
import { distanceContextMetrics } from '../utils/advancedData'
import { getRestrictionBufferInfo, getClimateBufferInfo } from '../utils/presentation'
import { countLayerFeatures, filterLayerFeaturesForMap, getFeatureScope } from '../utils/mapLayers'

const RESTRICTION_KEYS = ['embargos', 'ti', 'uc', 'app', 'desmatamento'] as const
type RestrictionKey = typeof RESTRICTION_KEYS[number]

const CLIMATE_KEYS = ['fire_scars', 'water_surface', 'rivers'] as const
type ClimateKey = typeof CLIMATE_KEYS[number]
type DataLayerKey = RestrictionKey | ClimateKey | 'cars' | 'context_buffers'

const EMPTY_FEATURE_COLLECTION: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

const DATA_LAYER_FILES: Record<DataLayerKey, string> = {
  cars: 'cars.json',
  embargos: 'embargos.json',
  ti: 'ti.json',
  uc: 'uc.json',
  app: 'app.json',
  desmatamento: 'desmatamento.json',
  context_buffers: 'context_buffers.json',
  fire_scars: 'mapbiomas_fire_scars.json',
  water_surface: 'fbds_massas_dagua.json',
  rivers: 'fbds_rios_simples.json',
}

interface ClimateLayerConfig {
  label: string
  color: string
  colorByYear?: Record<number, string>
  filterByCar?: boolean
  supportsBuffer?: boolean
  isLine?: boolean
}

const LAYER_CONFIG: Record<RestrictionKey | 'cars', { color: string; label: string; filterByCar?: boolean; supportsBuffer?: boolean }> = {
  cars: { color: '#146E37', label: 'CARs analisados' },
  embargos: { color: '#C62828', label: 'Embargos IBAMA', filterByCar: true, supportsBuffer: true },
  ti: { color: '#730028', label: 'Terras Indígenas', filterByCar: true, supportsBuffer: true },
  uc: { color: '#3FA110', label: 'Unidades de Conservação', filterByCar: true, supportsBuffer: true },
  app: { color: '#1E88A8', label: 'APP (FBDS)', filterByCar: true, supportsBuffer: false },
  desmatamento: { color: '#FF6400', label: 'Desmatamento', filterByCar: true, supportsBuffer: true },
}

const BUFFER_LAYER_KEYS: Record<5000 | 10000, string> = {
  5000: 'buffer_5000m',
  10000: 'buffer_10000m',
}

const BUFFER_RING_COLORS: Record<5000 | 10000, string> = {
  5000: '#1E88A8',
  10000: '#8E6BB0',
}

const CLIMATE_LAYER_CONFIG: Record<ClimateKey, ClimateLayerConfig> = {
  fire_scars: {
    label: 'Cicatrizes de queimada',
    color: '#FF6D00',
    colorByYear: { 2022: '#FFB300', 2023: '#FF6D00', 2024: '#D50000' },
    filterByCar: true,
    supportsBuffer: false,
  },
  water_surface: {
    label: 'Superfície hídrica',
    color: '#1565C0',
    filterByCar: true,
    supportsBuffer: true,
  },
  rivers: {
    label: 'Rios (FBDS)',
    color: '#0288D1',
    filterByCar: true,
    supportsBuffer: true,
    isLine: true,
  },
}

async function fetchLayer(key: DataLayerKey): Promise<[DataLayerKey, GeoJSON.FeatureCollection]> {
  const response = await fetch(`/data/layers/${DATA_LAYER_FILES[key]}`)
  if (!response.ok) return [key, EMPTY_FEATURE_COLLECTION]
  return [key, await response.json() as GeoJSON.FeatureCollection]
}

const BASEMAPS = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
  },
}

function filterFeaturesForCar(
  collection: GeoJSON.FeatureCollection,
  carId: string | undefined,
  filterByCar: boolean,
  activeBuffer: RestrictionBufferMode | null = null,
): GeoJSON.FeatureCollection {
  return filterLayerFeaturesForMap(collection, carId, filterByCar, activeBuffer)
}

function FlyToProperty({ property }: { property: Property | null }) {
  const map = useMap()
  useEffect(() => {
    if (property) {
      const zoom = property.area_ha > 1000 ? 10 : property.area_ha > 100 ? 12 : 14
      map.flyTo([property.lat, property.lng], zoom, { duration: 1.2 })
    }
  }, [property, map])
  return null
}

interface MapViewProps {
  selectedProperty: Property | null
  onSelectProperty: (id: string) => void
}

const defaultRestrictionBuffers = (): Record<RestrictionKey, RestrictionBufferMode> => ({
  embargos: null,
  ti: null,
  uc: null,
  app: null,
  desmatamento: null,
})

const defaultClimateBuffers = (): Record<ClimateKey, RestrictionBufferMode> => ({
  fire_scars: null,
  water_surface: null,
  rivers: null,
})

export default function MapView({ selectedProperty, onSelectProperty }: MapViewProps) {
  const [dataLayers, setDataLayers] = useState<Record<DataLayerKey, GeoJSON.FeatureCollection>>({
    cars: EMPTY_FEATURE_COLLECTION,
    embargos: EMPTY_FEATURE_COLLECTION,
    ti: EMPTY_FEATURE_COLLECTION,
    uc: EMPTY_FEATURE_COLLECTION,
    app: EMPTY_FEATURE_COLLECTION,
    desmatamento: EMPTY_FEATURE_COLLECTION,
    context_buffers: EMPTY_FEATURE_COLLECTION,
    fire_scars: EMPTY_FEATURE_COLLECTION,
    water_surface: EMPTY_FEATURE_COLLECTION,
    rivers: EMPTY_FEATURE_COLLECTION,
  })
  const [visibleLayers, setVisibleLayers] = useState<Record<RestrictionKey, boolean>>({
    embargos: true, ti: true, uc: true, app: true, desmatamento: true,
  })
  const [restrictionBuffers, setRestrictionBuffers] = useState<Record<RestrictionKey, RestrictionBufferMode>>(
    defaultRestrictionBuffers,
  )
  const [visibleClimateLayers, setVisibleClimateLayers] = useState<Record<ClimateKey, boolean>>({
    fire_scars: true,
    water_surface: false,
    rivers: false,
  })
  const [climateBuffers, setClimateBuffers] = useState<Record<ClimateKey, RestrictionBufferMode>>(
    defaultClimateBuffers,
  )
  const [basemap, setBasemap] = useState<'osm' | 'satellite'>('satellite')

  const toggleBasemap = () => {
    setBasemap(prev => (prev === 'satellite' ? 'osm' : 'satellite'))
  }

  const carId = selectedProperty?.id

  useEffect(() => {
    let cancelled = false
    Promise.all((Object.keys(DATA_LAYER_FILES) as DataLayerKey[]).map(fetchLayer))
      .then(entries => {
        if (!cancelled) {
          setDataLayers(Object.fromEntries(entries) as Record<DataLayerKey, GeoJSON.FeatureCollection>)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const distMetrics = useMemo(
    () => distanceContextMetrics.find(d => d.car_id === carId),
    [carId],
  )

  const layerData = useMemo(() => {
    const out: Record<string, GeoJSON.FeatureCollection> = {}
    for (const key of RESTRICTION_KEYS) {
      const cfg = LAYER_CONFIG[key]
      const activeBuffer = restrictionBuffers[key]
      out[key] = filterFeaturesForCar(
        dataLayers[key],
        carId,
        cfg.filterByCar ?? false,
        cfg.supportsBuffer ? activeBuffer : null,
      )
    }
    out.cars = filterFeaturesForCar(dataLayers.cars, carId, false)
    return out
  }, [carId, dataLayers, restrictionBuffers])

  const bufferData = useMemo(() => {
    const all = dataLayers.context_buffers
    if (!carId) return { type: 'FeatureCollection' as const, features: [] }
    return {
      type: 'FeatureCollection' as const,
      features: all.features.filter(
        f => String(f.properties?.car_id ?? '') === carId,
      ),
    }
  }, [carId, dataLayers])

  const climateLayerData = useMemo(() => {
    const out: Record<string, GeoJSON.FeatureCollection> = {}
    for (const key of CLIMATE_KEYS) {
      const cfg = CLIMATE_LAYER_CONFIG[key]
      const activeBuffer = climateBuffers[key]
      out[key] = filterFeaturesForCar(
        dataLayers[key],
        carId,
        cfg.filterByCar ?? false,
        cfg.supportsBuffer ? activeBuffer : null,
      )
    }
    return out
  }, [carId, climateBuffers, dataLayers])

  const activeBufferRings = useMemo(() => {
    const rings = new Set<5000 | 10000>()
    for (const key of RESTRICTION_KEYS) {
      const buf = restrictionBuffers[key]
      if (buf && visibleLayers[key]) rings.add(buf)
    }
    for (const key of CLIMATE_KEYS) {
      const cfg = CLIMATE_LAYER_CONFIG[key]
      const buf = climateBuffers[key]
      if (buf && cfg.supportsBuffer && visibleClimateLayers[key]) rings.add(buf)
    }
    return [...rings]
  }, [restrictionBuffers, visibleLayers, climateBuffers, visibleClimateLayers])

  const toggleClimateLayer = (key: ClimateKey) => {
    setVisibleClimateLayers(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleClimateBuffer = (key: ClimateKey, buffer: RestrictionBufferMode) => {
    setClimateBuffers(prev => ({ ...prev, [key]: buffer }))
    if (buffer) {
      setVisibleClimateLayers(prev => ({ ...prev, [key]: true }))
    }
  }

  const toggleRestrictionBuffer = (key: RestrictionKey, buffer: RestrictionBufferMode) => {
    setRestrictionBuffers(prev => ({ ...prev, [key]: buffer }))
    if (buffer) {
      setVisibleLayers(prev => ({ ...prev, [key]: true }))
    }
  }

  const toggleLayer = (key: RestrictionKey) => {
    setVisibleLayers(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const styleFor = (
    color: string,
    isCar = false,
    isSelected = false,
    scope: 'property' | 'surroundings' | 'buffer' = 'property',
  ): PathOptions => {
    if (scope !== 'property') {
      return {
        color,
        weight: 1.2,
        dashArray: scope === 'surroundings' ? '5 4' : '3 3',
        fillColor: color,
        fillOpacity: 0.2,
        opacity: 0.75,
      }
    }
    return {
      color: isCar ? (isSelected ? '#FFCD00' : '#146E37') : color,
      weight: isCar ? (isSelected ? 3.5 : 2) : 1.2,
      fillColor: isCar ? (isSelected ? '#FFCD00' : '#3FA110') : color,
      fillOpacity: isCar ? (isSelected ? 0.28 : 0.14) : 0.42,
      opacity: 0.88,
    }
  }

  const onEachRestrictionFeature = (label: string) => (feature: GeoJSON.Feature, layer: Layer) => {
    const props = feature.properties || {}
    const scope = getFeatureScope(props as Record<string, unknown>)
    const bufferM = props.buffer_m ? `${Number(props.buffer_m) / 1000} km` : null
    const area = props.intersect_area_ha != null ? `${Number(props.intersect_area_ha).toFixed(2)} ha` : null
    const scopeLabel = scope === 'property' ? 'No imóvel' : `Entorno · buffer ${bufferM ?? 'n/d'}`
    layer.bindPopup(`
      <div style="font-family:var(--font-body);min-width:200px">
        <strong style="color:#146E37">${label}</strong><br/>
        <span style="font-size:12px;color:#666">${scopeLabel}</span>
        ${area ? `<br/><span style="font-size:12px">${area}</span>` : ''}
      </div>
    `)
  }

  const onEachFireScar = (feature: GeoJSON.Feature, layer: Layer) => {
    const props = feature.properties || {}
    const year = props.fire_year ?? 'n/d'
    layer.bindPopup(`
      <div style="font-family:var(--font-body);min-width:200px">
        <strong style="color:#D50000">Cicatriz de queimada ${year}</strong><br/>
        <span style="font-size:12px;color:#666">${props.fonte || 'MapBiomas Fogo C5'}</span>
      </div>
    `)
  }

  const onEachClimateFeature = (label: string) => (feature: GeoJSON.Feature, layer: Layer) => {
    const props = feature.properties || {}
    const scope = getFeatureScope(props as Record<string, unknown>)
    const bufferM = props.buffer_m ? `${Number(props.buffer_m) / 1000} km` : null
    const area = props.intersect_area_ha != null && Number(props.intersect_area_ha) > 0
      ? `${Number(props.intersect_area_ha).toFixed(2)} ha`
      : null
    const lengthKm = props.intersect_length_km != null && Number(props.intersect_length_km) > 0
      ? `${Number(props.intersect_length_km).toFixed(2)} km`
      : null
    const scopeLabel = scope === 'property' ? 'No imóvel' : `Entorno climático · buffer ${bufferM ?? 'n/d'}`
    layer.bindPopup(`
      <div style="font-family:var(--font-body);min-width:200px">
        <strong style="color:#1565C0">${label}</strong><br/>
        <span style="font-size:12px;color:#666">${scopeLabel}</span>
        ${area ? `<br/><span style="font-size:12px">${area}</span>` : ''}
        ${lengthKm ? `<br/><span style="font-size:12px">${lengthKm} de extensão</span>` : ''}
      </div>
    `)
  }

  const styleFireScar = (feature?: GeoJSON.Feature): PathOptions => {
    const year = Number(feature?.properties?.fire_year)
    const colors = CLIMATE_LAYER_CONFIG.fire_scars.colorByYear
    const color = colors?.[year] ?? '#FF6D00'
    return {
      color,
      weight: 0.9,
      fillColor: color,
      fillOpacity: 0.58,
      opacity: 0.92,
    }
  }

  const styleClimateLayer = (key: ClimateKey, cfg: ClimateLayerConfig, feature?: GeoJSON.Feature): PathOptions => {
    if (key === 'fire_scars') return styleFireScar(feature)
    const scope = getFeatureScope(feature?.properties as Record<string, unknown> | undefined)
    if (cfg.isLine) {
      return {
        color: cfg.color,
        weight: scope === 'property' ? 2.2 : 1.6,
        opacity: scope === 'property' ? 0.9 : 0.7,
        dashArray: scope === 'property' ? undefined : '6 4',
      }
    }
    return styleFor(cfg.color, false, false, scope)
  }

  const onEachCar = (feature: GeoJSON.Feature, layer: Layer) => {
    const props = feature.properties || {}
    layer.bindPopup(`
      <div style="font-family:var(--font-body);min-width:180px">
        <strong style="color:#146E37">${props.label || props.id}</strong><br/>
        <span style="font-size:12px;color:#666">${props.uf} · ${props.area_ha?.toFixed?.(1) ?? 'n/d'} ha</span>
      </div>
    `)
    layer.on('click', () => {
      if (props.id) onSelectProperty(props.id)
    })
  }

  const center: [number, number] = selectedProperty
    ? [selectedProperty.lat, selectedProperty.lng]
    : [-15, -52]

  const bm = BASEMAPS[basemap]

  const restrictionItems: RestrictionMenuItem[] = RESTRICTION_KEYS.map(key => {
    const cfg = LAYER_CONFIG[key]
    const activeBuffer = restrictionBuffers[key]
    return {
      key,
      label: cfg.label,
      color: cfg.color,
      count: countLayerFeatures(
        dataLayers[key],
        carId,
        cfg.filterByCar ?? false,
        cfg.supportsBuffer ? activeBuffer : null,
      ),
      active: visibleLayers[key],
      onToggle: () => toggleLayer(key),
      supportsBuffer: cfg.supportsBuffer,
      activeBuffer,
      bufferInfo: activeBuffer && distMetrics
        ? getRestrictionBufferInfo(key, distMetrics, activeBuffer)
        : null,
      onBufferChange: (buffer: RestrictionBufferMode) => toggleRestrictionBuffer(key, buffer),
    }
  })

  const climaticItems: ClimateMenuItem[] = CLIMATE_KEYS.map(key => {
    const cfg = CLIMATE_LAYER_CONFIG[key]
    const activeBuffer = climateBuffers[key]
    return {
      key,
      label: cfg.label,
      color: cfg.color,
      count: countLayerFeatures(
        dataLayers[key],
        carId,
        cfg.filterByCar ?? false,
        cfg.supportsBuffer ? activeBuffer : null,
      ),
      active: visibleClimateLayers[key],
      onToggle: () => toggleClimateLayer(key),
      supportsBuffer: cfg.supportsBuffer,
      activeBuffer,
      bufferInfo: activeBuffer && distMetrics && cfg.supportsBuffer
        ? getClimateBufferInfo(key, distMetrics, activeBuffer)
        : null,
      onBufferChange: (buffer: RestrictionBufferMode) => toggleClimateBuffer(key, buffer),
    }
  })

  return (
    <div className="map-panel">
      <MapLayerToolbar
        restrictions={restrictionItems}
        climatic={climaticItems}
        basemap={basemap}
        onToggleBasemap={toggleBasemap}
      />

      <MapContainer center={center} zoom={5} className="leaflet-map" zoomControl={false}>
        <TileLayer attribution={bm.attribution} url={bm.url} />
        <FlyToProperty property={selectedProperty} />
        {layerData.cars?.features.length > 0 && (
          <GeoJSON
            key={`cars-${carId}`}
            data={layerData.cars}
            style={(feature) => {
              const isSelected = feature?.properties?.id === selectedProperty?.id
              return styleFor(LAYER_CONFIG.cars.color, true, isSelected)
            }}
            onEachFeature={onEachCar}
          />
        )}
        {activeBufferRings.map(bufferM => {
          const layerKey = BUFFER_LAYER_KEYS[bufferM]
          const feats = bufferData.features.filter(f => f.properties?.layer === layerKey)
          if (!feats.length) return null
          const color = BUFFER_RING_COLORS[bufferM]
          return (
            <GeoJSON
              key={`buf-ring-${bufferM}-${carId}`}
              data={{ type: 'FeatureCollection', features: feats } as GeoJSON.FeatureCollection}
              style={() => ({
                color,
                weight: 1.5,
                fillColor: color,
                fillOpacity: 0.05,
                opacity: 0.75,
                dashArray: '6 4',
              })}
            />
          )
        })}
        {RESTRICTION_KEYS.map(key => {
          const cfg = LAYER_CONFIG[key]
          const data = layerData[key]
          if (!visibleLayers[key] || !data?.features.length) return null
          return (
            <GeoJSON
              key={`${key}-${carId}-${restrictionBuffers[key]}-${data.features.length}`}
              data={data}
              style={(feature) => styleFor(
                cfg.color,
                false,
                false,
                getFeatureScope(feature?.properties as Record<string, unknown> | undefined),
              )}
              onEachFeature={onEachRestrictionFeature(cfg.label)}
            />
          )
        })}
        {CLIMATE_KEYS.map(key => {
          const cfg = CLIMATE_LAYER_CONFIG[key]
          const data = climateLayerData[key]
          if (!visibleClimateLayers[key] || !data?.features.length) return null
          return (
            <GeoJSON
              key={`climate-${key}-${carId}-${climateBuffers[key]}-${data.features.length}`}
              data={data}
              style={(feature) => styleClimateLayer(key, cfg, feature)}
              onEachFeature={
                key === 'fire_scars'
                  ? onEachFireScar
                  : onEachClimateFeature(cfg.label)
              }
            />
          )
        })}
      </MapContainer>
    </div>
  )
}
