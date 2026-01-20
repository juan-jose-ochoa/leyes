"""
Extractor especifico para RMF (Resolucion Miscelanea Fiscal).

Caracteristicas:
- No tiene outline en el PDF
- Usa numeracion decimal jerarquica (2.1.1, 3.10.5)
- La estructura se deriva de la numeracion
- Usa PyMuPDF (fitz) en lugar de pdfplumber
"""

import re
from typing import Optional
from dataclasses import dataclass, field

try:
    import fitz
except ImportError:
    raise ImportError("PyMuPDF no instalado. Ejecuta: pip install pymupdf")

from .base import ExtractorBase, Parrafo, Articulo, Division


# =============================================================================
# CONSTANTES ESPECIFICAS RMF
# =============================================================================

# Dimensiones de pagina
PAGINA_WIDTH = 612
CENTRO_PAGINA = PAGINA_WIDTH / 2
TOLERANCIA_CENTRADO = 50

# Coordenadas X para clasificacion de parrafos
X_REGLA = 99           # Numero de regla
X_TEXTO = 156          # Texto normal y fracciones
X_INCISO = 198         # Incisos a), b), c)
X_NUMERAL = 241        # Numerales 1., 2., 3.
X_CONTENIDO_NUM = 269  # Contenido de numerales
X_TOLERANCIA = 10      # Tolerancia para comparacion

# Umbral para detectar nuevo parrafo
SALTO_PARRAFO = 12.5

# Patrones
PATRON_TITULO = re.compile(r'^Título\s+(\d+)\.\s+(.+)$')
PATRON_CAPITULO = re.compile(r'^Capítulo\s+(\d+\.\d+)\.\s+(.+)$')
PATRON_REGLA = re.compile(r'^(\d+\.\d+\.\d+(?:\.\d+)?)\.\s*$')
PATRON_REGLA_INICIO = re.compile(r'^(\d+\.\d+\.\d+(?:\.\d+)?)\.\s*')
PATRON_FRACCION = re.compile(r'^([IVX]+)\.\s*')
PATRON_INCISO = re.compile(r'^([a-z])\)\s*')
PATRON_NUMERAL = re.compile(r'^(\d+)\.\s*')
PATRON_REFERENCIAS = re.compile(
    r'^(CFF|LISR|LIVA|LIEPS|LIF|RCFF|RMF|RISR|RLISR|Ley|CPEUM|LCF|LSS|Convención)\s'
)
# Patrón para detectar encabezados de tabla numerados (ej: "1. 2. 3. 4. 5.")
PATRON_ENCABEZADO_TABLA = re.compile(r'^(\d+\.\s*)+$')


# =============================================================================
# DATACLASSES AUXILIARES (especificos de RMF)
# =============================================================================

@dataclass
class ReglaRef:
    """Referencia a una regla con su ubicacion."""
    numero: str
    pagina: int
    nombre: Optional[str] = None


@dataclass
class CapituloRef:
    """Capitulo con sus reglas."""
    numero: str
    nombre: Optional[str]
    pagina: int
    reglas: list[ReglaRef] = field(default_factory=list)


@dataclass
class TituloRef:
    """Titulo con sus capitulos."""
    numero: str
    nombre: Optional[str]
    pagina: int
    capitulos: list[CapituloRef] = field(default_factory=list)


# =============================================================================
# CLASE EXTRACTOR RMF
# =============================================================================

class ExtractorRMF(ExtractorBase):
    """
    Extractor especifico para Resolucion Miscelanea Fiscal.

    Caracteristicas:
    - Usa PyMuPDF (fitz) para lectura del PDF
    - Extrae estructura de Titulos/Capitulos del texto (no del outline)
    - Identifica reglas por patron numerico X.Y.Z
    - Clasifica parrafos por coordenadas X
    """

    def __init__(self, codigo: str, config: dict):
        super().__init__(codigo, config)
        self.doc: fitz.Document = None
        self._titulos: list[TituloRef] = []
        self._reglas_ref: list[ReglaRef] = []

    # =========================================================================
    # METODOS ABSTRACTOS IMPLEMENTADOS
    # =========================================================================

    def abrir_pdf(self):
        """Abre el PDF con PyMuPDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {self.pdf_path}")
        self.doc = fitz.open(str(self.pdf_path))

    def cerrar_pdf(self):
        """Cierra el PDF."""
        if self.doc:
            self.doc.close()
            self.doc = None

    def _get_num_paginas(self) -> int:
        """Retorna numero de paginas."""
        return len(self.doc) if self.doc else 0

    def _extraer_texto_pagina(self, pagina: int) -> str:
        """Extrae texto de una pagina."""
        if self.doc and 0 <= pagina < len(self.doc):
            return self.doc[pagina].get_text()
        return ""

    def extraer_estructura(self) -> list[Division]:
        """
        Extrae estructura jerarquica (Titulos/Capitulos) del PDF.

        Detecta lineas centradas y bold con patrones:
        - "Titulo X. Nombre"
        - "Capitulo X.Y. Nombre"
        """
        self._titulos = []
        titulo_actual = None

        y_header_max = self.filtro_y.get("header_max", 0)
        y_footer_min = self.filtro_y.get("footer_min", 999)

        for page_num, page in enumerate(self.doc):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    y_pos = line["bbox"][1]
                    if y_pos < y_header_max or y_pos > y_footer_min:
                        continue

                    # Reconstruir linea
                    texto_linea, x_min, x_max = self._reconstruir_linea(line)
                    if not texto_linea:
                        continue

                    # Solo procesar si centrado y bold
                    if not (self._es_centrado(x_min, x_max) and self._linea_es_bold(line["spans"])):
                        continue

                    # Es titulo?
                    match = PATRON_TITULO.match(texto_linea)
                    if match:
                        titulo_actual = TituloRef(
                            numero=match.group(1),
                            nombre=match.group(2).strip(),
                            pagina=page_num + 1
                        )
                        self._titulos.append(titulo_actual)
                        continue

                    # Es capitulo?
                    match = PATRON_CAPITULO.match(texto_linea)
                    if match:
                        if titulo_actual is None:
                            titulo_actual = TituloRef(numero="0", nombre="Preliminar", pagina=1)
                            self._titulos.append(titulo_actual)

                        capitulo = CapituloRef(
                            numero=match.group(1),
                            nombre=match.group(2).strip(),
                            pagina=page_num + 1
                        )
                        titulo_actual.capitulos.append(capitulo)

        # Convertir a Division para compatibilidad
        divisiones = []
        orden = 0
        for titulo in self._titulos:
            orden += 1
            div_titulo = Division(
                tipo="titulo",
                numero=titulo.numero,
                nombre=titulo.nombre,
                orden=orden,
                padre_orden=None,
                pagina=titulo.pagina
            )
            divisiones.append(div_titulo)
            orden_titulo = orden

            for cap in titulo.capitulos:
                orden += 1
                div_cap = Division(
                    tipo="capitulo",
                    numero=cap.numero,
                    nombre=cap.nombre,
                    orden=orden,
                    padre_orden=orden_titulo,
                    pagina=cap.pagina
                )
                divisiones.append(div_cap)

        return divisiones

    def extraer_contenido(self) -> list[Articulo]:
        """
        Extrae reglas con sus parrafos.

        Proceso:
        1. Encontrar todas las reglas (numeros X.Y.Z en bold)
        2. Asignar reglas a capitulos
        3. Extraer contenido de cada regla
        """
        # 1. Extraer referencias de reglas
        self._reglas_ref = self._extraer_reglas_ref()
        print(f"   Reglas encontradas: {len(self._reglas_ref)}")

        # 2. Asignar reglas a capitulos
        self._asignar_reglas_a_capitulos()

        # 3. Extraer contenido
        contenido_reglas = self._extraer_contenido_reglas()

        # 4. Convertir a lista de Articulo
        articulos = []
        orden = 0

        for titulo in self._titulos:
            for cap in titulo.capitulos:
                for regla_ref in cap.reglas:
                    orden += 1
                    contenido = contenido_reglas.get(regla_ref.numero)

                    if contenido:
                        parrafos = self._convertir_parrafos(contenido["parrafos"])
                        articulo = Articulo(
                            numero=regla_ref.numero,
                            tipo="regla",
                            parrafos=parrafos,
                            orden=orden,
                            pagina=regla_ref.pagina,
                            nombre=contenido.get("nombre"),
                            division=f"Titulo {titulo.numero} > Capitulo {cap.numero}",
                            referencias=contenido.get("referencias")
                        )
                    else:
                        articulo = Articulo(
                            numero=regla_ref.numero,
                            tipo="regla",
                            parrafos=[],
                            orden=orden,
                            pagina=regla_ref.pagina,
                            division=f"Titulo {titulo.numero} > Capitulo {cap.numero}"
                        )

                    articulos.append(articulo)

        return articulos

    # =========================================================================
    # METODOS PRIVADOS - EXTRACCION DE REGLAS
    # =========================================================================

    def _extraer_reglas_ref(self) -> list[ReglaRef]:
        """Extrae referencias de todas las reglas del PDF."""
        reglas = []
        reglas_vistas = set()

        y_header_max = self.filtro_y.get("header_max", 0)
        y_footer_min = self.filtro_y.get("footer_min", 999)

        for page_num, page in enumerate(self.doc):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    y_pos = line["bbox"][1]
                    if y_pos < y_header_max or y_pos > y_footer_min:
                        continue

                    for span in line["spans"]:
                        texto = span["text"].strip()
                        x = span["bbox"][0]

                        match = PATRON_REGLA.match(texto)
                        if match and self._es_bold(span["flags"]) and abs(x - X_REGLA) < X_TOLERANCIA:
                            numero = match.group(1)
                            if numero not in reglas_vistas:
                                reglas_vistas.add(numero)
                                reglas.append(ReglaRef(numero=numero, pagina=page_num + 1))

        return reglas

    def _asignar_reglas_a_capitulos(self):
        """Asigna reglas a capitulos basandose en la numeracion."""
        capitulos_idx = {}
        for titulo in self._titulos:
            for cap in titulo.capitulos:
                capitulos_idx[cap.numero] = cap

        for regla in self._reglas_ref:
            partes = regla.numero.split('.')
            if len(partes) >= 2:
                cap_num = f"{partes[0]}.{partes[1]}"
                if cap_num in capitulos_idx:
                    capitulos_idx[cap_num].reglas.append(regla)

    def _extraer_contenido_reglas(self) -> dict:
        """Extrae el contenido de cada regla."""
        contenido = {}

        y_header_max = self.filtro_y.get("header_max", 0)
        y_footer_min = self.filtro_y.get("footer_min", 999)

        # Crear conjunto de numeros de regla para busqueda rapida
        numeros_reglas = {r.numero for r in self._reglas_ref}

        # Estado del parser
        regla_actual = None
        parrafos_actuales = []
        nombre_regla = None
        texto_acumulado = ""
        tipo_parrafo = "texto"
        numero_parrafo = None
        y_anterior = None
        titulo_pendiente = None
        # Coordenadas del párrafo actual (para sincronización con PDF)
        pagina_parrafo = None
        y_parrafo = None

        def guardar_parrafo():
            nonlocal texto_acumulado, tipo_parrafo, numero_parrafo, pagina_parrafo, y_parrafo
            if texto_acumulado.strip():
                parrafos_actuales.append({
                    "tipo": tipo_parrafo,
                    "contenido": texto_acumulado.strip(),
                    "identificador": numero_parrafo,
                    "pagina": pagina_parrafo,
                    "y": int(y_parrafo) if y_parrafo is not None else None
                })
            texto_acumulado = ""
            tipo_parrafo = "texto"
            numero_parrafo = None
            pagina_parrafo = None
            y_parrafo = None

        def guardar_regla():
            nonlocal regla_actual, parrafos_actuales, nombre_regla, y_anterior
            if regla_actual:
                guardar_parrafo()

                # Filtrar referencias
                parrafos_finales = []
                referencias_lista = []
                for p in parrafos_actuales:
                    if p["tipo"] == "referencias":
                        referencias_lista.append(p["contenido"])
                    else:
                        parrafos_finales.append(p)

                contenido[regla_actual] = {
                    "nombre": nombre_regla,
                    "parrafos": parrafos_finales,
                    "referencias": " ".join(referencias_lista) if referencias_lista else None
                }

            regla_actual = None
            parrafos_actuales = []
            nombre_regla = None
            y_anterior = None

        # Procesar paginas
        for page_num, page in enumerate(self.doc):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    texto_linea, x_min, _ = self._reconstruir_linea(line)
                    y_actual = line["bbox"][1]

                    if y_actual < y_header_max or y_actual > y_footer_min:
                        continue

                    if not texto_linea:
                        continue

                    es_bold = self._linea_es_bold(line["spans"])
                    es_italica = self._linea_es_italica(line["spans"])

                    # Es inicio de nueva regla?
                    match_regla = PATRON_REGLA_INICIO.match(texto_linea)
                    if match_regla and abs(x_min - X_REGLA) < X_TOLERANCIA:
                        numero = match_regla.group(1)
                        if numero in numeros_reglas:
                            guardar_regla()
                            regla_actual = numero
                            y_anterior = None

                            if titulo_pendiente:
                                nombre_regla = titulo_pendiente
                                titulo_pendiente = None

                            if not nombre_regla:
                                resto = texto_linea[match_regla.end():].strip()
                                if resto:
                                    nombre_regla = resto
                            continue

                    # Saltar Titulo/Capitulo
                    if PATRON_TITULO.match(texto_linea) or PATRON_CAPITULO.match(texto_linea):
                        titulo_pendiente = None
                        continue

                    # Bold en X_TEXTO que NO es fraccion -> titulo de siguiente regla
                    if es_bold and abs(x_min - X_TEXTO) < X_TOLERANCIA:
                        if not PATRON_FRACCION.match(texto_linea):
                            # Ignorar encabezados de tabla numerados (ej: "1. 2. 3. 4.")
                            if PATRON_ENCABEZADO_TABLA.match(texto_linea):
                                continue
                            if titulo_pendiente:
                                titulo_pendiente += " " + texto_linea
                            else:
                                titulo_pendiente = texto_linea
                            continue

                    if not regla_actual:
                        continue

                    # Detectar referencias
                    if not es_bold and abs(x_min - X_TEXTO) < X_TOLERANCIA:
                        if PATRON_REFERENCIAS.match(texto_linea) or es_italica:
                            guardar_parrafo()
                            parrafos_actuales.append({
                                "tipo": "referencias",
                                "contenido": texto_linea,
                                "identificador": None
                            })
                            continue

                    # Clasificar por posicion X
                    if abs(x_min - X_CONTENIDO_NUM) < X_TOLERANCIA:
                        # Contenido de numeral
                        if texto_acumulado:
                            texto_acumulado += " " + texto_linea
                        else:
                            texto_acumulado = texto_linea
                            # Capturar coordenadas al iniciar párrafo
                            if pagina_parrafo is None:
                                pagina_parrafo = page_num + 1
                                y_parrafo = y_actual

                    elif abs(x_min - X_NUMERAL) < X_TOLERANCIA:
                        # Numeral 1., 2., 3.
                        match_num = PATRON_NUMERAL.match(texto_linea)
                        if match_num:
                            guardar_parrafo()
                            tipo_parrafo = "numeral"
                            numero_parrafo = match_num.group(1)
                            texto_acumulado = texto_linea[match_num.end():].strip()
                            # Capturar coordenadas del nuevo párrafo
                            pagina_parrafo = page_num + 1
                            y_parrafo = y_actual
                        else:
                            texto_acumulado += " " + texto_linea

                    elif abs(x_min - X_INCISO) < X_TOLERANCIA:
                        # Inciso a), b), c)
                        match_inc = PATRON_INCISO.match(texto_linea)
                        if match_inc:
                            guardar_parrafo()
                            tipo_parrafo = "inciso"
                            numero_parrafo = match_inc.group(1)
                            texto_acumulado = texto_linea[match_inc.end():].strip()
                            # Capturar coordenadas del nuevo párrafo
                            pagina_parrafo = page_num + 1
                            y_parrafo = y_actual
                        else:
                            texto_acumulado += " " + texto_linea

                    elif abs(x_min - X_TEXTO) < X_TOLERANCIA:
                        # Texto normal o fraccion
                        match_frac = PATRON_FRACCION.match(texto_linea)
                        if match_frac:
                            guardar_parrafo()
                            tipo_parrafo = "fraccion"
                            numero_parrafo = match_frac.group(1)
                            texto_acumulado = texto_linea[match_frac.end():].strip()
                            # Capturar coordenadas del nuevo párrafo
                            pagina_parrafo = page_num + 1
                            y_parrafo = y_actual
                        else:
                            # Detectar nuevo parrafo por salto Y
                            es_nuevo = (
                                y_anterior is not None and
                                (y_actual - y_anterior) > SALTO_PARRAFO and
                                texto_acumulado
                            )

                            if es_nuevo:
                                guardar_parrafo()
                                texto_acumulado = texto_linea
                                # Capturar coordenadas del nuevo párrafo
                                pagina_parrafo = page_num + 1
                                y_parrafo = y_actual
                            elif texto_acumulado:
                                texto_acumulado += " " + texto_linea
                            else:
                                texto_acumulado = texto_linea
                                # Capturar coordenadas al iniciar párrafo
                                pagina_parrafo = page_num + 1
                                y_parrafo = y_actual
                    else:
                        # Otra posicion - continuacion
                        if texto_acumulado:
                            texto_acumulado += " " + texto_linea
                        else:
                            # Inicio de párrafo en posición no estándar
                            texto_acumulado = texto_linea
                            pagina_parrafo = page_num + 1
                            y_parrafo = y_actual

                    y_anterior = y_actual

        # Guardar ultima regla
        guardar_regla()

        return contenido

    def _convertir_parrafos(self, parrafos_raw: list[dict]) -> list[Parrafo]:
        """Convierte diccionarios a objetos Parrafo."""
        resultado = []
        for idx, p in enumerate(parrafos_raw, start=1):
            parrafo = Parrafo(
                numero=idx,
                tipo=p["tipo"],
                identificador=p.get("identificador"),
                contenido=p["contenido"],
                padre_numero=None,  # Se calculara en _asignar_padres() de la base
                pagina=p.get("pagina"),
                y=p.get("y")
            )
            resultado.append(parrafo)
        return resultado

    # =========================================================================
    # UTILIDADES ESPECIFICAS PyMuPDF
    # =========================================================================

    def _reconstruir_linea(self, line: dict) -> tuple[str, float, float]:
        """Reconstruye texto de linea y retorna (texto, x_min, x_max)."""
        texto = ""
        x_min = float('inf')
        x_max = 0

        for span in line["spans"]:
            texto += span["text"]
            bbox = span["bbox"]
            x_min = min(x_min, bbox[0])
            x_max = max(x_max, bbox[2])

        return texto.strip(), x_min, x_max

    def _es_centrado(self, x_min: float, x_max: float) -> bool:
        """Determina si un elemento esta centrado."""
        centro_texto = (x_min + x_max) / 2
        return abs(centro_texto - CENTRO_PAGINA) < TOLERANCIA_CENTRADO

    def _es_bold(self, flags: int) -> bool:
        """Determina si el texto es bold."""
        return bool(flags & 2 ** 4)

    def _linea_es_bold(self, spans: list) -> bool:
        """Determina si >80% de la linea es bold."""
        texto_bold = 0
        texto_total = 0

        for span in spans:
            longitud = len(span["text"].strip())
            if longitud > 0:
                texto_total += longitud
                if self._es_bold(span["flags"]):
                    texto_bold += longitud

        return texto_total > 0 and (texto_bold / texto_total) > 0.8

    def _linea_es_italica(self, spans: list) -> bool:
        """Determina si >50% de la linea es italica."""
        texto_italic = 0
        texto_total = 0

        for span in spans:
            texto = span["text"].strip()
            if texto:
                texto_total += len(texto)
                if span["flags"] & 2:  # bit 1 = italic
                    texto_italic += len(texto)

        return texto_total > 0 and (texto_italic / texto_total) > 0.5
