#!/usr/bin/env python3
"""
Descargador de Resolución Miscelánea Fiscal (RMF) del SAT

Descarga:
- RMF compilada (última versión)
- Anexos compilados

Fuente: https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/normatividad_rmf_rgce2025.html
"""

import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Configuración
BASE_DIR = Path(__file__).parent.parent / "doc" / "rmf"
ANEXOS_DIR = BASE_DIR / "anexos"

SAT_BASE_URL = "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/"
SAT_PAGE_URL = SAT_BASE_URL + "normatividad_rmf_rgce2025.html"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get_session():
    """Crea sesión HTTP configurada."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9",
    })
    return session


def calcular_sha256(filepath: Path) -> str:
    """Calcula hash SHA256."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extraer_fecha_archivo(nombre: str) -> str:
    """Extrae fecha del nombre del archivo (formato DDMMYYYY)."""
    match = re.search(r'(\d{2})(\d{2})(\d{4})', nombre)
    if match:
        dia, mes, anio = match.groups()
        return f"{anio}-{mes}-{dia}"
    return ""


def parsear_pagina_sat(session) -> dict:
    """
    Parsea la página del SAT y encuentra los documentos compilados más recientes.

    Returns:
        {
            "rmf_principal": {"nombre": ..., "url": ..., "fecha": ...},
            "anexos": [{"nombre": ..., "url": ..., "fecha": ...}, ...]
        }
    """
    print(f"Parseando: {SAT_PAGE_URL}")

    response = session.get(SAT_PAGE_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    documentos = {
        "rmf_principal": None,
        "anexos": []
    }

    # Buscar todos los enlaces a PDFs
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        texto = link.get_text(strip=True)

        if not href.lower().endswith(".pdf"):
            continue

        # Solo documentos compilados
        if "compilad" not in href.lower() and "compilad" not in texto.lower():
            continue

        url_completa = urljoin(SAT_BASE_URL, href)
        fecha = extraer_fecha_archivo(href)
        nombre_archivo = Path(href).name

        doc_info = {
            "nombre": texto or nombre_archivo,
            "url": url_completa,
            "archivo": nombre_archivo,
            "fecha": fecha
        }

        # Clasificar: RMF principal vs Anexos
        nombre_lower = nombre_archivo.lower()

        if "anexo" in nombre_lower:
            # Es un anexo
            # Extraer número de anexo
            match = re.search(r'anexo[_\s]*(\d+[-_]?[a-z]?)', nombre_lower)
            if match:
                doc_info["numero_anexo"] = match.group(1).replace("_", "-").upper()
            documentos["anexos"].append(doc_info)
        elif "resolucion" in nombre_lower or "miscelanea" in nombre_lower or "rmf" in nombre_lower:
            # Es la RMF principal
            # Solo guardar si es más reciente
            if documentos["rmf_principal"] is None:
                documentos["rmf_principal"] = doc_info
            elif fecha and fecha > (documentos["rmf_principal"].get("fecha") or ""):
                documentos["rmf_principal"] = doc_info

    # Ordenar anexos por número
    documentos["anexos"].sort(key=lambda x: x.get("numero_anexo", "99"))

    return documentos


def descargar_documento(session, doc_info: dict, destino: Path) -> dict:
    """Descarga un documento y retorna metadatos."""
    url = doc_info["url"]
    nombre = doc_info.get("archivo", Path(url).name)

    archivo_destino = destino / nombre

    print(f"  Descargando: {nombre}...")

    response = session.get(url, timeout=120, stream=True)
    response.raise_for_status()

    with open(archivo_destino, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Calcular hash
    sha256 = calcular_sha256(archivo_destino)

    return {
        **doc_info,
        "archivo_local": str(archivo_destino.relative_to(BASE_DIR.parent.parent)),
        "sha256": sha256,
        "tamaño_bytes": archivo_destino.stat().st_size,
        "fecha_descarga": datetime.now().isoformat()
    }


def main():
    print("=" * 60)
    print("DESCARGADOR DE RMF - SAT")
    print("=" * 60)

    # Crear directorios
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    ANEXOS_DIR.mkdir(exist_ok=True)

    session = get_session()

    # Parsear página
    print("\n1. Buscando documentos compilados...")
    documentos = parsear_pagina_sat(session)

    if not documentos["rmf_principal"]:
        print("ERROR: No se encontró la RMF compilada")
        return 1

    print(f"   RMF Principal: {documentos['rmf_principal']['archivo']}")
    print(f"   Anexos encontrados: {len(documentos['anexos'])}")

    # Descargar RMF principal
    print("\n2. Descargando RMF principal...")
    rmf_meta = descargar_documento(session, documentos["rmf_principal"], BASE_DIR)
    print(f"   OK: {rmf_meta['tamaño_bytes'] / 1024 / 1024:.1f} MB")

    # Descargar anexos
    print("\n3. Descargando anexos compilados...")
    anexos_meta = []
    for anexo in documentos["anexos"]:
        try:
            meta = descargar_documento(session, anexo, ANEXOS_DIR)
            anexos_meta.append(meta)
            print(f"   OK: {meta.get('numero_anexo', '?')} - {meta['tamaño_bytes'] / 1024:.0f} KB")
        except Exception as e:
            print(f"   ERROR: {anexo['archivo']} - {e}")

    # Guardar manifest
    print("\n4. Generando manifest...")
    manifest = {
        "generado": datetime.now().isoformat(),
        "fuente": SAT_PAGE_URL,
        "rmf_principal": rmf_meta,
        "anexos": anexos_meta,
        "total_documentos": 1 + len(anexos_meta)
    }

    manifest_path = BASE_DIR / "manifest_rmf.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"   Guardado: {manifest_path}")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"RMF Principal: {rmf_meta['archivo']}")
    print(f"Anexos descargados: {len(anexos_meta)}")
    print(f"Directorio: {BASE_DIR}")

    return 0


if __name__ == "__main__":
    exit(main())
