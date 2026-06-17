"""Índice Climático de Risco ao Crédito (ICRC) — risco prospectivo 0–100."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_config import ICRC_MIN_COVERAGE_FOR_RESCALE, ICRC_WEIGHTS
from utils_advanced import score_class_icrc
from utils_geo import PROJECT_ROOT, ensure_dir, read_car_codes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WEIGHTS = ICRC_WEIGHTS


def load_csv(name: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "output" / "tables" / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def scale_01(val: Optional[float], max_pts: float) -> tuple[float, bool]:
    if val is None or pd.isna(val):
        return 0.0, False
    return round(min(max_pts, float(val) * max_pts), 2), True


def drought_component(row: pd.Series, adapta: pd.Series) -> tuple[float, bool]:
    stress = row.get("stress_hidrico_idx")
    if pd.notna(stress):
        return scale_01(float(stress), WEIGHTS["drought"])

    drought_manual = adapta.get("drought_risk_score")
    if pd.notna(drought_manual):
        return scale_01(float(drought_manual) / 100, WEIGHTS["drought"])

    seca = adapta.get("seca_agro_idx")
    if pd.notna(seca):
        return scale_01(float(seca), WEIGHTS["drought"] * 0.8)

    return 0.0, False


def water_surface_component(water: pd.Series) -> tuple[float, bool]:
    change = water.get("water_surface_change_pct")
    recent = water.get("water_surface_recent_ha")
    if pd.notna(change):
        neg = max(0, -float(change))
        pts = min(WEIGHTS["water_surface"], neg * 0.5)
        return round(pts, 2), True
    if pd.notna(recent) and float(recent) < 0.5:
        return round(WEIGHTS["water_surface"] * 0.4, 2), True
    if pd.notna(recent):
        return round(WEIGHTS["water_surface"] * 0.1, 2), True
    return 0.0, False


def hydrology_component(ctx: pd.Series) -> tuple[float, bool]:
    dist = ctx.get("nearest_water_m")
    density = ctx.get("drainage_density_5km")
    pts = 0.0
    has = False
    if pd.notna(dist):
        has = True
        d = float(dist)
        if d > 5000:
            pts += WEIGHTS["hydrology"] * 0.7
        elif d > 2000:
            pts += WEIGHTS["hydrology"] * 0.4
        elif d > 500:
            pts += WEIGHTS["hydrology"] * 0.15
    if pd.notna(density):
        has = True
        if float(density) < 0.5:
            pts += WEIGHTS["hydrology"] * 0.2
    return round(min(WEIGHTS["hydrology"], pts), 2), has


def agro_component(adapta: pd.Series, wide: pd.Series) -> tuple[float, bool]:
    agro = adapta.get("agro_climate_risk_score")
    if pd.notna(agro):
        return scale_01(float(agro) / 100, WEIGHTS["agro_sensitivity"])
    seca = adapta.get("seca_agro_idx")
    if pd.notna(seca):
        return scale_01(float(seca), WEIGHTS["agro_sensitivity"])
    water_sec = adapta.get("water_security_risk_score")
    if pd.notna(water_sec):
        return scale_01(float(water_sec) / 100, WEIGHTS["agro_sensitivity"] * 0.8)
    return 0.0, False


def fire_component(ctx: pd.Series, fire: pd.Series) -> tuple[float, bool]:
    prop_ha = float(fire.get("fire_recent_ha_property") or 0) if not fire.empty else 0.0
    buf_ha = float(ctx.get("fire_recent_5km_ha") or fire.get("fire_recent_5km_ha") or 0)
    years = int(fire.get("fire_years_active") or 0) if not fire.empty else 0

    if prop_ha <= 0 and buf_ha <= 0:
        return 0.0, False

    pts = min(WEIGHTS["fire"], prop_ha * 4 + buf_ha * 1.5)
    if years >= 2:
        pts = max(pts, 4.0)
    if years >= 3:
        pts = max(pts, 7.0)
    return round(min(WEIGHTS["fire"], pts), 2), True


def redistribute(components: dict[str, tuple[float, bool]]) -> tuple[float, float]:
    available = {k: v for k, v in components.items() if v[1]}
    if not available:
        return 0.0, 0.0
    total_w = sum(WEIGHTS[k] for k in available)
    score = sum(v[0] for v in available.values())
    coverage_pct = round(total_w, 1)
    if total_w >= ICRC_MIN_COVERAGE_FOR_RESCALE and total_w < 100:
        score = score * (100 / total_w)
    return round(min(100, score), 2), coverage_pct


def interpret_icrc(score: float, main_driver: str, car_id: str, coverage: float, conf: str) -> str:
    cls = score_class_icrc(score)
    level = "elevada" if score > 50 else "moderada" if score > 25 else "baixa"
    caveat = ""
    if coverage < ICRC_MIN_COVERAGE_FOR_RESCALE or conf == "Baixa":
        caveat = " Requer validação climática complementar antes de conclusão forte."
    return (
        f"A exposição climática do imóvel {car_id} foi classificada como {cls.lower()} ({level}) "
        f"porque {main_driver}, o que pode afetar produtividade agrícola e capacidade futura de "
        f"pagamento ao longo do ciclo da operação de crédito rural.{caveat}"
    )


def main():
    wide = load_csv("intersections_wide.csv")
    ctx = load_csv("distance_context_metrics.csv")
    water = load_csv("water_surface_by_car.csv")
    adapta = load_csv("adaptabrasil_extended_by_car.csv")
    fire = load_csv("fire_context_by_car.csv")
    cars = read_car_codes()

    if wide.empty:
        logger.error("Execute o pipeline base (04–10) primeiro.")
        sys.exit(1)

    records = []
    for _, car in cars.iterrows():
        car_id = car["id"]
        w = wide[wide["car_id"] == car_id].iloc[0] if car_id in wide["car_id"].values else pd.Series()
        c = ctx[ctx["car_id"] == car_id].iloc[0] if not ctx.empty and car_id in ctx["car_id"].values else pd.Series()
        wt = water[water["car_id"] == car_id].iloc[0] if not water.empty and car_id in water["car_id"].values else pd.Series()
        ad = adapta[adapta["car_id"] == car_id].iloc[0] if not adapta.empty and car_id in adapta["car_id"].values else pd.Series()
        fr = fire[fire["car_id"] == car_id].iloc[0] if not fire.empty and car_id in fire["car_id"].values else pd.Series()

        comps = {
            "drought": drought_component(w, ad),
            "water_surface": water_surface_component(wt),
            "hydrology": hydrology_component(c),
            "agro_sensitivity": agro_component(ad, w),
            "fire": fire_component(c, fr),
        }
        missing = [k for k, v in comps.items() if not v[1]]
        icrc, coverage = redistribute(comps)

        driver_scores = {k: v[0] for k, v in comps.items()}
        main_key = max(driver_scores, key=driver_scores.get) if icrc > 0 else "drought"
        driver_labels = {
            "drought": "há indicador regional de seca/estresse hídrico",
            "water_surface": "o contexto hídrico local apresenta baixa disponibilidade de superfície de água",
            "hydrology": "a distância a cursos d'água e a baixa densidade de drenagem no entorno aumentam vulnerabilidade",
            "agro_sensitivity": "a sensibilidade agroclimática municipal é relevante para a atividade produtiva",
            "fire": "há cicatrizes de queimada MapBiomas no imóvel ou no entorno (2022–2024)",
        }
        main_driver = driver_labels.get(main_key, "fatores climáticos combinados")

        if coverage < ICRC_MIN_COVERAGE_FOR_RESCALE:
            conf = "Baixa"
        elif len(missing) <= 1:
            conf = "Alta"
        elif len(missing) <= 3:
            conf = "Média"
        else:
            conf = "Baixa"

        icrc_class = score_class_icrc(icrc)
        if coverage < ICRC_MIN_COVERAGE_FOR_RESCALE and icrc_class in ("Baixo", "Médio"):
            icrc_class = f"{icrc_class}*"

        records.append({
            "car_id": car_id,
            "car_code": car["car_code"],
            "icrc_score": icrc,
            "icrc_class": icrc_class,
            "data_coverage_pct": coverage,
            "drought_component": comps["drought"][0],
            "water_surface_component": comps["water_surface"][0],
            "hydrology_component": comps["hydrology"][0],
            "agro_sensitivity_component": comps["agro_sensitivity"][0],
            "fire_component": comps["fire"][0],
            "main_climate_driver": main_driver,
            "climate_interpretation": interpret_icrc(icrc, main_driver, car_id, coverage, conf),
            "missing_components": ",".join(missing) if missing else "",
            "data_confidence": conf,
        })

    out = PROJECT_ROOT / "output" / "tables" / "climate_credit_risk.csv"
    ensure_dir(out.parent)
    pd.DataFrame(records).to_csv(out, index=False)
    logger.info("ICRC calculado → %s", out)


if __name__ == "__main__":
    main()
