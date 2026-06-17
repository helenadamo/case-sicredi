# Arquitetura

## Visão geral

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Fontes     │────▶│  Pipeline    │────▶│  Outputs    │
│  Oficiais   │     │  Python      │     │  CSV/PDF    │
└─────────────┘     └──────┬───────┘     └──────┬──────┘
                           │                     │
                           ▼                     ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  PostGIS     │     │  WebGIS     │
                    │  (escala)    │     │  React      │
                    └──────────────┘     └─────────────┘
```

## Versão local

- Pipeline Python reprodutível (`scripts/`)
- Dados em GeoPackage + JSON estático
- Frontend React/Leaflet com dados exportados
- Backend FastAPI opcional lendo JSONs

## Versão corporativa (escala)

- PostGIS com schema em `database/schema.sql`
- Ingestão batch de CARs via API
- Versionamento de bases oficiais (`source_layers`, `processing_runs`)
- Processamento assíncrono (scheduler mensal/trimestral)
- Alertas e dashboard para área de risco SAC
- Validação humana em casos sensíveis

## Endpoints API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /properties | Lista imóveis |
| GET | /properties/{id} | Detalhe do imóvel |
| GET | /properties/{id}/evidence | Evidências |
| GET | /properties/{id}/risk | Score e risco |
| GET | /layers/{name} | Camada GeoJSON |
| GET | /summary | Resumo geral |

## Narrativa

A plataforma foi construída como prova técnica de triagem socioambiental para crédito rural. A implementação foi acelerada pelo reaproveitamento de arquitetura e componentes WebGIS já dominados em projetos anteriores, adaptados ao escopo do case.
