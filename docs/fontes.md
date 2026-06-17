# Fontes de Dados — Case Sicredi

| Tema | Fonte Oficial | URL | Data | Formato | Confiança |
|------|---------------|-----|------|---------|-----------|
| Imóveis rurais (CAR) | SICAR / CAR | https://consultapublica.car.gov.br/ | Registro em source_registry.csv | GPKG/GeoJSON | Alta/Média |
| Embargos ambientais | IBAMA | https://servicos.ibama.gov.br/ctf/publico/areasembargadas/ | Registro em source_registry.csv | SHP/GPKG | Alta |
| Terras Indígenas | FUNAI | https://geoserver.funai.gov.br/geoserver/Funai/ows | Registro em source_registry.csv | WFS/GPKG | Alta |
| Unidades de Conservação | ICMBio / CNUC / MMA | https://dadosabertos.mma.gov.br/ | Registro em source_registry.csv | SHP/WFS | Alta |
| Desmatamento | MapBiomas Alerta / PRODES | https://plataforma.alerta.mapbiomas.org/ / TerraBrasilis | Registro em source_registry.csv | GeoJSON/WFS | Média/Alta |
| Stress hídrico (clima) | ANA / CEMADEN / WRI Aqueduct | Referência metodológica | Registro em source_registry.csv | Metadados | Média |

Registro detalhado gerado pelo pipeline: `processed/audit/source_registry.csv`.

## Notas

- Tentativas de download e alternativas estão documentadas nos logs de cada script.
- Quando fonte oficial estiver indisponível, confiança da evidência é rebaixada.
- CAR tratado como base declaratória ambiental (Sparovek et al.; Imaflora).
