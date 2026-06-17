"""Download camadas climáticas AdaptaBrasil (estresse hídrico e susceptibilidade)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, ensure_dir, read_car_codes, reproject, save_gpkg
from utils_sources import fetch_adaptabrasil_indicator

CLIMATE_INDICATORS = {
    "stress_hidrico": {"id": 2, "year": 2020, "label": "Risco de estresse hídrico"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def ibge_from_car_code(car_code: str) -> str:
    return str(car_code).strip().upper().replace("-", "")[2:9]


def main():
    cars = read_car_codes()
    ibge_codes = sorted({ibge_from_car_code(c) for c in cars["car_code"]})
    logger.info("Municípios dos CARs (IBGE): %s", ibge_codes)

    gpkg_dir = PROJECT_ROOT / "processed" / "geopackage"
    ensure_dir(gpkg_dir)

    for key in CLIMATE_INDICATORS:
        logger.info("AdaptaBrasil : %s", CLIMATE_INDICATORS[key]["label"])
        gdf = fetch_adaptabrasil_indicator(key, ibge_codes=ibge_codes)
        if gdf.empty:
            logger.warning("Camada %s vazia", key)
            continue
        gdf = reproject(gdf, CRS_DISPLAY)
        out = gpkg_dir / f"adaptabrasil_{key}.gpkg"
        save_gpkg(gdf, out)
        logger.info("%s : %d municípios → %s", key, len(gdf), out)

    # Tabela auxiliar CAR × índices
    rows = []
    for _, car in cars.iterrows():
        ibge = ibge_from_car_code(car["car_code"])
        row = {"car_id": car["id"], "car_code": car["car_code"], "ibge_muni": ibge}
        for key in CLIMATE_INDICATORS:
            path = gpkg_dir / f"adaptabrasil_{key}.gpkg"
            if path.exists():
                layer = gpd.read_file(path)
                match = layer[layer["ibge_muni"].astype(str) == ibge]
                row[f"{key}_idx"] = float(match["indice"].iloc[0]) if not match.empty else None
            else:
                row[f"{key}_idx"] = None
        rows.append(row)

    table_dir = PROJECT_ROOT / "output" / "tables"
    ensure_dir(table_dir)
    climate_path = table_dir / "climate_indices_by_car.csv"
    pd.DataFrame(rows).to_csv(climate_path, index=False)
    logger.info("Índices climáticos por CAR → %s", climate_path)


if __name__ == "__main__":
    main()
