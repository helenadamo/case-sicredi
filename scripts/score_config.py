"""Configuração central de índices — fonte única para scripts, export e documentação."""

from __future__ import annotations

# IRSA — Índice de Restrição Socioambiental Atual (sobreposição no imóvel, total 100)
IRSA_LABEL = "IRSA"
IRSA_FULL_NAME = "Índice de Restrição Socioambiental Atual"
IRSA_CRITERIA = [
    # (pct_col, ha_col, max_pts, multiplier) — saturação em 10% do imóvel
    ("embargo_pct", "embargo_ha", 35, 3.5),
    ("ti_pct", "ti_ha", 25, 2.5),
    ("uc_pct", "uc_ha", 15, 1.5),
    ("app_pct", "app_ha", 15, 1.5),
    ("desmatamento_pct", "desmatamento_ha", 10, 1.0),
]
IRSA_OVERRIDES = {
    "embargo_floor": 50,
    "ti_floor": 45,
}
IRSA_CLASS_ALTO_SCORE = 50
IRSA_CLASS_MEDIO_SCORE = 20

# ICRC — Índice Climático de Risco ao Crédito
ICRC_LABEL = "ICRC"
ICRC_FULL_NAME = "Índice Climático de Risco ao Crédito"
ICRC_WEIGHTS = {
    "drought": 35,
    "water_surface": 25,
    "hydrology": 15,
    "agro_sensitivity": 15,
    "fire": 10,
}
ICRC_MIN_COVERAGE_FOR_RESCALE = 60  # abaixo disso não redistribui peso agressivamente

# IPT — Atenção de Entorno (pressão territorial, não restrição direta)
IPT_LABEL = "Atenção de Entorno"
IPT_FULL_NAME = "Índice de Pressão Territorial (atenção de entorno)"
IPT_WEIGHTS = {
    "protected_proximity": 30,
    "deforestation": 35,
    "embargo_context": 25,
    "fire": 10,
}

# IRTC — Índice Integrado de Risco Territorial para Crédito
IRTC_LABEL = "IRTC"
IRTC_FULL_NAME = "Índice Integrado de Risco Territorial para Crédito"
IRTC_BLEND = {"irsa": 0.60, "icrc": 0.25, "ipt": 0.15}
IRTC_OVERRIDES = {
    "embargo_floor": 65,
    "ti_floor": 55,
}
IRTC_CLASS_ALTO = 70
IRTC_CLASS_MEDIO = 40
IRTC_CLASS_ORDER = {"Baixo": 0, "Médio": 1, "Alto": 2, "Crítico": 3}


def _normalize_class_label(label: str) -> str:
    return str(label).replace("*", "").strip()


def dimension_floor(irsa_class: str, icrc_class: str, ipt_class: str) -> str:
    """Piso de classificação a partir das três dimensões (não é voto por maioria)."""
    classes = [_normalize_class_label(c) for c in (irsa_class, icrc_class, ipt_class)]
    highs = sum(1 for c in classes if c in {"Alto", "Crítico"})
    crits = sum(1 for c in classes if c == "Crítico")
    medios = sum(1 for c in classes if c == "Médio")

    if crits >= 1 or highs >= 2:
        return "Alto"
    if highs >= 1 or medios >= 2:
        return "Médio"
    return "Baixo"


def classify_irtc(
    score: float,
    irsa_class: str,
    icrc_class: str,
    ipt_class: str,
) -> str:
    """Classe do IRTC: score ponderado com piso pelas dimensões."""
    if score > IRTC_CLASS_ALTO:
        base = "Alto"
    elif score > IRTC_CLASS_MEDIO:
        base = "Médio"
    else:
        base = "Baixo"

    floor = dimension_floor(irsa_class, icrc_class, ipt_class)
    if IRTC_CLASS_ORDER[base] >= IRTC_CLASS_ORDER[floor]:
        return base
    return floor

# Proximidade — pontuação de atenção de entorno (metros)
PROXIMITY_BANDS_M = [
    (500, 1.0),
    (2000, 0.65),
    (10000, 0.30),
]
PROXIMITY_MAX_M = 10000  # além disso: 0 pts, só informação neutra

# Buffers de contexto
CONTEXT_BUFFER_DISTANCES_M = [500, 1000, 5000, 10000]
CONTEXT_LAYER_BBOX_BUFFER_DEG = 0.12  # ~10 km no recorte do case
