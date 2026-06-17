"""Cálculo dos índices de restrição socioambiental (IRSA) e risco climático municipal."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_config import (
    IRSA_CLASS_ALTO_SCORE,
    IRSA_CLASS_MEDIO_SCORE,
    IRSA_CRITERIA,
    IRSA_OVERRIDES,
)
from utils_geo import PROJECT_ROOT, ensure_dir, read_car_codes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Alias legado
RESTRICTION_CRITERIA = IRSA_CRITERIA


def calc_restriction_score(row: pd.Series) -> float:
    score = 0.0
    for pct_col, _, weight, mult in IRSA_CRITERIA:
        score += min(weight, row.get(pct_col, 0) * mult)

    if row.get("embargo_ha", 0) > 0.01:
        score = max(score, IRSA_OVERRIDES["embargo_floor"])
    if row.get("ti_ha", 0) > 0.01:
        score = max(score, IRSA_OVERRIDES["ti_floor"])
    return round(min(100, score), 2)


def calc_climate_score(row: pd.Series) -> float:
    stress = row.get("stress_hidrico_idx")
    if pd.isna(stress) or stress is None:
        return 0.0
    return round(min(100, float(stress) * 100), 2)


def restriction_class(score: float, row: pd.Series) -> str:
    if row.get("embargo_ha", 0) > 0.01 or score > IRSA_CLASS_ALTO_SCORE:
        return "Alto"
    if score > IRSA_CLASS_MEDIO_SCORE:
        return "Médio"
    return "Baixo"


def climate_class(score: float) -> str:
    if score >= 55:
        return "Alto"
    if score >= 35:
        return "Médio"
    return "Baixo"


def current_risk(row: pd.Series) -> str:
    drivers = []
    if row.get("embargo_ha", 0) > 0:
        drivers.append("embargo ativo")
    if row.get("ti_ha", 0) > 0:
        drivers.append("sobreposição TI")
    if row.get("uc_ha", 0) > 0:
        drivers.append("sobreposição UC")
    if row.get("app_ha", 0) > 0:
        drivers.append("sobreposição APP (FBDS)")
    if row.get("desmatamento_ha", 0) > 0:
        drivers.append("desmatamento identificado")
    if not drivers:
        return "Baixo: sem evidência objetiva relevante"
    if "embargo ativo" in drivers or "sobreposição TI" in drivers:
        return "Alto: " + ", ".join(drivers)
    return "Médio: " + ", ".join(drivers)


def climate_risk_text(row: pd.Series) -> str:
    stress = row.get("stress_hidrico_idx")
    if pd.isna(stress) or stress is None:
        return "Sem dado climático disponível"
    score = float(stress) * 100
    cls = climate_class(score)
    level = "elevado" if score >= 55 else "moderado" if score >= 35 else "baixo"
    return f"{cls}: estresse hídrico municipal {level} (AdaptaBrasil {float(stress):.0%})"


def prospective_risk(row: pd.Series, car_row: pd.Series) -> str:
    factors = []
    if row.get("desmatamento_ha", 0) > 0:
        factors.append("desmatamento recente no imóvel")
    if row.get("app_ha", 0) > 0:
        factors.append("APP FBDS mapeada (restrição de uso)")
    if car_row.get("source_confidence", "Alta") != "Alta":
        factors.append("baixa confiança da base CAR")
    if car_row.get("uf") in ("MT", "AM", "PA"):
        factors.append("região ambientalmente sensível")

    stress = row.get("stress_hidrico_idx")
    if pd.notna(stress) and float(stress) >= 0.55:
        factors.append(f"estresse hídrico elevado no município ({float(stress):.0%})")
    elif pd.notna(stress) and float(stress) >= 0.35:
        factors.append(f"estresse hídrico moderado no município ({float(stress):.0%})")

    if len(factors) == 0:
        return "Baixo: monitoramento periódico padrão"
    if len(factors) <= 2 and not any("elevado" in f for f in factors):
        return "Baixo: " + "; ".join(factors)
    return "Médio: " + "; ".join(factors[:4])


def evidence_confidence(row: pd.Series, car_row: pd.Series) -> str:
    if car_row.get("source_confidence") == "Baixa":
        return "Baixa"
    if row.get("desmatamento_ha", 0) > 0 and row.get("embargo_ha", 0) == 0:
        return "Média"
    return car_row.get("source_confidence", "Alta")


def recommendation(risk: str) -> str:
    if risk == "Alto":
        return "Diligência e revisão de conformidade antes da decisão de crédito."
    if risk == "Médio":
        return "Análise complementar, condicionante e monitoramento recorrente."
    return "Fluxo normal de triagem, com monitoramento periódico."


def restriction_drivers(row: pd.Series) -> str:
    drivers = []
    for theme, col in [
        ("Embargo", "embargo_pct"),
        ("TI", "ti_pct"),
        ("UC", "uc_pct"),
        ("APP (FBDS)", "app_pct"),
        ("Desmatamento", "desmatamento_pct"),
    ]:
        if row.get(col.replace("_pct", "_ha"), 0) > 0:
            drivers.append(f"{theme} ({row.get(col, 0):.1f}%)")
    return "; ".join(drivers) if drivers else "Nenhuma restrição objetiva identificada"


def main():
    wide_path = PROJECT_ROOT / "output" / "tables" / "intersections_wide.csv"
    if not wide_path.exists():
        logger.error("Execute 04_intersections.py primeiro.")
        sys.exit(1)

    wide = pd.read_csv(wide_path)
    cars = read_car_codes()
    car_meta = cars.set_index("id").to_dict("index")

    import geopandas as gpd
    cars_gdf = gpd.read_file(PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg")
    car_confidence = cars_gdf.set_index("id")["source_confidence"].to_dict()

    records = []
    rec_records = []

    for _, row in wide.iterrows():
        car_id = row["car_id"]
        meta = car_meta.get(car_id, {})
        meta["source_confidence"] = car_confidence.get(car_id, "Média")

        restr_score = calc_restriction_score(row)
        clim_score = calc_climate_score(row)
        restr_cls = restriction_class(restr_score, row)
        clim_cls = climate_class(clim_score)
        conf = evidence_confidence(row, meta)

        records.append({
            "car_id": car_id,
            "car_code": row["car_code"],
            "area_ha": row["area_ha"],
            "irsa_score": restr_score,
            "restriction_score": restr_score,
            "restriction_class": restr_cls,
            "climate_score": clim_score,
            "climate_class": clim_cls,
            "stress_hidrico_idx": row.get("stress_hidrico_idx"),
            "iesc_score": restr_score,
            "risk_class": restr_cls,
            "current_risk": current_risk(row),
            "climate_risk": climate_risk_text(row),
            "prospective_risk": prospective_risk(row, meta),
            "evidence_confidence": conf,
            "recommendation": recommendation(restr_cls),
            "main_drivers": restriction_drivers(row),
        })

        rec_records.append({
            "car_id": car_id,
            "technical_recommendation": recommendation(restr_cls),
            "credit_relevance": "Triagem SAC: exposição socioambiental vinculada à operação de crédito rural.",
            "required_followup": "Diligência especializada" if restr_cls == "Alto" else "Monitoramento e documentação complementar" if restr_cls == "Médio" else "Monitoramento periódico padrão",
        })

    risk_df = pd.DataFrame(records)
    rec_df = pd.DataFrame(rec_records)

    ensure_dir(PROJECT_ROOT / "output" / "tables")
    risk_path = PROJECT_ROOT / "output" / "tables" / "risk_summary.csv"
    rec_path = PROJECT_ROOT / "output" / "tables" / "recommendations.csv"
    risk_df.to_csv(risk_path, index=False)
    rec_df.to_csv(rec_path, index=False)

    logger.info("IRSA e risco climático municipal calculados para %d imóveis → %s", len(risk_df), risk_path)


if __name__ == "__main__":
    main()
