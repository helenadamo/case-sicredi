interface SideMetric {
  label: string
  value: string
  hint?: string
}

interface IndexHeroStripProps {
  indexLabel: string
  riskClass: string
  mainValue: string
  sideMetrics?: SideMetric[]
}

export default function IndexHeroStrip({
  indexLabel,
  riskClass,
  mainValue,
  sideMetrics,
}: IndexHeroStripProps) {
  return (
    <div className={`index-hero index-hero--${riskClass}`}>
      <div className="index-hero-main">
        <div className="index-hero-label">{indexLabel}</div>
        <div className="index-hero-value">{mainValue}</div>
      </div>
      {sideMetrics && sideMetrics.length > 0 && (
        <div className="index-hero-side">
          {sideMetrics.map(metric => (
            <div key={metric.label} className="index-hero-metric">
              <span className="index-hero-metric-label">{metric.label}</span>
              <span className="index-hero-metric-value">{metric.value}</span>
              {metric.hint && <span className="index-hero-metric-hint">{metric.hint}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
