import type { Property, ScoreBreakdown, Evidence, ClimateCreditRisk, DistanceContextMetrics, TerritorialPressureIndex } from '../types'
import { climateCreditRisk, territorialPressure } from './advancedData'

export interface OverlapTheme {
  label: string
  ha: number
  pct: number
}

export function propertyShortName(property: Property): string {
  const m = property.label.match(/Imóvel\s*(\d+)/i)
  return m ? `Imóvel ${m[1].padStart(2, '0')}` : property.label
}

export function getOverlapThemes(property: Property): OverlapTheme[] {
  return [
    { label: 'Embargo IBAMA', ha: property.embargo_ha, pct: property.embargo_pct },
    { label: 'Terra Indígena', ha: property.ti_ha, pct: property.ti_pct },
    { label: 'Unidade de Conservação', ha: property.uc_ha, pct: property.uc_pct },
    { label: 'APP (FBDS)', ha: property.app_ha, pct: property.app_pct },
    { label: 'Desmatamento', ha: property.desmatamento_ha, pct: property.desmatamento_pct },
  ]
    .filter(t => t.ha > 0.01)
    .sort((a, b) => b.pct - a.pct)
}

/** Resumo de sobreposição no imóvel (soma aproximada de temas, teto 100%). */
export function getRestrictionAreaSummary(property: Property) {
  const overlapPct = Math.min(
    100,
    property.embargo_pct + property.ti_pct + property.uc_pct + property.app_pct + property.desmatamento_pct,
  )
  const restrictedHa = (property.area_ha * overlapPct) / 100
  const cleanHa = Math.max(0, property.area_ha - restrictedHa)
  const themes = getOverlapThemes(property)
  return {
    overlapPct,
    restrictedHa,
    cleanHa,
    topTheme: themes[0] ?? null,
    hasOverlap: themes.length > 0,
  }
}

export function rankProperties(properties: Property[]): Property[] {
  const order = { Alto: 0, Médio: 1, Baixo: 2, Crítico: 0 }
  return [...properties].sort((a, b) => {
    const riskDiff = (order[a.restriction_class as keyof typeof order] ?? 3) - (order[b.restriction_class as keyof typeof order] ?? 3)
    if (riskDiff !== 0) return riskDiff
    return b.restriction_score - a.restriction_score
  })
}

const IRTC_CLASS_ORDER: Record<string, number> = { Baixo: 0, Médio: 1, Alto: 2, Crítico: 3 }

function normalizeClassLabel(label: string | undefined): string {
  return (label ?? '').replace('*', '').trim()
}

function dimensionFloor(irsaClass: string, icrcClass: string | undefined, iptClass: string | undefined): string {
  const classes = [irsaClass, icrcClass, iptClass].map(c => normalizeClassLabel(c))
  const highs = classes.filter(c => c === 'Alto' || c === 'Crítico').length
  const crits = classes.filter(c => c === 'Crítico').length
  const medios = classes.filter(c => c === 'Médio').length

  if (crits >= 1 || highs >= 2) return 'Alto'
  if (highs >= 1 || medios >= 2) return 'Médio'
  return 'Baixo'
}

export function resolveIrtcClass(
  irtcScore: number,
  irsaClass: string,
  icrcClass: string | undefined,
  iptClass: string | undefined,
): string {
  let base = 'Baixo'
  if (irtcScore > 70) base = 'Alto'
  else if (irtcScore > 40) base = 'Médio'

  const floor = dimensionFloor(irsaClass, icrcClass, iptClass)
  return (IRTC_CLASS_ORDER[base] ?? 0) >= (IRTC_CLASS_ORDER[floor] ?? 0) ? base : floor
}

export function explainIrtcClass(
  irtcScore: number,
  irsaClass: string,
  icrcClass: string | undefined,
  iptClass: string | undefined,
  resolvedClass: string,
): string {
  const base =
    irtcScore > 70 ? 'Alto' : irtcScore > 40 ? 'Médio' : 'Baixo'
  const floor = dimensionFloor(irsaClass, icrcClass, iptClass)

  if (resolvedClass !== base) {
    return `A média ponderada sugere ${base}, mas a regra de prudência das dimensões eleva a triagem para ${resolvedClass}.`
  }
  return 'Classificação segue a combinação ponderada das três dimensões.'
}

export function formatIrtcBlend(
  irtc: {
    irtc_score: number
    weighted_irtc_score?: number | null
    prudential_floor_reason?: string | null
    current_restriction_score?: number
    icrc_score: number
    ipt_score: number
  },
): string {
  const irsa = irtc.current_restriction_score ?? 0
  const icrc = irtc.icrc_score
  const ipt = irtc.ipt_score
  const weighted = irtc.weighted_irtc_score ?? (0.6 * irsa + 0.25 * icrc + 0.15 * ipt)
  const formula = `60% restrição + 25% clima + 15% entorno = ${weighted.toFixed(1)}`
  if (irtc.prudential_floor_reason && irtc.irtc_score > weighted + 0.05) {
    return `${formula}; final ${irtc.irtc_score.toFixed(1)} por ${irtc.prudential_floor_reason}.`
  }
  return `${formula}.`
}

export function rankPropertiesByIntegrated(
  properties: Property[],
  integrated: { car_id: string; irtc_score: number }[],
): Property[] {
  if (!integrated.length) return rankProperties(properties)
  const icrcMap = Object.fromEntries(climateCreditRisk.map(r => [r.car_id, r.icrc_class]))
  const iptMap = Object.fromEntries(territorialPressure.map(r => [r.car_id, r.ipt_class]))
  const irtcClassMap = Object.fromEntries(
    integrated.map(r => {
      const prop = properties.find(p => p.id === r.car_id)
      return [
        r.car_id,
        resolveIrtcClass(
          r.irtc_score,
          prop?.restriction_class ?? 'Baixo',
          icrcMap[r.car_id],
          iptMap[r.car_id],
        ),
      ]
    }),
  )
  const order = { Alto: 0, Crítico: 0, Médio: 1, Baixo: 2 }
  const scoreMap = Object.fromEntries(integrated.map(r => [r.car_id, r.irtc_score]))
  return [...properties].sort((a, b) => {
    const classDiff =
      (order[irtcClassMap[a.id] as keyof typeof order] ?? 3) -
      (order[irtcClassMap[b.id] as keyof typeof order] ?? 3)
    if (classDiff !== 0) return classDiff
    return (scoreMap[b.id] ?? 0) - (scoreMap[a.id] ?? 0)
  })
}

export function primaryReason(property: Property): string | null {
  const top = getOverlapThemes(property)[0]
  if (!top) return null
  return `${top.pct.toFixed(1)}% da área sobreposta a ${top.label}`
}

export function secondaryReason(property: Property): string | null {
  const themes = getOverlapThemes(property)
  if (themes.length < 2) return null
  const sec = themes[1]
  return `${sec.pct.toFixed(1)}% de área com ${sec.label.toLowerCase()}`
}

export function humanizeProspectiveRisk(property: Property): string {
  const parts: string[] = []

  if (property.desmatamento_ha > 0.01) {
    parts.push(
      'O imóvel apresenta desmatamento recente. Caso esse padrão se mantenha, pode demandar monitoramento mais frequente ao longo do ciclo da operação.',
    )
  }

  if (['MT', 'AM', 'PA'].includes(property.uf)) {
    parts.push(
      'O imóvel está em região ambientalmente sensível, o que recomenda atenção redobrada em acompanhamentos periódicos.',
    )
  }

  if (property.stress_hidrico_idx != null && property.stress_hidrico_idx >= 0.55) {
    parts.push(
      `O município apresenta estresse hídrico elevado (${(property.stress_hidrico_idx * 100).toFixed(0)}% no AdaptaBrasil), o que pode afetar produtividade e fluxo de caixa ao longo do ciclo da operação.`,
    )
  } else if (property.stress_hidrico_idx != null && property.stress_hidrico_idx >= 0.35) {
    parts.push(
      `Estresse hídrico municipal moderado (${(property.stress_hidrico_idx * 100).toFixed(0)}% no AdaptaBrasil) : variável climática a monitorar.`,
    )
  }

  if (parts.length === 0) {
    return 'Não foram identificados fatores prospectivos que exijam atenção especial além do monitoramento periódico padrão de operações de crédito rural.'
  }

  return parts.join(' ')
}

export function generateTechnicalOpinion(property: Property): string {
  const themes = getOverlapThemes(property)
  const paragraphs: string[] = []

  if (themes.length === 0) {
    paragraphs.push(
      'A análise não identificou sobreposições relevantes com embargos ambientais, Terras Indígenas, Unidades de Conservação ou desmatamento nas bases oficiais consultadas.',
    )
  } else {
    const main = themes[0]
    paragraphs.push(
      `A análise identificou sobreposição relevante com ${main.label}, atingindo ${main.pct.toFixed(1)}% da área do imóvel (${main.ha.toFixed(1)} ha).`,
    )
    if (themes.length > 1) {
      const others = themes.slice(1)
      const detail = others
        .map(t => `${t.label.toLowerCase()} em aproximadamente ${t.pct.toFixed(1)}% da área`)
        .join('; ')
      paragraphs.push(`Também foi identificado ${detail}.`)
    }
    const absent: string[] = []
    if (property.embargo_ha <= 0.01) absent.push('embargos ambientais')
    if (property.ti_ha <= 0.01) absent.push('Terras Indígenas')
    if (property.uc_ha <= 0.01) absent.push('Unidades de Conservação')
    if (property.desmatamento_ha <= 0.01) absent.push('desmatamento')
    if (absent.length > 0 && absent.length < 4) {
      paragraphs.push(`Não foram identificadas sobreposições com ${absent.join(' nem ')}.`)
    }
  }

  paragraphs.push(
    `Com base nos critérios adotados, o imóvel foi classificado como Risco de Restrição ${property.restriction_class}.`,
  )
  if (property.climate_class !== 'Baixo') {
    paragraphs.push(
      `O risco climático municipal é ${property.climate_class} (estresse hídrico ${property.climate_score.toFixed(0)} no índice AdaptaBrasil).`,
    )
  }
  paragraphs.push(property.recommendation.endsWith('.') ? property.recommendation : `${property.recommendation}.`)

  return paragraphs.join('\n\n')
}

export function getScoreExplanation(score: ScoreBreakdown): { criterion: string; points: number; pct: number; weight: number }[] {
  return [...score.components]
    .sort((a, b) => b.value - a.value)
    .map(c => ({
      criterion: c.criterion,
      points: c.value,
      pct: c.pct,
      weight: c.weight,
    }))
}

const RESTRICTION_CRITERIA_META: Record<string, { multiplier: number; saturationPct: number }> = {
  'Embargo IBAMA': { multiplier: 3.5, saturationPct: 10 },
  'Terra Indígena': { multiplier: 2.5, saturationPct: 10 },
  'Unidade de Conservação': { multiplier: 1.5, saturationPct: 10 },
  'Desmatamento': { multiplier: 1.0, saturationPct: 10 },
  'APP (FBDS)': { multiplier: 1.5, saturationPct: 10 },
}

export interface IndexCriterionDetail {
  criterion: string
  pct: number
  ha: number
  cappedPoints: number
  saturated: boolean
}

export interface IndexBreakdown {
  indexLabel: string
  indexSubtitle: string
  criteria: IndexCriterionDetail[]
  subtotal: number
  overrides: { label: string; applied: boolean }[]
  scoreAfterOverrides: number
  classification: { class: string; rule: string }
}

export function getRestrictionBreakdown(property: Property, score: ScoreBreakdown): IndexBreakdown {
  const pctMap: Record<string, number> = {
    'Embargo IBAMA': property.embargo_pct,
    'Terra Indígena': property.ti_pct,
    'Unidade de Conservação': property.uc_pct,
    'APP (FBDS)': property.app_pct,
    'Desmatamento': property.desmatamento_pct,
  }
  const haMap: Record<string, number> = {
    'Embargo IBAMA': property.embargo_ha,
    'Terra Indígena': property.ti_ha,
    'Unidade de Conservação': property.uc_ha,
    'APP (FBDS)': property.app_ha,
    'Desmatamento': property.desmatamento_ha,
  }

  const criteria = score.components.map(c => {
    const meta = RESTRICTION_CRITERIA_META[c.criterion] ?? { multiplier: 1, saturationPct: 100 }
    const pct = pctMap[c.criterion] ?? c.pct
    const ha = haMap[c.criterion] ?? 0
    const rawPoints = pct * meta.multiplier
    const cappedPoints = c.value
    const saturated = rawPoints >= c.weight - 0.001
    return { criterion: c.criterion, pct, ha, cappedPoints, saturated }
  })

  const subtotal = criteria.reduce((s, c) => s + c.cappedPoints, 0)
  const embargoOverride = property.embargo_ha > 0.01
  const tiOverride = property.ti_ha > 0.01
  let scoreAfterOverrides = subtotal
  if (embargoOverride) scoreAfterOverrides = Math.max(scoreAfterOverrides, 50)
  if (tiOverride) scoreAfterOverrides = Math.max(scoreAfterOverrides, 45)
  scoreAfterOverrides = Math.min(100, scoreAfterOverrides)

  let classRule = ''
  if (property.embargo_ha > 0.01) {
    classRule = 'Alto: embargo ativo (regra qualitativa).'
  } else if (score.total > 50) {
    classRule = `Alto: índice ${score.total.toFixed(1)} > 50.`
  } else if (score.total > 20) {
    classRule = `Médio: índice ${score.total.toFixed(1)} entre 20 e 50.`
  } else {
    classRule = `Baixo: índice ${score.total.toFixed(1)} ≤ 20.`
  }

  return {
    indexLabel: 'Restrição Socioambiental Atual',
    indexSubtitle: 'Cada camada separa sobreposição dentro do imóvel e sinais de entorno, sem transformar proximidade em impedimento automático.',
    criteria,
    subtotal,
    overrides: [
      { label: 'Piso por embargo ativo', applied: embargoOverride },
      { label: 'Piso por Terra Indígena', applied: tiOverride },
    ],
    scoreAfterOverrides,
    classification: { class: property.restriction_class, rule: classRule },
  }
}

export function getClimateBreakdown(property: Property, score: ScoreBreakdown): IndexBreakdown {
  const idx = property.stress_hidrico_idx ?? 0
  const criteria = score.components.map(c => ({
    criterion: c.criterion,
    pct: c.pct,
    ha: 0,
    cappedPoints: c.value,
    saturated: false,
  }))

  let classRule = ''
  if (property.climate_score >= 55) {
    classRule = `Alto: estresse hídrico municipal ${(idx * 100).toFixed(0)}% (≥ 55).`
  } else if (property.climate_score >= 35) {
    classRule = `Médio: estresse hídrico municipal ${(idx * 100).toFixed(0)}% (35–54).`
  } else {
    classRule = `Baixo: estresse hídrico municipal ${(idx * 100).toFixed(0)}% (< 35).`
  }

  return {
    indexLabel: 'Risco climático',
    indexSubtitle: 'Estresse hídrico municipal (AdaptaBrasil, índice prospectivo)',
    criteria,
    subtotal: property.climate_score,
    overrides: [],
    scoreAfterOverrides: property.climate_score,
    classification: { class: property.climate_class, rule: classRule },
  }
}

/** @deprecated use getRestrictionBreakdown */
export function getIescBreakdown(property: Property, score: ScoreBreakdown) {
  const breakdown = getRestrictionBreakdown(property, score)
  return {
    ...breakdown,
    currentRisk: property.current_risk,
    prospectiveRisk: property.prospective_risk,
  }
}

export interface MethodologySection {
  title: string
  paragraphs: string[]
  references?: string[]
}

export function getMethodologySections(): MethodologySection[] {
  return [
    {
      title: 'Modelo de triagem',
      paragraphs: [
        'Restrição socioambiental atual: sobreposições objetivas dentro do polígono CAR (embargo 35, TI 25, UC 15, APP 15, desmatamento 10 pts).',
        'Risco climático: exposição prospectiva (seca, água, hidrografia, sensibilidade agropecuária e fogo), interpretada junto com cobertura de dados e capacidade de pagamento.',
        'Pressão no entorno: proximidade e pressão em buffers; qualifica monitoramento, não configura restrição legal por si só.',
        'Classificação consolidada: síntese executiva proprietária da solução (60% restrição, 25% clima, 15% entorno), com pisos prudenciais para embargo/TI e confiança dos dados.',
        'Bioma IBGE não é usado como proxy de uso do solo no score. Detalhes em docs/matriz_triagem.md e no relatório PDF.',
      ],
    },
  ]
}

export interface EntornoMetricRow {
  label: string
  value: string
}

function formatDistOrNull(m: number | null | undefined): string {
  if (m == null || Number.isNaN(m)) return 'sem feição no contexto 10 km'
  if (m <= 0) return 'no limite do imóvel'
  if (m > 10000) return `${(m / 1000).toFixed(1)} km (informativo, sem pontuação)`
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`
  return `${Math.round(m)} m`
}

/** Métricas compactas de atenção no entorno — aba Restrições. */
export function getRestrictionEntornoMetrics(dist: DistanceContextMetrics): EntornoMetricRow[] {
  const rows: EntornoMetricRow[] = []
  const ti = dist.nearest_ti_m
  const uc = dist.nearest_uc_m
  const emb = dist.nearest_embargo_m
  const desm = dist.nearest_deforestation_m

  if (ti != null && ti <= 10000) rows.push({ label: 'Terra Indígena mais próxima', value: formatDistOrNull(ti) })
  if (uc != null && uc <= 10000) rows.push({ label: 'UC mais próxima', value: formatDistOrNull(uc) })
  if (emb != null && emb <= 10000) rows.push({ label: 'Embargo mais próximo', value: formatDistOrNull(emb) })
  if (desm != null && desm <= 10000) rows.push({ label: 'Desmatamento mais próximo', value: formatDistOrNull(desm) })

  const def5 = dist.deforestation_5km_surroundings_ha ?? dist.deforestation_5km_ha
  const def10 = dist.deforestation_10km_surroundings_ha ?? dist.deforestation_10km_ha
  if (def5 > 0.01) rows.push({ label: 'Desmatamento no entorno (5 km)', value: `${def5.toFixed(1)} ha` })
  if (def10 > 0.01 && def10 !== def5) rows.push({ label: 'Desmatamento no entorno (10 km)', value: `${def10.toFixed(1)} ha` })
  if (dist.embargo_5km_surroundings_ha != null && dist.embargo_5km_surroundings_ha > 0) {
    rows.push({ label: 'Embargo no entorno (5 km)', value: `${dist.embargo_5km_surroundings_ha.toFixed(1)} ha` })
  }
  if (dist.protected_area_within_1km) rows.push({ label: 'Área protegida', value: '≤ 1 km do imóvel' })
  else if (dist.protected_area_within_5km) rows.push({ label: 'Área protegida', value: '≤ 5 km do imóvel' })

  return rows
}

/** Contexto climático/hídrico — aba Risco Climático. */
export function getClimateContextMetrics(dist: DistanceContextMetrics): EntornoMetricRow[] {
  const rows: EntornoMetricRow[] = []
  if (dist.nearest_water_m != null) {
    rows.push({ label: 'Curso d\'água / massa (FBDS)', value: formatDistOrNull(dist.nearest_water_m) })
  }
  if (dist.drainage_density_5km != null) {
    rows.push({ label: 'Densidade de drenagem (5 km)', value: `${dist.drainage_density_5km.toFixed(2)} km/km²` })
  }
  if (dist.water_surface_buffer_ha != null && dist.water_surface_buffer_ha > 0) {
    rows.push({ label: 'Massa d\'água no buffer 5 km', value: `${dist.water_surface_buffer_ha.toFixed(2)} ha` })
  }
  if (dist.water_surface_change_pct != null) {
    rows.push({ label: 'Variação superfície hídrica', value: `${dist.water_surface_change_pct.toFixed(1)}%` })
  }
  if ((dist.fire_recent_5km_ha ?? 0) > 0) {
    rows.push({
      label: 'Queimada no entorno (2022–2024)',
      value: `${dist.fire_recent_5km_ha!.toFixed(1)} ha${dist.fire_years_active ? ` · ${dist.fire_years_active} ano(s)` : ''}`,
    })
  }
  if (dist.fire_recurrence_class) {
    rows.push({ label: 'Recorrência de fogo', value: dist.fire_recurrence_class.replace(/_/g, ' ') })
  }
  return rows
}

export function filterPositiveEvidence(evidence: Evidence[]): Evidence[] {
  return evidence.filter(e => e.area_ha > 0.01)
}

export function aggregateEvidenceForDisplay(property: Property): { id: string; theme: string; ha: number; pct: number }[] {
  return getOverlapThemes(property).map((t, i) => ({
    id: `EV-${String(i + 1).padStart(3, '0')}`,
    theme: t.label,
    ha: t.ha,
    pct: t.pct,
  }))
}

const CRITERION_THEMES: Record<string, string[]> = {
  'Embargo IBAMA': ['embargos'],
  'Terra Indígena': ['terras_indigenas'],
  'Unidade de Conservação': ['unidades_conservacao'],
  'APP (FBDS)': ['app_fbds'],
  'Desmatamento': ['desmatamento'],
}

export function getEvidenceForCriterion(
  evidence: Evidence[],
  carId: string,
  criterion: string,
): Evidence[] {
  const themes = CRITERION_THEMES[criterion] ?? []
  const seen = new Set<string>()
  return evidence.filter(e => {
    if (e.car_id !== carId || !themes.includes(e.theme) || e.area_ha <= 0.01) return false
    if (seen.has(e.evidence_id)) return false
    seen.add(e.evidence_id)
    return true
  })
}

function formatDistanceM(m: number | null | undefined): string {
  if (m == null || Number.isNaN(m)) return 'sem feição mapeada'
  if (m <= 0) return 'no limite do imóvel'
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`
  return `${Math.round(m)} m`
}

function entornoRelevant(distM: number | null | undefined, bufferHa = 0): boolean {
  if (bufferHa > 0.01) return true
  if (distM == null || Number.isNaN(distM)) return false
  return distM <= 10000
}

/** Detalhe de proximidade/pressão no entorno por camada. */
export function restrictionEntornoNote(
  criterion: string,
  dist: DistanceContextMetrics,
): string | null {
  switch (criterion) {
    case 'Embargo IBAMA': {
      const surround = dist.embargo_5km_surroundings_ha ?? 0
      if (!entornoRelevant(dist.nearest_embargo_m, surround || dist.embargo_5km_ha)) return null
      const parts = [`mais próximo a ${formatDistanceM(dist.nearest_embargo_m)}`]
      if (surround > 0) parts.push(`${surround.toFixed(1)} ha no anel 5 km`)
      else if (dist.embargo_5km_ha > 0) parts.push(`${dist.embargo_5km_ha.toFixed(1)} ha no buffer 5 km`)
      return parts.join(' · ')
    }
    case 'Terra Indígena': {
      if (!entornoRelevant(dist.nearest_ti_m) && !dist.protected_area_within_5km) return null
      const parts = [`TI a ${formatDistanceM(dist.nearest_ti_m)}`]
      if (dist.protected_area_within_1km) parts.push('área sensível ≤ 1 km')
      else if (dist.protected_area_within_5km) parts.push('área sensível ≤ 5 km')
      return parts.join(' · ')
    }
    case 'Unidade de Conservação': {
      if (!entornoRelevant(dist.nearest_uc_m)) return null
      return `UC a ${formatDistanceM(dist.nearest_uc_m)}`
    }
    case 'APP (FBDS)':
      return null
    case 'Desmatamento': {
      const surround = dist.deforestation_5km_surroundings_ha ?? dist.deforestation_5km_ha
      if (!entornoRelevant(dist.nearest_deforestation_m, surround)) return null
      const parts = [`mais próximo a ${formatDistanceM(dist.nearest_deforestation_m)}`]
      if (surround > 0) {
        parts.push(`${surround.toFixed(1)} ha no anel 5 km`)
        if (dist.deforestation_alerts_5km > 0) parts.push(`${dist.deforestation_alerts_5km} alertas`)
      }
      return parts.join(' · ')
    }
    default:
      return null
  }
}

export interface CriterionEntornoBlock {
  points: string | null
  detail: string | null
}

function tiEntornoActive(dist: DistanceContextMetrics): boolean {
  return entornoRelevant(dist.nearest_ti_m) || dist.protected_area_within_5km
}

function ucEntornoActive(dist: DistanceContextMetrics): boolean {
  return entornoRelevant(dist.nearest_uc_m) || dist.protected_area_within_5km
}

/** Bloco unificado de entorno por critério de restrição (pontos IPT + detalhe). */
export function getRestrictionEntornoBlock(
  criterion: string,
  dist: DistanceContextMetrics | undefined,
  ipt: TerritorialPressureIndex | undefined,
): CriterionEntornoBlock | null {
  if (!dist) return null
  const detail = restrictionEntornoNote(criterion, dist)
  if (!detail && !ipt) return null

  let pts: number | null = null
  if (ipt) {
    switch (criterion) {
      case 'Embargo IBAMA':
        pts = ipt.embargo_context_component
        break
      case 'Desmatamento':
        pts = ipt.deforestation_pressure_component
        break
      case 'Terra Indígena': {
        if (!tiEntornoActive(dist)) break
        const prot = ipt.protected_area_proximity_component
        pts = ucEntornoActive(dist) ? prot / 2 : prot
        break
      }
      case 'Unidade de Conservação': {
        if (!ucEntornoActive(dist)) break
        const prot = ipt.protected_area_proximity_component
        pts = tiEntornoActive(dist) ? prot / 2 : prot
        break
      }
      default:
        break
    }
  }

  if ((pts == null || pts <= 0.01) && !detail) return null
  return {
    points: pts != null && pts > 0.01 ? `+${pts.toFixed(1)} pts` : null,
    detail,
  }
}

/** Bloco de contexto climático no entorno (qualitativo ou IPT fogo). */
export function getClimateEntornoBlock(
  componentName: string,
  dist: DistanceContextMetrics | undefined,
  ipt?: TerritorialPressureIndex,
): CriterionEntornoBlock | null {
  if (!dist) return null
  const detail = climateEntornoNote(componentName, dist)
  let pts: number | null = null
  if (componentName === 'Fogo / queimada' && ipt && (dist.fire_recent_5km_ha ?? 0) > 0) {
    pts = ipt.fire_context_component
  }
  if ((pts == null || pts <= 0.01) && !detail) return null
  return {
    points: pts != null && pts > 0.01 ? `+${pts.toFixed(1)} pts entorno` : null,
    detail,
  }
}

/** Sinal de entorno climático no buffer / proximidade. */
export function climateEntornoNote(
  componentName: string,
  dist: DistanceContextMetrics,
): string | null {
  switch (componentName) {
    case 'Superfície hídrica': {
      const buf = dist.water_surface_buffer_ha ?? 0
      if (buf <= 0.01 && (dist.nearest_water_m == null || dist.nearest_water_m > 10000)) return null
      const parts: string[] = []
      if (buf > 0) parts.push(`${buf.toFixed(2)} ha de massa d'água no buffer 5 km`)
      if (dist.nearest_water_m != null && dist.nearest_water_m <= 10000) {
        parts.push(`curso d'água a ${formatDistanceM(dist.nearest_water_m)}`)
      }
      return parts.length ? parts.join(' · ') : null
    }
    case 'Hidrografia / drenagem': {
      if (
        (dist.nearest_water_m == null || dist.nearest_water_m > 10000) &&
        (dist.drainage_density_5km == null || dist.drainage_density_5km < 0.01)
      ) return null
      const parts: string[] = []
      if (dist.nearest_water_m != null && dist.nearest_water_m <= 10000) {
        parts.push(`rio/massa a ${formatDistanceM(dist.nearest_water_m)}`)
      }
      if (dist.drainage_density_5km != null && dist.drainage_density_5km > 0) {
        parts.push(`drenagem ${dist.drainage_density_5km.toFixed(2)} km/km² no buffer 5 km`)
      }
      return parts.length ? parts.join(' · ') : null
    }
    case 'Fogo / queimada': {
      const buf = dist.fire_recent_5km_ha ?? 0
      if (buf <= 0.01) return null
      const parts = [`${buf.toFixed(1)} ha queimados no buffer 5 km`]
      if (dist.fire_years_active) parts.push(`${dist.fire_years_active} ano(s) com fogo`)
      if (dist.fire_recurrence_class) parts.push(dist.fire_recurrence_class.replace(/_/g, ' '))
      return parts.join(' · ')
    }
    case 'Seca / estresse hídrico':
    case 'Sensibilidade agropecuária':
      return null
    default:
      return null
  }
}

const RESTRICTION_LAYER_CRITERION: Record<string, string> = {
  embargos: 'Embargo IBAMA',
  ti: 'Terra Indígena',
  uc: 'Unidade de Conservação',
  app: 'APP (FBDS)',
  desmatamento: 'Desmatamento',
}

/** Métricas de entorno exibidas na toolbar do mapa por buffer. */
export function getRestrictionBufferInfo(
  layerKey: string,
  dist: DistanceContextMetrics,
  bufferM: 5000 | 10000,
): string | null {
  const criterion = RESTRICTION_LAYER_CRITERION[layerKey]
  if (!criterion || criterion === 'APP (FBDS)') return null

  const within = (m: number | null | undefined) =>
    m != null && !Number.isNaN(m) && m <= bufferM

  switch (criterion) {
    case 'Embargo IBAMA': {
      const surround = dist.embargo_5km_surroundings_ha ?? 0
      const ha = bufferM === 5000 ? (surround > 0 ? surround : dist.embargo_5km_ha) : dist.embargo_5km_ha
      if (!within(dist.nearest_embargo_m) && ha <= 0) {
        return `Sem embargo no buffer ${bufferM / 1000} km`
      }
      const parts = [`mais próximo a ${formatDistanceM(dist.nearest_embargo_m)}`]
      if (bufferM === 5000 && ha > 0) {
        parts.push(`${ha.toFixed(1)} ha no entorno`)
      }
      return parts.join(' · ')
    }
    case 'Terra Indígena': {
      if (!within(dist.nearest_ti_m) && !(bufferM >= 5000 && dist.protected_area_within_5km)) {
        return `Sem TI no buffer ${bufferM / 1000} km`
      }
      const parts = [`TI a ${formatDistanceM(dist.nearest_ti_m)}`]
      if (dist.protected_area_within_1km) parts.push('área sensível ≤ 1 km')
      else if (bufferM >= 5000 && dist.protected_area_within_5km) {
        parts.push('área sensível ≤ 5 km')
      }
      return parts.join(' · ')
    }
    case 'Unidade de Conservação': {
      if (!within(dist.nearest_uc_m)) return `Sem UC no buffer ${bufferM / 1000} km`
      return `UC a ${formatDistanceM(dist.nearest_uc_m)}`
    }
    case 'Desmatamento': {
      const surround5 = dist.deforestation_5km_surroundings_ha ?? dist.deforestation_5km_ha
      const surround10 = dist.deforestation_10km_surroundings_ha ?? dist.deforestation_10km_ha
      const ha = bufferM === 5000 ? surround5 : surround10
      if (!within(dist.nearest_deforestation_m) && ha <= 0) {
        return `Sem desmatamento no buffer ${bufferM / 1000} km`
      }
      const parts = [`mais próximo a ${formatDistanceM(dist.nearest_deforestation_m)}`]
      if (ha > 0) {
        parts.push(`${ha.toFixed(1)} ha no entorno`)
        if (bufferM === 5000 && dist.deforestation_alerts_5km > 0) {
          parts.push(`${dist.deforestation_alerts_5km} alerta(s)`)
        }
      }
      return parts.join(' · ')
    }
    default:
      return null
  }
}

/** Métricas de buffer para camadas climáticas (hidrografia). */
export function getClimateBufferInfo(
  layerKey: string,
  dist: DistanceContextMetrics,
  bufferM: 5000 | 10000,
): string | null {
  const within = (m: number | null | undefined) =>
    m != null && !Number.isNaN(m) && m <= bufferM

  switch (layerKey) {
    case 'water_surface': {
      const bufHa = dist.water_surface_buffer_ha ?? 0
      if (!within(dist.nearest_water_m) && bufHa <= 0) {
        return `Sem massa d'água no buffer ${bufferM / 1000} km`
      }
      const parts: string[] = []
      if (within(dist.nearest_water_m)) parts.push(`água a ${formatDistanceM(dist.nearest_water_m)}`)
      if (bufferM === 5000 && bufHa > 0) parts.push(`${bufHa.toFixed(2)} ha no buffer`)
      return parts.length ? parts.join(' · ') : `Contexto hídrico no buffer ${bufferM / 1000} km`
    }
    case 'rivers': {
      const density = dist.drainage_density_5km
      if (!within(dist.nearest_water_m) && (density == null || density < 0.01)) {
        return `Sem rios no buffer ${bufferM / 1000} km`
      }
      const parts: string[] = []
      if (within(dist.nearest_water_m)) parts.push(`curso a ${formatDistanceM(dist.nearest_water_m)}`)
      if (bufferM === 5000 && density != null && density > 0) {
        parts.push(`drenagem ${density.toFixed(2)} km/km²`)
      }
      return parts.join(' · ')
    }
    default:
      return null
  }
}

export interface IcrcComponentDetail {
  name: string
  points: number
  weight: number
  source: string
  layer: string
  metric: string
  confidence: string
}

function buildFireMetric(dist?: DistanceContextMetrics): string {
  const prop = dist?.fire_recent_ha_property
  const buf = dist?.fire_recent_5km_ha
  const years = dist?.fire_years_active
  const rec = dist?.fire_recurrence_class
  if ((prop ?? 0) === 0 && (buf ?? 0) === 0) {
    return 'Sem cicatriz de queimada MapBiomas no imóvel nem no buffer 5 km (2022–2024)'
  }
  return [
    `${(prop ?? 0).toFixed(2)} ha queimados no imóvel`,
    `${(buf ?? 0).toFixed(1)} ha no buffer 5 km`,
    years != null ? `${years} ano(s) com fogo` : null,
    rec ? `recorrência: ${rec}` : null,
  ].filter(Boolean).join(' · ')
}

export function getIcrcComponentDetails(
  property: Property,
  icrc: ClimateCreditRisk,
  dist?: DistanceContextMetrics,
): IcrcComponentDetail[] {
  const stress = property.stress_hidrico_idx
  const stressPct = stress != null ? `${(stress * 100).toFixed(0)}%` : 'n/d'

  const waterDist = dist?.nearest_water_m
  const waterDistLabel =
    waterDist == null ? 'sem curso d\'água mapeado no entorno' : waterDist >= 1000 ? `${(waterDist / 1000).toFixed(1)} km` : `${Math.round(waterDist)} m`

  const drainage = dist?.drainage_density_5km
  const drainageLabel = drainage != null ? `${drainage.toFixed(2)} km/km² (buffer 5 km)` : 'n/d'

  const waterHa = dist?.water_surface_recent_ha
  const waterBufHa = dist?.water_surface_buffer_ha
  const waterMetric =
    waterHa != null
      ? `${waterHa.toFixed(2)} ha de massa d'água no imóvel · ${(waterBufHa ?? 0).toFixed(2)} ha no buffer 5 km`
      : 'Massas d\'água FBDS — interseção calculada no pipeline'

  return [
    {
      name: 'Seca / estresse hídrico',
      points: icrc.drought_component,
      weight: 35,
      source: 'AdaptaBrasil MCTI',
      layer: 'adaptabrasil_stress_hidrico.gpkg',
      metric: `Índice municipal ${stressPct} · município ${property.uf}`,
      confidence: 'Média (escala municipal)',
    },
    {
      name: 'Superfície hídrica',
      points: icrc.water_surface_component,
      weight: 25,
      source: 'FBDS',
      layer: 'fbds_massas_dagua.gpkg',
      metric: waterMetric,
      confidence: 'Alta',
    },
    {
      name: 'Hidrografia / drenagem',
      points: icrc.hydrology_component,
      weight: 15,
      source: 'FBDS',
      layer: 'fbds_rios_simples.gpkg + fbds_massas_dagua.gpkg',
      metric: `Distância hidro FBDS: ${waterDistLabel} · Densidade rios simples: ${drainageLabel}`,
      confidence: 'Alta',
    },
    {
      name: 'Sensibilidade agropecuária',
      points: icrc.agro_sensitivity_component,
      weight: 15,
      source: 'AdaptaBrasil MCTI',
      layer: 'adaptabrasil_seca_agro.gpkg',
      metric: ['MT', 'AM', 'PA'].includes(property.uf)
        ? `Risco agroclimático municipal (índice AdaptaBrasil) · região ${property.uf} sensível`
        : 'Risco agroclimático municipal (índice AdaptaBrasil)',
      confidence: 'Média (escala municipal)',
    },
    {
      name: 'Fogo / queimada',
      points: icrc.fire_component,
      weight: 10,
      source: 'MapBiomas Fogo Coleção 5',
      layer: 'mapbiomas_fire_scars.gpkg',
      metric: buildFireMetric(dist),
      confidence: 'Alta (30 m · 2022–2024)',
    },
  ]
}
