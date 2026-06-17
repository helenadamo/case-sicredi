import { useState, type ReactNode } from 'react'
import type { Evidence } from '../types'

export interface CriterionEntorno {
  points?: string | null
  detail?: string | null
}

interface CriterionCardProps {
  name: string
  propertyPoints: string
  propertyMeta: ReactNode
  entorno?: CriterionEntorno | null
  evidence?: Evidence[]
}

export default function CriterionCard({
  name,
  propertyPoints,
  propertyMeta,
  entorno,
  evidence = [],
}: CriterionCardProps) {
  const [open, setOpen] = useState(false)
  const hasEvidence = evidence.length > 0
  const showEntorno = entorno && (entorno.points || entorno.detail)

  return (
    <div className="criterion-card">
      <div className="criterion-card-zone criterion-card-zone--property">
        <div className="criterion-card-head">
          <span className="criterion-card-name">{name}</span>
          <span className="criterion-card-points">{propertyPoints}</span>
        </div>
        <div className="criterion-card-zone-label">No imóvel</div>
        <div className="criterion-card-meta">{propertyMeta}</div>
      </div>

      {showEntorno && (
        <div className="criterion-card-zone criterion-card-zone--entorno">
          <div className="criterion-card-head">
            <span className="criterion-card-zone-label">Entorno</span>
            {entorno.points && (
              <span className="criterion-card-points criterion-card-points--entorno">{entorno.points}</span>
            )}
          </div>
          {entorno.detail && (
            <p className="criterion-entorno-detail">{entorno.detail}</p>
          )}
        </div>
      )}

      {hasEvidence && (
        <>
          <button
            type="button"
            className={`criterion-evidence-toggle ${open ? 'open' : ''}`}
            onClick={() => setOpen(v => !v)}
            aria-expanded={open}
          >
            {open ? 'Ocultar evidências' : `Evidências (${evidence.length})`}
            <span className="criterion-evidence-chevron" aria-hidden>{open ? '▴' : '▾'}</span>
          </button>
          {open && (
            <div className="criterion-evidence-list">
              {evidence.map(ev => (
                <div className="criterion-evidence-item" key={ev.evidence_id}>
                  <div className="criterion-evidence-item-top">
                    <span className="criterion-evidence-id">{ev.evidence_id}</span>
                    <span className="criterion-evidence-area">
                      {ev.area_ha.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ha
                      · {ev.percent_of_property.toFixed(1)}%
                    </span>
                  </div>
                  <div className="criterion-evidence-source">{ev.source_name}</div>
                  {ev.interpretation && (
                    <p className="criterion-evidence-text">{ev.interpretation}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
