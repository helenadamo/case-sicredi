import { useState } from 'react'
import MapView from './components/MapView'
import Sidebar from './components/Sidebar'
import DetailPanel from './components/DetailPanel'
import type { Property, Evidence, ScoreBreakdown, TabId } from './types'
import {
  climateCreditRisk,
  distanceContextMetrics,
  integratedCreditRisk,
  territorialPressure,
} from './utils/advancedData'

import propertiesData from './data/properties.json'
import evidenceData from './data/evidence.json'
import scoreData from './data/score_breakdown.json'

export default function App() {
  const properties = propertiesData as Property[]
  const evidence = evidenceData as Evidence[]
  const scoreBreakdown = scoreData as ScoreBreakdown[]

  const [selectedId, setSelectedId] = useState(
    properties.find(p => p.risk_class === 'Alto')?.id || properties[0]?.id || 'CAR_01',
  )
  const [activeTab, setActiveTab] = useState<TabId>('executive')

  const selected = properties.find(p => p.id === selectedId) || properties[0]

  const handleSelect = (id: string) => {
    setSelectedId(id)
    setActiveTab('executive')
  }

  return (
    <div className="app-shell">
      <Sidebar
        properties={properties}
        selectedId={selectedId}
        onSelect={handleSelect}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        integratedRisk={integratedCreditRisk}
      />

      <main className="workspace">
        <MapView
          selectedProperty={selected}
          onSelectProperty={handleSelect}
        />
        <DetailPanel
          property={selected}
          activeTab={activeTab}
          evidence={evidence}
          scoreBreakdown={scoreBreakdown}
          climateCredit={climateCreditRisk}
          territorialPressure={territorialPressure}
          integratedRisk={integratedCreditRisk}
          distanceMetrics={distanceContextMetrics}
        />
      </main>
    </div>
  )
}
