#!/usr/bin/env python3
"""
Extractor de CFF desde PDF
==========================

Extrae artículos del Código Fiscal de la Federación desde el PDF oficial,
incluyendo fracciones, incisos y párrafos finales.

Arquitectura (basada en extractor híbrido RMF):
┌─────────────────────────────────────────────────────────────┐
│                      EXTRACTOR CFF                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │  PyMuPDF    │ --> │   Parser    │ --> │  Validador  │   │
│  │   (PDF)     │     │ (fracciones)│     │  (calidad)  │   │
│  └─────────────┘     └─────────────┘     └─────────────┘   │
│                                                │            │
│                                                ▼            │
│                                         ┌─────────────┐    │
│                                         │    JSON     │    │
│                                         │  validado   │    │
│                                         └─────────────┘    │
└─────────────────────────────────────────────────────────────┘

Salida JSON:
{
  "estructura": {"titulos": [...], "capitulos": [...]},
  "articulos": [
    {
      "numero_raw": "17-H BIS",
      "numero_base": 17,
      "sufijo": "H BIS",
      "titulo": "...",
      "contenido": "Solo párrafo introductorio",
      "fracciones": [
        {"tipo": "fraccion", "numero": "I", "contenido": "..."},
        {"tipo": "inciso", "numero": "a", "contenido": "...", "padre": "XIII"},
        {"tipo": "parrafo", "contenido": "Párrafo final después de fracciones"}
      ],
      "referencias": "CFF 17-D, 19...",
      "pagina": 24
    }
  ]
}

Uso:
    python scripts/cff/extractor_cff.py
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).parent.parent.parent
PDF_PATH = BASE_DIR / "doc/leyes/cff/cff_codigo_fiscal_de_la_federacion.pdf"
OUTPUT_PATH = BASE_DIR / "doc/leyes/cff/cff_extraido.json"


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class Fraccion:
    """Fracción, inciso, numeral o párrafo de un artículo."""
    tipo: str           # 'fraccion', 'inciso', 'numeral', 'parrafo'
    numero: Optional[str]  # 'I', 'a', '1', None para párrafos
    contenido: str
    orden: int = 0
    padre: Optional[str] = None  # Para incisos: número de fracción padre

    def to_dict(self) -> dict:
        d = {
            "tipo": self.tipo,
            "numero": self.numero,
            "contenido": self.contenido,
            "orden": self.orden
        }
        if self.padre:
            d["padre"] = self.padre
        return d


@dataclass
class Articulo:
    """Artículo completo con metadata."""
    numero_raw: str         # "17-H BIS", "9o", "32-A"
    numero_base: int        # 17, 9, 32
    sufijo: Optional[str]   # "H BIS", None, "A"
    ordinal: Optional[str]  # "o", "a", None
    contenido: str          # Solo párrafo introductorio
    fracciones: list[Fraccion] = field(default_factory=list)
    referencias: Optional[str] = None
    pagina: int = 0
    es_transitorio: bool = False

    def to_dict(self) -> dict:
        return {
            "numero_raw": self.numero_raw,
            "numero_base": self.numero_base,
            "sufijo": self.sufijo,
            "ordinal": self.ordinal,
            "contenido": self.contenido,
            "fracciones": [f.to_dict() for f in self.fracciones],
            "referencias": self.referencias,
            "pagina": self.pagina,
            "es_transitorio": self.es_transitorio
        }


# =============================================================================
# PATRONES REGEX
# =============================================================================

# Números romanos válidos
ROMANOS = [
    'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
    'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX',
    'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX',
    'XXXI', 'XXXII', 'XXXIII', 'XXXIV', 'XXXV'
]
ROMANOS_SET = set(ROMANOS)

# Patrón para artículos: "Artículo 17-H Bis." al inicio de línea
# Captura: número base, ordinal opcional, sufijo letra, sufijo latino
PATRON_ARTICULO = re.compile(
    r'\n\s*Artículo\s+'
    r'(\d+)'                                # Grupo 1: número base (17)
    r'([oa])?'                              # Grupo 2: ordinal (o, a)
    r'(?:[-–\s]*'
    r'([A-Z])?'                             # Grupo 3: letra sufijo (H)
    r')?'
    r'(?:\s+'
    r'(Bis|Ter|Qu[áa]ter|Quinquies|Sexies)' # Grupo 4: sufijo latino
    r')?'
    r'\.',                                  # Punto final obligatorio
    re.IGNORECASE
)

# Fracción romana: "I." o "I. " al inicio de línea (con espacio después del punto en PDF)
PATRON_FRACCION = re.compile(r'^([IVXL]+)\.\s*$', re.MULTILINE)

# Inciso: "a)" al inicio de línea
PATRON_INCISO = re.compile(r'^([a-z])\)\s*$', re.MULTILINE)

# Numeral: "1." al inicio de línea (números pequeños)
PATRON_NUMERAL = re.compile(r'^(\d{1,2})\.\s*$', re.MULTILINE)

# Encabezados de página a limpiar
PATRON_ENCABEZADO = re.compile(
    r'CÓDIGO FISCAL DE LA FEDERACIÓN.*?(?:Parlamentarios|DOF \d{2}-\d{2}-\d{4})\s*',
    re.DOTALL
)
PATRON_PIE_PAGINA = re.compile(r'\n\s*\d+\s+de\s+\d+\s*\n')

# Referencias legales al final
PATRON_REFERENCIAS = re.compile(
    r'\n\s*((?:CFF|LISR|LIVA|LIEPS|LFD|RCFF|LSS|LFT|CPEUM|Ley|Código)[\s\d\-,;\.o°y]+)+\s*$',
    re.IGNORECASE
)


# =============================================================================
# EXTRACTOR PDF
# =============================================================================

class ExtractorCFF:
    """Extrae artículos del CFF desde PDF."""

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(str(pdf_path))
        self._texto: Optional[str] = None

    def _get_texto(self) -> str:
        """Obtiene todo el texto del PDF con marcadores de página."""
        if self._texto is not None:
            return self._texto

        partes = []
        for i, page in enumerate(self.doc):
            partes.append(f"\n[PAGE:{i+1}]\n")
            partes.append(page.get_text())

        self._texto = ''.join(partes)
        return self._texto

    def _limpiar_contenido(self, texto: str) -> str:
        """Limpia encabezados, pies de página y normaliza espacios."""
        # Quitar marcadores de página
        texto = re.sub(r'\[PAGE:\d+\]', '', texto)

        # Quitar números de página tipo "24 de 375"
        texto = re.sub(r'\n\s*\d+\s+de\s+\d+\s*\n', '\n', texto)

        # Quitar encabezados de página (CÁMARA DE DIPUTADOS...)
        texto = re.sub(
            r'CÁMARA DE DIPUTADOS[^\n]*\n[^\n]*Secretaría General[^\n]*\n[^\n]*Parlamentarios[^\n]*\n',
            '\n', texto
        )
        texto = PATRON_ENCABEZADO.sub('', texto)

        # Quitar "Última Reforma DOF..." que aparece como línea suelta
        texto = re.sub(r'\n\s*Última\s+Reforma\s+DOF[^\n]*\n', '\n', texto, flags=re.I)

        # Quitar notas de reforma entre fracciones
        texto = re.sub(r'\n\s*-?\s*(?:Párrafo|Fracción|Artículo|Inciso)\s+(?:reformad|adicionad|derogad)[^\n]*DOF[^\n]*\n', '\n', texto, flags=re.I)

        # Normalizar separadores de párrafo
        texto = re.sub(r'\n\s*\n+', '\n\n', texto)

        # Normalizar fracciones: "I.  \n" -> "I. "
        texto = re.sub(r'([IVXL]+)\.\s*\n', r'\1. ', texto)

        return texto.strip()

    def _parsear_fracciones(self, contenido: str) -> tuple[str, list[Fraccion]]:
        """
        Separa el contenido introductorio de las fracciones.

        Returns:
            tuple: (contenido_intro, lista_fracciones)
        """
        fracciones = []
        lineas = contenido.split('\n\n')

        contenido_intro_partes = []
        en_fracciones = False
        ultima_fraccion = None
        orden = 0

        for bloque in lineas:
            bloque = bloque.strip()
            if not bloque:
                continue

            # Detectar fracción romana: "I. Contenido..."
            match = re.match(r'^([IVXL]+)\.\s+(.+)$', bloque, re.DOTALL)
            if match and match.group(1) in ROMANOS_SET:
                en_fracciones = True
                orden += 1
                numero = match.group(1)
                texto = ' '.join(match.group(2).split())  # Normalizar espacios

                fraccion = Fraccion(
                    tipo='fraccion',
                    numero=numero,
                    contenido=texto,
                    orden=orden
                )
                fracciones.append(fraccion)
                ultima_fraccion = numero
                continue

            # Detectar inciso: "a) Contenido..."
            match = re.match(r'^([a-z])\)\s+(.+)$', bloque, re.DOTALL)
            if match:
                en_fracciones = True
                orden += 1
                texto = ' '.join(match.group(2).split())

                fraccion = Fraccion(
                    tipo='inciso',
                    numero=match.group(1),
                    contenido=texto,
                    orden=orden,
                    padre=ultima_fraccion
                )
                fracciones.append(fraccion)
                continue

            # Detectar numeral: "1. Contenido..."
            match = re.match(r'^(\d{1,2})\.\s+(.+)$', bloque, re.DOTALL)
            if match and int(match.group(1)) <= 20:
                en_fracciones = True
                orden += 1
                texto = ' '.join(match.group(2).split())

                fraccion = Fraccion(
                    tipo='numeral',
                    numero=match.group(1),
                    contenido=texto,
                    orden=orden,
                    padre=ultima_fraccion
                )
                fracciones.append(fraccion)
                continue

            # Si ya estamos en fracciones, este es un párrafo final
            if en_fracciones:
                # Filtrar basura (notas de reforma DOF, encabezados de página, etc.)
                es_basura = (
                    re.match(r'^(Párrafo|Fracción|Artículo)\s+(reformad|adicionad|derogad)', bloque, re.I) or
                    re.search(r'DOF\s+\d{2}-\d{2}-\d{4}', bloque) or
                    re.match(r'^Última\s+Reforma', bloque, re.I) or
                    re.match(r'^-\s*(Reformad|Adicionad|Derogad)', bloque, re.I) or
                    'Cámara de Diputados' in bloque or
                    'Secretaría de Servicios Parlamentarios' in bloque or
                    re.match(r'^\d+\s+de\s+\d+$', bloque)  # Número de página
                )

                if not es_basura and len(bloque) > 20:  # Párrafo significativo
                    orden += 1
                    fraccion = Fraccion(
                        tipo='parrafo',
                        numero=None,
                        contenido=' '.join(bloque.split()),
                        orden=orden
                    )
                    fracciones.append(fraccion)
            else:
                # Todavía en contenido introductorio
                contenido_intro_partes.append(bloque)

        contenido_intro = '\n\n'.join(contenido_intro_partes)
        return contenido_intro, fracciones

    def _extraer_referencias(self, texto: str) -> tuple[str, Optional[str]]:
        """Extrae referencias legales del final del texto."""
        match = PATRON_REFERENCIAS.search(texto)
        if match:
            referencias = match.group(0).strip()
            texto = texto[:match.start()].strip()
            return texto, referencias
        return texto, None

    def extraer_articulos(self) -> list[Articulo]:
        """Extrae todos los artículos del PDF."""
        texto = self._get_texto()
        articulos = []

        # Encontrar todas las posiciones de artículos
        matches = list(PATRON_ARTICULO.finditer(texto))
        print(f"   Encontrados {len(matches)} artículos en el PDF")

        for i, match in enumerate(matches):
            numero_base = int(match.group(1))
            ordinal = match.group(2)
            letra_sufijo = match.group(3)
            sufijo_latino = match.group(4)

            # Construir sufijo
            sufijo_partes = []
            if letra_sufijo:
                sufijo_partes.append(letra_sufijo.upper())
            if sufijo_latino:
                sufijo_partes.append(sufijo_latino.upper())
            sufijo = " ".join(sufijo_partes) if sufijo_partes else None

            # Construir numero_raw
            numero_raw = str(numero_base)
            if ordinal:
                numero_raw += ordinal.lower()
            if sufijo:
                numero_raw += f"-{sufijo}"

            # Extraer contenido hasta el siguiente artículo
            pos_inicio = match.end()
            if i + 1 < len(matches):
                pos_fin = matches[i + 1].start()
            else:
                pos_fin = len(texto)

            contenido_raw = texto[pos_inicio:pos_fin]

            # Limpiar contenido
            contenido_limpio = self._limpiar_contenido(contenido_raw)

            # Extraer referencias
            contenido_limpio, referencias = self._extraer_referencias(contenido_limpio)

            # Parsear fracciones
            contenido_intro, fracciones = self._parsear_fracciones(contenido_limpio)

            # Calcular página
            texto_antes = texto[:match.start()]
            pagina = texto_antes.count('[PAGE:') + 1

            articulo = Articulo(
                numero_raw=numero_raw,
                numero_base=numero_base,
                sufijo=sufijo,
                ordinal=ordinal.lower() if ordinal else None,
                contenido=contenido_intro,
                fracciones=fracciones,
                referencias=referencias,
                pagina=pagina
            )
            articulos.append(articulo)

        return articulos

    def extraer_estructura(self) -> dict:
        """Extrae la estructura jerárquica de títulos, capítulos y secciones."""
        texto = self._get_texto()

        divisiones = []
        orden = 0

        # Patrón unificado para detectar títulos, capítulos y secciones
        patron = re.compile(
            r'(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+'
            r'(PRIMERO|PRIMERA|SEGUNDO|SEGUNDA|TERCERO|TERCERA|CUARTO|CUARTA|'
            r'QUINTO|QUINTA|SEXTO|SEXTA|S[ÉE]PTIMO|S[ÉE]PTIMA|OCTAVO|OCTAVA|'
            r'NOVENO|NOVENA|D[ÉE]CIMO|D[ÉE]CIMA|[IVX]+|[ÚU]NICO|[ÚU]NICA)\s*\n\s*(.+?)(?=\n)',
            re.IGNORECASE
        )

        # Rastrear jerarquía actual
        titulo_actual = None
        capitulo_actual = None

        for match in patron.finditer(texto):
            tipo_raw = match.group(1).upper()
            numero = match.group(2).upper()
            nombre = match.group(3).strip()

            # Filtrar nombres basura
            if not nombre or len(nombre) < 5:
                continue
            if any(x in nombre for x in ['Artículo', 'DOF', '[PAGE:', 'Capítulo', 'Sección', '"']):
                continue

            orden += 1

            if 'TITULO' in tipo_raw or 'TÍTULO' in tipo_raw:
                titulo_actual = numero
                capitulo_actual = None
                divisiones.append({
                    'tipo': 'titulo',
                    'numero': numero,
                    'nombre': nombre,
                    'path_texto': f"Título {numero}",
                    'orden': orden
                })

            elif 'CAPITULO' in tipo_raw or 'CAPÍTULO' in tipo_raw:
                capitulo_actual = numero
                path = f"Título {titulo_actual} > Capítulo {numero}" if titulo_actual else f"Capítulo {numero}"
                divisiones.append({
                    'tipo': 'capitulo',
                    'numero': numero,
                    'nombre': nombre,
                    'path_texto': path,
                    'padre': f"Título {titulo_actual}" if titulo_actual else None,
                    'orden': orden
                })

            elif 'SECCION' in tipo_raw or 'SECCIÓN' in tipo_raw:
                if titulo_actual and capitulo_actual:
                    path = f"Título {titulo_actual} > Capítulo {capitulo_actual} > Sección {numero}"
                    padre = f"Título {titulo_actual} > Capítulo {capitulo_actual}"
                elif capitulo_actual:
                    path = f"Capítulo {capitulo_actual} > Sección {numero}"
                    padre = f"Capítulo {capitulo_actual}"
                else:
                    path = f"Sección {numero}"
                    padre = None

                divisiones.append({
                    'tipo': 'seccion',
                    'numero': numero,
                    'nombre': nombre,
                    'path_texto': path,
                    'padre': padre,
                    'orden': orden
                })

        return {'divisiones': divisiones}

    def close(self):
        self.doc.close()


# =============================================================================
# VALIDADOR
# =============================================================================

class ValidadorCFF:
    """Valida la calidad de los artículos extraídos."""

    def __init__(self):
        self.problemas = []
        self.estadisticas = {
            'total': 0,
            'con_fracciones': 0,
            'sin_contenido': 0,
            'contenido_corto': 0
        }

    def validar(self, articulos: list[Articulo]) -> list[Articulo]:
        """Valida y corrige artículos."""
        articulos_validos = []

        for art in articulos:
            self.estadisticas['total'] += 1

            # Validar contenido
            if not art.contenido and not art.fracciones:
                self.estadisticas['sin_contenido'] += 1
                self.problemas.append(f"{art.numero_raw}: sin contenido")
                continue

            if len(art.contenido) < 10 and not art.fracciones:
                self.estadisticas['contenido_corto'] += 1
                self.problemas.append(f"{art.numero_raw}: contenido muy corto ({len(art.contenido)} chars)")

            if art.fracciones:
                self.estadisticas['con_fracciones'] += 1

            articulos_validos.append(art)

        return articulos_validos

    def resumen(self) -> str:
        return (
            f"Validación: {self.estadisticas['total']} artículos, "
            f"{self.estadisticas['con_fracciones']} con fracciones, "
            f"{self.estadisticas['sin_contenido']} sin contenido, "
            f"{self.estadisticas['contenido_corto']} con contenido corto"
        )


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Ejecuta la extracción completa."""
    print("=" * 70)
    print("EXTRACTOR CFF")
    print("=" * 70)

    if not PDF_PATH.exists():
        print(f"ERROR: No se encontró el PDF en {PDF_PATH}")
        return 1

    # 1. Extraer del PDF
    print(f"\n1. Extrayendo del PDF: {PDF_PATH.name}")
    extractor = ExtractorCFF(PDF_PATH)

    articulos = extractor.extraer_articulos()
    estructura = extractor.extraer_estructura()
    extractor.close()

    divisiones = estructura.get('divisiones', [])
    print(f"   {len(articulos)} artículos extraídos")
    print(f"   {len([d for d in divisiones if d['tipo'] == 'titulo'])} títulos")
    print(f"   {len([d for d in divisiones if d['tipo'] == 'capitulo'])} capítulos")
    print(f"   {len([d for d in divisiones if d['tipo'] == 'seccion'])} secciones")

    # 2. Validar
    print("\n2. Validando calidad...")
    validador = ValidadorCFF()
    articulos = validador.validar(articulos)
    print(f"   {validador.resumen()}")

    if validador.problemas:
        print(f"   Primeros 5 problemas:")
        for p in validador.problemas[:5]:
            print(f"      - {p}")

    # 3. Estadísticas
    total_fracciones = sum(len(a.fracciones) for a in articulos)
    fracciones_tipo = {}
    for a in articulos:
        for f in a.fracciones:
            fracciones_tipo[f.tipo] = fracciones_tipo.get(f.tipo, 0) + 1

    print("\n3. Estadísticas:")
    print(f"   Total artículos: {len(articulos)}")
    print(f"   Total fracciones: {total_fracciones}")
    for tipo, count in sorted(fracciones_tipo.items(), key=lambda x: -x[1]):
        print(f"      {tipo}: {count}")

    # 4. Guardar JSON
    print(f"\n4. Guardando JSON: {OUTPUT_PATH.name}")
    resultado = {
        "ley": "Código Fiscal de la Federación",
        "codigo": "CFF",
        "estructura": estructura,
        "articulos": [a.to_dict() for a in articulos],
        "estadisticas": {
            "total_articulos": len(articulos),
            "total_fracciones": total_fracciones,
            "fracciones_por_tipo": fracciones_tipo,
            "problemas": len(validador.problemas)
        }
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"   Guardado en: {OUTPUT_PATH}")

    # 5. Verificar artículo específico
    print("\n5. Verificación de artículos clave:")
    for numero in ['17-H', '17-H BIS', '9o', '29']:
        for art in articulos:
            if art.numero_raw.upper() == numero.upper():
                print(f"\n   {art.numero_raw}:")
                print(f"      Contenido: {len(art.contenido)} chars")
                print(f"      Fracciones: {len(art.fracciones)}")
                if art.fracciones:
                    tipos = {}
                    for f in art.fracciones:
                        tipos[f.tipo] = tipos.get(f.tipo, 0) + 1
                    print(f"      Tipos: {tipos}")
                break

    print("\n" + "=" * 70)
    print("EXTRACCIÓN COMPLETADA")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(main())
