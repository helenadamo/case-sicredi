import {
  IRSA_RATIONALE,
  ICRC_RATIONALE,
  IPT_RATIONALE,
  IRTC_BLEND_RATIONALE,
  METHODOLOGY_REFS,
  type WeightRationale,
} from '../data/methodologyReferences'

const IRSA_WEIGHTS = IRSA_RATIONALE
const ICRC_WEIGHTS = ICRC_RATIONALE
const IPT_WEIGHTS = IPT_RATIONALE

const IRTC_BLEND = [
  { key: 'Socioambiental', pct: 60, color: '#C62828', desc: 'Sobreposição no imóvel' },
  { key: 'Climático', pct: 25, color: '#1E88A8', desc: 'Risco climático prospectivo' },
  { key: 'Entorno', pct: 15, color: '#E6A817', desc: 'Pressão territorial' },
]

function WeightRationaleList({ items }: { items: WeightRationale[] }) {
  return (
    <ul className="meth-rationale-list">
      {items.map(item => (
        <li key={item.label} className="meth-rationale-item">
          <span className="meth-rationale-head">
            <strong>{item.label}</strong> ({item.pts} pts)
          </span>
        </li>
      ))}
    </ul>
  )
}

function FlowArrow({ label }: { label?: string }) {
  return (
    <div className="meth-flow-arrow" aria-hidden>
      {label && <span className="meth-flow-arrow-label">{label}</span>}
      <span className="meth-flow-arrow-line" />
      <span className="meth-flow-arrow-head">▼</span>
    </div>
  )
}

function WeightBar({ items, total = 100 }: { items: { label: string; pts: number; color?: string }[]; total?: number }) {
  return (
    <div className="meth-weight-bar">
      {items.map(item => (
        <div
          key={item.label}
          className="meth-weight-segment"
          style={{
            flex: item.pts,
            background: item.color ?? 'var(--sicredi-green)',
          }}
          title={`${item.label}: ${item.pts} pts`}
        />
      ))}
    </div>
  )
}

function WeightLegend({ items }: { items: { label: string; pts: number; color?: string }[] }) {
  return (
    <div className="meth-weight-legend">
      {items.map(item => (
        <span key={item.label} className="meth-weight-legend-item">
          <span className="meth-weight-dot" style={{ background: item.color ?? 'var(--sicredi-green-dark)' }} />
          {item.label} <strong>{item.pts}</strong>
        </span>
      ))}
    </div>
  )
}

export default function MethodologyFlow() {
  return (
    <div className="meth-flow">
      <p className="meth-flow-lead">
        Três leituras independentes formam a classificação consolidada. Cada camada no painel separa <em>imóvel</em> e <em>entorno</em> no mesmo card.
      </p>

      {/* Conceitos */}
      <div className="meth-concept-row">
        <div className="meth-concept-card meth-concept-card--irsa">
          <span className="meth-concept-tag">No polígono CAR</span>
          <strong className="meth-concept-title">
            <span className="meth-concept-dot" aria-hidden />
            Socioambiental
          </strong>
          <span className="meth-concept-sub">Sobreposição = restrição atual</span>
        </div>
        <div className="meth-concept-card meth-concept-card--ipt">
          <span className="meth-concept-tag">Buffer 5 a 10 km</span>
          <strong className="meth-concept-title">
            <span className="meth-concept-dot" aria-hidden />
            Entorno
          </strong>
          <span className="meth-concept-sub">Proximidade = monitoramento</span>
        </div>
        <div className="meth-concept-card meth-concept-card--icrc">
          <span className="meth-concept-tag">Regional + entorno</span>
          <strong className="meth-concept-title">
            <span className="meth-concept-dot" aria-hidden />
            Climático
          </strong>
          <span className="meth-concept-sub">Clima = capacidade de pagamento</span>
        </div>
      </div>

      <FlowArrow label="compõem" />

      {/* IRTC blend */}
      <div className="meth-irtc-box">
        <div className="meth-irtc-header">
          <strong>Classificação consolidada</strong>
          <span>Matriz proprietária de triagem para crédito</span>
        </div>
        <div className="meth-irtc-formula">
          {IRTC_BLEND.map((b, i) => (
            <span key={b.key} className="meth-irtc-term">
              {i > 0 && <span className="meth-irtc-plus">+</span>}
              <span className="meth-irtc-pct" style={{ color: b.color }}>{b.pct}%</span>
              <span className="meth-irtc-key">{b.key}</span>
            </span>
          ))}
        </div>
        <div className="meth-irtc-bar">
          {IRTC_BLEND.map(b => (
            <div
              key={b.key}
              className="meth-irtc-bar-seg"
              style={{ flex: b.pct, background: b.color }}
              title={`${b.key} ${b.pct}%, ${b.desc}`}
            >
              <span>{b.pct}%</span>
            </div>
          ))}
        </div>
        <div className="meth-irtc-rules">
          <span className="meth-rule-chip">1 dimensão Alta ou 2 Médias → piso Médio</span>
          <span className="meth-rule-chip">2 dimensões Altas → piso Alto</span>
        </div>
        <ul className="meth-blend-rationale">
          {IRTC_BLEND_RATIONALE.map(b => (
            <li key={b.key} className="meth-blend-rationale-item">
              <strong style={{ color: b.color }}>{b.pct}% {b.key}</strong>
            </li>
          ))}
        </ul>
      </div>

      {/* Detalhe por índice */}
      <div className="meth-index-grid">
        <div className="meth-index-panel meth-index-panel--irsa">
          <div className="meth-index-panel-head">
            <span className="meth-index-acronym">
              <span className="meth-index-dot" aria-hidden />
              Restrição
            </span>
            <span>0 a 100 pts</span>
          </div>
          <WeightBar items={IRSA_WEIGHTS} />
          <WeightLegend items={IRSA_WEIGHTS} />
          <p className="meth-index-note">Evidências e ha% só no imóvel. Compõe 60% da classificação consolidada.</p>
          <WeightRationaleList items={IRSA_WEIGHTS} />
        </div>

        <div className="meth-index-panel meth-index-panel--icrc">
          <div className="meth-index-panel-head">
            <span className="meth-index-acronym">
              <span className="meth-index-dot" aria-hidden />
              Climático
            </span>
            <span>0 a 100 pts</span>
          </div>
          <WeightBar items={ICRC_WEIGHTS.map(w => ({ ...w, color: '#1E88A8' }))} />
          <WeightLegend items={ICRC_WEIGHTS.map(w => ({ ...w, color: '#1E88A8' }))} />
          <p className="meth-index-note">Cobertura &lt; 60% → validação climática. Compõe 25% da classificação consolidada.</p>
          <WeightRationaleList items={ICRC_WEIGHTS} />
        </div>

        <div className="meth-index-panel meth-index-panel--ipt">
          <div className="meth-index-panel-head">
            <span className="meth-index-acronym">
              <span className="meth-index-dot" aria-hidden />
              Entorno
            </span>
            <span>Entorno</span>
          </div>
          <WeightBar items={IPT_WEIGHTS.map(w => ({ ...w, color: '#E6A817' }))} />
          <WeightLegend items={IPT_WEIGHTS.map(w => ({ ...w, color: '#E6A817' }))} />
          <p className="meth-index-note">Anel externo do buffer, sem dupla contagem no imóvel. 15% da classificação consolidada.</p>
          <WeightRationaleList items={IPT_WEIGHTS} />
        </div>
      </div>

      {/* Fundamentação */}
      <div className="meth-references">
        <h4 className="meth-section-label">Fundamentação e fontes</h4>
        <p className="meth-flow-lead">
          Os pesos não são arbitrários: seguem hierarquia de <strong>materialidade regulatória</strong> (PRSAC/CMN),
          separação <strong>restrição atual × risco prospectivo</strong> (IFRS S2) e literatura de
          <strong> pressão no entorno</strong>. Calibração numérica documentada em <code>scripts/score_config.py</code>.
        </p>
        <div className="meth-ref-grid">
          {METHODOLOGY_REFS.map(ref => (
            <div key={ref.id} className="meth-ref-card">
              {ref.url ? (
                <a href={ref.url} target="_blank" rel="noopener noreferrer" className="meth-ref-card-title">
                  {ref.label}
                </a>
              ) : (
                <span className="meth-ref-card-title">{ref.label}</span>
              )}
              <p className="meth-ref-card-detail">{ref.detail}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline */}
      <div className="meth-pipeline">
        <h4 className="meth-section-label">Fluxo de dados</h4>
        <div className="meth-pipeline-track">
          {[
            'CAR + bases oficiais',
          'Interseção no imóvel',
            'Contexto 10 km',
            'Buffers + distância',
          'Clima + entorno',
          'Síntese + WebGIS',
          ].map((step, i, arr) => (
            <div key={step} className="meth-pipeline-node-wrap">
              <div className="meth-pipeline-node">
                <span className="meth-pipeline-num">{i + 1}</span>
                <span>{step}</span>
              </div>
              {i < arr.length - 1 && <span className="meth-pipeline-connector">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Classificação */}
      <div className="meth-class-ladder">
        <h4 className="meth-section-label">Classificação consolidada</h4>
        <div className="meth-ladder-steps">
          <div className="meth-ladder-step meth-ladder-step--baixo">
            <span>Baixo</span>
            <span>≤ 40</span>
          </div>
          <div className="meth-ladder-step meth-ladder-step--medio">
            <span>Médio</span>
            <span>41 a 70</span>
          </div>
          <div className="meth-ladder-step meth-ladder-step--alto">
            <span>Alto</span>
            <span>&gt; 70 ou 2 dim. altas</span>
          </div>
        </div>
      </div>
    </div>
  )
}
