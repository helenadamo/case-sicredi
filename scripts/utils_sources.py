"""Registro e download de fontes oficiais."""
from __future__ import annotations

import csv
import logging
import os
import re
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

from utils_geo import CRS_DISPLAY, PROJECT_ROOT, ensure_dir, fix_geometries, reproject, standardize_columns

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()

SOURCE_REGISTRY_FIELDS = [
    "layer_name", "theme", "official_source", "url", "download_date",
    "file_name", "format", "crs", "notes", "confidence",
]

# URLs oficiais verificadas
URLS = {
    "ibama_shp": "https://pamgia.ibama.gov.br/geoservicos/arquivos/adm_embargo_ibama_a.shp.zip",
    "ibama_arcgis": "https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/adm_embargos_ibama_a/FeatureServer/0",
    "ibama_ckan": "https://dadosabertos.ibama.gov.br/api/3/action/package_show?id=termos-de-embargo",
    "funai_wfs": "https://geoserver.funai.gov.br/geoserver/Funai/ows",
    "mapbiomas_wfs": "http://production.alerta.mapbiomas.org/geoserver/mapbiomas-alertas/wfs",
    "mapbiomas_alerts_layer": "mapbiomas-alertas:crew_alerts",
    "prodes_wfs": "https://terrabrasilis.dpi.inpe.br/geoserver/ows",
    "sicar_base": "https://consultapublica.car.gov.br/publico",
}

OFFICIAL_SOURCES = {
    "car": {"theme": "imoveis_rurais", "official_source": "SICAR / CAR", "urls": [URLS["sicar_base"]], "confidence": "Alta"},
    "ibama_embargos": {"theme": "embargos_ambientais", "official_source": "IBAMA / PAMGIA", "urls": [URLS["ibama_shp"]], "confidence": "Alta"},
    "funai_ti": {"theme": "terras_indigenas", "official_source": "FUNAI", "urls": [URLS["funai_wfs"]], "confidence": "Alta"},
    "icmbio_uc": {"theme": "unidades_conservacao", "official_source": "ICMBio / CNUC", "urls": ["https://dadosabertos.mma.gov.br/"], "confidence": "Alta"},
    "mapbiomas_alerta": {"theme": "desmatamento", "official_source": "MapBiomas Alerta", "urls": [URLS["mapbiomas_wfs"]], "confidence": "Alta"},
    "prodes": {"theme": "desmatamento", "official_source": "INPE / PRODES", "urls": [URLS["prodes_wfs"]], "confidence": "Alta"},
    "climate": {"theme": "stress_hidrico", "official_source": "AdaptaBrasil MCTI", "urls": ["https://adaptabrasil.mcti.gov.br/"], "confidence": "Média"},
    "adaptabrasil_stress": {"theme": "stress_hidrico", "official_source": "AdaptaBrasil MCTI", "urls": ["https://adaptabrasil.mcti.gov.br/"], "confidence": "Média"},
    "adaptabrasil_suscetibilidade": {"theme": "suscetibilidade_erosao", "official_source": "AdaptaBrasil MCTI", "urls": ["https://adaptabrasil.mcti.gov.br/"], "confidence": "Média"},
    "fbds_app": {"theme": "app_fbds", "official_source": "FBDS", "urls": ["https://geo.fbds.org.br/"], "confidence": "Alta"},
    "fbds_hydro": {"theme": "hidrografia_fbds", "official_source": "FBDS", "urls": ["https://geo.fbds.org.br/"], "confidence": "Alta"},
    "mapbiomas_fogo": {"theme": "fogo_queimadas", "official_source": "MapBiomas Fogo Coleção 5", "urls": ["https://brasil.mapbiomas.org/mapbiomas-fogo/"], "confidence": "Alta"},
}

ADAPTABRASIL_API = "https://sistema.adaptabrasil.mcti.gov.br/api/geometria/data"
ADAPTABRASIL_INDICATORS = {
    "stress_hidrico": {"id": 2, "year": 2020, "label": "Risco de estresse hídrico"},
    "suscetibilidade_erosao": {"id": 27, "year": 2020, "label": "Áreas com solos susceptíveis à erosão"},
    "seca_agro": {"id": 5, "year": 2020, "label": "Risco agroclimático"},
    "seguranca_hidrica": {"id": 8, "year": 2020, "label": "Segurança hídrica"},
}


def registry_path() -> Path:
    return PROJECT_ROOT / "processed" / "audit" / "source_registry.csv"


def load_registry() -> pd.DataFrame:
    path = registry_path()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=SOURCE_REGISTRY_FIELDS)


def append_registry(entry: dict) -> None:
    path = registry_path()
    ensure_dir(path.parent)
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SOURCE_REGISTRY_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: entry.get(k, "") for k in SOURCE_REGISTRY_FIELDS})


def log_source(layer_name: str, key: str, file_name: str, fmt: str, crs: str, notes: str,
               confidence: Optional[str] = None, url: Optional[str] = None):
    meta = OFFICIAL_SOURCES.get(key, {})
    append_registry({
        "layer_name": layer_name,
        "theme": meta.get("theme", key),
        "official_source": meta.get("official_source", key),
        "url": url or meta.get("urls", [""])[0],
        "download_date": TODAY,
        "file_name": file_name,
        "format": fmt,
        "crs": crs,
        "notes": notes,
        "confidence": confidence or meta.get("confidence", "Média"),
    })


def download_file(url: str, dest: Path, timeout: int = 300) -> bool:
    try:
        logger.info("Baixando %s", url)
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "SicrediCase/1.0"}, stream=True)
        resp.raise_for_status()
        ensure_dir(dest.parent)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                f.write(chunk)
        return True
    except Exception as exc:
        logger.warning("Falha ao baixar %s: %s", url, exc)
        return False


def download_zip_shapefile(url: str, dest_dir: Path) -> Optional[Path]:
    try:
        logger.info("Baixando shapefile %s", url)
        resp = requests.get(url, timeout=600, headers={"User-Agent": "SicrediCase/1.0"})
        resp.raise_for_status()
        ensure_dir(dest_dir)
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            zf.extractall(dest_dir)
        shp_files = list(dest_dir.glob("**/*.shp"))
        return shp_files[0] if shp_files else None
    except Exception as exc:
        logger.warning("Falha zip %s: %s", url, exc)
        return None


def clip_bbox(gdf: gpd.GeoDataFrame, bbox: Optional[tuple]) -> gpd.GeoDataFrame:
    if gdf.empty or bbox is None:
        return gdf
    gdf = reproject(gdf, CRS_DISPLAY)
    try:
        return gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    except Exception:
        return gdf


def fetch_ibama_embargos(bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
    """IBAMA via shapefile oficial PAMGIA (CKAN) ou ArcGIS REST."""
    raw_dir = PROJECT_ROOT / "raw_data" / "ibama_embargos"

    # 1) Shapefile oficial
    shp = download_zip_shapefile(URLS["ibama_shp"], raw_dir / "pamgia")
    if shp:
        gdf = fix_geometries(standardize_columns(gpd.read_file(shp)))
        gdf = clip_bbox(gdf, bbox)
        log_source("embargos_ibama", "ibama_embargos", shp.name, "SHP", str(gdf.crs),
                   f"IBAMA PAMGIA :  {len(gdf)} feições", url=URLS["ibama_shp"])
        return gdf

    # 2) ArcGIS REST com recorte espacial
    logger.info("Tentando IBAMA ArcGIS REST...")
    try:
        if bbox:
            geom = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
            url = (
                f"{URLS['ibama_arcgis']}/query?geometry={geom}&geometryType=esriGeometryEnvelope"
                "&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*"
                "&returnGeometry=true&f=geojson&resultRecordCount=2000"
            )
        else:
            url = f"{URLS['ibama_arcgis']}/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson&resultRecordCount=2000"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        gdf = gpd.read_file(BytesIO(resp.content))
        gdf = fix_geometries(standardize_columns(gdf))
        log_source("embargos_ibama", "ibama_embargos", "arcgis_rest", "GeoJSON", CRS_DISPLAY,
                   f"IBAMA ArcGIS REST :  {len(gdf)} feições", url=URLS["ibama_arcgis"])
        return gdf
    except Exception as exc:
        logger.warning("IBAMA ArcGIS: %s", exc)

    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_funai_ti(bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
    """FUNAI via geobr (mirror oficial) ou WFS."""
    try:
        import geobr
        gdf = geobr.read_indigenous_land(simplified=True)
        gdf = fix_geometries(standardize_columns(gdf))
        gdf = gdf.rename(columns={"terrai_nom": "nome", "fase_ti": "fase", "etnia_nome": "etnia", "abbrev_state": "uf"})
        gdf["fonte"] = "FUNAI/geobr"
        if gdf.crs is None:
            gdf = gdf.set_crs(CRS_DISPLAY)
        gdf = clip_bbox(gdf, bbox)
        log_source("terras_indigenas", "funai_ti", "geobr", "GPKG", str(gdf.crs),
                   f"FUNAI via geobr :  {len(gdf)} TIs", url="https://geobr.github.io/geobr/")
        return gdf
    except Exception as exc:
        logger.warning("FUNAI geobr: %s", exc)
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_uc(bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
    try:
        import geobr
        gdf = geobr.read_conservation_units(simplified=True)
        gdf = fix_geometries(standardize_columns(gdf))
        gdf = gdf.rename(columns={
            "name_conservation_unit": "nome", "category": "categoria",
            "group": "grupo", "government_level": "esfera",
        })
        gdf["fonte"] = "ICMBio/CNUC via geobr"
        if gdf.crs is None:
            gdf = gdf.set_crs(CRS_DISPLAY)
        gdf = clip_bbox(gdf, bbox)
        log_source("unidades_conservacao", "icmbio_uc", "geobr", "GPKG", str(gdf.crs),
                   f"CNUC via geobr :  {len(gdf)} UCs")
        return gdf
    except Exception as exc:
        logger.warning("UC geobr: %s", exc)
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_mapbiomas_alerts(bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
    """MapBiomas Alerta via WFS production (HTTP)."""
    if bbox is None:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
    try:
        bbox_str = ",".join(map(str, bbox)) + ",EPSG:4326"
        url = (
            f"{URLS['mapbiomas_wfs']}?service=WFS&version=1.0.0&request=GetFeature"
            f"&typeName={URLS['mapbiomas_alerts_layer']}&outputFormat=application/json"
            f"&bbox={bbox_str}&maxFeatures=5000"
        )
        logger.info("MapBiomas Alerta WFS (bbox)...")
        resp = requests.get(url, timeout=300, headers={"User-Agent": "SicrediCase/1.0"})
        if resp.status_code == 200 and b"FeatureCollection" in resp.content:
            gdf = gpd.read_file(BytesIO(resp.content))
            gdf = fix_geometries(standardize_columns(gdf))
            gdf["fonte"] = "MapBiomas Alerta"
            log_source("desmatamento_alerta", "mapbiomas_alerta", "crew_alerts_wfs", "GeoJSON",
                       CRS_DISPLAY, f"MapBiomas crew_alerts :  {len(gdf)} alertas", url=URLS["mapbiomas_wfs"])
            return gdf
    except Exception as exc:
        logger.warning("MapBiomas WFS: %s", exc)
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_adaptabrasil_indicator(
    indicator_key: str,
    ibge_codes: Optional[list[str]] = None,
    bbox: Optional[tuple] = None,
) -> gpd.GeoDataFrame:
    """Baixa indicador municipal do AdaptaBrasil (índice 0–1 por município)."""
    meta = ADAPTABRASIL_INDICATORS.get(indicator_key)
    if not meta:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)

    indicator_id = meta["id"]
    year = meta["year"]
    api_url = (
        f"{ADAPTABRASIL_API}/{indicator_id}/BR/null/{year}/municipio/GEOJSONz/adaptabrasil"
    )
    try:
        resp = requests.get(api_url, timeout=120, headers={"User-Agent": "SicrediCase/1.0"})
        resp.raise_for_status()
        payload = resp.json()
        cache_url = payload.get("location")
        if not cache_url:
            logger.warning("AdaptaBrasil %s sem URL de cache: %s", indicator_key, payload)
            return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)

        zip_resp = requests.get(cache_url, timeout=300, headers={"User-Agent": "SicrediCase/1.0"})
        zip_resp.raise_for_status()
        with zipfile.ZipFile(BytesIO(zip_resp.content)) as zf:
            geojson_name = next((n for n in zf.namelist() if n.endswith(".geojson")), None)
            if not geojson_name:
                return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
            gdf = gpd.read_file(BytesIO(zf.read(geojson_name)))

        gdf = fix_geometries(standardize_columns(gdf))
        gdf = gdf.rename(columns={"geocod_ibge": "ibge_muni", "name": "municipio"})
        gdf["indicador"] = indicator_key
        gdf["indicador_label"] = meta["label"]
        gdf["indicador_id"] = indicator_id
        gdf["ano"] = year
        gdf["fonte"] = "AdaptaBrasil MCTI"
        if "value" in gdf.columns:
            gdf["indice"] = pd.to_numeric(gdf["value"], errors="coerce")
        else:
            gdf["indice"] = pd.NA
        gdf["ibge_muni"] = gdf["ibge_muni"].astype(str).str.strip()

        if ibge_codes:
            codes = {str(c).strip() for c in ibge_codes}
            gdf = gdf[gdf["ibge_muni"].isin(codes)]

        gdf = clip_bbox(gdf, bbox)
        registry_key = (
            "adaptabrasil_stress" if indicator_key == "stress_hidrico" else "adaptabrasil_suscetibilidade"
        )
        log_source(
            f"adaptabrasil_{indicator_key}",
            registry_key,
            f"indicador_{indicator_id}_{year}.geojson",
            "GeoJSON",
            CRS_DISPLAY,
            f"AdaptaBrasil {meta['label']} ({year}) : {len(gdf)} municípios",
            url=api_url,
        )
        return gdf
    except Exception as exc:
        logger.warning("AdaptaBrasil %s: %s", indicator_key, exc)
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_prodes(bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
    """PRODES via TerraBrasilis WFS."""
    layer_candidates = [
        "prodes-legal-amz:yearly_deforestation",
        "prodes-amazon-nb:yearly_deforestation",
        "prodes-cerrado-nb:yearly_deforestation",
    ]
    for layer in layer_candidates:
        try:
            params = {
                "service": "WFS", "version": "1.0.0", "request": "GetFeature",
                "typeName": layer, "outputFormat": "application/json", "maxFeatures": 3000,
            }
            if bbox:
                params["bbox"] = ",".join(map(str, bbox)) + ",EPSG:4326"
            resp = requests.get(URLS["prodes_wfs"], params=params, timeout=180)
            if resp.status_code == 200 and len(resp.content) > 500 and b"Feature" in resp.content:
                gdf = gpd.read_file(BytesIO(resp.content))
                gdf = fix_geometries(standardize_columns(gdf))
                gdf["fonte"] = "PRODES/INPE"
                log_source("desmatamento_prodes", "prodes", layer, "WFS", CRS_DISPLAY,
                           f"PRODES :  {len(gdf)} polígonos", url=URLS["prodes_wfs"])
                return gdf
        except Exception as exc:
            logger.debug("PRODES %s: %s", layer, exc)
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def fetch_wfs_layer(
    wfs_url: str, type_name: str, bbox: Optional[tuple] = None,
    cql_filter: Optional[str] = None, max_features: int = 5000,
    version: str = "1.0.0", output_format: str = "application/json",
) -> gpd.GeoDataFrame:
    params = {
        "service": "WFS", "version": version, "request": "GetFeature",
        "typeName": type_name, "outputFormat": output_format, "maxFeatures": max_features,
    }
    if bbox:
        params["bbox"] = ",".join(map(str, bbox)) + ",EPSG:4326"
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
    try:
        resp = requests.get(wfs_url, params=params, timeout=180)
        resp.raise_for_status()
        if b"FeatureCollection" not in resp.content and b"features" not in resp.content:
            return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)
        return gpd.read_file(BytesIO(resp.content))
    except Exception as exc:
        logger.warning("WFS %s/%s: %s", wfs_url, type_name, exc)
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def download_sicar_municipality(muni_code: int, folder: Path, tries: int = 20) -> Optional[Path]:
    """Download CAR municipal via consultapublica (menor que estadual)."""
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for tp in tesseract_paths:
        if Path(tp).exists():
            os.environ["PATH"] = str(Path(tp).parent) + os.pathsep + os.environ.get("PATH", "")
            break

    try:
        from download_car import DownloadCar
        from urllib.parse import urlencode
        import time, random

        dc = DownloadCar()
        ensure_dir(folder)
        zip_path = folder / f"{muni_code}_AREA_IMOVEL.zip"

        while tries > 0:
            try:
                captcha = dc._driver.get_captcha(dc._download_captcha())
                if len(captcha) != 5:
                    tries -= 1
                    continue
                query = urlencode({
                    "idMunicipio": muni_code,
                    "tipoBase": "AREA_IMOVEL",
                    "ReCaptcha": captcha,
                })
                url = f"{URLS['sicar_base']}/municipios/downloadBase?{query}"
                resp = dc._get(url, timeout=300)
                if resp.status_code == 200 and "zip" in resp.headers.get("content-type", "").lower():
                    zip_path.write_bytes(resp.content)
                    logger.info("Município %d baixado (%d bytes)", muni_code, len(resp.content))
                    return zip_path
            except Exception as exc:
                logger.warning("Município %d tentativa: %s", muni_code, str(exc)[:80])
            tries -= 1
            time.sleep(random.random() + 1)
    except Exception as exc:
        logger.warning("download município %d: %s", muni_code, exc)
    return None


def download_sicar_state(uf: str, folder: Path, tries: int = 15) -> Optional[Path]:
    """Download CAR estadual via biblioteca download-car (consultapublica + captcha)."""
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for tp in tesseract_paths:
        if Path(tp).exists():
            os.environ["PATH"] = str(Path(tp).parent) + os.pathsep + os.environ.get("PATH", "")
            break

    try:
        from download_car import DownloadCar, State, Polygon
        dc = DownloadCar()
        result = dc.download_state(
            State(uf.upper()), Polygon.AREA_PROPERTY, folder=str(folder),
            tries=tries, debug=False, timeout=300, max_retries=8,
        )
        if result and result is not False:
            return Path(result)
    except Exception as exc:
        logger.warning("download-car estado %s: %s", uf, exc)
    return None


def car_code_variants(code: str) -> list[str]:
    """Gera variantes do código CAR: compacto, com hífens, maiúsculas."""
    raw = str(code).strip().upper().replace(" ", "")
    variants = {raw, raw.replace("-", "")}
    compact = raw.replace("-", "")
    m = re.match(r"^([A-Z]{2})(\d{7})([A-F0-9]+)$", compact)
    if m:
        hyphenated = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        variants.add(hyphenated)
        variants.add(compact)
    return list(variants)


def filter_car_from_shapefile(shp_path: Path, car_code: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp_path)
    gdf = standardize_columns(fix_geometries(gdf))
    col = None
    for c in gdf.columns:
        if any(x in c for x in ["cod_imovel", "car", "cod_car"]):
            col = c
            break
    if col is None:
        for c in gdf.columns:
            if "cod" in c:
                col = c
                break
    if col is None:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)

    # Normalizar coluna: remover hífens para comparação flexível
    gdf["_car_norm"] = gdf[col].astype(str).str.upper().str.replace("-", "").str.strip()
    target_norm = car_code.upper().replace("-", "")
    filtered = gdf[gdf["_car_norm"] == target_norm]
    if not filtered.empty:
        return filtered.drop(columns=["_car_norm"], errors="ignore")

    # Tentar match parcial pelas variantes
    for variant in car_code_variants(car_code):
        vnorm = variant.replace("-", "")
        filtered = gdf[gdf["_car_norm"] == vnorm]
        if not filtered.empty:
            return filtered.drop(columns=["_car_norm"], errors="ignore")
    return gpd.GeoDataFrame(geometry=[], crs=CRS_DISPLAY)


def extract_shapefile_from_zip(zip_path: Path, dest: Path) -> Optional[Path]:
    ensure_dir(dest)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    shps = list(dest.glob("**/*.shp"))
    return shps[0] if shps else None
