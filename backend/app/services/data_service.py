"""Serviço de leitura de dados exportados."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "output" / "web_exports"
LAYERS_DIR = DATA_DIR / "layers"


def _load_json(name: str) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        fallback = PROJECT_ROOT / "frontend" / "src" / "data" / name
        path = fallback
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_properties() -> list[dict]:
    return _load_json("properties.json")


def get_property(prop_id: str) -> dict | None:
    props = get_properties()
    for p in props:
        if p["id"] == prop_id:
            return p
    return None


def get_evidence(prop_id: str | None = None) -> list[dict]:
    evidence = _load_json("evidence.json")
    if prop_id:
        return [e for e in evidence if e.get("car_id") == prop_id]
    return evidence


def get_risk(prop_id: str) -> dict | None:
    summary = _load_json("risk_summary.json")
    for r in summary:
        if r.get("car_id") == prop_id:
            return r
    return None


def get_layer(layer_name: str) -> dict | None:
    path = LAYERS_DIR / f"{layer_name}.geojson"
    if not path.exists():
        alt = PROJECT_ROOT / "frontend" / "src" / "data" / "layers" / f"{layer_name}.geojson"
        path = alt
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_summary() -> dict:
    props = get_properties()
    risk = _load_json("risk_summary.json")
    integrated = _load_json("integrated_credit_risk.json")
    return {
        "total_properties": len(props),
        "restriction_distribution": {
            "Baixo": sum(1 for r in risk if r.get("restriction_class", r.get("risk_class")) == "Baixo"),
            "Médio": sum(1 for r in risk if r.get("restriction_class", r.get("risk_class")) == "Médio"),
            "Alto": sum(1 for r in risk if r.get("restriction_class", r.get("risk_class")) == "Alto"),
        },
        "integrated_distribution": {
            "Baixo": sum(1 for r in integrated if r.get("irtc_class") == "Baixo"),
            "Médio": sum(1 for r in integrated if r.get("irtc_class") == "Médio"),
            "Alto": sum(1 for r in integrated if r.get("irtc_class") == "Alto"),
            "Crítico": sum(1 for r in integrated if r.get("irtc_class") == "Crítico"),
        },
        "avg_restriction_score": round(
            sum(p.get("restriction_score", p.get("iesc_score", 0)) for p in props) / max(len(props), 1),
            2,
        ),
    }
