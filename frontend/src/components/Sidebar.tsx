import type { Property, TabId, IntegratedCreditRisk } from '../types'
import { propertyShortName, rankPropertiesByIntegrated, resolveIrtcClass } from '../utils/presentation'
import { climateCreditRisk, territorialPressure } from '../utils/advancedData'
import { IconFile, IconShield } from './Icons'

interface SidebarProps {
  properties: Property[]
  selectedId: string
  onSelect: (id: string) => void
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  integratedRisk: IntegratedCreditRisk[]
}

const NAV: { id: TabId; label: string; icon: typeof IconShield }[] = [
  { id: 'executive', label: 'Resumo Executivo', icon: IconShield },
  { id: 'restriction', label: 'Risco Socioambiental', icon: IconShield },
  { id: 'climate_credit', label: 'Risco Climático', icon: IconShield },
  { id: 'opinion', label: 'Parecer Técnico', icon: IconFile },
  { id: 'methodology', label: 'Metodologia', icon: IconFile },
  { id: 'report', label: 'Relatório', icon: IconFile },
]

const ORDINALS = ['1º', '2º', '3º', '4º', '5º', '6º', '7º', '8º']

export default function Sidebar({ properties, selectedId, onSelect, activeTab, onTabChange, integratedRisk }: SidebarProps) {
  const ranked = rankPropertiesByIntegrated(properties, integratedRisk)
  const alto = integratedRisk.length
    ? properties.filter(p => {
        const ir = integratedRisk.find(r => r.car_id === p.id)
        const icrc = climateCreditRisk.find(r => r.car_id === p.id)
        const ipt = territorialPressure.find(r => r.car_id === p.id)
        return (
          ir &&
          resolveIrtcClass(ir.irtc_score, p.restriction_class, icrc?.icrc_class, ipt?.ipt_class) === 'Alto'
        )
      }).length
    : properties.filter(p => p.restriction_class === 'Alto').length

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src="/sicredi-logo-clean.png" alt="Sicredi" className="brand-logo" />
        <div className="brand-text">
          <div className="brand-title">Triagem SAC</div>
          <div className="brand-sub">Crédito Rural</div>
        </div>
      </div>

      <div className="sidebar-stats">
        <div className="stat-pill stat-pill--danger">
          <span className="stat-num">{alto}</span>
          <span className="stat-lbl">Alto risco</span>
        </div>
        <div className="stat-pill">
          <span className="stat-num">{properties.length}</span>
          <span className="stat-lbl">Analisados</span>
        </div>
      </div>

      <div className="ranking-block">
        <div className="sidebar-section-label">Priorização</div>
        <div className="ranking-list">
          {ranked.map((p, i) => {
            const ir = integratedRisk.find(r => r.car_id === p.id)
            const icrc = climateCreditRisk.find(r => r.car_id === p.id)
            const ipt = territorialPressure.find(r => r.car_id === p.id)
            const riskLabel = ir
              ? resolveIrtcClass(ir.irtc_score, p.restriction_class, icrc?.icrc_class, ipt?.ipt_class)
              : p.restriction_class
            return (
            <button
              key={p.id}
              className={`ranking-item ${p.id === selectedId ? 'selected' : ''}`}
              onClick={() => onSelect(p.id)}
            >
              <span className="ranking-pos">{ORDINALS[i] || `${i + 1}º`}</span>
              <span className="ranking-name">{propertyShortName(p)}</span>
              <span className={`ranking-risk ranking-risk--${riskLabel}`}>
                {riskLabel}
              </span>
            </button>
            )
          })}
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`nav-item ${activeTab === id ? 'active' : ''}`}
            onClick={() => onTabChange(id)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
