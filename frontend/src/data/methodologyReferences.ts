export interface MethodologyRef {
  id: string
  label: string
  detail: string
  url?: string
}

export interface WeightRationale {
  label: string
  pts: number
  color?: string
  why: string
  refIds: string[]
}

export const METHODOLOGY_REFS: MethodologyRef[] = [
  {
    id: 'cmn4943',
    label: 'Res. CMN 4.943/2021',
    detail: 'Integra risco social, ambiental e climático à estrutura de gerenciamento de riscos das instituições financeiras.',
    url: 'https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=4943',
  },
  {
    id: 'cmn4945',
    label: 'Res. CMN 4.945/2021 (PRSAC)',
    detail: 'Dispõe sobre a Política de Responsabilidade Social, Ambiental e Climática e suas ações de efetividade.',
    url: 'https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=4945',
  },
  {
    id: 'cmn5193',
    label: 'Res. CMN 5.193/2024',
    detail: 'Conformidade socioambiental no MCR, reforça diligência em embargo, áreas protegidas e desmatamento ilegal.',
    url: 'https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=5193',
  },
  {
    id: 'ifrs-s2',
    label: 'IFRS S2, Riscos climáticos',
    detail: 'Separa exposição física (seca, água, fogo) da conformidade legal; base da leitura climática prospectiva.',
    url: 'https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/',
  },
  {
    id: 'bcbs-climate',
    label: 'BCBS, Princípios de risco climático (2022)',
    detail: 'Gestão de risco climático no sistema financeiro: materialidade, horizonte prospectivo e buffers territoriais.',
    url: 'https://www.bis.org/bcbs/publ/d567.htm',
  },
  {
    id: 'codigo-florestal',
    label: 'Lei 12.651/2012 (Código Florestal)',
    detail: 'APP como restrição de uso permanente, peso menor que embargo/TI, mas material para conformidade rural.',
    url: 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm',
  },
  {
    id: 'snuc',
    label: 'Lei 9.985/2000 (SNUC)',
    detail: 'Unidades de Conservação, restrições diferenciadas por categoria; sobreposição sinaliza risco de conformidade.',
    url: 'https://www.planalto.gov.br/ccivil_03/LEIS/L9985.htm',
  },
  {
    id: 'ibama-embargo',
    label: 'Embargos IBAMA (CTF)',
    detail: 'Sanção administrativa com impedimento de atividade, maior peso por materialidade jurídica imediata.',
    url: 'https://servicos.ibama.gov.br/ctf/publico/areasembargadas/',
  },
  {
    id: 'mapbiomas-alerta',
    label: 'MapBiomas Alerta',
    detail: 'Evidência temporal de desmatamento, peso moderado por ser sinal de monitoramento, não sanção automática.',
    url: 'https://plataforma.alerta.mapbiomas.org/',
  },
  {
    id: 'adaptabrasil',
    label: 'AdaptaBrasil, Seca e agro',
    detail: 'Índices de estresse hídrico e sensibilidade agropecuária por município para a dimensão climática.',
    url: 'https://adaptabrasil.mcti.gov.br/',
  },
  {
    id: 'aqueduct',
    label: 'WRI Aqueduct',
    detail: 'Referência internacional para estresse hídrico regional, complementa AdaptaBrasil na leitura climática.',
    url: 'https://www.wri.org/aqueduct',
  },
  {
    id: 'fbds',
    label: 'FBDS, Hidrografia municipal',
    detail: 'Massas d\'água e rios 1:25.000, mesma base da APP; suporte a superfície hídrica e drenagem.',
    url: 'https://geoftp.ibge.gov.br/',
  },
  {
    id: 'sparovek-car',
    label: 'Sparovek et al., Limites do CAR',
    detail: 'CAR como unidade declaratória de triagem, não prova fundiária, justifica separar imóvel × entorno.',
    url: 'https://doi.org/10.1016/j.landusepol.2019.104051',
  },
  {
    id: 'barber-frontier',
    label: 'Barber et al. (2014), Fronteira de desmatamento',
    detail: 'Pressão no entorno prediz desmatamento futuro e fundamenta a leitura de buffers e proximidade.',
    url: 'https://doi.org/10.1038/srep04329',
  },
]

export const IRSA_RATIONALE: WeightRationale[] = [
  {
    label: 'Embargo',
    pts: 35,
    color: '#C62828',
    why: 'Sanção administrativa com impedimento de uso, maior materialidade jurídica e de crédito (CMN 5.193; IBAMA).',
    refIds: ['ibama-embargo', 'cmn5193'],
  },
  {
    label: 'TI',
    pts: 25,
    why: 'Sobreposição com território indígena homologado, risco constitucional e de conflito fundiário elevado.',
    refIds: ['cmn4943', 'cmn4945', 'cmn5193'],
  },
  {
    label: 'UC',
    pts: 15,
    why: 'Unidades de Conservação (SNUC), restrição legal variável por categoria, abaixo de embargo/TI.',
    refIds: ['snuc', 'cmn5193'],
  },
  {
    label: 'APP',
    pts: 15,
    why: 'Área de Preservação Permanente (Código Florestal), obrigação permanente, satura em ~10% do imóvel.',
    refIds: ['codigo-florestal', 'fbds'],
  },
  {
    label: 'Desmat.',
    pts: 10,
    why: 'Evidência temporal de supressão, sinal de monitoramento e conformidade, não equivalência a embargo.',
    refIds: ['mapbiomas-alerta', 'cmn5193'],
  },
]

export const ICRC_RATIONALE: WeightRationale[] = [
  {
    label: 'Seca',
    pts: 35,
    color: '#1E88A8',
    why: 'Estresse hídrico municipal (AdaptaBrasil), principal driver de produtividade e fluxo de caixa no agro.',
    refIds: ['adaptabrasil', 'ifrs-s2', 'bcbs-climate'],
  },
  {
    label: 'Água',
    pts: 25,
    why: 'Disponibilidade de superfície hídrica no imóvel e buffer, risco físico à irrigação e pecuária.',
    refIds: ['fbds', 'aqueduct', 'ifrs-s2'],
  },
  {
    label: 'Hidro',
    pts: 15,
    why: 'Proximidade e densidade de drenagem (FBDS), acesso a recurso hídrico e vulnerabilidade local.',
    refIds: ['fbds', 'bcbs-climate'],
  },
  {
    label: 'Agro',
    pts: 15,
    why: 'Sensibilidade agropecuária regional, exposição do portfólio produtivo típico do bioma/município.',
    refIds: ['adaptabrasil', 'ifrs-s2'],
  },
  {
    label: 'Fogo',
    pts: 10,
    why: 'Cicatrizes de queimada recentes, evento extremo com impacto pontual (MapBiomas Fogo).',
    refIds: ['mapbiomas-alerta', 'ifrs-s2'],
  },
]

export const IPT_RATIONALE: WeightRationale[] = [
  {
    label: 'Prox. TI/UC',
    pts: 30,
    color: '#E6A817',
    why: 'Proximidade a áreas protegidas, régua 500 m / 2 km / 10 km; monitoramento, não restrição automática.',
    refIds: ['barber-frontier', 'snuc', 'sparovek-car'],
  },
  {
    label: 'Desmat. entorno',
    pts: 35,
    why: 'Desmatamento no anel externo do buffer, maior peso por evidência de pressão na fronteira (Barber et al.).',
    refIds: ['barber-frontier', 'mapbiomas-alerta'],
  },
  {
    label: 'Embargo entorno',
    pts: 25,
    why: 'Embargos no entorno indicam contexto de ilegalidade territorial adjacente.',
    refIds: ['ibama-embargo', 'cmn5193'],
  },
  {
    label: 'Fogo entorno',
    pts: 10,
    why: 'Queimadas no buffer, evento recorrente de menor peso estrutural que desmatamento contínuo.',
    refIds: ['mapbiomas-alerta', 'ifrs-s2'],
  },
]

export const IRTC_BLEND_RATIONALE = [
  {
    key: 'Socioambiental',
    pct: 60,
    color: '#C62828',
    why: 'Restrição legal atual no CAR, eixo principal da conformidade PRSAC/MCR (materialidade imediata).',
    refIds: ['cmn4943', 'cmn4945', 'cmn5193'],
  },
  {
    key: 'Climático',
    pct: 25,
    why: 'Risco climático prospectivo, capacidade de pagamento no horizonte da operação (IFRS S2 / BCBS).',
    refIds: ['ifrs-s2', 'bcbs-climate', 'adaptabrasil'],
  },
  {
    key: 'Entorno',
    pct: 15,
    why: 'Atenção de entorno, qualifica monitoramento sem dupla contagem; peso menor por natureza prospectiva.',
    refIds: ['barber-frontier', 'sparovek-car', 'cmn4943', 'cmn4945'],
  },
]

export function refsById(ids: string[]): MethodologyRef[] {
  const map = Object.fromEntries(METHODOLOGY_REFS.map(r => [r.id, r]))
  return ids.map(id => map[id]).filter(Boolean)
}
