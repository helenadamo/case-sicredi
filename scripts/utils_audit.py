"""Trilha de auditoria de evidências."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from utils_geo import PROJECT_ROOT, ensure_dir

AUDIT_FIELDS = [
    "evidence_id", "car_id", "car_code", "theme", "source_name", "source_url",
    "download_date", "source_version", "geometry_operation", "area_ha",
    "percent_of_property", "confidence", "interpretation", "limitation", "created_at",
]

THEME_PREFIX = {
    "embargos": "IBAMA",
    "terras_indigenas": "TI",
    "unidades_conservacao": "UC",
    "desmatamento": "DESM",
}


def audit_path() -> Path:
    return PROJECT_ROOT / "output" / "tables" / "evidence_audit_log.csv"


def load_audit() -> pd.DataFrame:
    path = audit_path()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=AUDIT_FIELDS)


def _next_evidence_id(car_id: str, theme: str, existing: pd.DataFrame) -> str:
    prefix = THEME_PREFIX.get(theme, theme.upper()[:4])
    car_num = car_id.replace("CAR_", "CAR")
    pattern = f"EV-{car_num}-{prefix}-"
    existing_ids = existing[existing["evidence_id"].str.startswith(pattern, na=False)]["evidence_id"] if not existing.empty else pd.Series(dtype=str)
    seq = len(existing_ids) + 1
    return f"{pattern}{seq:03d}"


def append_evidence(
    car_id: str,
    car_code: str,
    theme: str,
    source_name: str,
    source_url: str,
    download_date: str,
    area_ha: float,
    percent_of_property: float,
    confidence: str,
    interpretation: str,
    limitation: str = "",
    source_version: str = "",
    geometry_operation: str = "intersection",
) -> str:
    path = audit_path()
    ensure_dir(path.parent)
    existing = load_audit()
    evidence_id = _next_evidence_id(car_id, theme, existing)

    row = {
        "evidence_id": evidence_id,
        "car_id": car_id,
        "car_code": car_code,
        "theme": theme,
        "source_name": source_name,
        "source_url": source_url,
        "download_date": download_date,
        "source_version": source_version,
        "geometry_operation": geometry_operation,
        "area_ha": round(area_ha, 4),
        "percent_of_property": round(percent_of_property, 4),
        "confidence": confidence,
        "interpretation": interpretation,
        "limitation": limitation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    return evidence_id


def evidence_for_no_overlap(car_id: str, car_code: str, theme: str, source_name: str, source_url: str, download_date: str):
    """Registra ausência de sobreposição como evidência negativa auditável."""
    return append_evidence(
        car_id=car_id,
        car_code=car_code,
        theme=theme,
        source_name=source_name,
        source_url=source_url,
        download_date=download_date,
        area_ha=0.0,
        percent_of_property=0.0,
        confidence="Alta",
        interpretation=f"Não foi identificada sobreposição com {theme} na área do imóvel.",
        limitation="Ausência de interseção não exclui riscos fora do perímetro analisado.",
    )
