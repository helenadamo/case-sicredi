"""Setup inicial do projeto."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import PROJECT_ROOT, ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DIRS = [
    "input", "raw_data/car", "raw_data/fbds", "raw_data/ibama_embargos",
    "raw_data/mapbiomas_alerta", "raw_data/climate", "raw_data/advanced/mapbiomas_fire",
    "processed/geopackage", "processed/geojson", "processed/audit",
    "output/tables", "output/maps", "output/report", "output/web_exports",
    "docs", "database", "backend/app", "frontend/src/data/layers",
]


def main():
    logger.info("Configurando projeto em %s", PROJECT_ROOT)
    for d in DIRS:
        ensure_dir(PROJECT_ROOT / d)
    logger.info("Estrutura de pastas verificada.")
    logger.info("CRS documentado em utils_geo.py")
    logger.info("Próximo passo: python scripts/01_download_car.py")


if __name__ == "__main__":
    main()
