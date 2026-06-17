"""Download mínimo FBDS :  APP municipal para os municípios dos 4 CARs."""
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

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, ensure_dir, fix_geometries, read_car_codes, reproject, save_gpkg
from utils_sources import append_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FBDS_BASE = "https://geo.fbds.org.br"
SHP_EXTS = ("shp", "shx", "dbf", "prj", "cpg")


def fbds_slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")


def ibge_from_car_code(car_code: str) -> str:
    return car_code[2:9]


def municipality_name(ibge: int) -> str:
    import geobr
    m = geobr.read_municipality(code_muni=ibge, year=2020)
    return str(m["name_muni"].iloc[0])


def list_app_shp_links(uf: str, slug: str) -> list[str]:
    url = f"{FBDS_BASE}/{uf}/{slug}/APP/"
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return [m.group(1) for m in re.finditer(r'href="(/[^"]+_APP\.shp)"', r.text, re.I)]


def download_shapefile(remote_base_path: str, dest_dir: Path) -> Path:
    """remote_base_path like /RS/MUN/APP/RS_4319406_APP"""
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
        targets.append({
            "uf": row["uf"],
            "ibge": ibge,
            "slug": fbds_slug(name),
            "name": name,
            "car_ids": [cars[cars["car_code"].str.contains(ibge, na=False)]["id"].tolist()],
        })

    raw_dir = PROJECT_ROOT / "raw_data" / "fbds"
    frames = []

    for t in targets:
        uf, ibge, slug, name = t["uf"], t["ibge"], t["slug"], t["name"]
        logger.info("FBDS APP :  %s/%s (%s)", uf, name, ibge)
        links = list_app_shp_links(uf, slug)
        app_links = [l for l in links if l.endswith("_APP.shp") and not l.endswith("_APP_USO.shp")]
        if not app_links:
            logger.error("APP não encontrado para %s/%s", uf, slug)
            continue
        remote = app_links[0].replace(".shp", "")
        dest = raw_dir / uf / ibge
        shp_path = download_shapefile(remote, dest)
        gdf = gpd.read_file(shp_path)
        gdf = fix_geometries(gdf)
        gdf = reproject(gdf, CRS_DISPLAY)
        clean = gpd.GeoDataFrame(geometry=gdf.geometry, crs=CRS_DISPLAY)
        clean["ibge_muni"] = str(ibge)
        clean["muni_slug"] = slug
        clean["uf_code"] = uf
        clean["layer_src"] = "FBDS_APP"
        frames.append(clean)
        append_registry({
            "layer_name": "fbds_app",
            "theme": "app_fbds",
            "official_source": "FBDS",
            "url": f"{FBDS_BASE}/{uf}/{slug}/APP/",
            "download_date": pd.Timestamp.today().date().isoformat(),
            "file_name": Path(remote).name + ".shp",
            "format": "SHP",
            "crs": CRS_DISPLAY,
            "notes": f"APP municipal :  {name}/{uf} (IBGE {ibge}), escopo mínimo case",
            "confidence": "Alta",
        })

    if not frames:
        logger.error("Nenhuma camada FBDS APP baixada.")
        sys.exit(1)

    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_DISPLAY)
    out_path = PROJECT_ROOT / "processed" / "geopackage" / "fbds_app.gpkg"
    save_gpkg(merged, out_path)
    logger.info("FBDS APP consolidado: %d feições → %s", len(merged), out_path)


if __name__ == "__main__":
    main()
