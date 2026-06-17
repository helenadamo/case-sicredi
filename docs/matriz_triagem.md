# Matriz de triagem

Este documento consolida as camadas complementares e a matriz de triagem usada no case Sicredi. As siglas internas existem apenas para manter arquivos, colunas e funcoes estaveis; na apresentacao executiva, use os nomes de negocio abaixo.

| Sigla interna | Nome de apresentacao | Papel |
|---------------|----------------------|-------|
| IRSA | Restricao socioambiental atual | Sobreposicoes objetivas dentro do CAR |
| ICRC | Risco climatico | Exposicao prospectiva ligada a produtividade e capacidade de pagamento |
| IPT | Pressao no entorno | Sinais territoriais para monitoramento recorrente |
| IRTC | Classificacao consolidada de triagem | Sintese proprietaria para priorizacao e diligencia |

Esses indicadores nao sao rating regulatorio, nao automatizam aprovacao/reprovacao e nao substituem validacao humana.

## Dimensoes

### Restricao socioambiental atual

Mede sobreposicoes dentro do imovel: embargo, Terra Indigena, Unidade de Conservacao, APP FBDS e desmatamento. E a dimensao mais objetiva da triagem, pois se baseia em ocorrencias espaciais no perimetro declarado do CAR.

### Risco climatico

Dimensao prospectiva ligada a produtividade, fluxo de caixa rural e capacidade futura de pagamento. Componentes:

| Componente | Peso | Fonte principal |
|------------|------|-----------------|
| Seca / estresse hidrico | 35 | AdaptaBrasil |
| Superficie hidrica | 25 | FBDS massas d'agua |
| Hidrografia / drenagem | 15 | FBDS rios simples + massas d'agua |
| Sensibilidade agropecuaria | 15 | AdaptaBrasil / contexto municipal |
| Fogo / queimada | 10 | MapBiomas Fogo Colecao 5 |

Quando algum componente nao tem dado, o pipeline registra cobertura (`data_coverage_pct`). Redistribuicao de pesos so ocorre quando a cobertura minima e suficiente.

### Pressao no entorno

Mede sinais fora do imovel, em buffers de monitoramento. Proximidade nao equivale a impedimento legal; o objetivo e orientar acompanhamento recorrente.

| Componente | Peso |
|------------|------|
| Proximidade TI/UC | 30 |
| Desmatamento no entorno | 35 |
| Embargos no entorno | 25 |
| Fogo / queimada no entorno | 10 |

Metricas geradas: buffers de 500 m, 1 km, 5 km e 10 km; distancias minimas para TI, UC, embargo, desmatamento e agua; hectares de eventos no entorno.

### Classificacao consolidada

```text
Score consolidado = 0,60 x restricao no imovel
                   + 0,25 x risco climatico
                   + 0,15 x pressao no entorno
```

Regras prudenciais:

- Embargo ativo no imovel: score consolidado minimo 65.
- Sobreposicao com Terra Indigena: score consolidado minimo 55.
- Baixa cobertura climatica ou baixa confianca: recomendacao de validacao complementar.

Classes:

- Baixo: <= 40
- Medio: > 40 e <= 70
- Alto: > 70, ou elevacao por regra prudencial/dimensoes criticas

## Scripts relacionados

Use `python scripts/run_pipeline.py --profile full` para a execucao completa.

| Etapa | Funcao |
|-------|--------|
| `02b_download_fbds_app.py` | APP FBDS usada na restricao socioambiental |
| `02d_download_fbds_hydro.py` | Massas d'agua e rios simples FBDS |
| `02e_download_mapbiomas_fire.py` | Cicatrizes de queimada MapBiomas Fogo |
| `09_download_advanced_layers.py` | Camadas complementares de agua, clima e contexto |
| `10_distance_and_context_metrics.py` | Buffers, distancias e pressao territorial |
| `11_climate_credit_risk.py` | Risco climatico |
| `12_territorial_pressure_index.py` | Pressao no entorno |
| `13_integrated_credit_risk.py` | Classificacao consolidada |
| `14_export_advanced_web_data.py` | JSONs complementares para o frontend |

## Saidas

- `output/tables/climate_credit_risk.csv`
- `output/tables/territorial_pressure_index.csv`
- `output/tables/integrated_credit_risk.csv`
- `frontend/src/data/climate_credit_risk.json`
- `frontend/src/data/territorial_pressure_index.json`
- `frontend/src/data/integrated_credit_risk.json`
