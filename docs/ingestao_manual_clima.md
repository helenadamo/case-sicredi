# Ingestão manual — AdaptaBrasil e WRI Aqueduct

Quando a API do AdaptaBrasil ou o download do WRI Aqueduct não estiverem automatizáveis, use os arquivos abaixo.

## AdaptaBrasil (`input/adaptabrasil_manual.csv`)

Baixe indicadores em [AdaptaBrasil](https://adaptabrasil.mcti.gov.br/) para os municípios dos CARs:

| CAR | Município | Código IBGE |
|-----|-----------|-------------|
| CAR_01 | São Pedro do Sul/RS | 4319406 |
| CAR_02 | Guarapuava/PR | 4109401 |
| CAR_03 | Colniza/MT | 5103254 |
| CAR_04 | Aripuanã/MT | 5101407 |

**Schema:**

```csv
municipio_codigo_ibge,municipio_nome,uf,drought_risk_score,agro_climate_risk_score,water_security_risk_score,source_year,source_url,confidence
4319406,São Pedro do Sul,RS,37,41,35,2020,https://adaptabrasil.mcti.gov.br/,Média
```

Scores em escala 0–100 (percentual do índice municipal).

## WRI Aqueduct (`input/aqueduct_manual.csv`)

Fonte complementar: [WRI Aqueduct](https://www.wri.org/aqueduct).

```csv
car_id,municipio_codigo_ibge,aqueduct_water_stress,aqueduct_drought_risk,aqueduct_seasonal_variability,aqueduct_flood_risk,source_year,source_url,aqueduct_confidence
CAR_01,4319406,2.1,1.8,1.5,0.9,2019,https://www.wri.org/aqueduct,Média
```

Valores típicos Aqueduct: 0–5 (quanto maior, maior o risco).

## Execução após ingestão

```bash
python scripts/run_pipeline.py --profile advanced
```
