"""Exporta dados para frontend e backend."""
from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, ensure_dir, reproject, to_geojson_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def sanitize_for_json(obj):
    """Remove NaN/Inf para JSON válido."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.floating, np.integer)):
        val = float(obj)
        return None if math.isnan(val) or math.isinf(val) else val
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(sanitize_for_json(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_geojson_layers():
    layers_dir = PROJECT_ROOT / "frontend" / "src" / "data" / "layers"
    public_layers_dir = PROJECT_ROOT / "frontend" / "public" / "data" / "layers"
    web_dir = PROJECT_ROOT / "output" / "web_exports" / "layers"
    ensure_dir(layers_dir)
    ensure_dir(public_layers_dir)
    ensure_dir(web_dir)

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"

    def _export_gdf(gdf: gpd.GeoDataFrame, dest: str) -> None:
        gdf = reproject(gdf, CRS_DISPLAY)
        try:
            gdf["geometry"] = gdf.geometry.simplify(0.0001, preserve_topology=True)
        except Exception:
            pass
        geojson = to_geojson_dict(gdf)
        for out_dir in [layers_dir, public_layers_dir, web_dir]:
            write_json(out_dir / f"{dest}.geojson", geojson)
            write_json(out_dir / f"{dest}.json", geojson)

    cars_path = gpkg_dir / "cars_analisados.gpkg"
    if cars_path.exists():
        _export_gdf(gpd.read_file(cars_path), "cars")
        logger.info("Exportado cars")

    # Referência: apenas feições que intersectam CARs (geometrias de sobreposição)
    intersect_export = {
        "intersect_embargos": "embargos",
        "intersect_ti": "ti",
        "intersect_uc": "uc",
        "intersect_desmatamento": "desmatamento",
        "intersect_app": "app",
    }
    climate_export = {}
    inter_path = gpkg_dir / "intersections.gpkg"
    if inter_path.exists():
        import fiona
        for layer, dest in intersect_export.items():
            if layer not in fiona.listlayers(inter_path):
                _export_gdf(gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY), dest)
                continue
            gdf = gpd.read_file(inter_path, layer=layer)
            _export_gdf(gdf, dest)
            logger.info("Exportado %s (%d feições de interseção)", dest, len(gdf))
    else:
        logger.warning("intersections.gpkg não encontrado")


def export_json_data():
    data_dir = PROJECT_ROOT / "frontend" / "src" / "data"
    web_dir = PROJECT_ROOT / "output" / "web_exports"
    ensure_dir(data_dir)
    ensure_dir(web_dir)

    cars = gpd.read_file(PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg")
    risk = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "risk_summary.csv")
    wide = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "intersections_wide.csv")
    audit = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "evidence_audit_log.csv")
    rec = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "recommendations.csv")

    properties = []
    for _, car in cars.iterrows():
        r = risk[risk["car_id"] == car["id"]].iloc[0] if not risk[risk["car_id"] == car["id"]].empty else {}
        w = wide[wide["car_id"] == car["id"]].iloc[0] if not wide[wide["car_id"] == car["id"]].empty else {}
        rec_row = rec[rec["car_id"] == car["id"]].iloc[0] if not rec[rec["car_id"] == car["id"]].empty else {}
        centroid = car.geometry.centroid
        properties.append({
            "id": car["id"],
            "car_code": car["car_code"],
            "uf": car["uf"],
            "label": car["label"],
            "area_ha": float(car["area_ha"]),
            "lat": float(centroid.y),
            "lng": float(centroid.x),
            "iesc_score": float(r.get("restriction_score", r.get("iesc_score", 0))),
            "restriction_score": float(r.get("restriction_score", r.get("iesc_score", 0))),
            "restriction_class": r.get("restriction_class", r.get("risk_class", "n/d")),
            "climate_score": float(r.get("climate_score", 0)),
            "climate_class": r.get("climate_class", "n/d"),
            "climate_risk": r.get("climate_risk", ""),
            "risk_class": r.get("restriction_class", r.get("risk_class", "n/d")),
            "current_risk": r.get("current_risk", ""),
            "prospective_risk": r.get("prospective_risk", ""),
            "evidence_confidence": r.get("evidence_confidence", ""),
            "main_drivers": r.get("main_drivers", ""),
            "recommendation": r.get("recommendation", ""),
            "embargo_ha": float(w.get("embargo_ha", 0)),
            "embargo_pct": float(w.get("embargo_pct", 0)),
            "ti_ha": float(w.get("ti_ha", 0)),
            "ti_pct": float(w.get("ti_pct", 0)),
            "uc_ha": float(w.get("uc_ha", 0)),
            "uc_pct": float(w.get("uc_pct", 0)),
            "desmatamento_ha": float(w.get("desmatamento_ha", 0)),
            "desmatamento_pct": float(w.get("desmatamento_pct", 0)),
            "app_ha": float(w.get("app_ha", 0)),
            "app_pct": float(w.get("app_pct", 0)),
            "stress_hidrico_idx": float(w["stress_hidrico_idx"]) if pd.notna(w.get("stress_hidrico_idx")) else None,
            "technical_recommendation": rec_row.get("technical_recommendation", ""),
            "required_followup": rec_row.get("required_followup", ""),
        })

    evidence = audit.to_dict(orient="records")
    risk_summary = risk.to_dict(orient="records")

    exports = {
        "properties.json": properties,
        "evidence.json": evidence,
        "risk_summary.json": risk_summary,
    }

    for filename, data in exports.items():
        for out_dir in [data_dir, web_dir]:
            write_json(out_dir / filename, data)

    # Score breakdown para aba Risco
    restriction_breakdown = []
    climate_breakdown = []
    for p in properties:
        stress_idx = p.get("stress_hidrico_idx") or 0
        restriction_breakdown.append({
            "car_id": p["id"],
            "index_type": "restriction",
            "components": [
                {"criterion": "Embargo IBAMA", "weight": 35, "value": min(35, p["embargo_pct"] * 3.5), "pct": p["embargo_pct"]},
                {"criterion": "Terra Indígena", "weight": 25, "value": min(25, p["ti_pct"] * 2.5), "pct": p["ti_pct"]},
                {"criterion": "Unidade de Conservação", "weight": 15, "value": min(15, p["uc_pct"] * 1.5), "pct": p["uc_pct"]},
                {"criterion": "Desmatamento", "weight": 10, "value": min(10, p["desmatamento_pct"] * 1.0), "pct": p["desmatamento_pct"]},
                {"criterion": "APP (FBDS)", "weight": 15, "value": min(15, p["app_pct"] * 1.5), "pct": p["app_pct"]},
            ],
            "total": p["restriction_score"],
        })
        climate_breakdown.append({
            "car_id": p["id"],
            "index_type": "climate",
            "components": [
                {
                    "criterion": "Estresse hídrico (AdaptaBrasil)",
                    "weight": 100,
                    "value": p["climate_score"],
                    "pct": stress_idx * 100,
                },
            ],
            "total": p["climate_score"],
        })

    score_breakdown = restriction_breakdown

    for out_dir in [data_dir, web_dir]:
        write_json(out_dir / "score_breakdown.json", score_breakdown)
        write_json(out_dir / "restriction_breakdown.json", restriction_breakdown)
        write_json(out_dir / "climate_breakdown.json", climate_breakdown)

    # Export XLSX
    tables_dir = PROJECT_ROOT / "output" / "tables"
    xlsx_path = tables_dir / "resultados_completos.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        risk.to_excel(writer, sheet_name="risk_summary", index=False)
        wide.to_excel(writer, sheet_name="intersections_wide", index=False)
        audit.to_excel(writer, sheet_name="evidence_audit", index=False)
    logger.info("XLSX exportado: %s", xlsx_path)

    logger.info("Dados JSON exportados para frontend e web_exports")


def main():
    export_geojson_layers()
    export_json_data()
    logger.info("Exportação web concluída.")


if __name__ == "__main__":
    main()
