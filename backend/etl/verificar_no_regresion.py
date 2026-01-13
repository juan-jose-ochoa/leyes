#!/usr/bin/env python3
"""
Verificador de no-regresión usando pdftotext como segunda opinión.

Proceso:
1. git diff → identifica artículos que cambiaron
2. Para cada cambio, usa pdftotext (independiente) para verificar PDF
3. Si lo nuevo coincide con PDF → MEJORA
4. Si lo nuevo difiere del PDF → REGRESIÓN

Uso:
    python backend/etl/verificar_no_regresion.py LFT
    python backend/etl/verificar_no_regresion.py --todas
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import get_config, listar_leyes

BASE_DIR = Path(__file__).parent.parent.parent


@dataclass
class CambioArticulo:
    """Representa un cambio detectado en un artículo."""
    numero: str
    pagina: Optional[int]
    antes_tiene_contenido: bool
    despues_tiene_contenido: bool
    tipo_cambio: str  # "agregado", "eliminado", "modificado"


@dataclass
class ResultadoArticulo:
    """Resultado de verificación para un artículo."""
    numero: str
    veredicto: str  # "MEJORA", "REGRESION", "NEUTRAL"
    cambio: str  # Descripción del cambio
    pdf_tiene: bool
    json_antes: bool
    json_despues: bool
    detalle: str = ""


@dataclass
class ResultadoLey:
    """Resultado de verificación para una ley."""
    codigo: str
    articulos: list[ResultadoArticulo] = field(default_factory=list)

    @property
    def mejoras(self) -> int:
        return sum(1 for a in self.articulos if a.veredicto == "MEJORA")

    @property
    def regresiones(self) -> int:
        return sum(1 for a in self.articulos if a.veredicto == "REGRESION")

    @property
    def es_ok(self) -> bool:
        return self.regresiones == 0


class VerificadorNoRegresion:
    """
    Verifica cambios usando pdftotext como segunda opinión independiente.
    """

    def __init__(self, codigo: str):
        self.codigo = codigo.upper()
        self.config = get_config(self.codigo)
        self.pdf_path = BASE_DIR / self.config["pdf_path"]
        self.json_path = BASE_DIR / Path(self.config["pdf_path"]).parent / "contenido.json"

        # Cache de páginas extraídas con pdftotext
        self._cache_paginas: dict[int, str] = {}

    def _normalizar_numero(self, numero: str) -> str:
        """Normaliza número de artículo para comparación."""
        numero = re.sub(r'\s+', ' ', numero.strip())
        numero = re.sub(r'[-–—]', '-', numero)
        numero = re.sub(r'(\d[oa]?)\.\s*(bis|ter|quáter|quinquies|sexies)',
                       r'\1 \2', numero, flags=re.IGNORECASE)
        return numero.lower()

    def _extraer_pagina_pdftotext(self, pagina: int) -> str:
        """Extrae texto de una página usando pdftotext (poppler)."""
        if pagina in self._cache_paginas:
            return self._cache_paginas[pagina]

        try:
            result = subprocess.run(
                ["pdftotext", "-f", str(pagina), "-l", str(pagina),
                 str(self.pdf_path), "-"],
                capture_output=True, text=True, timeout=30
            )
            texto = result.stdout
            self._cache_paginas[pagina] = texto
            return texto
        except Exception as e:
            print(f"   Error extrayendo página {pagina}: {e}")
            return ""

    def _verificar_articulo_en_pdf(self, numero: str, pagina: int) -> tuple[bool, str]:
        """
        Verifica si un artículo tiene contenido en el PDF usando pdftotext.

        Returns:
            (tiene_contenido, muestra_texto)
        """
        # Extraer página y adyacentes (el artículo puede cruzar páginas)
        texto = ""
        for p in range(max(1, pagina - 1), pagina + 3):
            texto += self._extraer_pagina_pdftotext(p) + "\n"

        # Construir patrón para encontrar el artículo
        # Normalizar número para regex
        num_pattern = re.escape(numero)
        # Manejar variantes: "3o Bis" puede ser "3o. Bis" en PDF
        num_pattern = re.sub(r'(\d)o\\?', r'\1o\\.?', num_pattern)
        num_pattern = re.sub(r'\\ ', r'[.\\s]+', num_pattern)

        # Buscar el artículo
        patron = rf'Art[ií]culo\s+{num_pattern}\s*[.\-–]\s*(.+?)(?=Art[ií]culo\s+\d|$)'

        match = re.search(patron, texto, re.DOTALL | re.IGNORECASE)

        if match:
            contenido = match.group(1).strip()
            # Limpiar contenido de ruido (headers, footers)
            contenido = self._limpiar_ruido(contenido)

            # Verificar si tiene contenido real (más que solo referencia de reforma)
            tiene_contenido = len(contenido) > 20 and not self._es_solo_derogado(contenido)

            return tiene_contenido, contenido[:150]

        return False, ""

    def _limpiar_ruido(self, texto: str) -> str:
        """Remueve ruido común de headers/footers."""
        lineas = texto.split('\n')
        lineas_limpias = []

        for linea in lineas:
            linea = linea.strip()
            # Ignorar líneas de ruido
            if re.match(r'^\d+\s+de\s+\d+$', linea):  # "1 de 450"
                continue
            if re.match(r'^Cámara de Diputados', linea, re.IGNORECASE):
                continue
            if re.match(r'^Secretaría', linea, re.IGNORECASE):
                continue
            if re.match(r'^Última Reforma', linea, re.IGNORECASE):
                continue
            if re.match(r'^LEY\s+', linea):
                continue
            if len(linea) < 3:
                continue
            lineas_limpias.append(linea)

        return ' '.join(lineas_limpias)

    def _es_solo_derogado(self, texto: str) -> bool:
        """Verifica si el contenido es solo 'Se deroga'."""
        texto_limpio = re.sub(r'\s+', ' ', texto.lower().strip())
        return texto_limpio in ['se deroga', 'se deroga.', '(se deroga)', '(se deroga).']

    def _cargar_json_git(self) -> dict:
        """Carga contenido.json desde git HEAD."""
        try:
            relative_path = self.json_path.relative_to(BASE_DIR)
            result = subprocess.run(
                ["git", "show", f"HEAD:{relative_path}"],
                cwd=BASE_DIR, capture_output=True, text=True
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return {"articulos": []}

    def _cargar_json_disco(self) -> dict:
        """Carga contenido.json desde disco."""
        if not self.json_path.exists():
            return {"articulos": []}
        with open(self.json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _articulo_tiene_contenido(self, art: dict) -> bool:
        """Verifica si un artículo tiene contenido."""
        if art.get("parrafos"):
            return True
        contenido = art.get("contenido", "").strip()
        if contenido and not self._es_solo_derogado(contenido):
            return True
        return False

    def _detectar_cambios(self) -> list[CambioArticulo]:
        """Detecta artículos que cambiaron entre git HEAD y disco."""
        json_antes = self._cargar_json_git()
        json_despues = self._cargar_json_disco()

        # Indexar por número normalizado
        antes_map = {}
        for art in json_antes.get("articulos", []):
            key = self._normalizar_numero(art["numero"])
            antes_map[key] = art

        despues_map = {}
        for art in json_despues.get("articulos", []):
            key = self._normalizar_numero(art["numero"])
            despues_map[key] = art

        cambios = []
        todos_nums = set(antes_map.keys()) | set(despues_map.keys())

        for num in todos_nums:
            art_antes = antes_map.get(num)
            art_despues = despues_map.get(num)

            antes_tiene = self._articulo_tiene_contenido(art_antes) if art_antes else False
            despues_tiene = self._articulo_tiene_contenido(art_despues) if art_despues else False

            # Solo registrar si hubo cambio
            if antes_tiene != despues_tiene:
                if not antes_tiene and despues_tiene:
                    tipo = "agregado"
                elif antes_tiene and not despues_tiene:
                    tipo = "eliminado"
                else:
                    tipo = "modificado"

                # Obtener página del artículo
                art_ref = art_despues or art_antes
                pagina = art_ref.get("pagina", 1) if art_ref else 1

                cambios.append(CambioArticulo(
                    numero=art_ref.get("numero", num) if art_ref else num,
                    pagina=pagina,
                    antes_tiene_contenido=antes_tiene,
                    despues_tiene_contenido=despues_tiene,
                    tipo_cambio=tipo
                ))

        return cambios

    def verificar(self) -> ResultadoLey:
        """Ejecuta verificación de no-regresión."""
        resultado = ResultadoLey(codigo=self.codigo)

        # 1. Detectar qué cambió
        cambios = self._detectar_cambios()

        if not cambios:
            print("   Sin cambios en artículos")
            return resultado

        print(f"   {len(cambios)} artículos con cambios")

        # 2. Para cada cambio, verificar contra PDF con pdftotext
        for cambio in cambios:
            print(f"   Verificando Art. {cambio.numero} (pág. {cambio.pagina})...")

            # Usar pdftotext como segunda opinión
            pdf_tiene, muestra = self._verificar_articulo_en_pdf(
                cambio.numero, cambio.pagina
            )

            # 3. Determinar veredicto
            veredicto, detalle = self._evaluar_cambio(
                pdf_tiene=pdf_tiene,
                antes_tiene=cambio.antes_tiene_contenido,
                despues_tiene=cambio.despues_tiene_contenido,
                tipo_cambio=cambio.tipo_cambio,
                muestra_pdf=muestra
            )

            resultado.articulos.append(ResultadoArticulo(
                numero=cambio.numero,
                veredicto=veredicto,
                cambio=cambio.tipo_cambio,
                pdf_tiene=pdf_tiene,
                json_antes=cambio.antes_tiene_contenido,
                json_despues=cambio.despues_tiene_contenido,
                detalle=detalle
            ))

        return resultado

    def _evaluar_cambio(self, pdf_tiene: bool, antes_tiene: bool,
                        despues_tiene: bool, tipo_cambio: str,
                        muestra_pdf: str) -> tuple[str, str]:
        """
        Evalúa si un cambio es mejora o regresión.

        Regla:
        - Si DESPUÉS coincide con PDF → MEJORA (o neutral)
        - Si DESPUÉS difiere de PDF → REGRESIÓN
        """

        # Caso: Se agregó contenido
        if tipo_cambio == "agregado":
            if pdf_tiene:
                return "MEJORA", f"Agregó contenido que SÍ está en PDF"
            else:
                return "REGRESION", f"Agregó contenido que NO está en PDF (fantasma)"

        # Caso: Se eliminó contenido
        if tipo_cambio == "eliminado":
            if pdf_tiene:
                return "REGRESION", f"Eliminó contenido que SÍ está en PDF"
            else:
                return "MEJORA", f"Eliminó contenido fantasma (no está en PDF)"

        # Caso: Se modificó
        if despues_tiene == pdf_tiene:
            return "MEJORA", "Cambio alinea con PDF"
        else:
            return "REGRESION", "Cambio difiere de PDF"


def imprimir_resultado(resultado: ResultadoLey):
    """Imprime resultado de verificación."""
    print("\n" + "=" * 70)
    print(f"RESULTADO VERIFICACIÓN: {resultado.codigo}")
    print("=" * 70)

    if not resultado.articulos:
        print("\n✓ Sin cambios que verificar")
        return

    # Regresiones
    regresiones = [a for a in resultado.articulos if a.veredicto == "REGRESION"]
    if regresiones:
        print("\n" + "-" * 70)
        print("✗ REGRESIONES (bloquean commit):")
        print("-" * 70)
        for art in regresiones:
            print(f"  Art. {art.numero} [{art.cambio}]")
            print(f"    PDF: {'✓' if art.pdf_tiene else '✗'} | "
                  f"Antes: {'✓' if art.json_antes else '✗'} | "
                  f"Después: {'✓' if art.json_despues else '✗'}")
            print(f"    → {art.detalle}")

    # Mejoras
    mejoras = [a for a in resultado.articulos if a.veredicto == "MEJORA"]
    if mejoras:
        print("\n" + "-" * 70)
        print("✓ MEJORAS:")
        print("-" * 70)
        for art in mejoras:
            print(f"  Art. {art.numero}: {art.detalle}")

    # Resumen
    print("\n" + "-" * 70)
    print("RESUMEN:")
    print(f"  Mejoras:     {resultado.mejoras}")
    print(f"  Regresiones: {resultado.regresiones}")

    if resultado.es_ok:
        print("\n✓ VERIFICACIÓN EXITOSA - Cambios son válidos")
    else:
        print("\n✗ VERIFICACIÓN FALLIDA - Hay regresiones")
        print("  Los cambios NO deben ser commiteados")


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/etl/verificar_no_regresion.py <CODIGO>")
        print("     python backend/etl/verificar_no_regresion.py --todas")
        sys.exit(1)

    if sys.argv[1] == "--todas":
        leyes = listar_leyes()
        todas_ok = True

        for codigo in leyes:
            config = get_config(codigo)
            if not config.get("pdf_path"):
                continue

            print(f"\n{'='*70}")
            print(f"Verificando {codigo}...")

            try:
                verificador = VerificadorNoRegresion(codigo)
                resultado = verificador.verificar()
                imprimir_resultado(resultado)

                if not resultado.es_ok:
                    todas_ok = False
            except Exception as e:
                print(f"ERROR: {e}")
                todas_ok = False

        sys.exit(0 if todas_ok else 1)

    else:
        codigo = sys.argv[1].upper()

        try:
            verificador = VerificadorNoRegresion(codigo)
            resultado = verificador.verificar()
            imprimir_resultado(resultado)
            sys.exit(0 if resultado.es_ok else 1)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
