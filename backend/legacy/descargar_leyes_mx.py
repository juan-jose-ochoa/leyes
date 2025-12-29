#!/usr/bin/env python3
"""
Descargador de Leyes y Reglamentos Fiscales/Laborales de México
Fuentes oficiales: Cámara de Diputados, DOF, SAT, STPS, IMSS, INFONAVIT

Autor: Script para legal-tech / DevOps
Versión: 1.0
Licencia: MIT
"""

import os
import sys
import json
import csv
import hashlib
import shutil
import logging
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from urllib.parse import urljoin, urlparse, unquote, parse_qs
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from unidecode import unidecode
from tqdm import tqdm

# Importar URLs conocidas
try:
    from urls_conocidas import (
        LEYES_CAMARA_DIPUTADOS,
        REGLAMENTOS_CAMARA_DIPUTADOS,
        MISCELANEAS_SAT,
        PATRONES_ARCHIVOS_DIPUTADOS,
    )
except ImportError:
    LEYES_CAMARA_DIPUTADOS = []
    REGLAMENTOS_CAMARA_DIPUTADOS = []
    MISCELANEAS_SAT = []
    PATRONES_ARCHIVOS_DIPUTADOS = {}

# ============================================================================
# CONFIGURACION
# ============================================================================

BASE_DIR = Path(__file__).parent.parent / "doc"
LOGS_DIR = BASE_DIR / "logs"
VERSIONS_DIR = BASE_DIR / "versions"

# Directorios por tipo
DIRS = {
    "ley": BASE_DIR / "leyes",
    "reglamento": BASE_DIR / "reglamentos",
    "miscelanea": BASE_DIR / "miscelanea",
    "dof": BASE_DIR / "dof",
}

# User-Agent realista
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Configuración de red
TIMEOUT = 90
MAX_RETRIES = 5
DELAY_ENTRE_REQUESTS = 1  # segundos

# URLs base oficiales
URLS_BASE = {
    "diputados": "https://www.diputados.gob.mx/LeyesBiblio/",
    "sat": "https://www.sat.gob.mx/",
    "dof": "https://www.dof.gob.mx/",
    "stps": "https://www.gob.mx/stps",
}

# ============================================================================
# FILTRO DE LEYES Y REGLAMENTOS A DESCARGAR
# Solo se descargan documentos relacionados con contabilidad, fiscal y laboral
# ============================================================================

# Códigos de leyes permitidas (nombre_corto debe contener alguno de estos)
LEYES_PERMITIDAS = {
    "CPEUM",    # Constitución Política de los Estados Unidos Mexicanos
    "CFF",      # Código Fiscal de la Federación
    "LFT",      # Ley Federal del Trabajo
    "LIEPS",    # Ley del Impuesto Especial sobre Producción y Servicios
    "LISR",     # Ley del Impuesto Sobre la Renta
    "LIVA",     # Ley del Impuesto al Valor Agregado
    "LSS",      # Ley del Seguro Social
}

# Patrones para identificar reglamentos de las leyes permitidas
REGLAMENTOS_PERMITIDOS = {
    "RCFF", "REG_CFF",           # Reglamento del CFF
    "RLIEPS", "REG_LIEPS",       # Reglamento del IEPS
    "RLISR", "REG_LISR",         # Reglamento del ISR
    "RLIVA", "REG_LIVA",         # Reglamento del IVA
    "RLFT", "REG_LFT",           # Reglamento de la LFT
    "RLSS", "REG_LSS",           # Reglamento del Seguro Social
    "RACERF",                    # Reglamento de Afiliación IMSS
}

def documento_permitido(nombre_corto: str, tipo: str) -> bool:
    """Verifica si un documento está en la lista de permitidos."""
    nombre_upper = nombre_corto.upper()

    if tipo == "ley":
        return any(ley in nombre_upper for ley in LEYES_PERMITIDAS)
    elif tipo == "reglamento":
        # Verificar patrones de reglamentos
        if any(reg in nombre_upper for reg in REGLAMENTOS_PERMITIDOS):
            return True
        # También verificar si el nombre contiene referencias a las leyes permitidas
        for ley in LEYES_PERMITIDAS:
            if f"REG_{ley}" in nombre_upper or f"R{ley}" in nombre_upper:
                return True
            if f"REGLAMENTO" in nombre_upper and ley in nombre_upper:
                return True
        return False

    return False  # Por defecto, no descargar otros tipos


# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class DocumentoMeta:
    """Metadatos de un documento descargado."""
    nombre: str
    nombre_corto: str
    tipo: str
    autoridad: str
    url: str
    fecha_descarga: str
    sha256: str
    archivo_local: str
    formato: str
    estado: str = "nuevo"
    version_anterior: Optional[str] = None


# ============================================================================
# UTILIDADES
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configura el sistema de logging."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"descarga_{timestamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger = logging.getLogger("leyes_mx")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def normalizar_nombre(nombre: str, max_chars: int = 120) -> str:
    """Normaliza nombre de archivo."""
    nombre = unidecode(nombre)
    nombre = nombre.lower()
    nombre = re.sub(r'[^\w\-.]', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre)
    nombre = nombre.strip('_')

    if len(nombre) > max_chars:
        if '.' in nombre:
            base, ext = nombre.rsplit('.', 1)
            max_base = max_chars - len(ext) - 1
            nombre = f"{base[:max_base]}.{ext}"
        else:
            nombre = nombre[:max_chars]

    return nombre


def calcular_sha256(filepath: Path) -> str:
    """Calcula hash SHA256 de un archivo."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def crear_estructura_directorios():
    """Crea la estructura de directorios necesaria."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    VERSIONS_DIR.mkdir(exist_ok=True)
    for dir_path in DIRS.values():
        dir_path.mkdir(exist_ok=True)


def get_session() -> requests.Session:
    """Crea una sesión HTTP configurada."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


# ============================================================================
# DESCARGA CON REINTENTOS
# ============================================================================

class DescargadorConReintentos:
    """Descargador con manejo de reintentos y backoff exponencial."""

    def __init__(self, session: requests.Session, logger: logging.Logger):
        self.session = session
        self.logger = logger
        self.last_request_time = 0

    def _esperar_rate_limit(self):
        """Espera entre requests para no saturar servidores."""
        elapsed = time.time() - self.last_request_time
        if elapsed < DELAY_ENTRE_REQUESTS:
            time.sleep(DELAY_ENTRE_REQUESTS - elapsed)
        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((
            requests.RequestException,
            requests.ConnectionError,
            requests.Timeout,
        ))
    )
    def descargar(self, url: str) -> requests.Response:
        """Descarga una URL con reintentos."""
        self._esperar_rate_limit()
        self.logger.debug(f"GET: {url}")

        response = self.session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=False
        )
        response.raise_for_status()
        return response

    def descargar_seguro(self, url: str) -> Optional[requests.Response]:
        """Descarga con manejo de errores, retorna None si falla."""
        try:
            return self.descargar(url)
        except Exception as e:
            self.logger.warning(f"Error descargando {url}: {e}")
            return None


# ============================================================================
# CONVERSION HTML A PDF
# ============================================================================

class ConvertidorPDF:
    """Convierte HTML a PDF usando herramientas disponibles."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.tiene_wkhtmltopdf = self._verificar_wkhtmltopdf()
        self.tiene_playwright = self._verificar_playwright()

    def _verificar_wkhtmltopdf(self) -> bool:
        try:
            result = subprocess.run(
                ["wkhtmltopdf", "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False

    def _verificar_playwright(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False

    def convertir(self, html_path: Path, pdf_path: Path) -> bool:
        """Intenta convertir HTML a PDF."""
        if self.tiene_wkhtmltopdf:
            if self._convertir_wkhtmltopdf(html_path, pdf_path):
                return True

        if self.tiene_playwright:
            if self._convertir_playwright(html_path, pdf_path):
                return True

        return False

    def _convertir_wkhtmltopdf(self, html_path: Path, pdf_path: Path) -> bool:
        try:
            result = subprocess.run(
                [
                    "wkhtmltopdf",
                    "--quiet",
                    "--encoding", "utf-8",
                    "--page-size", "Letter",
                    "--margin-top", "15mm",
                    "--margin-bottom", "15mm",
                    "--margin-left", "15mm",
                    "--margin-right", "15mm",
                    str(html_path),
                    str(pdf_path)
                ],
                capture_output=True,
                timeout=180
            )
            return result.returncode == 0 and pdf_path.exists()
        except Exception as e:
            self.logger.debug(f"wkhtmltopdf error: {e}")
            return False

    def _convertir_playwright(self, html_path: Path, pdf_path: Path) -> bool:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(
                    f"file://{html_path.absolute()}",
                    wait_until="networkidle",
                    timeout=60000
                )
                page.pdf(
                    path=str(pdf_path),
                    format="Letter",
                    margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"}
                )
                browser.close()

            return pdf_path.exists()
        except Exception as e:
            self.logger.debug(f"playwright error: {e}")
            return False


# ============================================================================
# PARSERS DE SITIOS
# ============================================================================

class ParserDiputados:
    """Parser para www.diputados.gob.mx/LeyesBiblio/"""

    BASE_URL = "https://www.diputados.gob.mx/LeyesBiblio/"

    def __init__(self, descargador: DescargadorConReintentos, logger: logging.Logger):
        self.descargador = descargador
        self.logger = logger

    def obtener_documentos(self) -> List[Dict]:
        """Obtiene todos los documentos del sitio."""
        documentos = []
        urls_vistas: Set[str] = set()

        # 1. Agregar URLs conocidas primero
        self.logger.info("Cargando URLs conocidas de leyes y reglamentos...")
        for doc in LEYES_CAMARA_DIPUTADOS + REGLAMENTOS_CAMARA_DIPUTADOS:
            if doc["url"] not in urls_vistas:
                documentos.append(doc.copy())
                urls_vistas.add(doc["url"])

        # 2. Descubrir leyes desde el índice principal
        self.logger.info("Descubriendo leyes desde índice principal...")
        docs_indice = self._parsear_indice("index.htm", "ley")
        for doc in docs_indice:
            if doc["url"] not in urls_vistas:
                documentos.append(doc)
                urls_vistas.add(doc["url"])

        # 3. Descubrir reglamentos
        self.logger.info("Descubriendo reglamentos...")
        docs_reglamentos = self._parsear_indice("regla.htm", "reglamento")
        for doc in docs_reglamentos:
            if doc["url"] not in urls_vistas:
                documentos.append(doc)
                urls_vistas.add(doc["url"])

        # 4. Intentar índice alternativo de marco jurídico
        self.logger.info("Buscando en marco jurídico...")
        docs_marco = self._parsear_marco_juridico()
        for doc in docs_marco:
            if doc["url"] not in urls_vistas:
                documentos.append(doc)
                urls_vistas.add(doc["url"])

        self.logger.info(f"Total documentos encontrados en Diputados: {len(documentos)}")
        return documentos

    def _parsear_indice(self, pagina: str, tipo: str) -> List[Dict]:
        """Parsea una página de índice."""
        documentos = []
        url = urljoin(self.BASE_URL, pagina)

        response = self.descargador.descargar_seguro(url)
        if not response:
            return documentos

        soup = BeautifulSoup(response.content, "html.parser")

        # Buscar todos los enlaces
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            texto = link.get_text(strip=True)

            # Solo PDFs
            if not (href.lower().endswith(".pdf") or "/pdf/" in href.lower()):
                continue

            # Ignorar enlaces vacíos o muy cortos
            if len(texto) < 3:
                continue

            url_completa = urljoin(self.BASE_URL, href)

            # Determinar nombre corto
            nombre_corto = self._extraer_nombre_corto(texto, href)

            documentos.append({
                "nombre": texto,
                "nombre_corto": nombre_corto,
                "url": url_completa,
                "tipo": tipo,
                "autoridad": "CDD",
            })

        return documentos

    def _parsear_marco_juridico(self) -> List[Dict]:
        """Parsea secciones adicionales del marco jurídico."""
        documentos = []

        # Intentar varias secciones conocidas
        secciones = [
            "pdf_mov/",
            "ref/",
            "regley/",
        ]

        for seccion in secciones:
            url = urljoin(self.BASE_URL, seccion)
            response = self.descargador.descargar_seguro(url)

            if response and response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.lower().endswith(".pdf"):
                        texto = link.get_text(strip=True) or Path(href).stem
                        url_completa = urljoin(url, href)

                        tipo = "reglamento" if "reg" in seccion.lower() else "ley"

                        documentos.append({
                            "nombre": texto,
                            "nombre_corto": self._extraer_nombre_corto(texto, href),
                            "url": url_completa,
                            "tipo": tipo,
                            "autoridad": "CDD",
                        })

        return documentos

    def _extraer_nombre_corto(self, texto: str, href: str) -> str:
        """Extrae un nombre corto del texto o URL."""
        # Primero intentar patrones conocidos
        texto_lower = texto.lower()
        for clave, patrones in PATRONES_ARCHIVOS_DIPUTADOS.items():
            for patron in patrones:
                if patron.lower() in texto_lower or patron.lower() in href.lower():
                    return clave

        # Extraer del nombre del archivo
        nombre_archivo = Path(urlparse(href).path).stem
        return normalizar_nombre(nombre_archivo[:30])


class ParserSAT:
    """Parser para www.sat.gob.mx"""

    BASE_URL = "https://www.sat.gob.mx/"

    # Páginas conocidas de normatividad
    PAGINAS_NORMATIVIDAD = [
        ("normatividad/98887/resolucion-miscelanea-fiscal", "RMF"),
        ("normatividad/82617/reglas-generales-de-comercio-exterior", "RGCE"),
        ("normatividad/58917/resolucion-de-facilidades-administrativas", "RFA"),
    ]

    def __init__(self, descargador: DescargadorConReintentos, logger: logging.Logger):
        self.descargador = descargador
        self.logger = logger
        self.year = datetime.now().year

    def obtener_documentos(self) -> List[Dict]:
        """Obtiene misceláneas y documentos normativos del SAT."""
        documentos = []
        urls_vistas: Set[str] = set()

        for ruta, prefijo in self.PAGINAS_NORMATIVIDAD:
            url = urljoin(self.BASE_URL, ruta)
            self.logger.info(f"Buscando {prefijo} en SAT...")

            docs = self._parsear_pagina_normatividad(url, prefijo)
            for doc in docs:
                if doc["url"] not in urls_vistas:
                    documentos.append(doc)
                    urls_vistas.add(doc["url"])

        self.logger.info(f"Total documentos encontrados en SAT: {len(documentos)}")
        return documentos

    def _parsear_pagina_normatividad(self, url: str, prefijo: str) -> List[Dict]:
        """Parsea una página de normatividad del SAT."""
        documentos = []

        response = self.descargador.descargar_seguro(url)
        if not response:
            return documentos

        soup = BeautifulSoup(response.content, "html.parser")

        # Buscar enlaces a PDFs o al DOF
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            texto = link.get_text(strip=True)

            # Filtrar por año actual o por tipo de documento
            if not self._es_documento_relevante(texto, href):
                continue

            # Construir URL completa
            if href.startswith("http"):
                url_doc = href
            else:
                url_doc = urljoin(url, href)

            # Verificar si es del año actual
            if str(self.year) in texto or str(self.year) in href or "vigente" in texto.lower():
                documentos.append({
                    "nombre": texto or f"{prefijo} {self.year}",
                    "nombre_corto": f"{prefijo}_{self.year}",
                    "url": url_doc,
                    "tipo": "miscelanea",
                    "autoridad": "SAT",
                })

        return documentos

    def _es_documento_relevante(self, texto: str, href: str) -> bool:
        """Verifica si un documento es relevante para descarga."""
        texto_lower = texto.lower()
        href_lower = href.lower()

        # Debe ser PDF o enlace al DOF
        if ".pdf" not in href_lower and "dof.gob.mx" not in href_lower:
            return False

        # Términos relevantes
        terminos = [
            "miscelanea", "miscelánea", "rmf",
            "comercio exterior", "rgce",
            "facilidades", "rfa",
            "compilad", "vigente", "actualiz"
        ]

        return any(t in texto_lower or t in href_lower for t in terminos)


class ParserDOF:
    """Parser para www.dof.gob.mx"""

    BASE_URL = "https://www.dof.gob.mx/"

    def __init__(self, descargador: DescargadorConReintentos, logger: logging.Logger):
        self.descargador = descargador
        self.logger = logger
        self.year = datetime.now().year

    def obtener_documentos(self) -> List[Dict]:
        """Busca documentos fiscales en el DOF."""
        documentos = []

        # Términos de búsqueda para documentos fiscales
        terminos = [
            f"Resolución Miscelánea Fiscal {self.year}",
            f"Reglas Generales de Comercio Exterior {self.year}",
        ]

        for termino in terminos:
            docs = self._buscar(termino)
            documentos.extend(docs)

        self.logger.info(f"Total documentos encontrados en DOF: {len(documentos)}")
        return documentos

    def _buscar(self, termino: str) -> List[Dict]:
        """Realiza una búsqueda en el DOF."""
        documentos = []

        # El DOF tiene diferentes endpoints de búsqueda
        url_busqueda = f"{self.BASE_URL}busqueda_detalle.php"

        self.logger.info(f"Buscando en DOF: {termino}")

        try:
            response = self.descargador.descargador.session.get(
                url_busqueda,
                params={"busqueda": termino},
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                return documentos

            soup = BeautifulSoup(response.content, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                texto = link.get_text(strip=True)

                if "nota_detalle.php" in href or ".pdf" in href.lower():
                    url_completa = urljoin(self.BASE_URL, href)

                    documentos.append({
                        "nombre": texto or termino,
                        "nombre_corto": normalizar_nombre(termino[:30]),
                        "url": url_completa,
                        "tipo": "miscelanea",
                        "autoridad": "DOF",
                    })

        except Exception as e:
            self.logger.warning(f"Error buscando en DOF: {e}")

        return documentos


# ============================================================================
# GESTOR PRINCIPAL
# ============================================================================

class GestorLeyesMX:
    """Gestor principal de descargas."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.session = get_session()
        self.descargador = DescargadorConReintentos(self.session, logger)
        self.convertidor = ConvertidorPDF(logger)
        self.documentos_descargados: List[DocumentoMeta] = []
        self.errores: List[Dict] = []

    def cargar_manifest_anterior(self) -> Dict[str, Dict]:
        """Carga el manifest existente."""
        manifest_path = BASE_DIR / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {item["url"]: item for item in data.get("documentos", [])}
            except Exception as e:
                self.logger.warning(f"Error cargando manifest: {e}")
        return {}

    def recolectar_documentos(self) -> List[Dict]:
        """Recolecta todos los documentos de todas las fuentes."""
        todos: List[Dict] = []
        urls_vistas: Set[str] = set()

        # 1. Cámara de Diputados
        self.logger.info("\n" + "=" * 60)
        self.logger.info("FUENTE: Cámara de Diputados")
        self.logger.info("=" * 60)

        parser_diputados = ParserDiputados(self.descargador, self.logger)
        for doc in parser_diputados.obtener_documentos():
            if doc["url"] not in urls_vistas:
                todos.append(doc)
                urls_vistas.add(doc["url"])

        # 2. SAT
        self.logger.info("\n" + "=" * 60)
        self.logger.info("FUENTE: SAT")
        self.logger.info("=" * 60)

        parser_sat = ParserSAT(self.descargador, self.logger)
        for doc in parser_sat.obtener_documentos():
            if doc["url"] not in urls_vistas:
                todos.append(doc)
                urls_vistas.add(doc["url"])

        # 3. DOF
        self.logger.info("\n" + "=" * 60)
        self.logger.info("FUENTE: DOF")
        self.logger.info("=" * 60)

        parser_dof = ParserDOF(self.descargador, self.logger)
        for doc in parser_dof.obtener_documentos():
            if doc["url"] not in urls_vistas:
                todos.append(doc)
                urls_vistas.add(doc["url"])

        return todos

    def descargar_documento(self, doc: Dict, manifest_anterior: Dict) -> Optional[DocumentoMeta]:
        """Descarga un documento individual."""
        url = doc["url"]
        nombre = doc["nombre"]
        nombre_corto = doc["nombre_corto"]
        tipo = doc["tipo"]
        autoridad = doc["autoridad"]

        dir_tipo = DIRS.get(tipo, DIRS["ley"])

        # Crear subdirectorio para cada ley/reglamento basado en nombre_corto
        dir_destino = dir_tipo / nombre_corto
        dir_destino.mkdir(parents=True, exist_ok=True)

        try:
            self.logger.info(f"Descargando: {nombre_corto}")
            response = self.descargador.descargar(url)

            # Determinar formato
            content_type = response.headers.get("Content-Type", "").lower()
            es_pdf = "application/pdf" in content_type or response.content[:4] == b"%PDF"

            if es_pdf:
                formato = "pdf"
                extension = ".pdf"
            else:
                formato = "html"
                extension = ".html"

            # Nombre de archivo normalizado (ahora dentro de la subcarpeta)
            nombre_archivo = normalizar_nombre(f"{nombre_corto}_{nombre[:50]}")
            archivo_base = dir_destino / nombre_archivo
            archivo_principal = archivo_base.with_suffix(extension)

            # Guardar contenido
            with open(archivo_principal, "wb") as f:
                f.write(response.content)

            # Convertir HTML a PDF si es necesario
            archivo_final = archivo_principal
            if formato == "html":
                archivo_pdf = archivo_base.with_suffix(".pdf")
                if self.convertidor.convertir(archivo_principal, archivo_pdf):
                    archivo_final = archivo_pdf
                    formato = "pdf"
                    self.logger.info(f"  Convertido a PDF")
                else:
                    self.logger.warning(f"  No se pudo convertir a PDF, guardando HTML")

            # Calcular hash
            sha256 = calcular_sha256(archivo_final)

            # Verificar cambios
            estado = "nuevo"
            version_anterior = None

            if url in manifest_anterior:
                anterior = manifest_anterior[url]
                if anterior.get("sha256") == sha256:
                    estado = "sin_cambios"
                    self.logger.info(f"  Sin cambios")
                else:
                    estado = "changed"
                    version_anterior = self._archivar_version(
                        archivo_final, anterior.get("sha256", ""), nombre_corto
                    )
                    self.logger.warning(f"  CAMBIO DETECTADO - versión anterior archivada")

            # Crear metadatos
            fecha_descarga = datetime.now(timezone.utc).isoformat()

            meta = DocumentoMeta(
                nombre=nombre,
                nombre_corto=nombre_corto,
                tipo=tipo,
                autoridad=autoridad,
                url=url,
                fecha_descarga=fecha_descarga,
                sha256=sha256,
                archivo_local=str(archivo_final.relative_to(BASE_DIR)),
                formato=formato,
                estado=estado,
                version_anterior=version_anterior,
            )

            # Guardar archivos auxiliares
            self._guardar_archivos_auxiliares(archivo_base, url, meta)

            return meta

        except Exception as e:
            self.logger.error(f"  ERROR: {e}")
            self.errores.append({
                "url": url,
                "nombre": nombre,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return None

    def _archivar_version(self, archivo: Path, sha256_anterior: str, nombre_corto: str) -> str:
        """Archiva una versión anterior del documento."""
        if not archivo.exists():
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sha_corto = sha256_anterior[:8] if sha256_anterior else "unknown"
        nombre_version = f"{nombre_corto}_{sha_corto}_{timestamp}{archivo.suffix}"
        destino = VERSIONS_DIR / nombre_version

        shutil.copy2(archivo, destino)
        return str(destino.relative_to(BASE_DIR))

    def _guardar_archivos_auxiliares(self, archivo_base: Path, url: str, meta: DocumentoMeta):
        """Guarda archivos .url.txt y .meta.json"""
        # .url.txt
        url_file = archivo_base.with_suffix(".url.txt")
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(url)

        # .meta.json
        meta_file = archivo_base.with_suffix(".meta.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(asdict(meta), f, ensure_ascii=False, indent=2)

    def generar_manifests(self):
        """Genera manifest.json y manifest.csv"""
        # JSON
        manifest_data = {
            "generado": datetime.now(timezone.utc).isoformat(),
            "total_documentos": len(self.documentos_descargados),
            "estadisticas": {
                "nuevos": sum(1 for d in self.documentos_descargados if d.estado == "nuevo"),
                "sin_cambios": sum(1 for d in self.documentos_descargados if d.estado == "sin_cambios"),
                "cambiados": sum(1 for d in self.documentos_descargados if d.estado == "changed"),
                "errores": len(self.errores),
            },
            "documentos": [asdict(d) for d in self.documentos_descargados],
            "errores": self.errores,
        }

        with open(BASE_DIR / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)

        # CSV
        with open(BASE_DIR / "manifest.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "nombre", "nombre_corto", "tipo", "autoridad", "url",
                "fecha_descarga", "sha256", "archivo", "formato", "estado"
            ])
            for doc in self.documentos_descargados:
                writer.writerow([
                    doc.nombre, doc.nombre_corto, doc.tipo, doc.autoridad, doc.url,
                    doc.fecha_descarga, doc.sha256, doc.archivo_local, doc.formato, doc.estado
                ])

        self.logger.info("Manifests generados: manifest.json, manifest.csv")

    def ejecutar(self):
        """Ejecuta el proceso completo de descarga."""
        self.logger.info("=" * 70)
        self.logger.info("INICIANDO DESCARGA DE LEYES Y REGLAMENTOS")
        self.logger.info("=" * 70)

        # Cargar estado anterior
        manifest_anterior = self.cargar_manifest_anterior()
        if manifest_anterior:
            self.logger.info(f"Manifest anterior: {len(manifest_anterior)} documentos")

        # Recolectar documentos
        documentos_todos = self.recolectar_documentos()
        self.logger.info(f"\nTotal documentos encontrados: {len(documentos_todos)}")

        # Filtrar solo documentos permitidos (leyes fiscales/laborales y sus reglamentos)
        documentos = [
            doc for doc in documentos_todos
            if documento_permitido(doc["nombre_corto"], doc["tipo"])
        ]
        self.logger.info(f"Documentos después del filtro: {len(documentos)}")

        # Descargar
        self.logger.info("\n" + "=" * 60)
        self.logger.info("DESCARGANDO")
        self.logger.info("=" * 60)

        for doc in tqdm(documentos, desc="Descargando", unit="doc"):
            meta = self.descargar_documento(doc, manifest_anterior)
            if meta:
                self.documentos_descargados.append(meta)

        # Generar manifests
        self.logger.info("\n" + "=" * 60)
        self.logger.info("GENERANDO MANIFESTS")
        self.logger.info("=" * 60)
        self.generar_manifests()

        # Resumen
        self._imprimir_resumen()

    def _imprimir_resumen(self):
        """Imprime resumen final."""
        nuevos = sum(1 for d in self.documentos_descargados if d.estado == "nuevo")
        sin_cambios = sum(1 for d in self.documentos_descargados if d.estado == "sin_cambios")
        cambiados = sum(1 for d in self.documentos_descargados if d.estado == "changed")

        self.logger.info("\n" + "=" * 60)
        self.logger.info("RESUMEN FINAL")
        self.logger.info("=" * 60)
        self.logger.info(f"Documentos descargados: {len(self.documentos_descargados)}")
        self.logger.info(f"  - Nuevos:       {nuevos}")
        self.logger.info(f"  - Sin cambios:  {sin_cambios}")
        self.logger.info(f"  - Cambiados:    {cambiados}")
        self.logger.info(f"  - Errores:      {len(self.errores)}")

        if self.errores:
            self.logger.warning("\nDocumentos con error:")
            for err in self.errores[:10]:
                self.logger.warning(f"  - {err['nombre'][:50]}: {err['error'][:50]}")
            if len(self.errores) > 10:
                self.logger.warning(f"  ... y {len(self.errores) - 10} más")


# ============================================================================
# INSTALACION DE DEPENDENCIAS
# ============================================================================

def verificar_dependencias(logger: logging.Logger):
    """Verifica e instala dependencias del sistema."""
    logger.info("Verificando dependencias del sistema...")

    # wkhtmltopdf
    try:
        subprocess.run(["wkhtmltopdf", "--version"], capture_output=True, check=True)
        logger.info("  wkhtmltopdf: OK")
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning("  wkhtmltopdf: No encontrado")
        try:
            logger.info("  Instalando wkhtmltopdf...")
            subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True, capture_output=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "wkhtmltopdf"], check=True)
            logger.info("  wkhtmltopdf: Instalado")
        except Exception as e:
            logger.warning(f"  No se pudo instalar wkhtmltopdf: {e}")

    # Playwright
    try:
        logger.info("  Configurando Playwright...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=300
        )
        logger.info("  Playwright chromium: OK")
    except Exception as e:
        logger.warning(f"  Playwright: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 70)
    print("  DESCARGADOR DE LEYES FISCALES Y LABORALES DE MEXICO")
    print("  Fuentes: Cámara de Diputados, DOF, SAT")
    print("=" * 70 + "\n")

    # Crear estructura
    crear_estructura_directorios()

    # Logging
    logger = setup_logging()
    logger.info(f"Directorio base: {BASE_DIR}")
    logger.info(f"Fecha: {datetime.now().isoformat()}")

    # Dependencias
    verificar_dependencias(logger)

    # Ejecutar
    gestor = GestorLeyesMX(logger)
    gestor.ejecutar()

    print("\n" + "=" * 70)
    print(f"  COMPLETADO: {len(gestor.documentos_descargados)} documentos")
    print(f"  Errores: {len(gestor.errores)}")
    print(f"  Directorio: {BASE_DIR}")
    print("=" * 70 + "\n")

    return 0 if not gestor.errores else 1


if __name__ == "__main__":
    sys.exit(main())
