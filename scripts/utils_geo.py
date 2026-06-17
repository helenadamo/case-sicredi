"""Utilitários geoespaciais para o case Sicredi."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import mapping
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRS_DISPLAY = "EPSG:4326"
CRS_AREA = "EPSG:5880"  # SIRGAS 2000 / Brazil Polyconic


def get_project_root() -> Path:
    return PROJECT_ROOT


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_car_codes() -> pd.DataFrame:
    path = PROJECT_ROOT / "input" / "car_codes.csv"
    return pd.read_csv(path)


def fix_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    gdf = gdf.copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)
    return gdf


def standardize_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf.columns = [c.lower().strip().replace(" ", "_") for c in gdf.columns]
    return gdf


def reproject(gdf: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_DISPLAY)
    return gdf.to_crs(crs)


def calculate_area_ha(gdf: gpd.GeoDataFrame, crs_area: str = CRS_AREA) -> gpd.GeoDataFrame:
    """Calcula área em hectares usando CRS projetado :  nunca em EPSG:4326."""
    if gdf.empty:
        out = gdf.copy()
        out["area_ha"] = 0.0
        return out
    projected = reproject(gdf, crs_area)
    out = gdf.copy()
    out["area_ha"] = projected.geometry.area / 10000.0
    return out


def intersect_areas(
    properties: gpd.GeoDataFrame,
    layer: gpd.GeoDataFrame,
    layer_name: str,
) -> gpd.GeoDataFrame:
    """Intersecta imóveis com camada de referência e calcula áreas."""
    if properties.empty or layer.empty:
        return gpd.GeoDataFrame(
            columns=["car_id", "car_code", "theme", "source_layer", "intersect_area_ha",
                     "car_area_ha", "percent_of_property", "geometry"],
            crs=CRS_DISPLAY,
        )

    props = reproject(properties, CRS_DISPLAY)
    ref = reproject(layer, CRS_DISPLAY)

    joined = gpd.overlay(props, ref, how="intersection", keep_geom_type=False)
    if joined.empty:
        return gpd.GeoDataFrame(
            columns=["car_id", "car_code", "theme", "source_layer", "intersect_area_ha",
                     "car_area_ha", "percent_of_property", "geometry"],
            crs=CRS_DISPLAY,
        )

    joined = calculate_area_ha(joined)
    car_areas = properties.set_index("id")["area_ha"].to_dict()

    records = []
    for _, row in joined.iterrows():
        car_id = row.get("id", row.get("car_id", ""))
        car_code = row.get("car_code", "")
        car_area = car_areas.get(car_id, row.get("area_ha", 0))
        intersect_ha = row["area_ha"]
        pct = (intersect_ha / car_area * 100) if car_area > 0 else 0
        records.append({
            "car_id": car_id,
            "car_code": car_code,
            "theme": layer_name,
            "source_layer": layer_name,
            "intersect_area_ha": round(intersect_ha, 4),
            "car_area_ha": round(car_area, 4),
            "percent_of_property": round(pct, 4),
            "geometry": row.geometry,
        })

    return gpd.GeoDataFrame(records, crs=CRS_DISPLAY)


def dissolve_intersections(gdf: gpd.GeoDataFrame, group_cols: list[str]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    dissolved = []
    for keys, group in gdf.groupby(group_cols):
        geom = unary_union(group.geometry.tolist())
        rec = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        rec["intersect_area_ha"] = round(
            reproject(gpd.GeoDataFrame([{"geometry": geom}], geometry="geometry", crs=CRS_DISPLAY), CRS_AREA)
            .geometry.area.iloc[0] / 10000, 4
        )
        rec["geometry"] = geom
        dissolved.append(rec)
    return gpd.GeoDataFrame(dissolved, crs=CRS_DISPLAY)


def to_geojson_dict(gdf: gpd.GeoDataFrame) -> dict:
    gdf = reproject(gdf, CRS_DISPLAY)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in row.items() if k != "geometry"},
                "geometry": mapping(row.geometry) if row.geometry else None,
            }
            for _, row in gdf.iterrows()
        ],
    }


def save_gpkg(gdf: gpd.GeoDataFrame, path: Path, layer: Optional[str] = None) -> None:
    ensure_dir(path.parent)
    if layer:
        gdf.to_file(path, layer=layer, driver="GPKG")
    else:
        gdf.to_file(path, driver="GPKG")


def save_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    gdf_out = reproject(gdf, CRS_DISPLAY)
    gdf_out.to_file(path, driver="GeoJSON")


def utm_crs_for_geometry(gdf: gpd.GeoDataFrame) -> str:
    """Retorna CRS UTM adequado para cálculo pontual."""
    if gdf.empty:
        return CRS_AREA
    centroid = reproject(gdf, CRS_DISPLAY).geometry.unary_union.centroid
    zone = int((centroid.x + 180) / 6) + 1
    hemisphere = "south" if centroid.y < 0 else "north"
    return f"+proj=utm +zone={zone} +{'south' if hemisphere == 'south' else 'north'} +datum=WGS84 +units=m +no_defs"


def crs_documentation() -> str:
    return (
        f"Visualização: {CRS_DISPLAY} (WGS84). "
        f"Cálculo de área: {CRS_AREA} ({CRS.from_string(CRS_AREA).name}). "
        "Área nunca calculada em coordenadas geográficas."
    )
