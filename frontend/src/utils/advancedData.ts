import climateCreditData from '../data/climate_credit_risk.json'
import territorialData from '../data/territorial_pressure_index.json'
import integratedData from '../data/integrated_credit_risk.json'
import distanceData from '../data/distance_context_metrics.json'
import breakdownData from '../data/advanced_score_breakdown.json'
import type {
  AdvancedScoreBreakdown,
  ClimateCreditRisk,
  DistanceContextMetrics,
  IntegratedCreditRisk,
  TerritorialPressureIndex,
} from '../types'

export const climateCreditRisk = climateCreditData as ClimateCreditRisk[]
export const territorialPressure = territorialData as TerritorialPressureIndex[]
export const integratedCreditRisk = integratedData as IntegratedCreditRisk[]
export const distanceContextMetrics = distanceData as DistanceContextMetrics[]
export const advancedScoreBreakdown = breakdownData as AdvancedScoreBreakdown[]

export function findByCarId<T extends { car_id: string }>(rows: T[], carId: string): T | undefined {
  return rows.find(r => r.car_id === carId)
}
