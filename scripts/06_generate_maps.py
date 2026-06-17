"""Mapas cartograficos de relatorio, layout visual Sicredi."""
from __future__ import annotations

import logging
import shutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils_geo import CRS_AREA, PROJECT_ROOT, ensure_dir, reproject

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CRS_WEB = "EPSG:3857"
SATELLITE = ctx.providers.Esri.WorldImagery

# Folha paisagem fixa (consistencia visual no PDF)
SHEET_SIZE = (13.8, 9.75)
MAP_DPI = 180
LOGO_PATH = PROJECT_ROOT / "frontend" / "public" / "sicredi-logo-clean.png"
MAPS_PDF_PATH = PROJECT_ROOT / "output" / "maps" / "anexo_mapas_socioambientais.pdf"
TMP_MAP_DIR = PROJECT_ROOT / "output" / "maps" / "_tmp"

PALETTE = {
    "green_dark": "#146E37",
    "green": "#3FA110",
    "green_light": "#D7E6C8",
    "green_soft": "#EDF6E6",
    "yellow": "#FFCD00",
    "text": "#2A3328",
    "muted": "#5A645A",
    "panel": "#FAFCF8",
    "grid": "#FFFFFF",
}

LAYERS = {
    "car": ("#146E37", "Perimetro CAR"),
    "embargos": ("#C62828", "Embargos IBAMA"),
    "ti": ("#730028", "Terras Indigenas"),
    "uc": ("#3FA110", "Unidades de Conservacao"),
    "desmatamento": ("#FF6400", "Desmatamento"),
    "app": ("#1E88A8", "APP (FBDS)"),
}

FONT_DIR = PROJECT_ROOT / "assets" / "fonts"


@dataclass
class LegendItem:
    color: str
    label: str
    subtitle: str = ""


class CartographicSheet:
    """Mapa no layout visual do anexo: header Sicredi, satelite e painel lateral."""

    def __init__(self, title: str, subtitle: str, sheet_id: str):
        self.title = title
        self.subtitle = subtitle
        self.sheet_id = sheet_id
        self.header_y = 0.885
        self.panel_x = 0.742
        self.panel_w = 0.258
        self.map_w = self.panel_x + 0.025
        self.bounds: tuple[float, float, float, float] | None = None

        self.fig = plt.figure(figsize=SHEET_SIZE, facecolor="white", dpi=100)
        self.ax_map = self.fig.add_axes([0.0, 0.0, self.map_w, self.header_y])
        self.ax_side = self.fig.add_axes([self.panel_x, 0.0, self.panel_w, self.header_y])
        self.ax_map.set_zorder(1)
        self.ax_side.set_zorder(9)
        self.ax_side.set_axis_off()
        self.ax_side.set_xlim(0, 1)
        self.ax_side.set_ylim(0, 1)
        self.ax_side.patch.set_alpha(0)
        self._fonts = _load_fonts()

    @property
    def map_aspect(self) -> float:
        return (self.map_w * SHEET_SIZE[0]) / (self.header_y * SHEET_SIZE[1])

    def _font(self, kind: str) -> str:
        return self._fonts.get(kind, "DejaVu Sans")

    def draw_chrome(self) -> None:
        header = Rectangle(
            (0, self.header_y), 1, 1 - self.header_y,
            transform=self.fig.transFigure,
            facecolor=PALETTE["green_dark"], edgecolor="none", zorder=20,
        )
        panel = FancyBboxPatch(
            (self.panel_x, 0), self.panel_w + 0.04, self.header_y,
            boxstyle="round,pad=0.0,rounding_size=0.03",
            transform=self.fig.transFigure,
            facecolor="white", edgecolor="none", zorder=8,
        )
        self.fig.patches.extend([header, panel])

        if LOGO_PATH.exists():
            ax_logo = self.fig.add_axes([0.026, self.header_y + 0.026, 0.047, 0.062], zorder=22)
            ax_logo.imshow(mpimg.imread(LOGO_PATH))
            ax_logo.set_axis_off()

        self.fig.text(
            0.098, self.header_y + 0.055, self.title,
            fontfamily=self._font("display"), fontsize=15.5,
            color="white", va="center", ha="left", zorder=22,
        )
        self.fig.text(
            0.963, self.header_y + 0.055, self.subtitle,
            fontfamily=self._font("body"), fontsize=10.7,
            color="white", va="center", ha="right", zorder=22,
        )

    def draw_basemap(self, bounds: tuple[float, float, float, float]) -> None:
        self.bounds = _fit_bounds_to_aspect(bounds, self.map_aspect)
        ax = self.ax_map
        ax.set_xlim(self.bounds[0], self.bounds[2])
        ax.set_ylim(self.bounds[1], self.bounds[3])
        ax.set_facecolor("#152316")
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()
        try:
            ctx.add_basemap(ax, crs=CRS_WEB, source=SATELLITE, zoom="auto", attribution=False, reset_extent=False)
        except Exception as exc:
            logger.warning("Basemap satelite indisponivel (%s)", exc)
        ax.set_xlim(self.bounds[0], self.bounds[2])
        ax.set_ylim(self.bounds[1], self.bounds[3])
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()

    def draw_legend_panel(self, title: str, items: list[LegendItem], notes: list[str] | None = None) -> None:
        ax = self.ax_side
        ax.text(
            0.12, 0.95, title,
            fontfamily=self._font("display"), fontsize=11.5, fontweight="bold",
            color=PALETTE["green"], transform=ax.transAxes, va="top",
        )

        y = 0.875
        for item in items:
            swatch_h = 0.031
            swatch_w = swatch_h * (self.header_y * SHEET_SIZE[1]) / (self.panel_w * SHEET_SIZE[0])
            swatch = FancyBboxPatch(
                (0.13, y - swatch_h / 2), swatch_w, swatch_h,
                boxstyle="round,pad=0.002,rounding_size=0.006",
                transform=ax.transAxes,
                facecolor=item.color, edgecolor="none", alpha=0.95,
            )
            ax.add_patch(swatch)
            text_x = 0.13 + swatch_w + 0.065
            ax.text(
                text_x, y + 0.008, item.label,
                fontfamily=self._font("body"), fontsize=9.7,
                color=PALETTE["green_dark"], transform=ax.transAxes, va="center",
            )
            if item.subtitle:
                ax.text(
                    text_x, y - 0.026, item.subtitle,
                    fontfamily=self._font("body"), fontsize=7.6,
                    color=PALETTE["muted"], transform=ax.transAxes, va="center",
                )
                y -= 0.083
            else:
                y -= 0.064

        if notes:
            note_y = min(0.32, y - 0.055)
            ax.text(
                0.12, note_y, "Notas",
                fontfamily=self._font("display"), fontsize=11.0, fontweight="bold",
                color=PALETTE["green"], transform=ax.transAxes, va="top",
            )
            ny = note_y - 0.060
            for note in notes:
                for idx, line in enumerate(textwrap.wrap(note, width=30)):
                    ax.text(
                        0.13, ny, f"- {line}" if idx == 0 else f"  {line}",
                        fontfamily=self._font("body"), fontsize=8.6,
                        color=PALETTE["green_dark"], transform=ax.transAxes, va="top",
                    )
                    ny -= 0.034
                ny -= 0.018

    def draw_scale_north(self, bounds: tuple[float, float, float, float]) -> None:
        active_bounds = self.bounds or bounds
        ax = self.ax_map
        minx, miny, maxx, maxy = active_bounds
        w, h = maxx - minx, maxy - miny
        bar_m = _nice_scale_bar_length(w)
        x0 = minx + w * 0.052
        y0 = miny + h * 0.058
        seg = bar_m / 2
        box_pad_x = bar_m * 0.18
        box_h = h * 0.060

        ax.add_patch(FancyBboxPatch(
            (x0 - box_pad_x, y0 - box_h * 0.45), bar_m + box_pad_x * 2, box_h * 1.25,
            boxstyle=f"round,pad=0.0,rounding_size={box_h * 0.12}",
            facecolor="white", edgecolor="none", alpha=0.92, zorder=20,
        ))
        label = f"{bar_m / 1000:.0f} km" if bar_m >= 1000 else f"{bar_m:.0f} m"
        ax.text(
            x0 + bar_m / 2, y0 + box_h * 0.25, label,
            ha="center", va="bottom", fontsize=8.5, fontweight="bold",
            fontfamily=self._font("body"), color=PALETTE["text"], zorder=22,
        )
        for start, col in [(0, PALETTE["green_dark"]), (seg, "white")]:
            ax.add_patch(Rectangle(
                (x0 + start, y0 - box_h * 0.12), seg, box_h * 0.16,
                facecolor=col, edgecolor=PALETTE["green_dark"], linewidth=1.0, zorder=21,
            ))

    def draw_locator_inset(self, *_args, **_kwargs) -> None:
        return None

    def save(self, path: Path, *, write_pdf: bool = False) -> Path:
        ensure_dir(path.parent)
        save_kwargs = {
            "dpi": MAP_DPI,
            "facecolor": "white",
            "edgecolor": "none",
            "pad_inches": 0,
        }
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            save_kwargs["pil_kwargs"] = {"quality": 82, "optimize": True, "progressive": True}
        self.fig.savefig(path, **save_kwargs)
        if write_pdf and path.suffix.lower() != ".pdf":
            self.fig.savefig(path.with_suffix(".pdf"), facecolor="white", edgecolor="none", pad_inches=0)
        plt.close(self.fig)
        return path


def _ensure_fonts() -> dict[str, Path]:
    """Registra fontes locais do projeto quando disponíveis."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for path in FONT_DIR.glob("*.ttf"):
        out[path.name] = path
    return out


_FONTS_CACHE: dict[str, str] | None = None


def _load_fonts() -> dict[str, str]:
    global _FONTS_CACHE
    if _FONTS_CACHE is not None:
        return _FONTS_CACHE
    files = _ensure_fonts()
    display, body = "Segoe UI", "Segoe UI"
    available = {f.name for f in fm.fontManager.ttflist}
    if "Segoe UI" not in available:
        display, body = "DejaVu Sans", "DejaVu Sans"
    for path in files.values():
        try:
            fm.fontManager.addfont(str(path))
            prop = fm.FontProperties(fname=str(path))
            name = prop.get_name()
            if "Exo" in name:
                display = name
            if "Nunito" in name:
                body = name
        except Exception:
            continue
    _FONTS_CACHE = {"display": display, "body": body}
    return _FONTS_CACHE


def _nice_grid_step(span_m: float) -> float:
    raw = span_m / 5
    return max(10 ** np.floor(np.log10(max(raw, 1))), 1)


def _nice_scale_bar_length(width_m: float) -> float:
    target = width_m * 0.22
    bar = 10 ** np.floor(np.log10(max(target, 10)))
    while bar > target:
        bar /= 2
    if bar < 1:
        bar = max(target * 0.5, 10)
    return bar


def _bounds_with_pad(gdf: gpd.GeoDataFrame, pad_ratio: float = 0.22) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = gdf.total_bounds
    pad_x = max((maxx - minx) * pad_ratio, 400)
    pad_y = max((maxy - miny) * pad_ratio, 400)
    return minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y


def _fit_bounds_to_aspect(bounds: tuple[float, float, float, float], target_aspect: float):
    minx, miny, maxx, maxy = bounds
    w, h = max(maxx - minx, 1.0), max(maxy - miny, 1.0)
    current = w / h
    if current < target_aspect:
        extra = (h * target_aspect - w) / 2
        return minx - extra, miny, maxx + extra, maxy
    extra = (w / target_aspect - h) / 2
    return minx, miny - extra, maxx, maxy + extra


def _plot_halo(ax, gdf: gpd.GeoDataFrame, color: str, *, alpha: float = 0.82, lw: float = 1.6, zorder: int = 6):
    if gdf.empty:
        return
    gdf.plot(ax=ax, facecolor="none", edgecolor="white", linewidth=lw + 0.45, zorder=zorder)
    gdf.plot(ax=ax, facecolor=color, edgecolor="white", linewidth=max(lw * 0.55, 0.35), alpha=alpha, zorder=zorder + 1)


def mapa_por_imovel(car_id: str) -> Path | None:
    cars = gpd.read_file(PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg")
    car = cars[cars["id"] == car_id]
    if car.empty:
        return None

    car = reproject(car, CRS_AREA)
    row0 = car.iloc[0]
    label = row0["label"]
    area = row0.get("area_ha", 0)

    layer_defs = {
        "intersect_embargos": "embargos",
        "intersect_ti": "ti",
        "intersect_uc": "uc",
        "intersect_desmatamento": "desmatamento",
        "intersect_app": "app",
    }

    plot_layers: list[tuple[gpd.GeoDataFrame, str]] = []
    inter_path = PROJECT_ROOT / "processed" / "geopackage" / "intersections.gpkg"
    all_geoms = [car]
    if inter_path.exists():
        for layer_name, key in layer_defs.items():
            try:
                inter = gpd.read_file(inter_path, layer=layer_name)
                inter = inter[inter["car_id"] == car_id]
                if not inter.empty:
                    inter = reproject(inter, CRS_AREA)
                    all_geoms.append(inter)
                    plot_layers.append((inter, key))
            except Exception:
                pass

    combined = gpd.GeoDataFrame(pd.concat(all_geoms, ignore_index=True), geometry="geometry", crs=CRS_AREA)
    car_web = reproject(car, CRS_WEB)
    bounds = _bounds_with_pad(reproject(combined, CRS_WEB), 0.20)

    sheet = CartographicSheet(
        "Mapa de Analise Socioambiental",
        f"{label} - {car_id} - {area:,.0f} ha".replace(",", "."),
        f"MAP-{car_id}",
    )
    sheet.draw_chrome()
    sheet.draw_basemap(bounds)

    _plot_halo(sheet.ax_map, car_web, LAYERS["car"][0], alpha=0.30, lw=1.1, zorder=5)
    legend_items = [LegendItem(LAYERS["car"][0], LAYERS["car"][1], "Limite declaratorio SICAR")]

    for gdf, key in plot_layers:
        color, name = LAYERS[key]
        _plot_halo(sheet.ax_map, reproject(gdf, CRS_WEB), color, alpha=0.84, lw=0.6, zorder=7)
        legend_items.append(LegendItem(color, name, "Intersecao confirmada"))

    sheet.draw_scale_north(bounds)
    sheet.draw_locator_inset(car, all_cars=cars, highlight_id=car_id)
    sheet.draw_legend_panel(
        "Legenda",
        legend_items,
        notes=[
            "Sobreposicoes calculadas em EPSG:5880 e exibidas sem distorcao.",
            "Areas de intersecao refletem dissolve por tema no pipeline.",
        ],
    )

    out = TMP_MAP_DIR / f"{car_id}.jpg"
    sheet.save(out)
    logger.info("Mapa %s: %s", car_id, out)
    return out


def build_pdf_anexo(map_paths: list[Path]) -> None:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    ensure_dir(MAPS_PDF_PATH.parent)
    page_w, page_h = SHEET_SIZE[0] * 72, SHEET_SIZE[1] * 72
    pdf = canvas.Canvas(str(MAPS_PDF_PATH), pagesize=(page_w, page_h))

    for img_path in map_paths:
        if not img_path.exists():
            logger.warning("Mapa ausente no anexo: %s", img_path)
            continue
        pdf.drawImage(ImageReader(str(img_path)), 0, 0, width=page_w, height=page_h, mask="auto")
        pdf.showPage()

    pdf.save()
    logger.info("Anexo PDF de mapas: %s", MAPS_PDF_PATH)


def main():
    _load_fonts()
    if TMP_MAP_DIR.exists():
        shutil.rmtree(TMP_MAP_DIR)
    cars = gpd.read_file(PROJECT_ROOT / "processed" / "geopackage" / "cars_analisados.gpkg")
    car_ids = list(cars["id"])
    map_paths = []
    for car_id in car_ids:
        map_path = mapa_por_imovel(car_id)
        if map_path:
            map_paths.append(map_path)
    build_pdf_anexo(map_paths)
    if TMP_MAP_DIR.exists():
        shutil.rmtree(TMP_MAP_DIR)
    logger.info("Mapas gerados.")


if __name__ == "__main__":
    main()


