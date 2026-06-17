"""Download MapBiomas Fogo — cicatrizes de queimada anuais (vetorial, Coleção 5)."""
from __future__ import annotations

import logging
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_advanced import car_bboxes, load_cars_gdf, merge_bboxes
from utils_geo import CRS_AREA, CRS_DISPLAY, PROJECT_ROOT, ensure_dir, fix_geometries, reproject, save_gpkg
from utils_sources import log_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FIRE_YEARS = [2022, 2023, 2024]
FIRE_ZIP_URL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_10/"
    "fire-col5/annual_burned_vectors_v1/mapbiomas_fire_collection5_burned_area_{year}.zip"
)
RAW_DIR = PROJECT_ROOT / "raw_data" / "advanced" / "mapbiomas_fire"
GPKG_PATH = PROJECT_ROOT / "processed" / "geopackage" / "mapbiomas_fire_scars.gpkg"


def study_bbox() -> tuple[float, float, float, float]:
    return merge_bboxes([b for _, b in car_bboxes(0.12)])


def download_year_vectors(year: int, bbox: tuple) -> gpd.GeoDataFrame:
    url = FIRE_ZIP_URL.format(year=year)
    cache_zip = RAW_DIR / f"burned_area_{year}.zip"
    ensure_dir(RAW_DIR)

    if cache_zip.exists():
        logger.info("Usando cache %s", cache_zip.name)
        content = cache_zip.read_bytes()
    else:
        logger.info("Baixando MapBiomas Fogo %d...", year)
        resp = requests.get(url, timeout=600, headers={"User-Agent": "SicrediCase/1.0"})
        resp.raise_for_status()
        content = resp.content
        cache_zip.write_bytes(content)

    extract_dir = RAW_DIR / str(year)
    ensure_dir(extract_dir)
    with zipfile.ZipFile(BytesIO(content)) as zf:
        zf.extractall(extract_dir)

    shp_files = list(extract_dir.glob("**/*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Shapefile não encontrado em {extract_dir}")

    gdf = gpd.read_file(shp_files[0])
    gdf = fix_geometries(gdf)
    gdf = reproject(gdf, CRS_DISPLAY)
    gdf = gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    gdf["fire_year"] = year
    gdf["fonte"] = "MapBiomas Fogo Coleção 5"
    gdf["layer_src"] = "MBFOGO_ANNUAL_BURNED_VECTORS"
    logger.info("MapBiomas Fogo %d: %d cicatrizes no recorte", year, len(gdf))
    return gdf[["geometry", "fire_year", "fonte", "layer_src"]]


def recurrence_class(years_active: int, prop_ha: float, buf_ha: float) -> str:
    if prop_ha > 0.1 and years_active >= 2:
        return "alta_recorrencia_no_imovel"
    if years_active >= 3:
        return "alta"
    if years_active == 2 or buf_ha > 50:
        return "media"
    if years_active == 1 or prop_ha > 0 or buf_ha > 0:
        return "baixa"
    return "sem_sinal"


def compute_fire_metrics(cars: gpd.GeoDataFrame, fire: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    fire_p = reproject(fire, CRS_AREA)
    cars_p = reproject(cars, CRS_AREA)

    for _, car in cars_p.iterrows():
        car_id = car["id"]
        car_code = car["car_code"]
        car_geom = car.geometry
        buf5 = car_geom.buffer(5000)

        prop_ha = 0.0
        buf_ha = 0.0
        years_active = set()
        scars_5km = 0

        for year in FIRE_YEARS:
            year_fire = fire_p[fire_p["fire_year"] == year]
            if year_fire.empty:
                continue

            prop_inter = gpd.overlay(
                gpd.GeoDataFrame(geometry=[car_geom], crs=CRS_AREA),
                year_fire,
                how="intersection",
                keep_geom_type=False,
            )
            if not prop_inter.empty:
                ha = prop_inter.geometry.area.sum() / 10000
                if ha > 0.001:
                    prop_ha += ha
                    years_active.add(year)

            buf_inter = gpd.overlay(
                gpd.GeoDataFrame(geometry=[buf5], crs=CRS_AREA),
                year_fire,
                how="intersection",
                keep_geom_type=False,
            )
            if not buf_inter.empty:
                ha = buf_inter.geometry.area.sum() / 10000
                if ha > 0.001:
                    buf_ha += ha
                    years_active.add(year)
                    scars_5km += len(buf_inter)

        years_list = sorted(years_active)
        rows.append({
            "car_id": car_id,
            "car_code": car_code,
            "fire_recent_ha_property": round(prop_ha, 4),
            "fire_recent_5km_ha": round(buf_ha, 4),
            "fire_years_active": len(years_active),
            "fire_years_list": ",".join(str(y) for y in years_list),
            "fire_scars_5km": scars_5km,
            "fire_recurrence_class": recurrence_class(len(years_active), prop_ha, buf_ha),
            "fire_data_confidence": "Alta",
            "fire_source": "MapBiomas Fogo Coleção 5",
            "fire_resolution_m": 30,
            "fire_period": f"{min(FIRE_YEARS)}-{max(FIRE_YEARS)}",
        })

    return pd.DataFrame(rows)


def main():
    bbox = study_bbox()
    frames = []
    for year in FIRE_YEARS:
        try:
            frames.append(download_year_vectors(year, bbox))
        except Exception as exc:
            logger.error("Falha MapBiomas Fogo %d: %s", year, exc)

    if not frames:
        logger.error("Nenhuma cicatriz MapBiomas Fogo baixada.")
        sys.exit(1)

    fire = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_DISPLAY)
    save_gpkg(fire, GPKG_PATH)
    logger.info("MapBiomas Fogo consolidado: %d cicatrizes → %s", len(fire), GPKG_PATH)

    log_source(
        "mapbiomas_fire_scars",
        "mapbiomas_fogo",
        "annual_burned_vectors_v1",
        "SHP",
        CRS_DISPLAY,
        f"MapBiomas Fogo C5 cicatrizes {FIRE_YEARS[0]}-{FIRE_YEARS[-1]} recorte case",
        confidence="Alta",
        url="https://brasil.mapbiomas.org/mapbiomas-fogo/",
    )

    cars = load_cars_gdf()
    metrics = compute_fire_metrics(cars, fire)
    out = PROJECT_ROOT / "output" / "tables" / "fire_context_by_car.csv"
    ensure_dir(out.parent)
    metrics.to_csv(out, index=False)
    logger.info("Métricas de fogo → %s", out)


if __name__ == "__main__":
    main()
