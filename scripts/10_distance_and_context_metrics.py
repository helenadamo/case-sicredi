"""Métricas de distância, buffers e pressão no entorno."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_config import CONTEXT_BUFFER_DISTANCES_M
from utils_advanced import (
    count_features_in_buffer,
    drainage_density_km_km2,
    intersect_area_in_buffer,
    intersect_area_in_surroundings,
    load_cars_gdf,
    load_context_layer,
    load_fbds_hydro_combined,
    load_fbds_rios,
    make_car_buffers,
    nearest_distance_m,
    protected_presence,
)
from utils_geo import CRS_AREA, PROJECT_ROOT, ensure_dir, reproject, save_gpkg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BUFFER_DISTANCES = CONTEXT_BUFFER_DISTANCES_M


def load_optional_csv(name: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "output" / "tables" / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def main():
    cars = load_cars_gdf()
    cars_p = reproject(cars, CRS_AREA)

    ti = load_context_layer("ti_context_10km")
    uc = load_context_layer("uc_context_10km")
    embargos = load_context_layer("embargos_context_10km")
    desm = load_context_layer("desmatamento_context_10km")

    if ti.empty and uc.empty:
        logger.warning("Camadas de contexto vazias — execute 04_intersections.py para gerar context_layers.gpkg")

    hydro = load_context_layer("hidrografia_context_10km")
    if hydro.empty:
        hydro = load_fbds_hydro_combined()
    rios = load_fbds_rios()

    water_df = load_optional_csv("water_surface_by_car.csv")
    fire_df = load_optional_csv("fire_context_by_car.csv")

    buffers = make_car_buffers(cars, BUFFER_DISTANCES)
    buf_path = PROJECT_ROOT / "processed" / "geopackage" / "context_buffers.gpkg"
    ensure_dir(buf_path.parent)
    if buf_path.exists():
        buf_path.unlink()
    for dist in BUFFER_DISTANCES:
        layer = buffers[buffers["buffer_m"] == dist]
        save_gpkg(layer, buf_path, layer=f"buffer_{dist}m")
    logger.info("Buffers salvos → %s", buf_path)

    records = []
    for _, car in cars_p.iterrows():
        car_id = car["id"]
        car_geom = car.geometry

        buf5 = buffers[(buffers["car_id"] == car_id) & (buffers["buffer_m"] == 5000)].geometry.iloc[0]
        buf10 = buffers[(buffers["car_id"] == car_id) & (buffers["buffer_m"] == 10000)].geometry.iloc[0]
        buf1k = buffers[(buffers["car_id"] == car_id) & (buffers["buffer_m"] == 1000)].geometry.iloc[0]

        water_row = water_df[water_df["car_id"] == car_id].iloc[0] if not water_df.empty and car_id in water_df["car_id"].values else {}
        fire_row = fire_df[fire_df["car_id"] == car_id].iloc[0] if not fire_df.empty and car_id in fire_df["car_id"].values else {}

        notes = []
        conf_parts = []

        nearest_ti = nearest_distance_m(car_geom, ti)
        nearest_uc = nearest_distance_m(car_geom, uc)
        nearest_emb = nearest_distance_m(car_geom, embargos)
        nearest_desm = nearest_distance_m(car_geom, desm)
        nearest_water = nearest_distance_m(car_geom, hydro)

        if nearest_ti is not None:
            conf_parts.append("TI")
        if nearest_water is not None:
            conf_parts.append("hidro_fbds")
        else:
            notes.append("distância a curso d'água indisponível")

        defor_5_total = intersect_area_in_buffer(buf5, desm)
        defor_10_total = intersect_area_in_buffer(buf10, desm)
        defor_5_surround = intersect_area_in_surroundings(buf5, car_geom, desm)
        defor_10_surround = intersect_area_in_surroundings(buf10, car_geom, desm)
        alerts_5 = count_features_in_buffer(buf5, desm)
        embargo_5_total = intersect_area_in_buffer(buf5, embargos)
        embargo_5_surround = intersect_area_in_surroundings(buf5, car_geom, embargos)

        rec = {
            "car_id": car_id,
            "car_code": car["car_code"],
            "nearest_ti_m": nearest_ti,
            "nearest_uc_m": nearest_uc,
            "nearest_embargo_m": nearest_emb,
            "nearest_deforestation_m": nearest_desm,
            "nearest_water_m": nearest_water,
            "deforestation_5km_ha": defor_5_total,
            "deforestation_10km_ha": defor_10_total,
            "deforestation_5km_surroundings_ha": defor_5_surround,
            "deforestation_10km_surroundings_ha": defor_10_surround,
            "deforestation_alerts_5km": alerts_5,
            "embargo_5km_ha": embargo_5_total,
            "embargo_5km_surroundings_ha": embargo_5_surround,
            "protected_area_within_1km": protected_presence(buf1k, ti, uc),
            "protected_area_within_5km": protected_presence(buf5, ti, uc),
            "drainage_density_5km": drainage_density_km_km2(buf5, rios if not rios.empty else hydro),
            "water_surface_change_pct": water_row.get("water_surface_change_pct") if isinstance(water_row, dict) else getattr(water_row, "water_surface_change_pct", None),
            "water_surface_recent_ha": water_row.get("water_surface_recent_ha") if isinstance(water_row, dict) else getattr(water_row, "water_surface_recent_ha", None),
            "water_surface_buffer_ha": water_row.get("water_surface_buffer_ha") if isinstance(water_row, dict) else getattr(water_row, "water_surface_buffer_ha", None),
            "fire_recent_5km_ha": fire_row.get("fire_recent_5km_ha") if isinstance(fire_row, dict) else getattr(fire_row, "fire_recent_5km_ha", None),
            "fire_recent_ha_property": fire_row.get("fire_recent_ha_property") if isinstance(fire_row, dict) else getattr(fire_row, "fire_recent_ha_property", None),
            "fire_years_active": fire_row.get("fire_years_active") if isinstance(fire_row, dict) else getattr(fire_row, "fire_years_active", None),
            "fire_recurrence_class": fire_row.get("fire_recurrence_class") if isinstance(fire_row, dict) else getattr(fire_row, "fire_recurrence_class", None),
            "context_confidence": "Alta" if len(conf_parts) >= 3 else "Média" if conf_parts else "Baixa",
            "context_notes": "; ".join(notes) if notes else "",
        }
        records.append(rec)

    out = PROJECT_ROOT / "output" / "tables" / "distance_context_metrics.csv"
    ensure_dir(out.parent)
    pd.DataFrame(records).to_csv(out, index=False)
    logger.info("Métricas de contexto → %s (%d imóveis)", out, len(records))


if __name__ == "__main__":
    main()
