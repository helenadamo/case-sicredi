"""Exporta dados avançados (ICRC, IPT, IRTC, buffers) para o frontend."""
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


def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (np.floating, np.integer)):
        val = float(obj)
        return None if math.isnan(val) or math.isinf(val) else val
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(sanitize(data), ensure_ascii=False, indent=2), encoding="utf-8")


def export_table(name: str, data_dir: Path, web_dir: Path) -> bool:
    path = PROJECT_ROOT / "output" / "tables" / f"{name}.csv"
    if not path.exists():
        logger.warning("%s ausente", path.name)
        return False
    records = pd.read_csv(path).to_dict(orient="records")
    for out_dir in [data_dir, web_dir]:
        write_json(out_dir / f"{name}.json", records)
    return True


def export_buffers(data_dir: Path, web_dir: Path, public_dir: Path) -> None:
    buf_path = PROJECT_ROOT / "processed" / "geopackage" / "context_buffers.gpkg"
    if not buf_path.exists():
        return
    import fiona
    features = []
    for layer in fiona.listlayers(buf_path):
        if not layer.startswith("buffer_"):
            continue
        gdf = gpd.read_file(buf_path, layer=layer)
        gdf = reproject(gdf, CRS_DISPLAY)
        try:
            gdf["geometry"] = gdf.geometry.simplify(0.0002, preserve_topology=True)
        except Exception:
            pass
        geo = to_geojson_dict(gdf)
        for f in geo["features"]:
            f["properties"]["layer"] = layer
            features.append(f)
    collection = {"type": "FeatureCollection", "features": features}
    for out_dir in [data_dir / "layers", public_dir / "layers", web_dir / "layers"]:
        ensure_dir(out_dir)
        write_json(out_dir / "context_buffers.geojson", collection)
        write_json(out_dir / "context_buffers.json", collection)


def export_fbds_hydro_layers(data_dir: Path, web_dir: Path, public_dir: Path) -> None:
    """Exporta massas d'água e rios com recorte por imóvel e buffer (ICRC entorno)."""
    from utils_advanced import (
        clip_features_for_car_buffer,
        clip_hydro_to_property,
        load_cars_gdf,
        make_car_buffers,
    )
    from utils_geo import CRS_AREA

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    cars = load_cars_gdf()
    cars_p = reproject(cars, CRS_AREA)
    buffers = make_car_buffers(cars_p, [5000, 10000])

    hydro_sources = {
        "fbds_massas_dagua": "superficie_hidrica",
        "fbds_rios_simples": "rios",
    }

    for gpkg_name, theme in hydro_sources.items():
        path = gpkg_dir / f"{gpkg_name}.gpkg"
        if not path.exists():
            logger.warning("%s ausente", path.name)
            continue

        source = gpd.read_file(path)
        if source.empty:
            logger.warning("%s vazio", path.name)
            continue

        prop_parts = []
        buffer_parts = []

        for _, car in cars_p.iterrows():
            car_id = car["id"]
            car_geom = car.geometry

            prop = clip_hydro_to_property(car_geom, source)
            if not prop.empty:
                prop = prop.copy()
                keep_cols = [c for c in ("hydro_type", "layer_src", "ibge_muni", "uf_code") if c in prop.columns]
                base = gpd.GeoDataFrame({"geometry": prop.geometry}, crs=CRS_AREA)
                for col in keep_cols:
                    base[col] = prop[col].values
                base["intersect_area_ha"] = prop["intersect_area_ha"].values
                if "intersect_length_km" in prop.columns:
                    base["intersect_length_km"] = prop["intersect_length_km"].values
                base["car_id"] = car_id
                base["car_code"] = car.get("car_code", "")
                base["scope"] = "property"
                base["buffer_m"] = None
                base["theme"] = theme
                prop_parts.append(base)

            for buffer_m in (5000, 10000):
                buf_rows = buffers[(buffers["car_id"] == car_id) & (buffers["buffer_m"] == buffer_m)]
                if buf_rows.empty:
                    continue
                buf_geom = buf_rows.geometry.iloc[0]
                clipped = clip_features_for_car_buffer(car_geom, buf_geom, source, "buffer")
                if clipped.empty:
                    continue
                clipped = clipped.copy()
                keep_cols = [c for c in ("hydro_type", "layer_src", "ibge_muni", "uf_code") if c in clipped.columns]
                base = gpd.GeoDataFrame(
                    {
                        "geometry": clipped.geometry,
                        "intersect_area_ha": clipped["intersect_area_ha"],
                    },
                    crs=CRS_AREA,
                )
                if "intersect_length_km" in clipped.columns:
                    base["intersect_length_km"] = clipped["intersect_length_km"].values
                for col in keep_cols:
                    base[col] = clipped[col].values
                base["car_id"] = car_id
                base["car_code"] = car.get("car_code", "")
                base["scope"] = "buffer"
                base["buffer_m"] = buffer_m
                base["theme"] = theme
                buffer_parts.append(base)

        parts = prop_parts + buffer_parts
        if parts:
            merged = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS_AREA)
        else:
            merged = gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

        merged = reproject(merged, CRS_DISPLAY)
        try:
            merged["geometry"] = merged.geometry.simplify(0.00003, preserve_topology=True)
        except Exception:
            pass

        geo = to_geojson_dict(merged)
        prop_n = int((merged.get("scope", pd.Series(dtype=str)) == "property").sum()) if not merged.empty and "scope" in merged.columns else 0
        buf_n = len(merged) - prop_n if not merged.empty else 0
        for out_dir in [data_dir / "layers", public_dir / "layers", web_dir / "layers"]:
            ensure_dir(out_dir)
            write_json(out_dir / f"{gpkg_name}.json", geo)
            write_json(out_dir / f"{gpkg_name}.geojson", geo)
        logger.info("Exportado %s (%d no imóvel + %d no buffer)", gpkg_name, prop_n, buf_n)


def export_restriction_layers_with_buffers(data_dir: Path, web_dir: Path, public_dir: Path) -> None:
    """Mescla feições no imóvel (IRSA) com feições recortadas ao buffer/anel (IPT entorno)."""
    from utils_advanced import (
        BUFFER_CLIP_MODES,
        BUFFER_CONTEXT_LAYERS,
        clip_features_for_car_buffer,
        load_cars_gdf,
        load_context_layer,
        make_car_buffers,
    )
    from utils_geo import CRS_AREA

    inter_path = PROJECT_ROOT / "processed" / "geopackage" / "intersections.gpkg"
    if not inter_path.exists():
        logger.warning("intersections.gpkg ausente — execute 04_intersections.py")
        return

    import fiona

    layer_export = {
        "intersect_embargos": "embargos",
        "intersect_ti": "ti",
        "intersect_uc": "uc",
        "intersect_desmatamento": "desmatamento",
    }
    theme_by_dest = {
        "embargos": "embargos",
        "ti": "terras_indigenas",
        "uc": "unidades_conservacao",
        "desmatamento": "desmatamento",
    }

    cars = load_cars_gdf()
    cars_p = reproject(cars, CRS_AREA)
    buffers = make_car_buffers(cars_p, [5000, 10000])
    context_cache: dict[str, gpd.GeoDataFrame] = {}

    for dest, ctx_key in BUFFER_CONTEXT_LAYERS.items():
        context_cache[dest] = load_context_layer(ctx_key)

    for inter_layer, dest in layer_export.items():
        if inter_layer in fiona.listlayers(inter_path):
            prop_gdf = gpd.read_file(inter_path, layer=inter_layer)
        else:
            prop_gdf = gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)

        if not prop_gdf.empty:
            prop_gdf = prop_gdf.copy()
            prop_gdf["scope"] = "property"
            prop_gdf["buffer_m"] = None

        buffer_parts = []
        ctx_layer = context_cache.get(dest, gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY))
        clip_mode = BUFFER_CLIP_MODES.get(dest, "surroundings")

        for _, car in cars_p.iterrows():
            car_id = car["id"]
            car_geom = car.geometry
            for buffer_m in (5000, 10000):
                buf_rows = buffers[(buffers["car_id"] == car_id) & (buffers["buffer_m"] == buffer_m)]
                if buf_rows.empty:
                    continue
                buf_geom = buf_rows.geometry.iloc[0]
                clipped = clip_features_for_car_buffer(car_geom, buf_geom, ctx_layer, clip_mode)
                if clipped.empty:
                    continue
                clipped = gpd.GeoDataFrame(
                    {
                        "geometry": clipped.geometry,
                        "intersect_area_ha": clipped["intersect_area_ha"],
                    },
                    crs=CRS_AREA,
                )
                clipped["car_id"] = car_id
                clipped["car_code"] = car.get("car_code", "")
                clipped["scope"] = "surroundings" if clip_mode == "surroundings" else "buffer"
                clipped["buffer_m"] = buffer_m
                clipped["theme"] = theme_by_dest.get(dest, dest)
                buffer_parts.append(clipped)

        parts = []
        if not prop_gdf.empty:
            parts.append(reproject(prop_gdf, CRS_AREA))
        if buffer_parts:
            parts.append(gpd.GeoDataFrame(pd.concat(buffer_parts, ignore_index=True), crs=CRS_AREA))

        if parts:
            merged = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS_AREA)
        else:
            merged = gpd.GeoDataFrame(geometry=[], crs=CRS_AREA)

        merged = reproject(merged, CRS_DISPLAY)
        try:
            merged["geometry"] = merged.geometry.simplify(0.0001, preserve_topology=True)
        except Exception:
            pass

        geo = to_geojson_dict(merged)
        prop_n = int((merged.get("scope", pd.Series(dtype=str)) == "property").sum()) if not merged.empty and "scope" in merged.columns else 0
        buf_n = len(merged) - prop_n if not merged.empty else 0
        for out_dir in [data_dir / "layers", public_dir / "layers", web_dir / "layers"]:
            ensure_dir(out_dir)
            write_json(out_dir / f"{dest}.json", geo)
            write_json(out_dir / f"{dest}.geojson", geo)
        logger.info("Exportado %s (%d no imóvel + %d no buffer/entorno)", dest, prop_n, buf_n)


def export_fire_scars_per_car(data_dir: Path, web_dir: Path, public_dir: Path) -> None:
    """Interseção geométrica das cicatrizes com o polígono de cada CAR (como restrições)."""
    from utils_advanced import load_cars_gdf
    from utils_geo import CRS_AREA

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    path = gpkg_dir / "mapbiomas_fire_scars.gpkg"
    if not path.exists():
        logger.warning("mapbiomas_fire_scars.gpkg ausente")
        return

    cars = load_cars_gdf()
    fire = gpd.read_file(path)
    if fire.empty:
        logger.warning("mapbiomas_fire_scars vazio")
        return

    fire_p = reproject(fire, CRS_AREA)
    cars_p = reproject(cars, CRS_AREA)
    keep_cols = [c for c in ("fire_year", "fonte", "layer_src") if c in fire_p.columns]

    clips = []
    for _, car in cars_p.iterrows():
        car_geom = car.geometry
        if car_geom is None or car_geom.is_empty:
            continue
        subset = fire_p[fire_p.intersects(car_geom)]
        if subset.empty:
            continue
        car_gdf = gpd.GeoDataFrame({"car_id": [car["id"]]}, geometry=[car_geom], crs=CRS_AREA)
        inter = gpd.overlay(car_gdf, subset, how="intersection", keep_geom_type=False)
        if inter.empty:
            continue
        cols = ["car_id", "geometry"] + [c for c in keep_cols if c in inter.columns]
        clips.append(inter[cols])

    if clips:
        gdf = gpd.GeoDataFrame(pd.concat(clips, ignore_index=True), crs=CRS_AREA)
    else:
        gdf = gpd.GeoDataFrame(columns=["car_id", "geometry"] + keep_cols, crs=CRS_AREA)

    gdf = reproject(gdf, CRS_DISPLAY)
    try:
        gdf["geometry"] = gdf.geometry.simplify(0.00003, preserve_topology=True)
    except Exception:
        pass

    geo = to_geojson_dict(gdf)
    for out_dir in [data_dir / "layers", public_dir / "layers", web_dir / "layers"]:
        ensure_dir(out_dir)
        write_json(out_dir / "mapbiomas_fire_scars.json", geo)
        write_json(out_dir / "mapbiomas_fire_scars.geojson", geo)
    logger.info("Exportado mapbiomas_fire_scars (%d feições recortadas por CAR)", len(gdf))


def export_advanced_breakdown(data_dir: Path, web_dir: Path) -> None:
    icrc = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "climate_credit_risk.csv")
    ipt = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "territorial_pressure_index.csv")
    irtc = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "integrated_credit_risk.csv")

    breakdown = []
    for _, row in irtc.iterrows():
        car_id = row["car_id"]
        ci = icrc[icrc["car_id"] == car_id].iloc[0]
        pi = ipt[ipt["car_id"] == car_id].iloc[0]
        breakdown.append({
            "car_id": car_id,
            "irtc_score": row["irtc_score"],
            "irtc_class": row["irtc_class"],
            "restriction_score": row["current_restriction_score"],
            "icrc_score": row["icrc_score"],
            "icrc_class": ci["icrc_class"],
            "ipt_score": row["ipt_score"],
            "ipt_class": pi["ipt_class"],
            "icrc_components": [
                {"name": "Seca/estresse hídrico", "points": ci["drought_component"], "weight": 35},
                {"name": "Superfície hídrica", "points": ci["water_surface_component"], "weight": 25},
                {"name": "Hidrografia", "points": ci["hydrology_component"], "weight": 15},
                {"name": "Sensibilidade agro", "points": ci["agro_sensitivity_component"], "weight": 15},
                {"name": "Fogo/queimada", "points": ci["fire_component"], "weight": 10},
            ],
            "ipt_components": [
                {"name": "Proximidade TI/UC", "points": pi["protected_area_proximity_component"], "weight": 25},
                {"name": "Desmatamento entorno", "points": pi["deforestation_pressure_component"], "weight": 30},
                {"name": "Embargos entorno", "points": pi["embargo_context_component"], "weight": 20},
                {"name": "Fogo entorno", "points": pi["fire_context_component"], "weight": 10},
            ],
            "executive_summary": row["executive_summary"],
            "credit_recommendation": row["credit_recommendation"],
            "confidence_level": row["confidence_level"],
        })

    for out_dir in [data_dir, web_dir]:
        write_json(out_dir / "advanced_score_breakdown.json", breakdown)


def export_registry(data_dir: Path, web_dir: Path) -> None:
    reg_path = PROJECT_ROOT / "output" / "tables" / "advanced_layers_registry.json"
    if reg_path.exists():
        data = json.loads(reg_path.read_text(encoding="utf-8"))
    else:
        data = []
    for out_dir in [data_dir, web_dir]:
        write_json(out_dir / "advanced_layers_registry.json", data)


def main():
    data_dir = PROJECT_ROOT / "frontend" / "src" / "data"
    public_dir = PROJECT_ROOT / "frontend" / "public" / "data"
    web_dir = PROJECT_ROOT / "output" / "web_exports"
    ensure_dir(data_dir)
    ensure_dir(public_dir)
    ensure_dir(web_dir)

    export_table("climate_credit_risk", data_dir, web_dir)
    export_table("territorial_pressure_index", data_dir, web_dir)
    export_table("integrated_credit_risk", data_dir, web_dir)
    export_table("distance_context_metrics", data_dir, web_dir)
    export_buffers(data_dir, web_dir, public_dir)
    export_restriction_layers_with_buffers(data_dir, web_dir, public_dir)
    export_fbds_hydro_layers(data_dir, web_dir, public_dir)
    export_fire_scars_per_car(data_dir, web_dir, public_dir)
    export_registry(data_dir, web_dir)
    export_advanced_breakdown(data_dir, web_dir)

    logger.info("Exportação avançada concluída.")


if __name__ == "__main__":
    main()
