import type { Property } from '../types'

interface MetricCardsProps {
  property: Property
}

interface Metric {
  label: string
  ha: number
  pct: number
  color: string
}

export default function MetricCards({ property }: MetricCardsProps) {
  const metrics: Metric[] = [
    { label: 'Embargo IBAMA', ha: property.embargo_ha, pct: property.embargo_pct, color: 'var(--risk-high)' },
    { label: 'Terra Indígena', ha: property.ti_ha, pct: property.ti_pct, color: '#7B4FA0' },
    { label: 'Unid. Conservação', ha: property.uc_ha, pct: property.uc_pct, color: 'var(--sicredi-green)' },
    { label: 'Desmatamento', ha: property.desmatamento_ha, pct: property.desmatamento_pct, color: '#E67E22' },
  ]

  return (
    <div className="metrics-grid">
      <div className="metric-hero">
        <div className="metric-hero-label">Área total do imóvel</div>
        <div className="metric-hero-value">{property.area_ha.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} <span>ha</span></div>
      </div>

      {metrics.map(m => (
        <div className={`metric-card ${m.ha > 0 ? 'metric-card--active' : ''}`} key={m.label}>
          <div className="metric-card-header">
            <span className="metric-dot" style={{ background: m.color }} />
            <span className="metric-card-label">{m.label}</span>
            <span className="metric-card-pct">{m.pct.toFixed(1)}%</span>
          </div>
          <div className="metric-bar-track">
            <div
              className="metric-bar-fill"
              style={{ width: `${Math.min(100, m.pct)}%`, background: m.color }}
            />
          </div>
          <div className="metric-card-ha">{m.ha.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ha sobrepostos</div>
        </div>
      ))}

      <div className="metric-score-card metric-score-card--dual">
        <div className="dual-score-item">
          <div className="score-ring" style={{ ['--score-pct' as string]: `${property.restriction_score}%` }}>
            <div className="score-ring-inner">
              <span className="score-ring-value">{property.restriction_score.toFixed(0)}</span>
              <span className="score-ring-label">Restrição</span>
            </div>
          </div>
          <div className={`risk-badge risk-badge--${property.restriction_class}`}>{property.restriction_class}</div>
        </div>
        <div className="dual-score-item">
          <div className="score-ring score-ring--climate" style={{ ['--score-pct' as string]: `${property.climate_score}%` }}>
            <div className="score-ring-inner">
              <span className="score-ring-value">{property.climate_score.toFixed(0)}</span>
              <span className="score-ring-label">Climático</span>
            </div>
          </div>
          <div className={`risk-badge risk-badge--${property.climate_class}`}>{property.climate_class}</div>
        </div>
      </div>
    </div>
  )
}
