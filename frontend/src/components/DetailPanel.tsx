import type { ReactNode } from 'react'
import type {
  Property,
  Evidence,
  ScoreBreakdown,
  TabId,
  ClimateCreditRisk,
  TerritorialPressureIndex,
  IntegratedCreditRisk,
  DistanceContextMetrics,
} from '../types'
import {
  generateTechnicalOpinion,
  getEvidenceForCriterion,
  getIcrcComponentDetails,
  getRestrictionBreakdown,
  getRestrictionEntornoBlock,
  getClimateEntornoBlock,
  propertyShortName,
  resolveIrtcClass,
  getRestrictionAreaSummary,
} from '../utils/presentation'
import { findByCarId } from '../utils/advancedData'
import CriterionCard from './CriterionCard'
import IndexHeroStrip from './IndexHeroStrip'
import MethodologyFlow from './MethodologyFlow'

interface DetailPanelProps {
  property: Property
  activeTab: TabId
  evidence: Evidence[]
  scoreBreakdown: ScoreBreakdown[]
  climateCredit: ClimateCreditRisk[]
  territorialPressure: TerritorialPressureIndex[]
  integratedRisk: IntegratedCreditRisk[]
  distanceMetrics: DistanceContextMetrics[]
}

function Section({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`panel-section ${className}`}>
      <h3 className="panel-section-title">{title}</h3>
      {children}
    </section>
  )
}

export default function DetailPanel({
  property,
  activeTab,
  evidence,
  scoreBreakdown,
  climateCredit,
  territorialPressure,
  integratedRisk,
  distanceMetrics,
}: DetailPanelProps) {
  const restrictionScore = scoreBreakdown.find(s => s.car_id === property.id)
  const restriction = restrictionScore ? getRestrictionBreakdown(property, restrictionScore) : null
  const icrc = findByCarId(climateCredit, property.id)
  const ipt = findByCarId(territorialPressure, property.id)
  const irtc = findByCarId(integratedRisk, property.id)
  const dist = findByCarId(distanceMetrics, property.id)
  const icrcComponents = icrc ? getIcrcComponentDetails(property, icrc, dist) : []
  const opinion = generateTechnicalOpinion(property)
  const areaSummary = getRestrictionAreaSummary(property)

  const restrictionSideMetrics = areaSummary.hasOverlap
    ? [
        {
          label: 'Área sobreposta',
          value: `${areaSummary.restrictedHa.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} ha`,
          hint: `${areaSummary.overlapPct.toFixed(0)}% do imóvel`,
        },
      ]
    : [
        {
          label: 'Área sobreposta',
          value: '0 ha',
          hint: '0% do imóvel',
        },
        {
          label: 'Área sem sobreposição',
          value: `${property.area_ha.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} ha`,
          hint: '100% do imóvel',
        },
      ]

  const irtcClass = irtc
    ? resolveIrtcClass(
        irtc.irtc_score,
        property.restriction_class,
        icrc?.icrc_class,
        ipt?.ipt_class,
      )
    : property.restriction_class

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div>
          <div className="detail-eyebrow">Triagem socioambiental · {property.uf}</div>
          <h2 className="detail-title">{propertyShortName(property)}</h2>
          <div className="detail-car-code">{property.id} · {property.area_ha.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} ha</div>
        </div>
      </div>

      <div className="detail-body">
        {activeTab === 'executive' && (
          <>
            {irtc ? (
              <IndexHeroStrip
                indexLabel="Classificação consolidada de triagem"
                riskClass={irtcClass}
                mainValue={`${irtcClass} · ${irtc.irtc_score.toFixed(1)}/100`}
                sideMetrics={[
                  {
                    label: 'Risco socioambiental',
                    value: `${property.restriction_class} · ${property.restriction_score.toFixed(1)}`,
                    hint: 'Sobreposições legais no CAR',
                  },
                  {
                    label: 'Risco climático',
                    value: `${icrc?.icrc_class || property.climate_class} · ${(icrc?.icrc_score ?? property.climate_score).toFixed(1)}`,
                    hint: 'Seca, água, fogo e sensibilidade produtiva',
                  },
                  {
                    label: 'Entorno',
                    value: `${ipt?.ipt_class || 'n/d'} · ${ipt ? ipt.ipt_score.toFixed(1) : '—'}`,
                    hint: 'Pressão territorial em buffers',
                  },
                ]}
              />
            ) : (
              <IndexHeroStrip
                indexLabel="Risco socioambiental"
                riskClass={property.restriction_class}
                mainValue={`Risco ${property.restriction_class}`}
                sideMetrics={restrictionSideMetrics}
              />
            )}

            <div className="executive-triple-cards">
              <div className="exec-card">
                <div className="exec-card-label">Risco socioambiental</div>
                <div className="exec-card-value">{property.restriction_score.toFixed(0)}</div>
                <div className={`exec-card-class exec-card-class--${property.restriction_class}`}>{property.restriction_class}</div>
              </div>
              <div className="exec-card">
                <div className="exec-card-label">Risco climático</div>
                <div className="exec-card-value">{icrc ? icrc.icrc_score.toFixed(0) : property.climate_score.toFixed(0)}</div>
                <div className={`exec-card-class exec-card-class--${icrc?.icrc_class || property.climate_class}`}>
                  {icrc?.icrc_class || property.climate_class}
                </div>
              </div>
              <div className="exec-card">
                <div className="exec-card-label">Pressão no entorno</div>
                <div className="exec-card-value">{ipt ? ipt.ipt_score.toFixed(0) : '—'}</div>
                <div className={`exec-card-class exec-card-class--${ipt?.ipt_class || 'Baixo'}`}>
                  {ipt?.ipt_class || 'n/d'}
                </div>
              </div>
            </div>

            <div className="executive-facts">
              <div className="fact-row fact-row--action">
                <span className="fact-label">Recomendação</span>
                <span className="fact-value fact-value--emphasis">
                  {irtc?.credit_recommendation || property.recommendation}
                </span>
              </div>
            </div>
          </>
        )}

        {activeTab === 'restriction' && restriction && (
          <>
            <IndexHeroStrip
              indexLabel="Risco socioambiental"
              riskClass={property.restriction_class}
              mainValue={`${property.restriction_class} · ${restrictionScore!.total.toFixed(0)}/100`}
              sideMetrics={restrictionSideMetrics}
            />
            <p className="index-subtitle">{restriction.indexSubtitle}</p>

            <Section title="Camadas de análise">
              <div className="criterion-card-list">
                {restriction.criteria.map(c => {
                  const zeroOnProperty = c.cappedPoints <= 0.01
                  const entorno = getRestrictionEntornoBlock(c.criterion, dist, ipt)
                  return (
                  <CriterionCard
                    key={c.criterion}
                    name={c.criterion}
                    propertyPoints={`+${c.cappedPoints.toFixed(1)} pts`}
                    propertyMeta={
                      zeroOnProperty ? (
                        <span>Sem sobreposição no imóvel</span>
                      ) : (
                        <span>
                          {c.ha.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ha
                          · {c.pct.toFixed(1)}% do imóvel
                          {c.saturated ? ' · saturação de peso' : ''}
                        </span>
                      )
                    }
                    entorno={entorno}
                    evidence={getEvidenceForCriterion(evidence, property.id, c.criterion)}
                  />
                  )
                })}
              </div>
            </Section>

            {restriction.overrides.some(o => o.applied) && (
              <Section title="Regras qualitativas">
                <div className="iesc-summary-grid">
                  {restriction.overrides.filter(o => o.applied).map(o => (
                    <div className="iesc-override-row iesc-override-row--active" key={o.label}>
                      <span className="iesc-override-label">{o.label}</span>
                      <span className="iesc-override-status">Aplicado</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            <div className="score-final-block">
              <div className="score-final-label">Classificação</div>
              <div className={`risk-badge risk-badge--lg risk-badge--${property.restriction_class}`}>
                {property.restriction_class}
              </div>
              <p className="index-rule">{restriction.classification.rule}</p>
            </div>

            <Section title="Risco atual">
              <p className="prose">{property.current_risk}</p>
            </Section>
          </>
        )}

        {activeTab === 'restriction' && !restriction && (
          <p className="empty-state">Dados de risco socioambiental ainda não disponíveis.</p>
        )}

        {activeTab === 'climate_credit' && icrc && (
          <>
            <IndexHeroStrip
              indexLabel="Risco climático"
              riskClass={icrc.icrc_class}
              mainValue={`${icrc.icrc_class} · ${icrc.icrc_score.toFixed(0)}/100`}
            />
            <p className="index-subtitle">
              Risco prospectivo ligado a produtividade e capacidade de pagamento — separado do risco socioambiental atual.
            </p>

            <Section title="Camadas de análise">
              <div className="criterion-card-list">
                {icrcComponents.map(c => {
                  const entorno = getClimateEntornoBlock(c.name, dist, ipt)
                  return (
                  <CriterionCard
                    key={c.name}
                    name={c.name}
                    propertyPoints={`${c.points.toFixed(1)} / ${c.weight} pts`}
                    propertyMeta={
                      <>
                        <span><strong>Fonte:</strong> {c.source}</span>
                        <span><strong>Métrica no imóvel / regional:</strong> {c.metric}</span>
                        <span>Confiança: {c.confidence}</span>
                      </>
                    }
                    entorno={entorno}
                  />
                  )
                })}
              </div>
            </Section>

            <Section title="Interpretação para crédito">
              <p className="prose">{icrc.climate_interpretation}</p>
              <p className="detail-footnote">
                Driver: {icrc.main_climate_driver} · Confiança: {icrc.data_confidence}
                {icrc.data_coverage_pct != null && ` · Cobertura: ${icrc.data_coverage_pct.toFixed(0)}%`}
              </p>
            </Section>
          </>
        )}

        {activeTab === 'climate_credit' && !icrc && (
          <p className="empty-state">Dados de risco climático ainda não disponíveis. Execute scripts 09–14 do pipeline.</p>
        )}

        {activeTab === 'opinion' && (
          <Section title="Parecer técnico">
            <div className="opinion-document">
              <div className="opinion-header">
                <strong>{propertyShortName(property)}</strong> · {property.uf}<br />
                CAR: {property.car_code.replace(/(.{2})(\d{7})(.+)/, '$1-$2-$3').slice(0, 42)}…
              </div>
              {opinion.split('\n\n').map((para, i) => (
                <p key={i} className="opinion-paragraph">{para}</p>
              ))}
              <div className="opinion-footer">
                Restrição: {property.restriction_score.toFixed(0)} ({property.restriction_class}) · Climático: {property.climate_score.toFixed(0)} ({property.climate_class})
              </div>
            </div>
          </Section>
        )}

        {activeTab === 'methodology' && (
          <Section title="Como o score é montado">
            <MethodologyFlow />
          </Section>
        )}

        {activeTab === 'report' && (
          <Section title="Relatório técnico">
            <p className="prose report-intro">
              Os arquivos finais foram gerados pelo pipeline e ficam na pasta output do repositório.
              As tabelas de auditoria estão em output/tables, e os PDFs finais ficam em output/report e output/maps.
            </p>
            <div className="report-card">
              <div className="report-card-info">
                <strong>relatorio_tecnico_sicredi.pdf</strong>
                <span>relatório técnico consolidado em output/report</span>
              </div>
            </div>
            <div className="report-card">
              <div className="report-card-info">
                <strong>anexo_mapas_socioambientais.pdf</strong>
                <span>anexo cartográfico, uma página por imóvel, em output/maps</span>
              </div>
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}
