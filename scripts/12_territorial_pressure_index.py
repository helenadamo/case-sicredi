"""Índice de Pressão Territorial (IPT) — atenção de entorno, não restrição direta."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_config import IPT_WEIGHTS, PROXIMITY_BANDS_M, PROXIMITY_MAX_M
from utils_advanced import score_class_ipt
from utils_geo import PROJECT_ROOT, ensure_dir, read_car_codes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WEIGHTS = IPT_WEIGHTS


def proximity_score(dist_m: Optional[float], max_pts: float) -> tuple[float, bool]:
    if dist_m is None or pd.isna(dist_m):
        return 0.0, False
    d = float(dist_m)
    if d > PROXIMITY_MAX_M:
        return 0.0, True  # informação neutra, sem pontuação
    for limit, factor in PROXIMITY_BANDS_M:
        if d <= limit:
            return round(max_pts * factor, 2), True
    return 0.0, True


def main():
    ctx = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "distance_context_metrics.csv")
    fire_path = PROJECT_ROOT / "output" / "tables" / "fire_context_by_car.csv"
    fire_df = pd.read_csv(fire_path) if fire_path.exists() else pd.DataFrame()
    cars = read_car_codes()

    records = []
    for _, car in cars.iterrows():
        car_id = car["id"]
        c = ctx[ctx["car_id"] == car_id].iloc[0]

        ti_pts, ti_ok = proximity_score(c.get("nearest_ti_m"), WEIGHTS["protected_proximity"] / 2)
        uc_pts, uc_ok = proximity_score(c.get("nearest_uc_m"), WEIGHTS["protected_proximity"] / 2)
        prot_pts = round(min(WEIGHTS["protected_proximity"], ti_pts + uc_pts), 2)
        prot_ok = ti_ok or uc_ok

        defor_ha = float(c.get("deforestation_5km_surroundings_ha") or c.get("deforestation_5km_ha") or 0)
        defor_pts = min(WEIGHTS["deforestation"], defor_ha * 3 + int(c.get("deforestation_alerts_5km") or 0) * 2)
        defor_ok = defor_ha > 0 or (c.get("deforestation_alerts_5km") or 0) > 0

        emb_surround = float(c.get("embargo_5km_surroundings_ha") or 0)
        emb_pts = min(WEIGHTS["embargo_context"], emb_surround * 5)
        nearest_emb = c.get("nearest_embargo_m")
        if pd.notna(nearest_emb) and 0 < float(nearest_emb) <= 2000:
            emb_pts = max(emb_pts, WEIGHTS["embargo_context"] * 0.5)
        emb_ok = emb_pts > 0 or (pd.notna(nearest_emb) and float(nearest_emb) <= PROXIMITY_MAX_M)

        fr = fire_df[fire_df["car_id"] == car_id].iloc[0] if not fire_df.empty and car_id in fire_df["car_id"].values else pd.Series()

        fire_pts = 0.0
        fire_ok = False
        buf_ha = float(c.get("fire_recent_5km_ha") or fr.get("fire_recent_5km_ha") or 0)
        years = int(fr.get("fire_years_active") or c.get("fire_years_active") or 0)
        if buf_ha > 0:
            fire_pts = min(WEIGHTS["fire"], buf_ha * 1.5)
            if years >= 2:
                fire_pts = max(fire_pts, 4.0)
            fire_ok = True

        comps = {
            "protected_area_proximity_component": (prot_pts, prot_ok),
            "deforestation_pressure_component": (round(defor_pts, 2), defor_ok),
            "embargo_context_component": (round(emb_pts, 2), emb_ok),
            "fire_context_component": (round(fire_pts, 2), fire_ok),
            "land_use_change_component": (0.0, False),
        }

        total_w = sum(
            WEIGHTS[k] for k, v in zip(
                ["protected_proximity", "deforestation", "embargo_context", "fire"],
                [comps["protected_area_proximity_component"], comps["deforestation_pressure_component"],
                 comps["embargo_context_component"], comps["fire_context_component"]],
            ) if v[1]
        )
        raw = sum(v[0] for k, v in comps.items() if k != "land_use_change_component")
        ipt = round(min(100, raw * (100 / total_w) if total_w else raw), 2)

        missing = []
        if not prot_ok:
            missing.append("protected_proximity")
        if not defor_ok:
            missing.append("deforestation")
        if not emb_ok:
            missing.append("embargo_context")
        if not fire_ok:
            missing.append("fire")

        driver_map = {
            "protected_area_proximity_component": "proximidade a Terras Indígenas ou Unidades de Conservação",
            "deforestation_pressure_component": "desmatamento e alertas no entorno (anel 5 km)",
            "embargo_context_component": "embargos ambientais no entorno",
            "fire_context_component": "cicatrizes de queimada MapBiomas no entorno",
        }
        active = {k: v for k, v in comps.items() if v[1] and k != "land_use_change_component"}
        main_key = max(active, key=lambda k: active[k][0]) if active else "protected_area_proximity_component"
        main_driver = driver_map.get(main_key, "atenção territorial combinada")

        near_ti = c.get("nearest_ti_m")
        near_uc = c.get("nearest_uc_m")
        prox_text = ""
        if pd.notna(near_ti) and float(near_ti) <= PROXIMITY_MAX_M:
            prox_text = f"está a {float(near_ti):.0f} m de Terra Indígena"
        elif pd.notna(near_uc) and float(near_uc) <= PROXIMITY_MAX_M:
            prox_text = f"está a {float(near_uc):.0f} m de Unidade de Conservação"

        defor_text = ""
        if defor_ha > 0:
            defor_text = f"possui {defor_ha:.1f} ha de desmatamento no entorno (anel 5 km)"

        interpretation = (
            f"O imóvel {car_id} não apresenta necessariamente sobreposição direta com áreas sensíveis, "
            f"mas {prox_text or 'o entorno apresenta sinais de atenção territorial'}"
            f"{(' e ' + defor_text) if defor_text else ''}. "
            f"Isso não configura restrição automática, mas aumenta a necessidade de monitoramento territorial."
        )

        records.append({
            "car_id": car_id,
            "car_code": car["car_code"],
            "ipt_score": ipt,
            "ipt_class": score_class_ipt(ipt),
            "protected_area_proximity_component": comps["protected_area_proximity_component"][0],
            "deforestation_pressure_component": comps["deforestation_pressure_component"][0],
            "embargo_context_component": comps["embargo_context_component"][0],
            "fire_context_component": comps["fire_context_component"][0],
            "land_use_change_component": 0.0,
            "main_pressure_driver": main_driver,
            "pressure_interpretation": interpretation,
            "missing_components": ",".join(missing),
            "data_confidence": c.get("context_confidence", "Média"),
        })

    out = PROJECT_ROOT / "output" / "tables" / "territorial_pressure_index.csv"
    ensure_dir(out.parent)
    pd.DataFrame(records).to_csv(out, index=False)
    logger.info("IPT (atenção de entorno) calculado → %s", out)


if __name__ == "__main__":
    main()
