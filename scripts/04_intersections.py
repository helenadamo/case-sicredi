"""Cruzamentos espaciais CAR x bases oficiais."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_audit import append_evidence, evidence_for_no_overlap, load_audit
from utils_geo import (
    CRS_DISPLAY, PROJECT_ROOT, dissolve_intersections, ensure_dir, intersect_areas,
    read_car_codes, reproject, save_gpkg,
)
from utils_sources import OFFICIAL_SOURCES, TODAY, load_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

THEMES = {
    "embargos_ibama": {"theme": "embargos", "label": "Embargos IBAMA"},
    "terras_indigenas": {"theme": "terras_indigenas", "label": "Terras Indígenas"},
    "unidades_conservacao": {"theme": "unidades_conservacao", "label": "Unidades de Conservação"},
    "desmatamento": {"theme": "desmatamento", "label": "Desmatamento"},
    "fbds_app": {"theme": "app_fbds", "label": "APP (FBDS)"},
}


def load_layer(name: str) -> gpd.GeoDataFrame:
    path = PROJECT_ROOT / "processed" / "geopackage" / f"{name}.gpkg"
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    return gpd.read_file(path)


def source_meta(theme_key: str) -> tuple[str, str]:
    registry = load_registry()
    if not registry.empty:
        row = registry[registry["theme"].str.contains(theme_key.split("_")[0], case=False, na=False)]
        if not row.empty:
            r = row.iloc[0]
            return r["official_source"], r["url"]
    meta = OFFICIAL_SOURCES.get(theme_key, {})
    return meta.get("official_source", theme_key), meta.get("urls", [""])[0]


def aggregate_by_car(intersections: gpd.GeoDataFrame, car_areas: dict) -> dict:
    """Agrega interseções por imóvel/tema com dissolve (evita dupla contagem)."""
    if intersections.empty:
        return {}
    result = {}
    for (car_id, theme), group in intersections.groupby(["car_id", "theme"]):
        dissolved = dissolve_intersections(group, ["car_id", "theme"])
        area_ha = float(dissolved["intersect_area_ha"].iloc[0]) if not dissolved.empty else 0.0
        car_area = car_areas.get(car_id) or float(group["car_area_ha"].iloc[0])
        pct = (area_ha / car_area * 100) if car_area > 0 else 0.0
        result[(car_id, theme)] = {
            "car_id": car_id,
            "theme": theme,
            "intersect_area_ha": round(area_ha, 4),
            "percent_of_property": round(pct, 4),
            "evidence_count": len(group),
        }
    return result


def build_dissolved_layers(intersections: gpd.GeoDataFrame, car_areas: dict) -> gpd.GeoDataFrame:
    """Uma feição por imóvel/tema :  área única sem dupla contagem."""
    if intersections.empty:
        return intersections
    rows = []
    for (car_id, theme), group in intersections.groupby(["car_id", "theme"]):
        dissolved = dissolve_intersections(group, ["car_id", "theme"])
        if dissolved.empty:
            continue
        row = dissolved.iloc[0].to_dict()
        car_area = car_areas.get(car_id, group["car_area_ha"].iloc[0])
        row["car_code"] = group["car_code"].iloc[0]
        row["car_area_ha"] = round(float(car_area), 4)
        row["intersect_area_ha"] = dissolved["intersect_area_ha"].iloc[0]
        row["percent_of_property"] = round(
            (row["intersect_area_ha"] / car_area * 100) if car_area > 0 else 0, 4
        )
        row["feature_count"] = len(group)
        rows.append(row)
    return gpd.GeoDataFrame(rows, crs=CRS_DISPLAY)


def main():
    cars = load_layer("cars_analisados")
    if cars.empty:
        logger.error("Nenhum CAR processado. Execute 01_download_car.py primeiro.")
        sys.exit(1)

    cars = reproject(cars, CRS_DISPLAY)
    all_intersections = []
    intersection_layers = {}

    for layer_name, meta in THEMES.items():
        ref = load_layer(layer_name)
        theme = meta["theme"]
        label = meta["label"]

        if ref.empty:
            logger.warning("Camada %s vazia :  interseções zeradas", layer_name)
            for _, car in cars.iterrows():
                src_name, src_url = source_meta(layer_name.replace("embargos_ibama", "ibama_embargos").replace("terras_indigenas", "funai_ti").replace("unidades_conservacao", "icmbio_uc"))
                evidence_for_no_overlap(
                    car["id"], car["car_code"], theme, src_name, src_url, TODAY
                )
            continue

        ref = reproject(ref, CRS_DISPLAY)
        # Recorte espacial para performance
        bbox = cars.total_bounds
        pad = 0.1
        try:
            ref = ref.cx[bbox[0] - pad:bbox[2] + pad, bbox[1] - pad:bbox[3] + pad]
        except Exception:
            pass

        inter = intersect_areas(cars, ref, theme)
        layer_key = f"intersect_{theme}" if theme != "terras_indigenas" else "intersect_ti"
        if theme == "embargos":
            layer_key = "intersect_embargos"
        elif theme == "unidades_conservacao":
            layer_key = "intersect_uc"
        elif theme == "desmatamento":
            layer_key = "intersect_desmatamento"
        elif theme == "app_fbds":
            layer_key = "intersect_app"

        if not inter.empty:
            intersection_layers[layer_key] = inter
            all_intersections.append(inter)

            src_name, src_url = source_meta(
                "ibama_embargos" if theme == "embargos" else
                "funai_ti" if theme == "terras_indigenas" else
                "icmbio_uc" if theme == "unidades_conservacao" else
                "fbds_app" if theme == "app_fbds" else "mapbiomas_alerta"
            )
            for _, row in inter.iterrows():
                append_evidence(
                    car_id=row["car_id"],
                    car_code=row["car_code"],
                    theme=theme,
                    source_name=src_name,
                    source_url=src_url,
                    download_date=TODAY,
                    area_ha=row["intersect_area_ha"],
                    percent_of_property=row["percent_of_property"],
                    confidence="Alta" if row["intersect_area_ha"] > 0 else "Média",
                    interpretation=f"Sobreposição de {row['intersect_area_ha']:.2f} ha ({row['percent_of_property']:.2f}%) com {label}.",
                )
        else:
            src_name, src_url = source_meta(
                "ibama_embargos" if theme == "embargos" else
                "funai_ti" if theme == "terras_indigenas" else
                "icmbio_uc" if theme == "unidades_conservacao" else
                "fbds_app" if theme == "app_fbds" else "mapbiomas_alerta"
            )
            for _, car in cars.iterrows():
                evidence_for_no_overlap(car["id"], car["car_code"], theme, src_name, src_url, TODAY)

    # intersections_long.csv
    long_records = []
    if all_intersections:
        combined = gpd.GeoDataFrame(
            pd.concat(all_intersections, ignore_index=True), crs=CRS_DISPLAY
        )
        for _, row in combined.iterrows():
            long_records.append({
                "car_id": row["car_id"],
                "car_code": row["car_code"],
                "theme": row["theme"],
                "source_layer": row["source_layer"],
                "intersect_area_ha": row["intersect_area_ha"],
                "car_area_ha": row["car_area_ha"],
                "percent_of_property": row["percent_of_property"],
                "evidence_count": 1,
                "source": row["theme"],
                "source_date": TODAY,
                "confidence": "Alta",
                "notes": "",
            })
    else:
        combined = gpd.GeoDataFrame()

    long_df = pd.DataFrame(long_records)
    ensure_dir(PROJECT_ROOT / "output" / "tables")
    long_path = PROJECT_ROOT / "output" / "tables" / "intersections_long.csv"
    long_df.to_csv(long_path, index=False)

    # intersections_wide.csv :  usa dissolve (área única, % recalculado)
    wide_rows = []
    theme_map = {
        "embargos": ("embargo",),
        "terras_indigenas": ("ti",),
        "unidades_conservacao": ("uc",),
        "desmatamento": ("desmatamento",),
        "app_fbds": ("app",),
    }
    car_areas = cars.set_index("id")["area_ha"].to_dict()
    agg = aggregate_by_car(combined, car_areas) if not combined.empty else {}

    for _, car in cars.iterrows():
        row = {
            "car_id": car["id"],
            "car_code": car["car_code"],
            "area_ha": car["area_ha"],
            "embargo_ha": 0, "embargo_pct": 0,
            "ti_ha": 0, "ti_pct": 0,
            "uc_ha": 0, "uc_pct": 0,
            "desmatamento_ha": 0, "desmatamento_pct": 0,
            "app_ha": 0, "app_pct": 0,
        }
        for theme, (prefix,) in theme_map.items():
            key = (car["id"], theme)
            if key in agg:
                row[f"{prefix}_ha"] = agg[key]["intersect_area_ha"]
                row[f"{prefix}_pct"] = agg[key]["percent_of_property"]
        wide_rows.append(row)

    wide_df = pd.DataFrame(wide_rows)
    climate_path = PROJECT_ROOT / "output" / "tables" / "climate_indices_by_car.csv"
    if climate_path.exists():
        climate = pd.read_csv(climate_path)
        wide_df = wide_df.merge(
            climate[["car_id", "stress_hidrico_idx", "suscetibilidade_erosao_idx"]],
            on="car_id",
            how="left",
        )
    else:
        wide_df["stress_hidrico_idx"] = None
        wide_df["suscetibilidade_erosao_idx"] = None

    wide_path = PROJECT_ROOT / "output" / "tables" / "intersections_wide.csv"
    wide_df.to_csv(wide_path, index=False)

    # intersections.gpkg :  camadas dissolvidas (sem dupla contagem)
    gpkg_path = PROJECT_ROOT / "processed" / "geopackage" / "intersections.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()

    layer_theme_map = {
        "intersect_embargos": "embargos",
        "intersect_ti": "terras_indigenas",
        "intersect_uc": "unidades_conservacao",
        "intersect_desmatamento": "desmatamento",
        "intersect_app": "app_fbds",
    }
    dissolved_by_key: dict[str, gpd.GeoDataFrame] = {}
    if not combined.empty:
        dissolved_all = build_dissolved_layers(combined, car_areas)
        for theme in dissolved_all["theme"].unique():
            part = dissolved_all[dissolved_all["theme"] == theme]
            layer_key = {
                "embargos": "intersect_embargos",
                "terras_indigenas": "intersect_ti",
                "unidades_conservacao": "intersect_uc",
                "desmatamento": "intersect_desmatamento",
                "app_fbds": "intersect_app",
            }.get(theme, f"intersect_{theme}")
            dissolved_by_key[layer_key] = part

    for layer_key in layer_theme_map:
        part = dissolved_by_key.get(layer_key, gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY))
        save_gpkg(part, gpkg_path, layer=layer_key)

    logger.info("Interseções salvas: %s, %s", long_path, wide_path)
    build_context_layers(cars)
    clip_reference_layers_to_cars(cars)


def build_context_layers(cars: gpd.GeoDataFrame) -> None:
    """Salva camadas de contexto (bbox + ~10 km) antes do recorte por interseção CAR."""
    from score_config import CONTEXT_LAYER_BBOX_BUFFER_DEG

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    out_path = gpkg_dir / "context_layers.gpkg"
    if out_path.exists():
        out_path.unlink()

    cars_disp = reproject(cars, CRS_DISPLAY)
    minx, miny, maxx, maxy = cars_disp.total_bounds
    pad = CONTEXT_LAYER_BBOX_BUFFER_DEG
    bbox = (minx - pad, miny - pad, maxx + pad, maxy + pad)

    layer_map = {
        "ti_context_10km": "terras_indigenas",
        "uc_context_10km": "unidades_conservacao",
        "embargos_context_10km": "embargos_ibama",
        "desmatamento_context_10km": "desmatamento",
    }
    for ctx_name, src_name in layer_map.items():
        path = gpkg_dir / f"{src_name}.gpkg"
        if not path.exists():
            logger.warning("Contexto %s: %s ausente", ctx_name, src_name)
            save_gpkg(gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY), out_path, layer=ctx_name)
            continue
        gdf = gpd.read_file(path)
        if gdf.empty:
            save_gpkg(gdf, out_path, layer=ctx_name)
            continue
        gdf = reproject(gdf, CRS_DISPLAY)
        gdf = gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        save_gpkg(gdf, out_path, layer=ctx_name)
        logger.info("Contexto %s: %d feições (bbox estudo)", ctx_name, len(gdf))

    fire_path = gpkg_dir / "mapbiomas_fire_scars.gpkg"
    if fire_path.exists():
        fire = gpd.read_file(fire_path)
        fire = reproject(fire, CRS_DISPLAY)
        fire = fire.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        save_gpkg(fire, out_path, layer="fogo_context_10km")
        logger.info("Contexto fogo_context_10km: %d feições", len(fire))

    hydro = gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    for hydro_name in ("fbds_massas_dagua", "fbds_rios_simples"):
        hp = gpkg_dir / f"{hydro_name}.gpkg"
        if hp.exists():
            h = gpd.read_file(hp)
            if not h.empty:
                hydro = gpd.GeoDataFrame(
                    pd.concat([hydro, reproject(h, CRS_DISPLAY)], ignore_index=True),
                    crs=CRS_DISPLAY,
                ) if not hydro.empty else reproject(h, CRS_DISPLAY)
    if not hydro.empty:
        hydro = hydro.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    save_gpkg(hydro, out_path, layer="hidrografia_context_10km")
    logger.info("Contexto hidrografia_context_10km: %d feições", len(hydro))


def clip_reference_layers_to_cars(cars: gpd.GeoDataFrame):
    """Mantém nas camadas de referência apenas feições que intersectam algum CAR."""
    from shapely.ops import unary_union

    cars_union = unary_union(cars.geometry)
    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    for layer_name in ("embargos_ibama", "terras_indigenas", "unidades_conservacao", "desmatamento", "fbds_app"):
        path = gpkg_dir / f"{layer_name}.gpkg"
        if not path.exists():
            continue
        gdf = gpd.read_file(path)
        if gdf.empty:
            continue
        gdf = reproject(gdf, CRS_DISPLAY)
        before = len(gdf)
        clipped = gdf[gdf.intersects(cars_union)].copy()
        save_gpkg(clipped, path)
        logger.info(
            "%s: %d → %d feições (apenas as que intersectam CARs)",
            layer_name, before, len(clipped),
        )


if __name__ == "__main__":
    main()
