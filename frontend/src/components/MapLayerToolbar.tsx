import { useEffect, useRef, useState } from 'react'
import { IconBasemapSwitch } from './Icons'

export type RestrictionBufferMode = 5000 | 10000 | null

export interface LayerMenuItem {
  key: string
  label: string
  color: string
  count?: number
  active: boolean
  onToggle: () => void
}

export interface RestrictionMenuItem extends LayerMenuItem {
  supportsBuffer?: boolean
  activeBuffer: RestrictionBufferMode
  bufferInfo?: string | null
  onBufferChange: (buffer: RestrictionBufferMode) => void
}

export interface ClimateMenuItem extends LayerMenuItem {
  supportsBuffer?: boolean
  activeBuffer?: RestrictionBufferMode
  bufferInfo?: string | null
  onBufferChange?: (buffer: RestrictionBufferMode) => void
}

interface MapLayerToolbarProps {
  restrictions: RestrictionMenuItem[]
  climatic: ClimateMenuItem[]
  basemap: 'osm' | 'satellite'
  onToggleBasemap: () => void
}

type OpenMenu = 'restriction' | 'climate' | null

function ClimateMenuRow({ item }: { item: ClimateMenuItem }) {
  if (!item.supportsBuffer) {
    return (
      <label className="map-menu-row">
        <input type="checkbox" checked={item.active} onChange={item.onToggle} />
        <span className="map-menu-dot" style={{ background: item.color }} />
        <span className="map-menu-label">{item.label}</span>
        {item.count != null && item.count > 0 && (
          <span className="map-menu-count">{item.count}</span>
        )}
      </label>
    )
  }

  return (
    <div className={`map-menu-restriction ${item.active ? 'active' : ''}`}>
      <label className="map-menu-row">
        <input type="checkbox" checked={item.active} onChange={item.onToggle} />
        <span className="map-menu-dot" style={{ background: item.color }} />
        <span className="map-menu-label">{item.label}</span>
        {item.count != null && item.count > 0 && (
          <span className="map-menu-count">{item.count}</span>
        )}
      </label>
      <div className="map-menu-buffer-row">
        <button
          type="button"
          className={`map-buffer-pill ${item.activeBuffer === 5000 ? 'on' : ''}`}
          onClick={() => item.onBufferChange?.(item.activeBuffer === 5000 ? null : 5000)}
        >
          5 km
        </button>
        <button
          type="button"
          className={`map-buffer-pill ${item.activeBuffer === 10000 ? 'on' : ''}`}
          onClick={() => item.onBufferChange?.(item.activeBuffer === 10000 ? null : 10000)}
        >
          10 km
        </button>
      </div>
      {item.activeBuffer && item.bufferInfo && (
        <p className="map-menu-buffer-info">
          {item.bufferInfo}
          {item.count != null && item.count > 0 ? ` · ${item.count} feição(ões) no mapa` : ''}
        </p>
      )}
    </div>
  )
}

function RestrictionMenuRow({ item }: { item: RestrictionMenuItem }) {
  return (
    <div className={`map-menu-restriction ${item.active ? 'active' : ''}`}>
      <label className="map-menu-row">
        <input type="checkbox" checked={item.active} onChange={item.onToggle} />
        <span className="map-menu-dot" style={{ background: item.color }} />
        <span className="map-menu-label">{item.label}</span>
        {item.count != null && item.count > 0 && (
          <span className="map-menu-count">{item.count}</span>
        )}
      </label>
      {item.supportsBuffer && (
        <div className="map-menu-buffer-row">
          <button
            type="button"
            className={`map-buffer-pill ${item.activeBuffer === 5000 ? 'on' : ''}`}
            onClick={() => item.onBufferChange(item.activeBuffer === 5000 ? null : 5000)}
          >
            5 km
          </button>
          <button
            type="button"
            className={`map-buffer-pill ${item.activeBuffer === 10000 ? 'on' : ''}`}
            onClick={() => item.onBufferChange(item.activeBuffer === 10000 ? null : 10000)}
          >
            10 km
          </button>
        </div>
      )}
      {item.activeBuffer && item.bufferInfo && (
        <p className="map-menu-buffer-info">
          {item.bufferInfo}
          {item.count != null && item.count > 0 ? ` · ${item.count} feição(ões) no mapa` : ''}
        </p>
      )}
    </div>
  )
}

export default function MapLayerToolbar({
  restrictions,
  climatic,
  basemap,
  onToggleBasemap,
}: MapLayerToolbarProps) {
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  const activeRestrictions = restrictions.filter(r => r.active).length
  const activeClimatic = climatic.filter(c => c.active).length
  const activeClimateBuffers = climatic.filter(c => c.activeBuffer != null).length
  const activeBuffers = restrictions.filter(r => r.activeBuffer != null).length + activeClimateBuffers

  useEffect(() => {
    if (!openMenu) return
    const close = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [openMenu])

  const toggleMenu = (menu: OpenMenu) => {
    setOpenMenu(prev => (prev === menu ? null : menu))
  }

  return (
    <div className="map-toolbar" ref={rootRef}>
      <div className="map-toolbar-actions">
        <div className="map-tb-dropdown">
          <button
            type="button"
            className={`map-tb-trigger ${openMenu === 'restriction' ? 'open' : ''} ${activeBuffers > 0 ? 'has-active' : ''}`}
            onClick={() => toggleMenu('restriction')}
            aria-expanded={openMenu === 'restriction'}
          >
            <span>Restrições</span>
            <span className="map-tb-meta">{activeRestrictions}/{restrictions.length}</span>
            <span className="map-tb-chevron" aria-hidden>▾</span>
          </button>
          {openMenu === 'restriction' && (
            <div className="map-tb-menu map-tb-menu--restrictions" role="menu">
              {restrictions.map(item => (
                <RestrictionMenuRow key={item.key} item={item} />
              ))}
            </div>
          )}
        </div>

        <div className="map-tb-dropdown">
          <button
            type="button"
            className={`map-tb-trigger ${openMenu === 'climate' ? 'open' : ''} ${activeClimatic > 0 ? 'has-active' : ''}`}
            onClick={() => toggleMenu('climate')}
            aria-expanded={openMenu === 'climate'}
          >
            <span>Climáticos</span>
            <span className="map-tb-meta">{activeClimatic}/{climatic.length}</span>
            <span className="map-tb-chevron" aria-hidden>▾</span>
          </button>
          {openMenu === 'climate' && (
            <div className="map-tb-menu map-tb-menu--restrictions" role="menu">
              {climatic.map(item => (
                <ClimateMenuRow key={item.key} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        className="map-toolbar-basemap"
        onClick={onToggleBasemap}
        title={basemap === 'satellite' ? 'Alternar para mapa de ruas' : 'Alternar para imagem de satélite'}
      >
        <IconBasemapSwitch size={16} />
        <span>{basemap === 'satellite' ? 'Satélite' : 'Ruas'}</span>
      </button>
    </div>
  )
}
