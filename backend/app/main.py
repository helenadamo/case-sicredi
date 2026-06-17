from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.services.data_service import (
    get_evidence,
    get_layer,
    get_properties,
    get_property,
    get_risk,
    get_summary,
)

app = FastAPI(
    title="Sicredi SAC — Triagem Socioambiental",
    description="API para evidências auditáveis em risco SAC",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Sicredi SAC API", "docs": "/docs"}


@app.get("/properties")
def list_properties():
    return get_properties()


@app.get("/properties/{prop_id}")
def property_detail(prop_id: str):
    prop = get_property(prop_id)
    if not prop:
        raise HTTPException(404, "Imóvel não encontrado")
    return prop


@app.get("/properties/{prop_id}/evidence")
def property_evidence(prop_id: str):
    return get_evidence(prop_id)


@app.get("/properties/{prop_id}/risk")
def property_risk(prop_id: str):
    risk = get_risk(prop_id)
    if not risk:
        raise HTTPException(404, "Risco não encontrado")
    return risk


@app.get("/layers/{layer_name}")
def layer_geojson(layer_name: str):
    layer = get_layer(layer_name)
    if not layer:
        raise HTTPException(404, f"Camada {layer_name} não encontrada")
    return layer


@app.get("/summary")
def summary():
    return get_summary()
