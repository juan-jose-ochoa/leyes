#!/usr/bin/env python3
"""
Extractor de contenido de leyes para esquema leyesmx.

Extrae artículos y párrafos de PDFs oficiales.
La estructura (títulos/capítulos) viene de estructura_esperada.json (ver extraer_mapa.py).

Uso:
    python backend/etl/extraer.py CFF
"""

import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF no instalado. Ejecuta: pip install pymupdf")
    sys.exit(1)

from config import get_config, listar_leyes

BASE_DIR = Path(__file__).parent.parent.parent


@dataclass
class Parrafo:
    """Un párrafo dentro de un artículo."""
    numero: int                     # Orden secuencial: 1, 2, 3...
    tipo: str                       # 'texto', 'fraccion', 'inciso', 'numeral'
    identificador: Optional[str]    # 'I', 'a)', '1.', None para texto
    contenido: str
    padre_numero: Optional[int] = None  # Número del párrafo padre

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "tipo": self.tipo,
            "identificador": self.identificador,
            "contenido": self.contenido,
            "padre_numero": self.padre_numero,
        }


@dataclass
class Articulo:
    """Un artículo o regla."""
    numero: str                     # "1o", "17-H BIS", "2.1.1.1"
    tipo: str                       # "articulo", "regla", "transitorio"
    parrafos: list[Parrafo] = field(default_factory=list)
    orden: int = 0
    pagina: int = 0

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "tipo": self.tipo,
            "orden": self.orden,
            "pagina": self.pagina,
            "parrafos": [p.to_dict() for p in self.parrafos],
        }


@dataclass
class Division:
    """Una división estructural (título, capítulo, etc.)."""
    tipo: str                       # 'titulo', 'capitulo', 'seccion', 'libro'
    numero: str                     # 'PRIMERO', 'I', '2.1'
    nombre: Optional[str]           # 'Disposiciones Generales'
    orden: int
    padre_orden: Optional[int] = None  # Orden de la división padre

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "nombre": self.nombre,
            "orden": self.orden,
            "padre_orden": self.padre_orden,
        }


class Extractor:
    """Extractor genérico de leyes."""

    def __init__(self, codigo: str):
        self.codigo = codigo.upper()
        self.config = get_config(self.codigo)
        self.pdf_path = BASE_DIR / self.config["pdf_path"]
        self.doc = None
        self._texto = None

    def abrir_pdf(self):
        """Abre el PDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {self.pdf_path}")
        self.doc = fitz.open(str(self.pdf_path))
        print(f"   PDF: {self.pdf_path.name} ({len(self.doc)} páginas)")

    def cerrar_pdf(self):
        """Cierra el PDF."""
        if self.doc:
            self.doc.close()

    def _get_texto(self) -> str:
        """Extrae todo el texto del PDF con marcadores de página y limpieza global."""
        if self._texto is not None:
            return self._texto

        partes = []
        for i, page in enumerate(self.doc):
            partes.append(f"\n[PAGE:{i+1}]\n")
            partes.append(page.get_text())

        texto = ''.join(partes)

        # Aplicar limpieza de basura global (mantener marcadores de página)
        for patron in self.config.get("basura", []):
            texto = re.sub(patron, '', texto, flags=re.IGNORECASE | re.DOTALL)

        self._texto = texto
        return self._texto

    def _limpiar_texto(self, texto: str) -> str:
        """Limpia el contenido de un artículo (quita marcadores y normaliza)."""
        # Quitar marcadores de página
        texto = re.sub(r'\[PAGE:\d+\]', '', texto)

        # Normalizar espacios
        texto = re.sub(r'\n\s*\n+', '\n\n', texto)

        return texto.strip()

    def extraer_estructura(self) -> list[Division]:
        """Extrae la estructura jerárquica de divisiones."""
        texto = self._get_texto()
        lineas = texto.split('\n')
        divisiones = []
        orden = 0

        patrones = self.config["patrones"]
        niveles = self.config["divisiones_permitidas"]

        # Rastrear jerarquía
        ultimo_por_nivel = {}

        for i, linea in enumerate(lineas):
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue

            for nivel in niveles:
                patron = patrones.get(nivel)
                if not patron:
                    continue

                match = re.match(patron, linea_limpia, re.IGNORECASE)
                if not match:
                    continue

                numero = match.group(1).upper()

                # Extraer nombre de la siguiente línea
                nombre = None
                if i + 1 < len(lineas):
                    siguiente = lineas[i + 1].strip()
                    # Filtrar nombres basura
                    if siguiente and len(siguiente) >= 5:
                        if not any(x in siguiente for x in ['Artículo', 'DOF', '[PAGE:', 'CAPITULO', 'TITULO']):
                            nombre = siguiente

                orden += 1

                # Determinar padre
                padre_orden = None
                nivel_idx = niveles.index(nivel)
                if nivel_idx > 0:
                    nivel_padre = niveles[nivel_idx - 1]
                    padre_orden = ultimo_por_nivel.get(nivel_padre)

                division = Division(
                    tipo=nivel,
                    numero=numero,
                    nombre=nombre,
                    orden=orden,
                    padre_orden=padre_orden
                )
                divisiones.append(division)
                ultimo_por_nivel[nivel] = orden
                break  # Solo un match por línea

        return divisiones

    def _parsear_parrafos(self, contenido: str) -> list[Parrafo]:
        """Parsea el contenido de un artículo en párrafos."""
        parrafos = []
        patrones = self.config["patrones"]

        # Dividir en bloques
        bloques = contenido.split('\n\n')
        numero = 0
        ultimo_fraccion_numero = None

        for bloque in bloques:
            bloque = bloque.strip()
            if not bloque or len(bloque) < 3:
                continue

            # Detectar tipo de párrafo
            tipo = "texto"
            identificador = None
            padre_numero = None
            texto = bloque

            # ¿Es fracción? (I. II. III.)
            match = re.match(patrones.get("fraccion", r'^$'), bloque)
            if match:
                tipo = "fraccion"
                identificador = match.group(1)
                texto = bloque[match.end():].strip()
                numero += 1
                ultimo_fraccion_numero = numero
                parrafos.append(Parrafo(numero, tipo, identificador, texto, None))
                continue

            # ¿Es inciso? (a) b) c))
            match = re.match(patrones.get("inciso", r'^$'), bloque)
            if match:
                tipo = "inciso"
                identificador = match.group(1) + ")"
                texto = bloque[match.end():].strip()
                padre_numero = ultimo_fraccion_numero
                numero += 1
                parrafos.append(Parrafo(numero, tipo, identificador, texto, padre_numero))
                continue

            # ¿Es numeral? (1. 2. 3.)
            match = re.match(patrones.get("numeral", r'^$'), bloque)
            if match and int(match.group(1)) <= 20:
                tipo = "numeral"
                identificador = match.group(1) + "."
                texto = bloque[match.end():].strip()
                padre_numero = ultimo_fraccion_numero
                numero += 1
                parrafos.append(Parrafo(numero, tipo, identificador, texto, padre_numero))
                continue

            # Es texto normal
            numero += 1
            parrafos.append(Parrafo(numero, "texto", None, ' '.join(bloque.split()), None))

        return parrafos

    def extraer_contenido(self) -> list[Articulo]:
        """Extrae artículos/reglas con sus párrafos."""
        texto = self._get_texto()
        articulos = []

        patron_art = self.config["patrones"]["articulo"]
        tipo_contenido = self.config["tipo_contenido"]

        matches = list(re.finditer(patron_art, texto, re.IGNORECASE | re.MULTILINE))
        print(f"   Encontrados {len(matches)} {tipo_contenido}s")

        numeros_vistos = set()
        for i, match in enumerate(matches):
            # Construir número
            grupos = match.groups()
            numero_base = grupos[0]
            ordinal = grupos[1] if len(grupos) > 1 else None
            letra = grupos[2] if len(grupos) > 2 else None
            sufijo = grupos[3] if len(grupos) > 3 else None

            numero = numero_base
            if ordinal:
                numero += ordinal.lower()
            if letra:
                numero += f"-{letra.upper()}"
            if sufijo:
                numero += f" {sufijo.upper()}"

            # Saltar duplicados (erratas del DOF)
            if numero in numeros_vistos:
                continue
            numeros_vistos.add(numero)

            # Extraer contenido hasta siguiente artículo
            pos_inicio = match.end()
            pos_fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
            contenido_raw = texto[pos_inicio:pos_fin]

            # Limpiar y parsear
            contenido_limpio = self._limpiar_texto(contenido_raw)
            parrafos = self._parsear_parrafos(contenido_limpio)

            # Página
            texto_antes = texto[:match.start()]
            pagina = texto_antes.count('[PAGE:') + 1

            articulo = Articulo(
                numero=numero,
                tipo=tipo_contenido,
                parrafos=parrafos,
                orden=len(articulos) + 1,
                pagina=pagina
            )
            articulos.append(articulo)

        return articulos


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/extraer.py <CODIGO>")
        print(f"Leyes disponibles: {', '.join(listar_leyes())}")
        sys.exit(1)

    codigo = sys.argv[1].upper()

    print("=" * 60)
    print(f"EXTRACTOR LEYESMX: {codigo}")
    print("=" * 60)

    try:
        extractor = Extractor(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Abrir PDF
    print("\n1. Abriendo PDF...")
    try:
        extractor.abrir_pdf()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    config = extractor.config
    output_dir = BASE_DIR / Path(config["pdf_path"]).parent

    # Extraer contenido (la estructura viene de estructura_esperada.json)
    print("\n2. Extrayendo contenido...")
    articulos = extractor.extraer_contenido()

    # Estadísticas
    total_parrafos = sum(len(a.parrafos) for a in articulos)
    tipos_parrafo = {}
    for a in articulos:
        for p in a.parrafos:
            tipos_parrafo[p.tipo] = tipos_parrafo.get(p.tipo, 0) + 1

    print(f"   {len(articulos)} artículos, {total_parrafos} párrafos")
    for tipo, count in sorted(tipos_parrafo.items(), key=lambda x: -x[1]):
        print(f"      {tipo}: {count}")

    # Guardar
    contenido_path = output_dir / "contenido.json"
    with open(contenido_path, 'w', encoding='utf-8') as f:
        json.dump({
            "ley": codigo,
            "tipo_contenido": config["tipo_contenido"],
            "articulos": [a.to_dict() for a in articulos]
        }, f, ensure_ascii=False, indent=2)
    print(f"   Guardado: {contenido_path.name}")

    extractor.cerrar_pdf()

    print("\n" + "=" * 60)
    print("EXTRACCIÓN COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
