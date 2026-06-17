interface DistanceRiskScaleProps {
  label: string
  distanceM: number | null | undefined
}

function attentionLevel(distanceM: number | null | undefined): {
  level: 'alta' | 'media' | 'baixa' | 'nenhuma'
  label: string
  pct: number
} {
  if (distanceM == null || Number.isNaN(distanceM)) {
    return { level: 'nenhuma', label: 'Sem dado', pct: 0 }
  }
  const d = distanceM
  if (d <= 500) return { level: 'alta', label: 'Atenção alta (≤ 500 m)', pct: 100 }
  if (d <= 2000) return { level: 'media', label: 'Atenção média (500 m – 2 km)', pct: 66 }
  if (d <= 10000) return { level: 'baixa', label: 'Atenção baixa (2 – 10 km)', pct: 33 }
  return { level: 'nenhuma', label: 'Sem sinal relevante (> 10 km)', pct: 8 }
}

export default function DistanceRiskScale({ label, distanceM }: DistanceRiskScaleProps) {
  const att = attentionLevel(distanceM)
  const displayDist =
    distanceM == null ? 'n/d' : distanceM >= 1000 ? `${(distanceM / 1000).toFixed(1)} km` : `${Math.round(distanceM)} m`

  return (
    <div className={`distance-scale distance-scale--${att.level}`}>
      <div className="distance-scale-head">
        <span className="distance-scale-label">{label}</span>
        <span className="distance-scale-value">{displayDist}</span>
      </div>
      <div className="distance-scale-track">
        <div className="distance-scale-fill" style={{ width: `${att.pct}%` }} />
      </div>
      <div className="distance-scale-caption">{att.label}</div>
    </div>
  )
}
