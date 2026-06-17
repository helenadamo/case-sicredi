"""Download e ingestão de camadas avançadas (água, hidrografia, clima, uso do solo)."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_advanced import (
    ADAPTABRASIL_MANUAL_SCHEMA,
    AQUEDUCT_MANUAL_SCHEMA,
    ADVANCED_RAW,
    car_bboxes,
    ibge_from_car_code,
    load_cars_gdf,
    load_fbds_hydro_combined,
    load_fbds_massas,
    load_fbds_rios,
    load_manual_table,
    log_advanced_error,
    merge_bboxes,
    water_area_metrics,
)
from utils_geo import PROJECT_ROOT, calculate_area_ha, ensure_dir, read_car_codes, reproject, save_gpkg
from utils_sources import fetch_adaptabrasil_indicator, log_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GPKG_DIR = PROJECT_ROOT / "processed" / "geopackage"
REGISTRY_PATH = PROJECT_ROOT / "output" / "tables" / "advanced_layers_registry.json"

ADAPTABRASIL_EXTRA = {
    "seca_agro": {"id": 5, "year": 2020, "label": "Risco agroclimático"},
    "seguranca_hidrica": {"id": 8, "year": 2020, "label": "Segurança hídrica"},
}


def save_registry(entries: list[dict]) -> None:
    ensure_dir(REGISTRY_PATH.parent)
    REGISTRY_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def layer_fbds_hydro(cars: gpd.GeoDataFrame) -> list[dict]:
    """Superfície hídrica e hidrografia via FBDS (massas d'água + rios simples)."""
    registry = []
    massas = load_fbds_massas()
    rios = load_fbds_rios()

    if massas.empty and rios.empty:
        log_advanced_error(
            "fbds_hidrografia",
            "Camadas FBDS ausentes. Execute scripts/02d_download_fbds_hydro.py primeiro.",
        )
        return registry

    metrics_rows = []
    for _, car in cars.iterrows():
        m = water_area_metrics(car.geometry, massas)
        m.update({
            "car_id": car["id"],
            "car_code": car["car_code"],
            "water_source": "FBDS",
        })
        metrics_rows.append(m)

    table_path = PROJECT_ROOT / "output" / "tables" / "water_surface_by_car.csv"
    ensure_dir(table_path.parent)
    pd.DataFrame(metrics_rows).to_csv(table_path, index=False)
    logger.info("Métricas hídricas FBDS → %s", table_path)

    if not massas.empty:
        registry.append({
            "layer": "fbds_massas_dagua",
            "status": "ok",
            "features": len(massas),
            "source": "FBDS",
            "confidence": "Alta",
        })
    if not rios.empty:
        registry.append({
            "layer": "fbds_rios_simples",
            "status": "ok",
            "features": len(rios),
            "source": "FBDS",
            "confidence": "Alta",
        })

    combined = load_fbds_hydro_combined()
    if not combined.empty:
        save_gpkg(combined, GPKG_DIR / "fbds_hidrografia.gpkg")
        logger.info("FBDS hidrografia consolidada: %d feições", len(combined))

    return registry


def layer_adaptabrasil_extended(cars_df: pd.DataFrame) -> list[dict]:
    registry = []
    ibge_codes = sorted({ibge_from_car_code(c) for c in cars_df["car_code"]})
    rows = []

    manual_path = PROJECT_ROOT / "input" / "adaptabrasil_manual.csv"
    manual = load_manual_table(manual_path, ADAPTABRASIL_MANUAL_SCHEMA)

    for key, meta in ADAPTABRASIL_EXTRA.items():
        try:
            gdf = fetch_adaptabrasil_indicator(key, ibge_codes=ibge_codes)
            if gdf.empty:
                log_advanced_error("adaptabrasil", f"Indicador {key} vazio.")
                continue
            save_gpkg(gdf, GPKG_DIR / f"adaptabrasil_{key}.gpkg")
            registry.append({"layer": f"adaptabrasil_{key}", "status": "ok", "features": len(gdf)})
        except Exception as exc:
            log_advanced_error("adaptabrasil", f"{key}: {exc}")

    for _, car in cars_df.iterrows():
        ibge = ibge_from_car_code(car["car_code"])
        row = {"car_id": car["id"], "car_code": car["car_code"], "ibge_muni": ibge}
        for key in ADAPTABRASIL_EXTRA:
            path = GPKG_DIR / f"adaptabrasil_{key}.gpkg"
            if path.exists():
                gdf = gpd.read_file(path)
                match = gdf[gdf["ibge_muni"].astype(str) == ibge]
                row[f"{key}_idx"] = float(match["indice"].iloc[0]) if not match.empty else None
            else:
                row[f"{key}_idx"] = None

        if not manual.empty:
            m = manual[manual["municipio_codigo_ibge"].astype(str) == ibge]
            if not m.empty:
                mr = m.iloc[0]
                row["drought_risk_score"] = mr.get("drought_risk_score")
                row["agro_climate_risk_score"] = mr.get("agro_climate_risk_score")
                row["water_security_risk_score"] = mr.get("water_security_risk_score")
                row["adapta_manual_confidence"] = mr.get("confidence")

        rows.append(row)

    out = PROJECT_ROOT / "output" / "tables" / "adaptabrasil_extended_by_car.csv"
    ensure_dir(out.parent)
    pd.DataFrame(rows).to_csv(out, index=False)
    logger.info("AdaptaBrasil estendido → %s", out)

    if not manual_path.exists():
        log_advanced_error(
            "adaptabrasil_manual",
            "input/adaptabrasil_manual.csv ausente; ver docs/ingestao_manual_clima.md",
        )
    return registry


def layer_aqueduct() -> list[dict]:
    registry = []
    manual_path = PROJECT_ROOT / "input" / "aqueduct_manual.csv"
    manual = load_manual_table(manual_path, AQUEDUCT_MANUAL_SCHEMA)
    out = PROJECT_ROOT / "output" / "tables" / "aqueduct_by_car.csv"
    ensure_dir(out.parent)
    if manual.empty:
        log_advanced_error(
            "wri_aqueduct",
            "input/aqueduct_manual.csv ausente; ver docs/ingestao_manual_clima.md (seção Aqueduct).",
        )
        registry.append({"layer": "wri_aqueduct", "status": "manual_pending", "features": 0})
    else:
        manual.to_csv(out, index=False)
        registry.append({"layer": "wri_aqueduct", "status": "manual_loaded", "features": len(manual)})
        logger.info("WRI Aqueduct manual → %s", out)
    return registry


def layer_landcover_biomes(cars: gpd.GeoDataFrame) -> list[dict]:
    """Referência cartográfica de biomas — NÃO usado como proxy de uso do solo no score."""
    registry = []
    bbox = merge_bboxes([b for _, b in car_bboxes(0.08)])
    try:
        import geobr
        biomes = geobr.read_biomes(simplified=True)
        biomes = biomes.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        if biomes.empty:
            log_advanced_error("mapbiomas_landcover", "Biomas vazios no recorte.")
            return registry

        save_gpkg(biomes, GPKG_DIR / "landcover_biomes.gpkg")
        registry.append({
            "layer": "landcover_biomes",
            "status": "reference_only",
            "features": len(biomes),
            "confidence": "Média",
            "note": "Bioma IBGE não substitui MapBiomas Cobertura — excluído do IPT/IRTC",
        })
        logger.info("Biomas salvos como referência (sem score de uso do solo)")
    except Exception as exc:
        log_advanced_error("mapbiomas_landcover", str(exc))
    return registry


def layer_fire_context(cars: gpd.GeoDataFrame) -> list[dict]:
    """Cicatrizes de queimada MapBiomas Fogo (script 02e)."""
    registry = []
    gpkg = GPKG_DIR / "mapbiomas_fire_scars.gpkg"
    metrics_path = PROJECT_ROOT / "output" / "tables" / "fire_context_by_car.csv"

    if not gpkg.exists():
        log_advanced_error(
            "mapbiomas_fogo",
            "mapbiomas_fire_scars.gpkg ausente. Execute scripts/02e_download_mapbiomas_fire.py",
        )
        return registry

    fire = gpd.read_file(gpkg)
    registry.append({
        "layer": "mapbiomas_fire_scars",
        "status": "ok",
        "features": len(fire),
        "source": "MapBiomas Fogo Coleção 5",
        "confidence": "Alta",
        "resolution_m": 30,
        "period": "2022-2024",
    })
    logger.info("MapBiomas Fogo: %d cicatrizes carregadas", len(fire))

    if not metrics_path.exists():
        from importlib import import_module
        mod = import_module("02e_download_mapbiomas_fire")
        metrics = mod.compute_fire_metrics(cars, fire)
        ensure_dir(metrics_path.parent)
        metrics.to_csv(metrics_path, index=False)

    return registry


def main():
    ensure_dir(ADVANCED_RAW)
    ensure_dir(GPKG_DIR)
    ensure_dir(PROJECT_ROOT / "output" / "logs")

    cars = load_cars_gdf()
    cars_df = read_car_codes()

    registry: list[dict] = []
    registry.extend(layer_fbds_hydro(cars))
    registry.extend(layer_adaptabrasil_extended(cars_df))
    registry.extend(layer_aqueduct())
    registry.extend(layer_landcover_biomes(cars))
    registry.extend(layer_fire_context(cars))

    save_registry(registry)
    logger.info("Camadas avançadas concluídas. Registro → %s", REGISTRY_PATH)


if __name__ == "__main__":
    main()
