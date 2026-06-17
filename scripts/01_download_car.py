"""Download dos 4 CARs :  OBRIGATÓRIO polígono oficial antes de qualquer cruzamento."""
from __future__ import annotations

import json
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import (
    CRS_DISPLAY, PROJECT_ROOT, calculate_area_ha, ensure_dir,
    fix_geometries, read_car_codes, save_geojson, save_gpkg, standardize_columns,
)
from utils_sources import (
    URLS, car_code_variants, download_sicar_municipality, download_sicar_state,
    extract_shapefile_from_zip, filter_car_from_shapefile, log_source,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()
MANUAL_DIR = PROJECT_ROOT / "raw_data" / "car" / "manual"


def _normalize_car_code(code: str) -> str:
    return str(code).strip().upper()


def _find_car_column(gdf: gpd.GeoDataFrame) -> str | None:
    for c in gdf.columns:
        cl = c.lower()
        if cl in ("cod_imovel", "car", "cod_car", "codigo") or "cod_imovel" in cl:
            return c
    for c in gdf.columns:
        if "car" in c.lower() or "cod" in c.lower():
            return c
    return None


def load_from_manual_folder(car_id: str, car_code: str) -> gpd.GeoDataFrame | None:
    """Lê shapefile/zip/geojson colocado pelo usuário em raw_data/car/manual/CAR_XX/."""
    folder = MANUAL_DIR / car_id
    if not folder.exists():
        return None

    for pattern in ["**/*.shp", "**/*.geojson", "**/*.gpkg", "**/*.zip"]:
        for f in folder.glob(pattern):
            try:
                if f.suffix.lower() == ".zip":
                    extract_dir = folder / "extracted"
                    shp = extract_shapefile_from_zip(f, extract_dir)
                    if shp:
                        gdf = gpd.read_file(shp)
                    else:
                        continue
                else:
                    gdf = gpd.read_file(f)

                gdf = fix_geometries(standardize_columns(gdf))
                col = _find_car_column(gdf)
                if col:
                    gdf["_car_norm"] = gdf[col].astype(str).str.upper().str.replace("-", "").str.strip()
                    for variant in car_code_variants(car_code):
                        hit = gdf[gdf["_car_norm"] == variant.replace("-", "")]
                        if not hit.empty:
                            logger.info("CAR %s encontrado em manual: %s (variante %s)", car_id, f.name, variant)
                            return hit.drop(columns=["_car_norm"], errors="ignore")
                # shapefile de imóvel único pode não ter coluna car :  usar geometria direta
                if len(gdf) == 1:
                    logger.info("CAR %s :  shapefile único em manual: %s", car_id, f.name)
                    return gdf
            except Exception as exc:
                logger.warning("Erro lendo %s: %s", f, exc)
    return None


def load_from_automatic(row: pd.Series, muni_cache: dict, state_cache: dict) -> gpd.GeoDataFrame | None:
    """Tenta SICAR automático: estado primeiro (mais estável), depois município."""
    car_code = _normalize_car_code(row.get("car_code_hyphenated", row["car_code"]))
    uf = row["uf"]
    muni_code = int(str(row["car_code"]).replace("-", "")[2:9])

    # 1) Download por estado (funciona melhor que município neste ambiente)
    if uf not in state_cache:
        raw_dir = PROJECT_ROOT / "raw_data" / "car" / "estados" / uf
        existing = raw_dir / f"{uf}_AREA_IMOVEL.zip"
        if existing.exists() and existing.stat().st_size > 1_000_000:
            zip_path = existing
            logger.info("Reutilizando zip estadual existente: %s", existing)
        else:
            zip_path = download_sicar_state(uf, raw_dir, tries=15)
        if zip_path and Path(zip_path).exists():
            shp = extract_shapefile_from_zip(Path(zip_path), raw_dir / "extracted")
            state_cache[uf] = shp
        else:
            state_cache[uf] = None

    shp = state_cache.get(uf)
    if shp and Path(shp).exists():
        filtered = filter_car_from_shapefile(Path(shp), car_code)
        if not filtered.empty:
            return filtered

    # 2) Download por município (fallback)
    if muni_code not in muni_cache:
        raw_dir = PROJECT_ROOT / "raw_data" / "car" / "municipios" / str(muni_code)
        zip_path = download_sicar_municipality(muni_code, raw_dir, tries=10)
        if zip_path and zip_path.exists():
            shp = extract_shapefile_from_zip(zip_path, raw_dir / "extracted")
            muni_cache[muni_code] = shp
        else:
            muni_cache[muni_code] = None

    shp = muni_cache.get(muni_code)
    if shp and Path(shp).exists():
        return filter_car_from_shapefile(Path(shp), car_code)

    return None


def gdf_to_record(row: pd.Series, gdf_hit: gpd.GeoDataFrame, source: str, confidence: str) -> dict:
    geom = gdf_hit.geometry.iloc[0]
    gdf_one = gpd.GeoDataFrame([{"geometry": geom}], geometry="geometry", crs=CRS_DISPLAY)
    if gdf_one.crs is None:
        gdf_one = gdf_one.set_crs(CRS_DISPLAY)
    gdf_one = calculate_area_ha(gdf_one)
    return {
        "id": row["id"],
        "car_code": row["car_code"],
        "car_code_hyphenated": row.get("car_code_hyphenated", row["car_code"]),
        "uf": row["uf"],
        "label": row["label"],
        "geometry": geom,
        "area_ha": round(gdf_one["area_ha"].iloc[0], 4),
        "source": source,
        "download_date": TODAY,
        "source_confidence": confidence,
    }


def write_manual_instructions(missing: list[str]):
    msg = f"""
================================================================================
CARs NÃO OBTIDOS :  download manual necessário
================================================================================

Faltam polígonos oficiais para: {', '.join(missing)}

Sem o perímetro real do CAR, o cruzamento NÃO será executado.

COMO BAIXAR (site SICAR):
  1. https://consultapublica.car.gov.br/publico/imoveis/index
  2. Selecione o estado, localize o imóvel, clique no polígono
  3. Baixe o shapefile do imóvel
  4. Coloque em: sicredi_case/raw_data/car/manual/CAR_XX/
     (pode ser .zip, .shp ou .geojson)

Guia completo: docs/guia_download_car.md

Depois rode novamente:
  python scripts/01_download_car.py

================================================================================
"""
    print(msg)
    (PROJECT_ROOT / "output" / "CAR_DOWNLOAD_PENDENTE.txt").write_text(msg, encoding="utf-8")


def main():
    cars_df = read_car_codes()
    ensure_dir(MANUAL_DIR)

    records = []
    missing = []
    muni_cache: dict = {}
    state_cache: dict = {}

    for _, row in cars_df.iterrows():
        car_id = row["id"]
        car_code = row["car_code"]

        # Prioridade 1: arquivos manuais
        hit = load_from_manual_folder(car_id, car_code)
        if hit is not None and not hit.empty:
            records.append(gdf_to_record(row, hit, "SICAR manual (arquivo local)", "Alta"))
            continue

        # Prioridade 2: download automático SICAR
        hit = load_from_automatic(row, muni_cache, state_cache)
        if hit is not None and not hit.empty:
            records.append(gdf_to_record(row, hit, "SICAR consultapublica (automático)", "Alta"))
            logger.info("CAR %s obtido via SICAR automático", car_id)
            continue

        missing.append(car_id)
        logger.error("CAR %s NÃO obtido :  %s", car_id, car_code[:24])

    if missing:
        write_manual_instructions(missing)
        meta = {"download_date": TODAY, "status": "INCOMPLETO", "missing": missing,
                "obtidos": [r["id"] for r in records]}
        (PROJECT_ROOT / "raw_data" / "car" / "download_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if len(records) < len(cars_df):
            logger.error(
                "Abortando: %d/%d CARs sem polígono oficial. Baixe manualmente e rode de novo.",
                len(missing), len(cars_df),
            )
            sys.exit(1)

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_DISPLAY)
    save_gpkg(gdf, PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg")
    save_geojson(gdf, PROJECT_ROOT / "processed" / "geojson" / "cars_analisados.geojson")

    log_source("cars_analisados", "car", "cars_analisados.gpkg", "GPKG", CRS_DISPLAY,
               f"{len(records)} imóveis com polígono oficial SICAR", "Alta", url=URLS["sicar_base"])

    (PROJECT_ROOT / "raw_data" / "car" / "download_meta.json").write_text(
        json.dumps({"download_date": TODAY, "status": "OK", "count": len(records)}, indent=2),
        encoding="utf-8",
    )
    logger.info("OK :  %d CARs oficiais salvos. Pode rodar scripts 02 em diante.", len(gdf))


if __name__ == "__main__":
    main()
