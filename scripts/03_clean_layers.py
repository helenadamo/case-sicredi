"""Limpeza, padronização e validação das camadas."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import (
    CRS_AREA, CRS_DISPLAY, PROJECT_ROOT, calculate_area_ha, fix_geometries,
    reproject, save_gpkg, standardize_columns,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

LAYERS = {
    "cars_analisados": {"theme": "car", "required_cols": ["id", "car_code", "uf", "area_ha"]},
    "embargos_ibama": {"theme": "embargos", "required_cols": []},
    "terras_indigenas": {"theme": "ti", "required_cols": []},
    "unidades_conservacao": {"theme": "uc", "required_cols": []},
    "desmatamento": {"theme": "desmatamento", "required_cols": []},
}


def clean_layer(name: str, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    logger.info("Limpando %s (%d feições)", name, len(gdf))
    if gdf.empty:
        return gdf

    gdf = standardize_columns(gdf)
    gdf = fix_geometries(gdf)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_DISPLAY)
        logger.warning("%s sem CRS :  assumido %s", name, CRS_DISPLAY)

    gdf = reproject(gdf, CRS_DISPLAY)

    if name == "cars_analisados":
        gdf = calculate_area_ha(gdf)

    if name == "unidades_conservacao":
        for col in ["categoria", "grupo", "esfera", "nome"]:
            if col not in gdf.columns:
                for alt in gdf.columns:
                    if col in alt:
                        gdf[col] = gdf[alt]
                        break

    logger.info("%s: %d feições válidas, CRS=%s", name, len(gdf), gdf.crs)
    return gdf


def main():
    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"

    for layer_name in LAYERS:
        path = gpkg_dir / f"{layer_name}.gpkg"
        if not path.exists():
            logger.warning("Camada %s não encontrada :  pulando", layer_name)
            continue
        gdf = gpd.read_file(path)
        cleaned = clean_layer(layer_name, gdf)
        save_gpkg(cleaned, path)
        logger.info("Salvo %s", path)

    # Documentar CRS
    crs_doc = PROJECT_ROOT / "processed" / "audit" / "crs_documentation.txt"
    crs_doc.write_text(
        f"CRS visualização: {CRS_DISPLAY}\n"
        f"CRS cálculo área: {CRS_AREA}\n"
        "Regra: área nunca calculada em EPSG:4326.\n",
        encoding="utf-8",
    )
    logger.info("Limpeza concluída.")


if __name__ == "__main__":
    main()
