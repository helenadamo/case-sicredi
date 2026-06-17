"""Download FBDS hidrografia municipal: massas d'água e rios simples (4 municípios dos CARs)."""
from __future__ import annotations

import logging
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, calculate_area_ha, ensure_dir, fix_geometries, read_car_codes, reproject, save_gpkg
from utils_sources import append_registry, log_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FBDS_BASE = "https://geo.fbds.org.br"
SHP_EXTS = ("shp", "shx", "dbf", "prj", "cpg")

HYDRO_LAYERS = {
    "massas_dagua": "MASSAS_DAGUA",
    "rios_simples": "RIOS_SIMPLES",
}


def fbds_slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")


def ibge_from_car_code(car_code: str) -> str:
    return car_code[2:9]


def municipality_name(ibge: int) -> str:
    import geobr
    m = geobr.read_municipality(code_muni=ibge, year=2020)
    return str(m["name_muni"].iloc[0])


def list_hydro_shp_links(uf: str, slug: str) -> dict[str, str]:
    url = f"{FBDS_BASE}/{uf}/{slug}/HIDROGRAFIA/"
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    links = [m.group(1) for m in re.finditer(r'href="(/[^"]+\.shp)"', r.text, re.I)]
    out = {}
    for key, suffix in HYDRO_LAYERS.items():
        match = next((l for l in links if suffix in l.upper()), None)
        if match:
            out[key] = match.replace(".shp", "")
    return out


def download_shapefile(remote_base_path: str, dest_dir: Path) -> Path:
    ensure_dir(dest_dir)
    stem = Path(remote_base_path).name
    for ext in SHP_EXTS:
        url = f"{FBDS_BASE}{remote_base_path}.{ext}"
        out = dest_dir / f"{stem}.{ext}"
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            out.write_bytes(resp.content)
        except Exception as exc:
            logger.warning("Falha ao baixar %s: %s", url, exc)
    shp = dest_dir / f"{stem}.shp"
    if not shp.exists():
        raise FileNotFoundError(f"Shapefile não obtido: {shp}")
    return shp


def main():
    cars = read_car_codes()
    targets = []
    seen = set()
    for _, row in cars.iterrows():
        ibge = ibge_from_car_code(row["car_code"])
        key = (row["uf"], ibge)
        if key in seen:
            continue
        seen.add(key)
        name = municipality_name(int(ibge))
        targets.append({"uf": row["uf"], "ibge": ibge, "slug": fbds_slug(name), "name": name})

    raw_dir = PROJECT_ROOT / "raw_data" / "fbds"
    massas_frames = []
    rios_frames = []

    for t in targets:
        uf, ibge, slug, name = t["uf"], t["ibge"], t["slug"], t["name"]
        logger.info("FBDS hidrografia: %s/%s (%s)", uf, name, ibge)
        try:
            links = list_hydro_shp_links(uf, slug)
        except Exception as exc:
            logger.error("HIDROGRAFIA indisponível %s/%s: %s", uf, slug, exc)
            continue

        dest = raw_dir / uf / ibge / "HIDROGRAFIA"

        if "massas_dagua" in links:
            shp = download_shapefile(links["massas_dagua"], dest)
            gdf = fix_geometries(gpd.read_file(shp))
            gdf = reproject(gdf, CRS_DISPLAY)
            gdf["ibge_muni"] = str(ibge)
            gdf["muni_slug"] = slug
            gdf["uf_code"] = uf
            gdf["hydro_type"] = "massa_dagua"
            gdf["layer_src"] = "FBDS_MASSAS_DAGUA"
            massas_frames.append(gdf[["geometry", "ibge_muni", "muni_slug", "uf_code", "hydro_type", "layer_src"]])
            log_source(
                "fbds_massas_dagua", "fbds_hydro",
                Path(links["massas_dagua"]).name + ".shp", "SHP", CRS_DISPLAY,
                f"FBDS massas d'água: {name}/{uf} (IBGE {ibge})",
                url=f"{FBDS_BASE}/{uf}/{slug}/HIDROGRAFIA/",
            )

        if "rios_simples" in links:
            shp = download_shapefile(links["rios_simples"], dest)
            gdf = fix_geometries(gpd.read_file(shp))
            gdf = reproject(gdf, CRS_DISPLAY)
            gdf["ibge_muni"] = str(ibge)
            gdf["muni_slug"] = slug
            gdf["uf_code"] = uf
            gdf["hydro_type"] = "rio_simples"
            gdf["layer_src"] = "FBDS_RIOS_SIMPLES"
            rios_frames.append(gdf[["geometry", "ibge_muni", "muni_slug", "uf_code", "hydro_type", "layer_src"]])
            log_source(
                "fbds_rios_simples", "fbds_hydro",
                Path(links["rios_simples"]).name + ".shp", "SHP", CRS_DISPLAY,
                f"FBDS rios simples: {name}/{uf} (IBGE {ibge})",
                url=f"{FBDS_BASE}/{uf}/{slug}/HIDROGRAFIA/",
            )

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    ensure_dir(gpkg_dir)

    if massas_frames:
        massas = gpd.GeoDataFrame(pd.concat(massas_frames, ignore_index=True), crs=CRS_DISPLAY)
        out_massas = gpkg_dir / "fbds_massas_dagua.gpkg"
        save_gpkg(massas, out_massas)
        logger.info("FBDS massas d'água: %d feições → %s", len(massas), out_massas)
    else:
        logger.error("Nenhuma massa d'água FBDS baixada.")

    if rios_frames:
        rios = gpd.GeoDataFrame(pd.concat(rios_frames, ignore_index=True), crs=CRS_DISPLAY)
        out_rios = gpkg_dir / "fbds_rios_simples.gpkg"
        save_gpkg(rios, out_rios)
        logger.info("FBDS rios simples: %d feições → %s", len(rios), out_rios)
    else:
        logger.error("Nenhum rio simples FBDS baixado.")

    if massas_frames and rios_frames:
        combined = gpd.GeoDataFrame(pd.concat([massas, rios], ignore_index=True), crs=CRS_DISPLAY)
        save_gpkg(combined, gpkg_dir / "fbds_hidrografia.gpkg")
        logger.info("FBDS hidrografia combinada: %d feições", len(combined))

    if not massas_frames and not rios_frames:
        sys.exit(1)


if __name__ == "__main__":
    main()
