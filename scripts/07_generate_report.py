"""Geração do relatório técnico em PDF (case Sicredi)."""
from __future__ import annotations

import logging
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_config as sc
from utils_geo import CRS_AREA, CRS_DISPLAY, PROJECT_ROOT, ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TODAY = date.today().strftime("%d/%m/%Y")
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"

GREEN = "#146E37"
GREEN_LIGHT = "#3FA110"
GREEN_SOFT = "#EDF6E6"
TEXT = "#2A3328"
MUTED = "#5A645A"

REPORT_TITLE = "Relatório Técnico"
REPORT_TAGLINE = "Triagem Socioambiental de Imóveis Rurais"
REPORT_BANK = "Case Sicredi"
REPORT_ROLE = "Analista de Riscos Social, Ambiental e Climático PL"

ICRC_DIM_LABELS = {
    "drought": ("Seca", "AdaptaBrasil municipal"),
    "water_surface": ("Superfície hídrica", "FBDS MASSAS_DAGUA"),
    "hydrology": ("Hidrografia", "FBDS RIOS_SIMPLES"),
    "agro_sensitivity": ("Sensibilidade agro", "IBGE + contexto municipal"),
    "fire": ("Fogo", "MapBiomas cicatrizes 2022-2024"),
}

IPT_DIM_LABELS = {
    "protected_proximity": ("UC/TI próximas", "distância mínima ao CAR"),
    "deforestation": ("Desmatamento entorno", "anel 5 km"),
    "embargo_context": ("Embargos entorno", "anel 10 km"),
    "fire": ("Queimada entorno", "MapBiomas Fogo"),
}


def _uf_from_code(code: str) -> str:
    m = re.match(r"([A-Z]{2})", str(code))
    return m.group(1) if m else ""


def _clean_text(text: str) -> str:
    return (
        text.replace("—", ",")
        .replace("–", ",")
        .replace(" : ", ", ")
        .replace(": ", ", ")
    )


def _register_fonts() -> tuple[str, str, str, str]:
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    required = {
        "Nunito": "Nunito-Regular.ttf",
        "Nunito-Bold": "Nunito-Bold.ttf",
        "Exo2": "Exo2-Regular.ttf",
        "Exo2-Bold": "Exo2-Bold.ttf",
    }
    missing = [name for name, fname in required.items() if not (FONT_DIR / fname).exists()]
    if missing:
        logger.warning("Fontes Sicredi ausentes em %s, usando Helvetica", FONT_DIR)
        return "Helvetica", "Helvetica-Bold", "Helvetica", "Helvetica-Bold"

    for reg_name, fname in required.items():
        pdfmetrics.registerFont(TTFont(reg_name, str(FONT_DIR / fname)))

    addMapping("Nunito", 0, 0, "Nunito")
    addMapping("Nunito", 1, 0, "Nunito-Bold")
    addMapping("Exo2", 0, 0, "Exo2")
    addMapping("Exo2", 1, 0, "Exo2-Bold")
    return "Nunito", "Nunito-Bold", "Exo2", "Exo2-Bold"


def load_data() -> dict:
    risk_path = PROJECT_ROOT / "output" / "tables" / "risk_summary.csv"
    integrated_path = PROJECT_ROOT / "output" / "tables" / "integrated_credit_risk.csv"

    risk = pd.read_csv(risk_path) if risk_path.exists() else pd.DataFrame()
    integrated = pd.read_csv(integrated_path) if integrated_path.exists() else pd.DataFrame()

    if risk.empty and integrated.empty:
        raise FileNotFoundError("Execute o pipeline (05, 11-13) antes de gerar o relatório.")

    if not integrated.empty and not risk.empty:
        merged = integrated.merge(
            risk[["car_id", "area_ha", "restriction_score", "restriction_class"]],
            on="car_id",
            how="left",
            suffixes=("", "_risk"),
        )
    elif not integrated.empty:
        merged = integrated.copy()
    else:
        merged = risk.copy()

    merged["uf"] = merged.get("car_code", pd.Series(dtype=str)).map(_uf_from_code)
    return {"merged": merged}


def build_pdf(pdf_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate,
        Flowable,
        Frame,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    body_font, body_bold, display_font, display_bold = _register_fonts()
    data = load_data()
    merged = data["merged"]

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", fontName=display_bold, fontSize=18, leading=22,
        textColor=colors.HexColor(GREEN), alignment=TA_CENTER, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="CoverSub", fontName=body_font, fontSize=10, leading=13,
        textColor=colors.HexColor(MUTED), alignment=TA_CENTER, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="SectionH1", fontName=display_bold, fontSize=13, leading=16,
        textColor=colors.HexColor(GREEN), spaceBefore=8, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="SectionH2", fontName=display_bold, fontSize=11, leading=14,
        textColor=colors.HexColor(GREEN), spaceBefore=6, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="Body", fontName=body_font, fontSize=10, leading=13,
        textColor=colors.HexColor(TEXT), alignment=TA_JUSTIFY, firstLineIndent=0.5 * cm, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall", fontName=body_font, fontSize=9, leading=12,
        textColor=colors.HexColor(MUTED), alignment=TA_JUSTIFY, firstLineIndent=0.5 * cm, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SicrediBullet", fontName=body_font, fontSize=10, leading=13,
        textColor=colors.HexColor(TEXT), leftIndent=12, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="TableCell", fontName=body_font, fontSize=8.5, leading=10.5,
        textColor=colors.HexColor(TEXT), spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader", fontName=display_bold, fontSize=8.5, leading=10.5,
        textColor=colors.white, spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="Part2H1", fontName=display_bold, fontSize=13, leading=16,
        textColor=colors.HexColor(GREEN), spaceBefore=8, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Part2H2", fontName=display_bold, fontSize=11, leading=14,
        textColor=colors.HexColor(GREEN), spaceBefore=6, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="Part2Body", fontName=body_font, fontSize=10, leading=13,
        textColor=colors.HexColor(TEXT), alignment=TA_JUSTIFY, firstLineIndent=0.5 * cm, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Part2Cell", fontName=body_font, fontSize=8.8, leading=11,
        textColor=colors.HexColor(TEXT), spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="Part2CellStrong", fontName=body_bold, fontSize=8.8, leading=11,
        textColor=colors.HexColor(GREEN), spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="Part2HeaderCell", fontName=display_bold, fontSize=8.8, leading=11,
        textColor=colors.white, spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="Part2Note", fontName=body_font, fontSize=9, leading=12,
        textColor=colors.HexColor(MUTED), alignment=TA_JUSTIFY, firstLineIndent=0.5 * cm, spaceAfter=4,
    ))

    class RoundedTable(Flowable):
        """Tabela com cantos arredondados, borda suave e sombra leve."""

        def __init__(self, table: Table, radius: float = 9, pad: float = 4):
            super().__init__()
            self.table = table
            self.radius = radius
            self.pad = pad
            w, h = table.wrap(0, 0)
            self._w, self._h = w + 2 * pad + 2, h + 2 * pad + 2

        def wrap(self, availWidth, availHeight):
            return self._w, self._h

        def draw(self):
            c = self.canv
            x, y = self.pad + 1, self.pad
            w, h = self._w - 2, self._h - 2
            c.saveState()
            c.setFillColor(colors.HexColor("#00000012"))
            c.roundRect(2.5, -1.5, w, h, self.radius, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor(GREEN_LIGHT))
            c.setLineWidth(0.6)
            c.roundRect(0, 0, w, h, self.radius, fill=1, stroke=1)
            c.restoreState()
            self.table.drawOn(c, x, y)

    class ProcessDiagram(Flowable):
        """Fluxo visual da rotina de escala nacional."""

        steps = [
            "Entrada e validação",
            "PostGIS e scoring",
            "API/WebGIS e alertas",
        ]

        def __init__(self, width: float):
            super().__init__()
            self.width = width
            self.box_h = 0.82 * cm
            self.gap = 0.45 * cm
            self.height = self.box_h

        def wrap(self, availWidth, availHeight):
            return self.width, self.height

        def draw(self):
            c = self.canv
            box_w = (self.width - (len(self.steps) - 1) * self.gap) / len(self.steps)
            x = 0
            for idx, label in enumerate(self.steps):
                c.saveState()
                c.setFillColor(colors.HexColor(GREEN_SOFT))
                c.setStrokeColor(colors.HexColor(GREEN_LIGHT))
                c.setLineWidth(0.8)
                c.roundRect(x, 0, box_w, self.box_h, 5, fill=1, stroke=1)
                c.setFillColor(colors.HexColor(GREEN))
                c.setFont(display_bold, 10)
                c.drawCentredString(x + box_w / 2, 0.28 * cm, label)
                c.restoreState()
                if idx < len(self.steps) - 1:
                    start_x = x + box_w + 0.07 * cm
                    end_x = x + box_w + self.gap - 0.07 * cm
                    arrow_y = self.box_h / 2
                    c.saveState()
                    c.setStrokeColor(colors.HexColor(GREEN))
                    c.setFillColor(colors.HexColor(GREEN))
                    c.setLineWidth(1)
                    c.line(start_x, arrow_y, end_x, arrow_y)
                    c.line(end_x, arrow_y, end_x - 4, arrow_y + 3)
                    c.line(end_x, arrow_y, end_x - 4, arrow_y - 3)
                    c.restoreState()
                x += box_w + self.gap

    def _tbl(font_size: float = 8.8) -> TableStyle:
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), display_bold),
            ("FONTNAME", (0, 1), (-1, -1), body_font),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor(GREEN_LIGHT)),
            ("INNERGRID", (0, 1), (-1, -1), 0.2, colors.HexColor("#D8E8D0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(GREEN_SOFT)]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])

    def _report_table(data: list, colWidths: list, style: TableStyle) -> RoundedTable:
        t = Table(data, colWidths=colWidths, repeatRows=1)
        t.setStyle(style)
        return RoundedTable(t)

    def _append_table(data: list, colWidths: list, style: TableStyle, after: float = 0.22 * cm) -> None:
        story.append(_report_table(data, colWidths=colWidths, style=style))
        story.append(Spacer(1, after))

    def _section_title(num, title: str) -> str:
        return _clean_text(f"{num}. {title}")

    def _cell(text, *, header: bool = False) -> Paragraph:
        return Paragraph(str(text), styles["TableHeader" if header else "TableCell"])

    def _wrap_rows(rows: list[list]) -> list[list]:
        wrapped = []
        for row_idx, row in enumerate(rows):
            wrapped.append([_cell(value, header=(row_idx == 0)) for value in row])
        return wrapped

    def _p2_cell(text: str, strong: bool = False) -> Paragraph:
        return Paragraph(text, styles["Part2CellStrong" if strong else "Part2Cell"])

    def _p2_header(text: str) -> Paragraph:
        return Paragraph(text, styles["Part2HeaderCell"])

    def header_footer(canvas, doc):
        canvas.saveState()
        margin = 1.8 * cm
        canvas.setStrokeColor(colors.HexColor(GREEN_LIGHT))
        canvas.setLineWidth(0.4)
        canvas.line(margin, A4[1] - 1.3 * cm, A4[0] - margin, A4[1] - 1.3 * cm)
        canvas.setFont(body_font, 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(margin, 0.9 * cm, f"Sicredi, Triagem SAC/PRSAC, {TODAY}")
        canvas.drawRightString(A4[0] - margin, 0.9 * cm, f"Página {doc.page}")
        if doc.page > 1:
            canvas.setFont(display_bold, 8)
            canvas.setFillColor(colors.HexColor(GREEN))
            canvas.drawString(margin, A4[1] - 1.1 * cm, f"{REPORT_TITLE}, {REPORT_TAGLINE}")
        canvas.restoreState()

    doc = BaseDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 0.8 * cm, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])

    story: list = []

    # Página 1
    story.append(Spacer(1, 1.8 * cm))
    story.append(Paragraph(REPORT_TITLE, styles["CoverTitle"]))
    story.append(Paragraph(REPORT_TAGLINE, styles["CoverSub"]))
    story.append(Paragraph(
        _clean_text(f"{REPORT_BANK}, {REPORT_ROLE}, {TODAY}"),
        styles["CoverSub"],
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "Documentação técnica da solução de triagem socioambiental SAC/PRSAC para quatro imóveis rurais (CAR). "
        "Mapas cartográficos por imóvel em <b>anexo</b> (<i>output/maps/</i>) e WebGIS.",
        styles["Body"],
    ))
    story.append(Paragraph(_section_title(1, "Objetivo"), styles["SectionH1"]))
    story.append(Paragraph(
        "Quantificar sobreposições com bases oficiais, classificar risco socioambiental, risco climático, "
        "pressão de entorno e classificação consolidada, com trilha auditável para Risco SAC/PRSAC. "
        "O CAR é unidade ambiental declaratória, não prova de domínio fundiário (Sparovek et al.; Atlas Imaflora).",
        styles["Body"],
    ))
    story.append(Paragraph(_section_title(2, "Arquitetura do repositório"), styles["SectionH1"]))
    arch_rows = [
        ["Camada", "Diretório", "Papel"],
        ["Config", "scripts/score_config.py", "Pesos internos da matriz de triagem (fonte única)"],
        ["Pipeline", "scripts/run_pipeline.py", "Execução unificada por perfil"],
        ["Etapas auditáveis", "scripts/00-14", "Ingestão, limpeza, cruzamento, score e export separados"],
        ["Dados brutos", "raw_data/", "CAR, IBAMA, FUNAI, MapBiomas, FBDS, clima"],
        ["Processado", "processed/geopackage/", "Camadas limpas e interseções dissolvidas"],
        ["Saídas", "output/tables|maps|report/", "CSVs, XLSX, PDF técnico e anexo cartográfico"],
        ["WebGIS", "frontend/src/data/", "JSON estático (scripts 08 e 14)"],
        ["API", "backend/", "FastAPI opcional sobre os JSONs"],
        ["Docs", "docs/", "Metodologia, fontes e matriz de triagem"],
    ]
    _append_table(
        _wrap_rows(arch_rows),
        colWidths=[3.2 * cm, 4.9 * cm, 7.4 * cm],
        style=_tbl(font_size=8.8),
        after=0.28 * cm,
    )
    story.append(Paragraph(
        f"<b>Bloqueante:</b> sem polígono CAR válido (<i>01_download_car.py</i>) o cruzamento não executa. "
        f"CRS visualização {CRS_DISPLAY}; área e overlay {CRS_AREA}.",
        styles["BodySmall"],
    ))
    story.append(Paragraph(
        "Os scripts numerados foram mantidos como trilha auditável, não como requisito de execução manual. "
        "O comando <i>run_pipeline.py</i> orquestra a rotina completa; as etapas separadas permitem reprocessar apenas "
        "a base ou métrica afetada, revisar evidências intermediárias e migrar a solução para scheduler/PostGIS com governança.",
        styles["BodySmall"],
    ))
    story.append(PageBreak())

    # Página 2
    story.append(Paragraph(_section_title(3, "Pipeline e fluxo de dados"), styles["SectionH1"]))
    pipe_rows = [
        ["Script", "Função", "Saída principal"],
        ["01_download_car", "Geometria CAR (bloqueante)", "cars_analisados.gpkg"],
        ["02-02e", "Bases oficiais, FBDS, clima, fogo", "raw_data/*"],
        ["03_clean_layers", "make_valid, CRS, área", "processed/geopackage/*"],
        ["04_intersections", "overlay + dissolve por tema", "intersections_wide.csv"],
        ["05_risk_scoring", "Restrição atual + classe", "risk_summary.csv"],
        ["06_generate_maps", "Anexo cartográfico em PDF", "anexo_mapas_socioambientais.pdf"],
        ["08/14", "Export WebGIS base + avançado", "frontend/src/data/*"],
        ["09-10", "Buffers 5/10 km, distâncias", "context_metrics, distances"],
        ["11-13", "Clima, entorno e classificação consolidada", "integrated_credit_risk.csv"],
    ]
    _append_table(
        _wrap_rows(pipe_rows),
        colWidths=[3.5 * cm, 5.4 * cm, 6.6 * cm],
        style=_tbl(font_size=8.8),
    )
    story.append(Paragraph(_section_title("3.1", "Módulos e cruzamento"), styles["SectionH2"]))
    story.append(Paragraph(
        "<b>utils_geo</b> (reprojeção, área, overlay, dissolve), <b>utils_sources</b> (registro de fontes), "
        "<b>utils_audit</b> (evidence_id rastreável), <b>utils_advanced</b> (buffers property/buffer/surroundings), "
        "<b>score_config</b> (pesos únicos para scripts e frontend). "
        "Cruzamento, <i>gpd.overlay(intersection)</i> + dissolve por tema + % sobre área CAR. "
        "Proximidade no entorno alimenta monitoramento, não gera restrição automática. APP FBDS cobre os 4 municípios do case.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "A granularidade dos scripts replica uma rotina controlável de risco: cada etapa deixa insumos, intermediários "
        "e saídas verificáveis em <i>raw_data/</i>, <i>processed/</i> ou <i>output/</i>. Para apresentação e reprodução do case, "
        "a interface operacional é o <i>scripts/run_pipeline.py</i>, com perfis <i>full</i>, <i>base</i>, <i>advanced</i> e <i>publish</i>.",
        styles["BodySmall"],
    ))
    # Metodologia + referências
    story.append(Paragraph(_section_title(4, "Metodologia de score e referências"), styles["SectionH1"]))
    story.append(Paragraph(
        "Três dimensões independentes convergem na classificação consolidada. A primeira mede restrição legal/objetiva no polígono CAR. "
        "A segunda mede risco climático prospectivo à capacidade de pagamento (IFRS S2, BCBS 2022). "
        "A terceira qualifica pressão territorial no entorno sem dupla contagem. As siglas internas do código (IRSA, ICRC, IPT e IRTC) "
        "não são rating regulatório; são nomes técnicos internos da solução. Pesos em <i>score_config.py</i>, calibrados por materialidade regulatória "
        "(PRSAC CMN 4.945, Res. CMN 4.943, MCR 2-9/CMN 5.193).",
        styles["Body"],
    ))

    story.append(Paragraph(_section_title("4.1", "Restrição, clima, entorno e síntese"), styles["SectionH2"]))
    labels = ["Embargo IBAMA", "Terra Indígena", "UC", "APP (FBDS)", "Desmatamento"]
    irsa_rows = [["Critério de restrição", "Peso", "Fórmula", "Base"]]
    bases = ["IBAMA PAMGIA", "FUNAI", "MMA/CNUC", "FBDS municipal", "MapBiomas/PRODES"]
    for label, base, (_pct, _ha, mx, mult) in zip(labels, bases, sc.IRSA_CRITERIA):
        irsa_rows.append([label, f"{mx}", f"min({mx}, %×{mult})", base])
    irsa_rows.append([
        "Pisos/classes", "", "",
        f"embargo≥{sc.IRSA_OVERRIDES['embargo_floor']}; TI≥{sc.IRSA_OVERRIDES['ti_floor']}; "
        f"Baixo≤{sc.IRSA_CLASS_MEDIO_SCORE}; Médio≤{sc.IRSA_CLASS_ALTO_SCORE}",
    ])
    _append_table(
        _wrap_rows(irsa_rows),
        colWidths=[3.0 * cm, 1.2 * cm, 3.8 * cm, 5.5 * cm],
        style=_tbl(font_size=8.5),
        after=0.18 * cm,
    )

    icrc_ipt_rows = [["Dimensão", "Componente", "Peso", "Fonte / escopo"]]
    for k, w in sc.ICRC_WEIGHTS.items():
        label, src = ICRC_DIM_LABELS.get(k, (k, ""))
        icrc_ipt_rows.append(["Clima", label, str(w), f"{src}, município + buffer"])
    for k, w in sc.IPT_WEIGHTS.items():
        label, src = IPT_DIM_LABELS.get(k, (k, ""))
        icrc_ipt_rows.append(["Entorno", label, str(w), f"{src}, anel 5-10 km"])
    _append_table(
        _wrap_rows(icrc_ipt_rows),
        colWidths=[1.8 * cm, 3.4 * cm, 1.2 * cm, 7.1 * cm],
        style=_tbl(font_size=8.5),
        after=0.22 * cm,
    )

    blend = sc.IRTC_BLEND
    prox = ", ".join(f"{int(d)}m={int(f*100)}%" for d, f in sc.PROXIMITY_BANDS_M)
    story.append(Paragraph(
        f"<b>Classificação consolidada</b> = {blend['irsa']:.0%} × restrição + {blend['icrc']:.0%} × clima + {blend['ipt']:.0%} × entorno. "
        f"Classes (&gt;{sc.IRTC_CLASS_ALTO} Alto; &gt;{sc.IRTC_CLASS_MEDIO} Médio) com <b>piso dimensional</b> "
        f"(<i>dimension_floor</i>). Entorno usa bandas {prox}. Bioma IBGE é contexto visual, fora do score.",
        styles["BodySmall"],
    ))

    story.append(Paragraph(_section_title("4.2", "Fontes oficiais e respaldo"), styles["SectionH2"]))
    ref_rows = [
        ["Tema", "Fonte", "Uso"],
        ["CAR", "SICAR", "Geometria base, bloqueante"],
        ["Embargo / TI / UC", "IBAMA, FUNAI, MMA-CNUC", "Restrição, materialidade regulatória"],
        ["Desmatamento", "MapBiomas, PRODES", "Risco socioambiental e pressão no entorno"],
        ["APP / hidro", "FBDS 1:25.000", "APP na restrição, água/hidro no clima"],
        ["Seca / fogo", "AdaptaBrasil, MapBiomas Fogo", "Clima prospectivo e entorno"],
        ["Regulatório", "CMN 4.943/4.945, 5.193; IFRS S2", "PRSAC, MCR, risco climático"],
    ]
    _append_table(
        _wrap_rows(ref_rows),
        colWidths=[2.2 * cm, 5.0 * cm, 6.3 * cm],
        style=_tbl(font_size=8.5),
        after=0.12 * cm,
    )
    story.append(Paragraph(
        "URLs, datas de obtenção, versão/escopo e confiança das bases ficam registrados em "
        "<i>processed/audit/source_registry.csv</i>, gerado pelo pipeline.",
        styles["BodySmall"],
    ))
    # Resultados
    story.append(Paragraph(_section_title(5, "Resultados consolidados (4 CARs)"), styles["SectionH1"]))
    res_rows = [["CAR", "UF", "Área (ha)", "Restr.", "Clima", "Entorno", "Consol.", "Classe"]]
    for _, r in merged.iterrows():
        area = r.get("area_ha", 0)
        irsa = r.get("current_restriction_score", r.get("restriction_score", 0))
        res_rows.append([
            str(r.get("car_id", "")),
            str(r.get("uf", "")),
            f"{float(area):.0f}" if pd.notna(area) else "",
            f"{float(irsa):.1f}" if pd.notna(irsa) else "",
            f"{float(r.get('icrc_score', 0)):.1f}",
            f"{float(r.get('ipt_score', 0)):.1f}",
            f"{float(r.get('irtc_score', 0)):.1f}",
            str(r.get("irtc_class", r.get("restriction_class", ""))),
        ])
    _append_table(
        _wrap_rows(res_rows),
        colWidths=[1.4 * cm, 0.8 * cm, 1.7 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, 1.8 * cm],
        style=_tbl(font_size=8.6),
        after=0.24 * cm,
    )
    story.append(Paragraph(
        "Breakdown, evidências e parecer por imóvel, <i>output/tables/</i>, WebGIS e painel <b>Parecer Técnico</b>.",
        styles["BodySmall"],
    ))
    story.append(Paragraph(_section_title(6, "Parte 2 do case, escala nacional e clima"), styles["Part2H1"]))
    story.append(Paragraph(
        "A solução proposta separa ingestão, processamento geoespacial, evidência auditável, decisão assistida e "
        "reprocessamento. Essa organização permite aplicar a mesma lógica de triagem a uma carteira nacional de CARs, "
        "com versionamento de bases, rastreabilidade dos resultados e governança SAC/PRSAC.",
        styles["Part2Body"],
    ))
    story.append(ProcessDiagram(doc.width))
    story.append(Spacer(1, 0.14 * cm))

    story.append(Paragraph(_section_title("6.1", "Arquitetura operacional para milhares de imóveis"), styles["Part2H2"]))
    scale_rows = [
        [_p2_header("Etapa"), _p2_header("Escala nacional"), _p2_header("Governança")],
        [
            _p2_cell("Entrada e validação"),
            _p2_cell("Lotes de CARs por proposta/carteira/cooperativa; API SICAR, espelho interno ou carga homologada."),
            _p2_cell("Deduplicação, status do lote, vínculo com crédito e fila para CAR inválido."),
        ],
        [
            _p2_cell("PostGIS analítico"),
            _p2_cell(f"Geometrias válidas, overlay em {CRS_AREA}, índice espacial, partição UF/município e dissolve por tema."),
            _p2_cell("source_layers, processing_runs, evidence e risk_scores versionados."),
        ],
        [
            _p2_cell("Score e governança"),
            _p2_cell("Risco socioambiental, climático, entorno e consolidado, com pesos em score_config.py."),
            _p2_cell("Alto/Crítico vai para validação humana; score não é decisão automática."),
        ],
        [
            _p2_cell("Consumo operacional"),
            _p2_cell("FastAPI, WebGIS, relatório por imóvel e painel para carteira/região/segunda linha."),
            _p2_cell("Alertas por sobreposição, mudança de classe, base expirada ou parecer."),
        ],
    ]
    scale_tbl = Table(scale_rows, colWidths=[3.3 * cm, 6.2 * cm, 6.0 * cm], repeatRows=1)
    scale_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), display_bold),
        ("FONTNAME", (0, 1), (-1, -1), body_font),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CFE3C3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(GREEN_SOFT)]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(scale_tbl)
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(
        "<b>Decisão de escala:</b> para FBDS, a execução local baixa por município; em produção, o desenho recomendado é espelho "
        "por UF em storage interno/PostGIS, com atualização controlada e custo marginal previsível por CAR.",
        styles["Part2Body"],
    ))

    story.append(Paragraph(_section_title("6.2", "Camada climática e complemento recomendado"), styles["Part2H2"]))
    story.append(Paragraph(
        "A solução já incorpora risco climático com seca municipal (AdaptaBrasil), água e hidrografia FBDS, fogo MapBiomas "
        "e sensibilidade agroterritorial. O complemento recomendado para produção é <b>estresse hídrico operacional</b>, "
        "por ligar risco climático físico à produtividade e ao fluxo de caixa rural. A dimensão climática permanece "
        "separada das restrições no imóvel: ela é variável prospectiva para monitoramento, prazo, mitigadores e acompanhamento.",
        styles["Part2Body"],
    ))

    story.append(Paragraph(
        f"<b>Implementação:</b> manter os layers já integrados e acrescentar WRI Aqueduct ou ANA/CEMADEN em "
        f"PostGIS raster/vector, com recorte por CAR/buffer, estatística zonal, cobertura mínima de "
        f"{sc.ICRC_MIN_COVERAGE_FOR_RESCALE}% e rescale quando houver lacuna.",
        styles["Part2Body"],
    ))
    story.append(Paragraph(
        "<b>Uso no crédito:</b> atualizar trimestralmente ou por safra, guardar o snapshot usado no parecer e tratar "
        "o indicador como apoio a prazo, garantias, monitoramento e encaminhamento especializado, sem criar bloqueio automático.",
        styles["Part2Body"],
    ))
    story.append(Paragraph(
        "<b>Anexos:</b> mapas em <i>output/maps/</i>; WebGIS em <i>frontend/</i>; docs em <i>docs/metodologia.md</i> "
        "e <i>docs/fontes.md</i>. IA apoiou estruturação de código e texto; cruzamentos, scores e nomenclaturas foram revisados manualmente.",
        styles["Part2Note"],
    ))

    doc.build(story)
    logger.info("PDF técnico gerado: %s", pdf_path)


def main():
    ensure_dir(PROJECT_ROOT / "output" / "report")

    pdf_path = PROJECT_ROOT / "output" / "report" / "relatorio_tecnico_sicredi.pdf"
    build_pdf(pdf_path)


if __name__ == "__main__":
    main()
