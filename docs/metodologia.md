# Metodologia

## Unidade de análise

O CAR (Cadastro Ambiental Rural) é utilizado como unidade de análise ambiental declaratória, conforme solicitado no case, mas **não** foi interpretado como confirmação definitiva de domínio fundiária. Essa distinção é relevante porque a literatura sobre malha fundiária brasileira aponta inconsistências e limites na leitura do CAR como representação cadastral plena (Sparovek et al.; Atlas Imaflora).

## Fluxo de processamento

1. Obtenção de geometrias CAR (SICAR WFS → download estadual → alternativas documentadas)
2. Download de bases oficiais (IBAMA, FUNAI, ICMBio, MapBiomas/PRODES)
3. Limpeza e validação geométrica
4. Reprojeção e cálculo de área
5. Interseções espaciais com registro auditável
6. Cálculo da restrição atual, risco climático prospectivo e classificação consolidada
7. Geração de mapas, relatório e exportação WebGIS

## Nomenclatura dos indicadores

As siglas `IRSA`, `ICRC`, `IPT` e `IRTC` são nomes técnicos internos para manter o pipeline reproduzível. Elas não são nomenclatura regulatória oficial, rating de crédito, regra de aprovação automática nem substituto de validação humana.

Na comunicação executiva, os mesmos blocos devem ser apresentados como:

| Sigla interna | Nome de apresentação | Uso |
|---------------|----------------------|-----|
| IRSA | Restrição socioambiental atual | Sobreposições objetivas dentro do CAR |
| ICRC | Risco climático | Exposição prospectiva ligada à capacidade de pagamento |
| IPT | Pressão no entorno | Sinais de monitoramento em buffers |
| IRTC | Classificação consolidada de triagem | Síntese proprietária para priorização |

## Sistema de coordenadas

- **Visualização:** EPSG:4326 (WGS84)
- **Cálculo de área:** EPSG:5880 (SIRGAS 2000 / Brazil Polyconic)

Regra: área **nunca** calculada em coordenadas geográficas (EPSG:4326).

## Restrição socioambiental atual

Sobreposições objetivas **dentro do polígono CAR** (não inclui proximidade no entorno).

| Critério | Peso máximo |
|----------|-------------|
| Embargo IBAMA | 35 pontos |
| Terra Indígena | 25 pontos |
| Unidade de Conservação | 15 pontos |
| APP (FBDS) | 15 pontos |
| Desmatamento no imóvel | 10 pontos |

Classes: 0–20 Baixo | >20–50 Médio | >50 Alto

Override qualitativo: embargo ativo ou sobreposição TI podem elevar risco independente do percentual.

**Proximidade no entorno** (buffers, distâncias) é tratada separadamente como *atenção de monitoramento*, não como restrição automática.

Configuração central: `scripts/score_config.py`

## Risco atual vs prospectivo

- **Risco atual:** evidências objetivas presentes (embargo, TI, UC, desmatamento)
- **Risco prospectivo:** tendências futuras (clima, entorno, baixa confiança, região sensível)
- **Confiança:** qualidade da base e clareza do cruzamento (Alta/Média/Baixa)

## Trilha de auditoria

Cada evidência possui ID único (ex: `EV-CAR01-IBAMA-001`) com fonte, data, operação geométrica, área, percentual, confiança e interpretação.

## Referências regulatórias e bibliográficas

- Resolução CMN 4.943/2021 e 4.945/2021 (PRSAC) — gestão integrada de riscos socioambientais e climáticos
- Resolução CMN 5.193/2024 — conformidade socioambiental no MCR
- IFRS S2 — riscos climáticos prospectivos
- BCBS (2022) — princípios de gestão de risco climático no sistema financeiro
- Lei 12.651/2012 — APP (peso 15 na restrição)
- Lei 9.985/2000 — SNUC / UC (peso 15 na restrição)
- Embargos IBAMA — materialidade jurídica imediata (peso 35 na restrição)
- MapBiomas Alerta — evidência temporal de desmatamento (peso 10 na restrição; também usado no entorno)
- AdaptaBrasil / WRI Aqueduct — seca e estresse hídrico
- FBDS — hidrografia municipal
- Sparovek et al. (2019) — limites do CAR como unidade de triagem
- Barber et al. (2014) — pressão no entorno e fronteira de desmatamento

**Calibração numérica:** `scripts/score_config.py` — pesos calibrados por hierarquia de materialidade regulatória, não por voto majoritário.
