"""Download das bases oficiais de referência."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, ensure_dir, reproject
from utils_sources import (
    TODAY, fetch_ibama_embargos, fetch_funai_ti, fetch_mapbiomas_alerts,
    fetch_prodes, fetch_uc, log_source,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_cars_bbox(pad: float = 0.5):
    gpkg = PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg"
    if not gpkg.exists():
        return None
    cars = gpd.read_file(gpkg)
    if cars.empty:
        return None
    cars = reproject(cars, CRS_DISPLAY)
    b = cars.total_bounds
    return (float(b[0] - pad), float(b[1] - pad), float(b[2] + pad), float(b[3] + pad))


def main():
    bbox = get_cars_bbox()
    logger.info("BBox análise: %s", bbox)
    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    ensure_dir(gpkg_dir)

    logger.info("Embargos IBAMA (PAMGIA/ArcGIS)...")
    emb = fetch_ibama_embargos(bbox)
    emb.to_file(gpkg_dir / "embargos_ibama.gpkg", driver="GPKG")
    logger.info("Embargos: %d feições", len(emb))

    logger.info("Terras Indígenas FUNAI...")
    ti = fetch_funai_ti(bbox)
    ti.to_file(gpkg_dir / "terras_indigenas.gpkg", driver="GPKG")
    logger.info("TIs: %d feições", len(ti))

    logger.info("Unidades de Conservação CNUC...")
    uc = fetch_uc(bbox)
    uc.to_file(gpkg_dir / "unidades_conservacao.gpkg", driver="GPKG")
    logger.info("UCs: %d feições", len(uc))

    logger.info("Desmatamento MapBiomas Alerta...")
    alerta = fetch_mapbiomas_alerts(bbox)
    logger.info("MapBiomas alertas: %d", len(alerta))

    logger.info("Desmatamento PRODES...")
    prodes = fetch_prodes(bbox)
    logger.info("PRODES: %d", len(prodes))

    frames = [f for f in [alerta, prodes] if not f.empty]
    if frames:
        for i, f in enumerate(frames):
            drop_cols = [c for c in f.columns if c.lower() in ("fid", "id", "ogc_fid")]
            if drop_cols:
                frames[i] = f.drop(columns=drop_cols, errors="ignore")
        desm = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
        # Harmonizar colunas duplicadas
        desm = desm.loc[:, ~desm.columns.duplicated()]
    else:
        desm = gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
        log_source("desmatamento", "mapbiomas_alerta", "vazio", ": ", CRS_DISPLAY,
                   "Sem alertas no recorte :  fontes consultadas sem retorno no bbox", "Média")

    desm.to_file(gpkg_dir / "desmatamento.gpkg", driver="GPKG")
    logger.info("Desmatamento total: %d feições", len(desm))

    climate_meta = PROJECT_ROOT / "raw_data" / "climate" / "stress_hidrico_meta.json"
    ensure_dir(climate_meta.parent)
    climate_meta.write_text(
        f'{{"indicador":"stress_hidrico","fontes":["ANA","CEMADEN","WRI Aqueduct"],'
        f'"download_date":"{TODAY}"}}', encoding="utf-8",
    )
    log_source("stress_hidrico", "climate", "meta.json", "JSON", CRS_DISPLAY, "Indicador prospectivo Parte 2")
    logger.info("Download concluído.")


if __name__ == "__main__":
    main()
