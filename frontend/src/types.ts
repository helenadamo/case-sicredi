export interface Property {
  id: string
  car_code: string
  uf: string
  label: string
  area_ha: number
  lat: number
  lng: number
  iesc_score: number
  restriction_score: number
  restriction_class: string
  climate_score: number
  climate_class: string
  climate_risk: string
  risk_class: string
  current_risk: string
  prospective_risk: string
  evidence_confidence: string
  main_drivers: string
  recommendation: string
  embargo_ha: number
  embargo_pct: number
  ti_ha: number
  ti_pct: number
  uc_ha: number
  uc_pct: number
  desmatamento_ha: number
  desmatamento_pct: number
  app_ha: number
  app_pct: number
  stress_hidrico_idx: number | null
  technical_recommendation: string
  required_followup: string
}

export interface Evidence {
  evidence_id: string
  car_id: string
  car_code: string
  theme: string
  source_name: string
  source_url: string
  download_date: string
  area_ha: number
  percent_of_property: number
  confidence: string
  interpretation: string
  limitation: string
}

export interface ScoreComponent {
  criterion: string
  weight: number
  value: number
  pct: number
}

export interface ScoreBreakdown {
  car_id: string
  components: ScoreComponent[]
  total: number
}

export type TabId =
  | 'executive'
  | 'restriction'
  | 'climate_credit'
  | 'opinion'
  | 'methodology'
  | 'report'

export interface ClimateCreditRisk {
  car_id: string
  car_code: string
  icrc_score: number
  icrc_class: string
  data_coverage_pct?: number
  drought_component: number
  water_surface_component: number
  hydrology_component: number
  agro_sensitivity_component: number
  fire_component: number
  main_climate_driver: string
  climate_interpretation: string
  missing_components: string | null
  data_confidence: string
}

export interface TerritorialPressureIndex {
  car_id: string
  car_code: string
  ipt_score: number
  ipt_class: string
  protected_area_proximity_component: number
  deforestation_pressure_component: number
  embargo_context_component: number
  fire_context_component: number
  land_use_change_component: number
  main_pressure_driver: string
  pressure_interpretation: string
  missing_components: string | null
  data_confidence: string
}

export interface IntegratedCreditRisk {
  car_id: string
  car_code: string
  current_restriction_score: number
  icrc_score: number
  ipt_score: number
  weighted_irtc_score?: number | null
  irtc_score: number
  irtc_class: string
  prudential_floor_reason?: string | null
  main_final_driver: string
  secondary_drivers: string | null
  confidence_level: string
  credit_recommendation: string
  executive_summary: string
  technical_note: string
}

export interface DistanceContextMetrics {
  car_id: string
  car_code: string
  nearest_ti_m: number | null
  nearest_uc_m: number | null
  nearest_embargo_m: number | null
  nearest_deforestation_m: number | null
  nearest_water_m: number | null
  deforestation_5km_ha: number
  deforestation_10km_ha: number
  deforestation_alerts_5km: number
  embargo_5km_ha: number
  embargo_5km_surroundings_ha?: number
  deforestation_5km_surroundings_ha?: number
  deforestation_10km_surroundings_ha?: number
  protected_area_within_1km: boolean
  protected_area_within_5km: boolean
  drainage_density_5km: number | null
  water_surface_change_pct: number | null
  fire_recent_5km_ha: number | null
  fire_recent_ha_property?: number | null
  fire_years_active?: number | null
  fire_recurrence_class?: string | null
  water_surface_recent_ha?: number | null
  water_surface_buffer_ha?: number | null
  context_confidence: string
  context_notes: string | null
}

export interface AdvancedScoreComponent {
  name: string
  points: number
  weight: number
}

export interface AdvancedScoreBreakdown {
  car_id: string
  irtc_score: number
  irtc_class: string
  restriction_score: number
  icrc_score: number
  icrc_class: string
  ipt_score: number
  ipt_class: string
  icrc_components: AdvancedScoreComponent[]
  ipt_components: AdvancedScoreComponent[]
  executive_summary: string
  credit_recommendation: string
  confidence_level: string
}
