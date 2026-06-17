"""Executa o pipeline do case por perfis de uso.

Mantem as etapas numeradas para auditoria, mas oferece um ponto unico de
execucao para reproducao do case.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

BASE_STEPS = [
    "00_setup_project.py",
    "01_download_car.py",
    "02_download_reference_layers.py",
    "02b_download_fbds_app.py",
    "02c_download_climate_layers.py",
    "02d_download_fbds_hydro.py",
    "02e_download_mapbiomas_fire.py",
    "03_clean_layers.py",
    "04_intersections.py",
    "05_risk_scoring.py",
]

ADVANCED_STEPS = [
    "09_download_advanced_layers.py",
    "10_distance_and_context_metrics.py",
    "11_climate_credit_risk.py",
    "12_territorial_pressure_index.py",
    "13_integrated_credit_risk.py",
]

PUBLISH_STEPS = [
    "06_generate_maps.py",
    "08_export_web_data.py",
    "14_export_advanced_web_data.py",
    "07_generate_report.py",
]

PROFILES = {
    "full": BASE_STEPS + ADVANCED_STEPS + PUBLISH_STEPS,
    "base": BASE_STEPS + ["06_generate_maps.py", "08_export_web_data.py", "07_generate_report.py"],
    "advanced": ADVANCED_STEPS + PUBLISH_STEPS,
    "publish": PUBLISH_STEPS,
}


def run_step(script_name: str) -> None:
    script_path = SCRIPT_DIR / script_name
    print(f"\n=== {script_name} ===", flush=True)
    subprocess.run([sys.executable, str(script_path)], cwd=SCRIPT_DIR.parent, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o pipeline geoespacial do case Sicredi.")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="full",
        help=(
            "full: pipeline completo; base: triagem socioambiental sem camadas complementares; "
            "advanced: recalcula camadas complementares e publicacao; "
            "publish: regenera mapas, JSONs e PDF a partir dos dados processados."
        ),
    )
    args = parser.parse_args()

    for step in PROFILES[args.profile]:
        run_step(step)


if __name__ == "__main__":
    main()
