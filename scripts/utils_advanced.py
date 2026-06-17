"""Utilitários para camadas avançadas, métricas de contexto e novos índices."""
from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, shape

from utils_geo import CRS_AREA, CRS_DISPLAY, PROJECT_ROOT, calculate_area_ha, ensure_dir, fix_geometries, reproject, standardize_columns

logger = logging.getLogger(__name__)

ADVANCED_RAW = PROJECT_ROOT / "raw_data" / "advanced"
ADVANCED_LOG = PROJECT_ROOT / "output" / "logs" / "advanced_layers_errors.log"

ADAPTABRASIL_MANUAL_SCHEMA = [
    "municipio_codigo_ibge", "municipio_nome", "uf",
    "drought_risk_score", "agro_climate_risk_score", "water_security_risk_score",
    "source_year", "source_url", "confidence",
]

AQUEDUCT_MANUAL_SCHEMA = [
    "car_id", "municipio_codigo_ibge", "aqueduct_water_stress", "aqueduct_drought_risk",
    "aqueduct_seasonal_variability", "aqueduct_flood_risk", "source_year", "source_url", "aqueduct_confidence",
]


def log_advanced_error(layer: str, message: str) -> None:
    ensure_dir(ADVANCED_LOG.parent)
    ts = datetime.now().isoformat(timespec="seconds")
    with open(ADVANCED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {layer}: {message}\n")
    logger.warning("%s: %s", layer, message)


def load_cars_gdf() -> gpd.GeoDataFrame:
    path = PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg"
    if not path.exists():
        raise FileNotFoundError("Execute 01_download_car.py primeiro.")
    return gpd.read_file(path)


def study_bbox(buffer_deg: float = 0.12) -> tuple[float, float, float, float]:
    """BBox WGS84 dos CARs com buffer (~10 km em latitudes do case)."""
    cars = load_cars_gdf()
    cars = reproject(cars, CRS_DISPLAY)
    minx, miny, maxx, maxy = cars.total_bounds
    return (float(minx - buffer_deg), float(miny - buffer_deg), float(maxx + buffer_deg), float(maxy + buffer_deg))


def car_bboxes(buffer_deg: float = 0.05) -> list[tuple[str, tuple[float, float, float, float]]]:
    """BBox individual por CAR (~5 km) para downloads leves."""
    cars = load_cars_gdf()
    cars = reproject(cars, CRS_DISPLAY)
    out = []
    for _, row in cars.iterrows():
        minx, miny, maxx, maxy = row.geometry.bounds
        out.append((
            row["id"],
            (float(minx - buffer_deg), float(miny - buffer_deg), float(maxx + buffer_deg), float(maxy + buffer_deg)),
        ))
    return out


def merge_bboxes(bboxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    minx = min(b[0] for b in bboxes)
    miny = min(b[1] for b in bboxes)
    maxx = max(b[2] for b in bboxes)
    maxy = max(b[3] for b in bboxes)
    return (minx, miny, maxx, maxy)


def ibge_from_car_code(car_code: str) -> str:
    return str(car_code).strip().upper().replace("-", "")[2:9]


def load_manual_table(path: Path, schema: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=schema)
    df = pd.read_csv(path)
    for col in schema:
        if col not in df.columns:
            df[col] = pd.NA
    return df[schema]


def arcgis_query_geojson(base_url: str, bbox: tuple, max_records: int = 2000, timeout: int = 90) -> gpd.GeoDataFrame:
    geom = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    params = {
        "geometry": geom,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": max_records,
    }
    resp = requests.get(f"{base_url.rstrip('/')}/query", params=params, timeout=timeout, headers={"User-Agent": "SicrediCase/1.0"})
    resp.raise_for_status()
    if b"FeatureCollection" not in resp.content:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    return gpd.read_file(__import__("io").BytesIO(resp.content))


def _osm_element_to_geom(el: dict):
    if el.get("type") == "way" and "geometry" in el:
        coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
        if len(coords) < 2:
            return None
        tags = el.get("tags", {})
        if tags.get("area") == "yes" or tags.get("natural") == "water" or tags.get("water"):
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            return Polygon(coords)
        return LineString(coords)
    if el.get("type") == "relation" and "members" in el:
        return None
    return None


def fetch_osm_waterways(bbox: tuple, timeout: int = 90) -> gpd.GeoDataFrame:
    """Hidrografia via OpenStreetMap (complementar; não substitui ANA BHO)."""
    south, west, north, east = bbox[1], bbox[0], bbox[3], bbox[2]
    query = (
        f'[out:json][timeout:60];'
        f'(way["waterway"]({south},{west},{north},{east});'
        f'way["natural"="water"]({south},{west},{north},{east}););out geom;'
    )
    resp = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=timeout,
        headers={"User-Agent": "SicrediCase/1.0"},
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = []
    for el in payload.get("elements", []):
        geom = _osm_element_to_geom(el)
        if geom is None or geom.is_empty:
            continue
        rows.append({
            "osm_id": el.get("id"),
            "waterway": el.get("tags", {}).get("waterway", el.get("tags", {}).get("natural", "")),
            "fonte": "OpenStreetMap",
            "geometry": geom,
        })
    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    gdf = gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)
    return fix_geometries(standardize_columns(gdf))


def fetch_osm_waterways_per_car() -> gpd.GeoDataFrame:
    """Baixa OSM por CAR (bbox local) e consolida — evita recorte continental."""
    frames = []
    for car_id, bbox in car_bboxes(buffer_deg=0.06):
        try:
            gdf = fetch_osm_waterways(bbox, timeout=90)
            if not gdf.empty:
                gdf["car_context"] = car_id
                frames.append(gdf)
        except Exception as exc:
            log_advanced_error("osm_waterways", f"{car_id}: {exc}")
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_DISPLAY)
    return merged.drop_duplicates(subset=["osm_id"], keep="first")


def fetch_ana_hidrografia(bbox: tuple) -> gpd.GeoDataFrame:
    """Tenta ANA/SNIRH; fallback OSM documentado."""
    candidates = [
        "https://portal1.snirh.gov.br/server/rest/services/dados_abertos/Trechos_de_Curso_de_Agua_Inundaveis/FeatureServer/0",
    ]
    for url in candidates:
        try:
            gdf = arcgis_query_geojson(url, bbox, max_records=1500, timeout=60)
            if not gdf.empty:
                gdf["fonte"] = "ANA/SNIRH"
                return fix_geometries(standardize_columns(gdf))
        except Exception as exc:
            log_advanced_error("hidrografia_ana", f"Falha {url}: {exc}")

    try:
        gdf = fetch_osm_waterways_per_car()
        if not gdf.empty:
            gdf["fonte"] = "OpenStreetMap (fallback hidrografia)"
            log_advanced_error(
                "hidrografia_ana",
                "ANA indisponível; usando OSM como proxy de cursos d'água (confiança Média).",
            )
            return gdf
    except Exception as exc:
        log_advanced_error("hidrografia_ana", f"OSM fallback falhou: {exc}")
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def water_area_metrics(car_geom, water_gdf: gpd.GeoDataFrame, buffer_m: float = 5000) -> dict:
    """Área de superfície hídrica no imóvel e buffer (polígonos FBDS massas d'água)."""
    out = {
        "water_surface_recent_ha": None,
        "water_surface_historical_mean_ha": None,
        "water_surface_change_pct": None,
        "water_trend_class": "sem_serie_temporal",
        "water_data_confidence": "Baixa",
        "water_source": "FBDS",
    }
    if water_gdf.empty:
        return out

    polys = water_gdf[water_gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if polys.empty:
        out["water_data_confidence"] = "Baixa"
        out["context_notes"] = "Somente linhas de drenagem disponíveis; sem polígonos de água."
        return out

    car_p = reproject(gpd.GeoDataFrame(geometry=[car_geom], crs=CRS_DISPLAY), CRS_AREA)
    buf_p = car_p.buffer(buffer_m)
    polys_p = reproject(polys, CRS_AREA)

    prop_inter = gpd.overlay(car_p, polys_p, how="intersection", keep_geom_type=False)
    buf_inter = gpd.overlay(gpd.GeoDataFrame(geometry=buf_p, crs=CRS_AREA), polys_p, how="intersection", keep_geom_type=False)

    prop_ha = prop_inter.geometry.area.sum() / 10000 if not prop_inter.empty else 0.0
    buf_ha = buf_inter.geometry.area.sum() / 10000 if not buf_inter.empty else 0.0

    out["water_surface_recent_ha"] = round(float(prop_ha), 4)
    out["water_surface_buffer_ha"] = round(float(buf_ha), 4)
    out["water_data_confidence"] = "Alta"
    out["water_source"] = "FBDS"
    return out


def load_fbds_massas() -> gpd.GeoDataFrame:
    path = PROJECT_ROOT / "processed" / "geopackage" / "fbds_massas_dagua.gpkg"
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    return gpd.read_file(path)


def load_fbds_rios() -> gpd.GeoDataFrame:
    path = PROJECT_ROOT / "processed" / "geopackage" / "fbds_rios_simples.gpkg"
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    return gpd.read_file(path)


def load_fbds_hydro_combined() -> gpd.GeoDataFrame:
    """Massas + rios FBDS para distância mínima."""
    frames = [load_fbds_massas(), load_fbds_rios()]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    import pandas as pd
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_DISPLAY)


def make_car_buffers(cars: gpd.GeoDataFrame, distances_m: list[int]) -> gpd.GeoDataFrame:
    """Buffers por CAR em CRS métrico."""
    projected = reproject(cars, CRS_AREA)
    rows = []
    for dist in distances_m:
        for _, row in projected.iterrows():
            rows.append({
                "car_id": row["id"],
                "car_code": row["car_code"],
                "buffer_m": dist,
                "geometry": row.geometry.buffer(dist),
            })
    return gpd.GeoDataFrame(rows, crs=CRS_AREA)


def nearest_distance_m(car_geom, layer: gpd.GeoDataFrame) -> Optional[float]:
    if layer.empty:
        return None
    car_p = reproject(gpd.GeoDataFrame(geometry=[car_geom], crs=CRS_DISPLAY), CRS_AREA)
    layer_p = reproject(layer, CRS_AREA)
    dist = car_p.geometry.iloc[0].distance(layer_p.geometry.unary_union)
    if dist is None or not math.isfinite(float(dist)):
        return None
    return round(float(dist), 1)


def intersect_area_in_buffer(buffer_geom, layer: gpd.GeoDataFrame) -> float:
    if layer.empty:
        return 0.0
    buf_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=CRS_AREA)
    layer_p = reproject(layer, CRS_AREA)
    inter = gpd.overlay(buf_gdf, layer_p, how="intersection", keep_geom_type=False)
    if inter.empty:
        return 0.0
    return round(float(inter.geometry.area.sum() / 10000), 4)


def count_features_in_buffer(buffer_geom, layer: gpd.GeoDataFrame) -> int:
    if layer.empty:
        return 0
    buf_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=CRS_AREA)
    layer_p = reproject(layer, CRS_AREA)
    return int(layer_p[layer_p.intersects(buf_gdf.geometry.iloc[0])].shape[0])


def protected_presence(buffer_geom, ti: gpd.GeoDataFrame, uc: gpd.GeoDataFrame) -> bool:
    for layer in (ti, uc):
        if layer.empty:
            continue
        layer_p = reproject(layer, CRS_AREA)
        buf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=CRS_AREA)
        if layer_p.intersects(buf.geometry.iloc[0]).any():
            return True
    return False


def drainage_density_km_km2(buffer_geom, hydro_lines: gpd.GeoDataFrame) -> Optional[float]:
    """Comprimento de drenagem / área do buffer (km/km²)."""
    if hydro_lines.empty:
        return None
    buf_area_km2 = buffer_geom.area / 1e6
    if buf_area_km2 <= 0:
        return None
    lines = hydro_lines[hydro_lines.geometry.type.isin(["LineString", "MultiLineString"])]
    if lines.empty:
        return None
    lines_p = reproject(lines, CRS_AREA)
    buf_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=CRS_AREA)
    clipped = gpd.clip(lines_p, buf_gdf)
    if clipped.empty:
        return 0.0
    length_km = clipped.geometry.length.sum() / 1000
    return round(float(length_km / buf_area_km2), 3)


def load_processed_layer(name: str) -> gpd.GeoDataFrame:
    """Camada de interseção (recortada ao polígono CAR) — uso IRSA."""
    path = PROJECT_ROOT / "processed" / "geopackage" / f"{name}.gpkg"
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    return gpd.read_file(path)


def load_context_layer(layer_key: str) -> gpd.GeoDataFrame:
    """Camada de contexto (bbox + buffer ~10 km) — distância e entorno."""
    path = PROJECT_ROOT / "processed" / "geopackage" / "context_layers.gpkg"
    if not path.exists():
        log_advanced_error("context_layers", f"{layer_key} indisponível — execute 04_intersections.py")
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    try:
        import fiona
        if layer_key not in fiona.listlayers(path):
            return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
        return gpd.read_file(path, layer=layer_key)
    except Exception as exc:
        log_advanced_error("context_layers", f"{layer_key}: {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def surround_ring(buffer_geom, car_geom):
    """Anel externo: buffer menos polígono do imóvel (evita dupla contagem)."""
    try:
        ring = buffer_geom.difference(car_geom)
        if ring.is_empty:
            return None
        return ring
    except Exception:
        return buffer_geom


def intersect_area_in_surroundings(buffer_geom, car_geom, layer: gpd.GeoDataFrame) -> float:
    ring = surround_ring(buffer_geom, car_geom)
    if ring is None:
        return 0.0
    return intersect_area_in_buffer(ring, layer)


BUFFER_CLIP_MODES = {
    "embargos": "surroundings",
    "ti": "buffer",
    "uc": "buffer",
    "desmatamento": "surroundings",
}

BUFFER_CONTEXT_LAYERS = {
    "embargos": "embargos_context_10km",
    "ti": "ti_context_10km",
    "uc": "uc_context_10km",
    "desmatamento": "desmatamento_context_10km",
}


def clip_geom_for_buffer_mode(buffer_geom, car_geom, mode: str):
    """Geometria de recorte: anel externo (entorno IPT) ou buffer completo (proximidade)."""
    if mode == "surroundings":
        return surround_ring(buffer_geom, car_geom)
    return buffer_geom


def clip_features_for_car_buffer(
    car_geom,
    buffer_geom,
    layer: gpd.GeoDataFrame,
    mode: str = "surroundings",
) -> gpd.GeoDataFrame:
    """Recorta feições de contexto ao buffer/anel do imóvel (para mapa e evidência de entorno)."""
    if layer.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

    clip_geom = clip_geom_for_buffer_mode(buffer_geom, car_geom, mode)
    if clip_geom is None or clip_geom.is_empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

    car_p = reproject(gpd.GeoDataFrame(geometry=[car_geom], crs=CRS_DISPLAY), CRS_AREA)
    clip_gdf = gpd.GeoDataFrame(geometry=[clip_geom], crs=CRS_AREA)
    layer_p = reproject(layer, CRS_AREA)
    hits = layer_p[layer_p.intersects(clip_gdf.geometry.iloc[0])]
    if hits.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

    inter = gpd.overlay(clip_gdf, hits, how="intersection", keep_geom_type=False)
    if inter.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

    inter["intersect_area_ha"] = (inter.geometry.area / 10000).round(4)
    line_mask = inter.geometry.type.isin(["LineString", "MultiLineString"])
    if line_mask.any():
        inter.loc[line_mask, "intersect_length_km"] = (inter.loc[line_mask].geometry.length / 1000).round(3)
    return inter


def clip_hydro_to_property(car_geom, layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Recorta hidrografia ao polígono do imóvel."""
    if layer.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)
    car_gdf = gpd.GeoDataFrame(geometry=[car_geom], crs=CRS_AREA)
    layer_p = reproject(layer, CRS_AREA)
    hits = layer_p[layer_p.intersects(car_geom)]
    if hits.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)
    inter = gpd.overlay(car_gdf, hits, how="intersection", keep_geom_type=False)
    if inter.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)
    inter["intersect_area_ha"] = (inter.geometry.area / 10000).round(4)
    line_mask = inter.geometry.type.isin(["LineString", "MultiLineString"])
    if line_mask.any():
        inter.loc[line_mask, "intersect_length_km"] = (inter.loc[line_mask].geometry.length / 1000).round(3)
    return inter


def score_class_icrc(score: float) -> str:
    if score > 75:
        return "Crítico"
    if score > 50:
        return "Alto"
    if score > 25:
        return "Médio"
    return "Baixo"


def score_class_ipt(score: float) -> str:
    if score > 75:
        return "Crítico"
    if score > 50:
        return "Alto"
    if score > 25:
        return "Médio"
    return "Baixo"


def score_class_irtc(score: float) -> str:
    if score > 70:
        return "Alto"
    if score > 40:
        return "Médio"
    return "Baixo"
