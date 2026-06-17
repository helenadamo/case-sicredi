"""Índice Integrado de Risco Territorial para Crédito (IRTC)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_config import IRTC_BLEND, IRTC_OVERRIDES, classify_irtc
from utils_advanced import score_class_icrc, score_class_ipt
from utils_geo import PROJECT_ROOT, ensure_dir, read_car_codes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    risk = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "risk_summary.csv")
    icrc = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "climate_credit_risk.csv")
    ipt = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "territorial_pressure_index.csv")
    wide = pd.read_csv(PROJECT_ROOT / "output" / "tables" / "intersections_wide.csv")
    cars = read_car_codes()

    records = []
    for _, car in cars.iterrows():
        car_id = car["id"]
        r = risk[risk["car_id"] == car_id].iloc[0]
        i = icrc[icrc["car_id"] == car_id].iloc[0]
        p = ipt[ipt["car_id"] == car_id].iloc[0]
        w = wide[wide["car_id"] == car_id].iloc[0]

        restr = float(r["restriction_score"])
        icrc_s = float(i["icrc_score"])
        ipt_s = float(p["ipt_score"])
        icrc_cov = float(i.get("data_coverage_pct", 100) or 100)

        weighted_irtc = round(
            IRTC_BLEND["irsa"] * restr + IRTC_BLEND["icrc"] * icrc_s + IRTC_BLEND["ipt"] * ipt_s,
            2,
        )
        irtc = weighted_irtc
        prudential_floor_reason = ""

        if float(w.get("embargo_ha", 0)) > 0.01:
            floor = IRTC_OVERRIDES["embargo_floor"]
            if irtc < floor:
                prudential_floor_reason = "piso prudencial por embargo ativo"
            irtc = max(irtc, floor)
        if float(w.get("ti_ha", 0)) > 0.01:
            floor = IRTC_OVERRIDES["ti_floor"]
            if irtc < floor:
                prudential_floor_reason = "piso prudencial por Terra Indígena"
            irtc = max(irtc, floor)

        confidences = [r.get("evidence_confidence"), i.get("data_confidence"), p.get("data_confidence")]
        conf = "Baixa" if confidences.count("Baixa") >= 2 else "Média" if "Baixa" in confidences else "Alta"

        irsa_cls = str(r["restriction_class"])
        icrc_cls = str(i["icrc_class"]).replace("*", "")
        ipt_cls = str(p["ipt_class"])

        irtc_class = classify_irtc(irtc, irsa_cls, icrc_cls, ipt_cls)

        drivers = []
        if restr >= 45:
            drivers.append(("restrição ambiental", restr))
        if icrc_s >= 40:
            drivers.append(("risco climático", icrc_s))
        if ipt_s >= 35:
            drivers.append(("pressão territorial", ipt_s))
        drivers.sort(key=lambda x: x[1], reverse=True)
        main_driver = drivers[0][0] if drivers else "monitoramento padrão"
        secondary = [d[0] for d in drivers[1:3]]

        if conf == "Baixa" or icrc_cov < 60:
            recommendation = "Requer validação antes de conclusão; dados complementares incompletos."
        elif irtc_class == "Alto" or float(w.get("embargo_ha", 0)) > 0:
            recommendation = "Diligência de conformidade e revisão especializada antes da decisão de crédito."
        elif irtc_class == "Médio" or irtc >= 40:
            recommendation = "Análise complementar, condicionantes e monitoramento recorrente."
        else:
            recommendation = "Fluxo normal de triagem com monitoramento periódico."

        executive = (
            f"Risco integrado {irtc_class.lower()}, puxado por {main_driver}"
            f"{(' e ' + secondary[0]) if secondary else ''}. {recommendation}"
        )

        floor_note = (
            f" Score ponderado={weighted_irtc:.1f}; score final={irtc:.1f} por {prudential_floor_reason}."
            if prudential_floor_reason else ""
        )
        technical = (
            f"IRTC ponderado={weighted_irtc:.1f} (0.60×restrição {restr:.1f} + 0.25×ICRC {icrc_s:.1f} + 0.15×IPT {ipt_s:.1f})."
            f"{floor_note} "
            f"Restrição: {r.get('main_drivers', '')}. Clima: {i.get('main_climate_driver', '')}. "
            f"Pressão: {p.get('main_pressure_driver', '')}. Confiança: {conf}."
        )

        records.append({
            "car_id": car_id,
            "car_code": car["car_code"],
            "current_restriction_score": restr,
            "icrc_score": icrc_s,
            "ipt_score": ipt_s,
            "weighted_irtc_score": weighted_irtc,
            "irtc_score": irtc,
            "irtc_class": irtc_class,
            "prudential_floor_reason": prudential_floor_reason,
            "main_final_driver": main_driver,
            "secondary_drivers": "; ".join(secondary),
            "confidence_level": conf,
            "credit_recommendation": recommendation,
            "executive_summary": executive,
            "technical_note": technical,
        })

    out = PROJECT_ROOT / "output" / "tables" / "integrated_credit_risk.csv"
    ensure_dir(out.parent)
    pd.DataFrame(records).to_csv(out, index=False)
    logger.info("IRTC calculado → %s", out)


if __name__ == "__main__":
    main()
