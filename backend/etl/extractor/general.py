"""
Extractor para leyes con estructura estandar (CFF, LISR, LIVA, etc.).

Caracteristicas:
- Usa PyMuPDF (fitz) para lectura del PDF (flags de bold confiables)
- Lee estructura desde mapa_estructura.json (generado por extraer_mapa.py)
- Detecta articulos por texto bold en margen izquierdo
- Calcula jerarquia de parrafos por coordenadas X
"""

import re
import json
from typing import Optional
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError("PyMuPDF no instalado. Ejecuta: pip install pymupdf")

from .base import ExtractorBase, Parrafo, Articulo, Division, BASE_DIR, DetectorIdentificadores
from .fsm import TokenLinea, FSMExtraccion, calcular_all_bold


# =============================================================================
# CONSTANTES ESPECIFICAS
# =============================================================================

# Coordenadas X para deteccion de jerarquia
X_FRACCION = 85
X_INCISO = 114
X_NUMERAL = 142
X_TOLERANCE = 10

# Coordenadas X para deteccion de articulos
X_ARTICULO_MIN = 80
X_ARTICULO_MAX = 95

# Espaciado vertical
Y_PARAGRAPH_GAP = 12

# Patron para detectar seccion de transitorios
PATRON_TRANSITORIOS = re.compile(r'TRANSITORI[OA]S?', re.IGNORECASE)


# =============================================================================
# CLASE EXTRACTOR GENERAL
# =============================================================================

class ExtractorGeneral(ExtractorBase):
    """
    Extractor para leyes con estructura estandar.

    Caracteristicas:
    - Usa PyMuPDF (fitz) para lectura con flags de bold
    - Detecta articulos por bold + coordenadas X
    - Calcula padre_numero basandose en coordenadas X
    - Lee estructura desde mapa_estructura.json
    """

    def __init__(self, codigo: str, config: dict):
        super().__init__(codigo, config)
        self.pdf: fitz.Document = None

        # Compilar patrones
        self._patron_articulo = re.compile(
            config["patrones"]["articulo"],
            re.IGNORECASE | re.MULTILINE
        )
        self._patron_siguiente = re.compile(
            r'(?:ARTICULO|ARTÍCULO|Artículo)\s+\d+[oa]?(?:[-–_\s]*[A-Z])?'
            r'(?:[.\-–_\s]+(?:bis|Bis|Ter|Quáter|Quinquies|Sexies)(?:[-–_\s]+\d+)?)?\.[- –\s]',
            re.IGNORECASE
        )

        # Patrones extra para fin de articulos
        self._fin_articulos_extra = [
            re.compile(p, re.IGNORECASE)
            for p in config.get("fin_articulos_extra", [])
        ]

    # =========================================================================
    # METODOS ABSTRACTOS IMPLEMENTADOS
    # =========================================================================

    def abrir_pdf(self):
        """Abre el PDF con PyMuPDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {self.pdf_path}")
        self.pdf = fitz.open(str(self.pdf_path))

    def cerrar_pdf(self):
        """Cierra el PDF."""
        if self.pdf:
            self.pdf.close()
            self.pdf = None

    def _get_num_paginas(self) -> int:
        """Retorna numero de paginas."""
        return len(self.pdf) if self.pdf else 0

    def _extraer_texto_pagina(self, pagina: int) -> str:
        """Extrae texto de una pagina."""
        if self.pdf and 0 <= pagina < len(self.pdf):
            return self.pdf[pagina].get_text() or ""
        return ""

    def extraer_estructura(self) -> list[Division]:
        """
        Lee estructura desde mapa_estructura.json.

        El archivo es generado previamente por extraer_mapa.py
        que extrae el outline del PDF.
        """
        mapa_path = self.pdf_path.parent / "mapa_estructura.json"

        if not mapa_path.exists():
            print(f"   AVISO: {mapa_path.name} no existe, estructura vacia")
            return []

        with open(mapa_path, 'r', encoding='utf-8') as f:
            mapa = json.load(f)

        divisiones = []
        orden = 0

        # Procesar titulos
        for num_titulo, titulo_data in mapa.get("titulos", {}).items():
            orden += 1
            div_titulo = Division(
                tipo="titulo",
                numero=num_titulo,
                nombre=titulo_data.get("nombre"),
                orden=orden,
                padre_orden=None,
                pagina=titulo_data.get("pagina", 0)
            )
            divisiones.append(div_titulo)
            orden_titulo = orden

            # Procesar capitulos
            for num_cap, cap_data in titulo_data.get("capitulos", {}).items():
                orden += 1
                div_cap = Division(
                    tipo="capitulo",
                    numero=num_cap,
                    nombre=cap_data.get("nombre"),
                    orden=orden,
                    padre_orden=orden_titulo,
                    pagina=cap_data.get("pagina", 0)
                )
                divisiones.append(div_cap)
                orden_cap = orden

                # Procesar secciones
                for num_sec, sec_data in cap_data.get("secciones", {}).items():
                    orden += 1
                    div_sec = Division(
                        tipo="seccion",
                        numero=num_sec,
                        nombre=sec_data.get("nombre"),
                        orden=orden,
                        padre_orden=orden_cap,
                        pagina=sec_data.get("pagina", 0)
                    )
                    divisiones.append(div_sec)

        return divisiones

    def extraer_contenido(self) -> list[Articulo]:
        """
        Extrae articulos con parrafos usando coordenadas X/Y.

        Proceso:
        1. Escanear PDF para encontrar articulos (bold en margen)
        2. Extraer parrafos de cada articulo
        3. Calcular jerarquia por coordenadas X
        """
        articulos = []
        tipo_contenido = self.config["tipo_contenido"]

        # 1. Encontrar todos los articulos
        articulos_encontrados = self._encontrar_articulos()
        print(f"   Encontrados {len(articulos_encontrados)} {tipo_contenido}s")

        # 2. Extraer cada articulo
        for idx, (numero, pag_inicio) in enumerate(articulos_encontrados):
            # Determinar pagina fin
            if idx + 1 < len(articulos_encontrados):
                pag_fin = articulos_encontrados[idx + 1][1]
            else:
                # Último artículo: leer hasta el fin del PDF
                pag_fin = len(self.pdf) - 1

            # Extraer parrafos
            parrafos = self._extraer_parrafos_articulo(numero, pag_inicio, pag_fin)

            articulo = Articulo(
                numero=numero,
                tipo=tipo_contenido,
                parrafos=parrafos,
                orden=len(articulos) + 1,
                pagina=pag_inicio + 1
            )
            articulos.append(articulo)

        return articulos

    # =========================================================================
    # METODOS PRIVADOS - BUSQUEDA DE ARTICULOS
    # =========================================================================

    def _encontrar_articulos(self) -> list[tuple[str, int]]:
        """
        Escanea el PDF para encontrar articulos.

        Busca texto bold en coordenadas X del margen izquierdo
        que coincida con el patron de articulo.

        Returns:
            Lista de (numero_articulo, pagina)
        """
        articulos_encontrados = []
        numeros_vistos = set()

        # PyMuPDF siempre tiene info de fuentes via spans
        pdf_tiene_spans = True

        for i in range(len(self.pdf)):
            page = self.pdf[i]
            # Buscar articulos en bold
            if pdf_tiene_spans:
                articulos_bold = self._encontrar_articulos_bold(page)
                for numero in articulos_bold:
                    if numero not in numeros_vistos:
                        numeros_vistos.add(numero)
                        articulos_encontrados.append((numero, i))
            else:
                # Fallback: patron en texto
                text = page.get_text() or ""
                for match in self._patron_articulo.finditer(text):
                    numero = self._extraer_numero_articulo(match)
                    if numero and numero not in numeros_vistos:
                        numeros_vistos.add(numero)
                        articulos_encontrados.append((numero, i))

            # Detectar fin de articulos (TRANSITORIOS)
            if self._pagina_tiene_fin_articulos(page):
                break

        return articulos_encontrados

    def _encontrar_articulos_bold(self, page) -> list[str]:
        """Encuentra articulos en bold en una pagina usando PyMuPDF."""
        articulos_bold = []
        vistos = set()

        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Verificar primer span
                first_span = spans[0]
                span_text = first_span.get("text", "").strip()
                if not span_text or not span_text.upper().startswith('A'):
                    continue

                x_pos = first_span.get("origin", (0, 0))[0]
                flags = first_span.get("flags", 0)
                is_bold = flags & 16  # bit 4 = bold

                is_margen = X_ARTICULO_MIN <= x_pos <= X_ARTICULO_MAX

                if is_bold and is_margen:
                    # Construir texto de la línea
                    texto = "".join(s.get("text", "") for s in spans)
                    match = self._patron_articulo.match(texto)
                    if match:
                        numero = self._extraer_numero_articulo(match)
                        if numero and numero not in vistos:
                            vistos.add(numero)
                            articulos_bold.append(numero)

        return articulos_bold

    def _extraer_numero_articulo(self, match: re.Match) -> Optional[str]:
        """Extrae numero de articulo de un match regex."""
        grupos = match.groups()
        numero_base = grupos[0]
        ordinal = grupos[1] if len(grupos) > 1 else None
        letra = grupos[2] if len(grupos) > 2 else None
        sufijo = grupos[3] if len(grupos) > 3 else None
        sufijo_num = grupos[4] if len(grupos) > 4 else None

        numero = numero_base
        if ordinal:
            numero += ordinal.lower()
        if letra:
            numero += f"-{letra.upper()}"
        if sufijo:
            numero += f" {sufijo.capitalize()}"
            if sufijo_num:
                numero += f" {sufijo_num}"

        return numero

    def _pagina_tiene_fin_articulos(self, page) -> bool:
        """Detecta si la pagina tiene indicador de fin de articulos usando PyMuPDF."""
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Construir texto de la línea
                texto = "".join(s.get("text", "") for s in spans)

                if PATRON_TRANSITORIOS.search(texto):
                    first_span = spans[0]
                    x = first_span.get("origin", (0, 0))[0]
                    flags = first_span.get("flags", 0)
                    is_bold = flags & 16
                    is_centrado = x > 150
                    if is_bold and is_centrado:
                        return True

        # Buscar patrones extra
        if self._fin_articulos_extra:
            lineas = self._extraer_lineas_pagina(page)
            for linea in lineas:
                if linea.get('is_bold'):
                    for patron in self._fin_articulos_extra:
                        if patron.search(linea['text']):
                            return True

        return False

    # =========================================================================
    # METODOS PRIVADOS - EXTRACCION DE PARRAFOS
    # =========================================================================

    def _extraer_parrafos_articulo(self, numero: str, pag_inicio: int, pag_fin: int) -> list[Parrafo]:
        """Extrae parrafos de un articulo usando FSM basada en tokens."""
        referencias = []
        lineas_flush = None  # Líneas capturadas cuando FSM hace flush

        # Verificar si este artículo tiene excepción
        excepciones = self.config.get("excepciones", {})
        modo = excepciones.get(numero, "normal")

        # Construir patron especifico para este articulo
        numero_patron = re.escape(numero).replace(r'\-', r'\.?-')
        numero_patron = re.sub(
            r'\\ (bis|ter|quáter|quinquies|sexies)',
            '[.\\-–\\\\s]+\\1',
            numero_patron,
            flags=re.IGNORECASE
        )
        patron_este = re.compile(
            rf'(?:ARTICULO|ARTÍCULO|Artículo)\s+{numero_patron}[oa]?\.(?![-–]?[A-Za-z]|\s*(?:Bis|Ter|Quáter|Quinquies|Sexies))',
            re.IGNORECASE
        )

        # Crear FSM con el número del artículo
        fsm = FSMExtraccion(patron_este, numero_articulo=numero)

        # Obtener page_width para calcular centrado
        page_width = self.pdf[0].rect.width

        # Filtros Y
        y_header_max = self.filtro_y.get("header_max", 0)
        y_footer_min = self.filtro_y.get("footer_min", 999)
        ruido = self.config.get("ruido_lineas", [])

        terminado = False

        for pag_num in range(pag_inicio, pag_fin + 1):
            if terminado:
                break

            page = self.pdf[pag_num]
            y_offset = (pag_num - pag_inicio) * 800

            # Extraer líneas con información de spans para calcular all_bold
            for block in page.get_text('dict')['blocks']:
                if block.get('type') != 0:
                    continue

                for line in block.get('lines', []):
                    spans = line.get('spans', [])
                    if not spans:
                        continue

                    # Construir texto
                    text = ''.join(s.get('text', '') for s in spans).strip()
                    if not text:
                        continue

                    # Coordenadas
                    bbox = line.get('bbox', (0, 0, 0, 0))
                    x_min, y_local, x_max, _ = bbox
                    y_global = y_local + y_offset

                    # Filtrar por coordenada X mínima
                    if x_min < 70:
                        continue

                    # Filtrar header/footer
                    if y_local < y_header_max or y_local > y_footer_min:
                        continue

                    # Calcular propiedades
                    all_bold = calcular_all_bold(spans)
                    first_flags = spans[0].get('flags', 0) if spans else 0
                    is_bold_first = bool(first_flags & 16)
                    font_size = spans[0].get('size', 12) if spans else 12

                    # Crear diccionario de línea para referencias y ruido
                    linea_dict = {
                        'x': x_min, 'x_end': x_max, 'y': y_local,
                        'y_global': y_global, 'text': text,
                        'is_bold': is_bold_first, 'font_size': font_size,
                        'is_italic': bool(first_flags & 2),
                        'is_non_black': spans[0].get('color', 0) != 0 if spans else False
                    }

                    # Detectar referencias (antes de FSM)
                    if self._es_referencia(linea_dict):
                        if fsm.estado.name == 'DENTRO_ARTICULO':
                            referencias.append((y_global, text))
                        continue

                    # Filtrar ruido
                    if ruido and self._es_ruido(text, ruido):
                        continue

                    # En modo texto_plano, no usar FSM para filtrado estructural
                    if modo == "texto_plano":
                        # Lógica simplificada para texto_plano
                        match_inicio = patron_este.search(text)
                        if match_inicio:
                            text = text[match_inicio.end():].strip().lstrip('- ').strip()
                            if text:
                                fsm.lineas_articulo.append({
                                    'x': x_min, 'x_end': x_max, 'y': y_global,
                                    'y_local': y_local, 'pagina': pag_num + 1,
                                    'text': text, 'is_bold': is_bold_first, 'font_size': font_size
                                })
                            fsm.estado = fsm.estado  # Mantener estado
                            continue
                        if fsm.lineas_articulo:  # Ya empezamos a capturar
                            # Detectar fin
                            if self._patron_siguiente.match(text) and x_min >= 80:
                                terminado = True
                                break
                            fsm.lineas_articulo.append({
                                'x': x_min, 'x_end': x_max, 'y': y_global,
                                'y_local': y_local, 'pagina': pag_num + 1,
                                'text': text, 'is_bold': is_bold_first, 'font_size': font_size
                            })
                        continue

                    # Crear token para FSM
                    token = TokenLinea(
                        texto=text,
                        x_min=x_min,
                        x_max=x_max,
                        y=y_global,
                        all_bold=all_bold,
                        font_size=font_size,
                        page_width=page_width,
                        first_bold=is_bold_first,
                        y_local=y_local,
                        pagina=pag_num + 1
                    )

                    # Procesar con FSM
                    resultado = fsm.procesar(token)

                    if resultado:
                        if resultado.get('accion') == 'fin':
                            terminado = True
                            break
                        if resultado.get('accion') == 'flush':
                            # Capturar líneas del artículo antes de que se borren
                            lineas_flush = resultado.get('lineas', [])
                            terminado = True
                            break

            # Si la FSM terminó el artículo, salir
            if fsm.estado.name in ('ENTRE_ARTICULOS', 'FIN') or terminado:
                break

        # Obtener líneas del artículo: del flush si hubo, o de la FSM
        todas_lineas = lineas_flush if lineas_flush is not None else fsm.lineas_articulo

        # Consolidar lineas en parrafos (pasamos número de artículo para excepciones)
        lineas_consolidadas = self._consolidar_lineas(todas_lineas, modo, articulo=numero)
        parrafos = self._construir_parrafos(lineas_consolidadas, modo)

        # Asociar referencias a parrafos
        self._asociar_referencias(parrafos, lineas_consolidadas, referencias)

        return parrafos

    def _extraer_lineas_pagina(self, page) -> list[dict]:
        """Extrae lineas con coordenadas y propiedades de fuente usando PyMuPDF."""
        result = []

        # Obtener texto estructurado con dict
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Solo bloques de texto
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Coordenadas de la línea
                bbox = line.get("bbox", (0, 0, 0, 0))
                x0 = round(bbox[0])
                x1 = round(bbox[2])
                y = round(bbox[1])

                # Construir texto y detectar propiedades
                text_parts = []
                total_chars = 0
                bold_chars = 0
                italic_chars = 0
                font_size = 12
                is_non_black = False

                for span in spans:
                    span_text = span.get("text", "")
                    text_parts.append(span_text)

                    char_count = len(span_text.strip())
                    if char_count > 0:
                        total_chars += char_count
                        flags = span.get("flags", 0)

                        # Bold: bit 4 (valor 16)
                        if flags & 16:
                            bold_chars += char_count

                        # Italic: bit 1 (valor 2)
                        if flags & 2:
                            italic_chars += char_count

                        # Tamaño de fuente (del primer span con contenido)
                        if font_size == 12:
                            font_size = span.get("size", 12)

                        # Color (detectar si no es negro)
                        color = span.get("color", 0)
                        if color != 0:
                            is_non_black = True

                text = "".join(text_parts).strip()

                if text and x0 >= 70:
                    # Bold si el PRIMER span (identificador) es bold
                    first_flags = spans[0].get("flags", 0) if spans else 0
                    is_bold = bool(first_flags & 16)
                    is_italic = total_chars > 0 and (italic_chars / total_chars) > 0.5

                    result.append({
                        'x': x0, 'x_end': x1, 'y': y, 'text': text,
                        'is_italic': is_italic, 'is_bold': is_bold,
                        'is_non_black': is_non_black, 'font_size': font_size
                    })

        # Ordenar por Y
        result.sort(key=lambda r: r['y'])
        return result

    def _consolidar_lineas(self, lineas: list[dict], modo: str = "normal",
                            articulo: str = None) -> list[dict]:
        """Consolida lineas fisicas en parrafos logicos."""
        if not lineas:
            return []

        X_SANGRIA = 80
        X_MARGEN_DERECHO = 530
        Y_GAP_NORMAL = 15

        lineas_consolidadas = []
        buffer_texto = ""
        buffer_x = None
        buffer_y_fin = None
        buffer_x_end = None
        buffer_es_identificador = False  # Track si el buffer es un identificador
        buffer_tipo = None
        buffer_id = None
        buffer_y_local = None  # Coordenada Y local de primera linea (para sync PDF)
        buffer_pagina = None   # Numero de pagina de primera linea (para sync PDF)

        # Máquina de estados para validar identificadores en secuencia
        # Pasamos contexto de ley y artículo para detectar excepciones conocidas
        detector = DetectorIdentificadores(ley=self.codigo, articulo=articulo)

        for linea in lineas:
            x = linea['x']
            x_end = linea.get('x_end', 544)
            y = linea.get('y_global', linea['y'])
            text = linea['text']
            is_bold = linea.get('is_bold', False)

            # En modo texto_plano, no detectar identificadores
            # En modo normal, usar detector con validación de secuencia + contexto
            es_identificador_valido = False
            tipo_detectado = None
            id_detectado = None
            if modo != "texto_plano":
                # Guardar estado antes de detectar (para restaurar si rechazamos)
                estado_previo = detector.guardar_estado()
                tipo_detectado, id_detectado, _, secuencia_valida = detector.detectar(text)
                if secuencia_valida:
                    # Validar bold según config (default: True)
                    requiere_bold = self.config.get('requiere_bold', True)
                    if not requiere_bold or is_bold:
                        es_identificador_valido = True
                    else:
                        # No es bold y se requiere: restaurar estado del detector
                        detector.restaurar_estado(estado_previo)

            if es_identificador_valido:
                if buffer_texto:
                    lineas_consolidadas.append({
                        'x': buffer_x, 'y_fin': buffer_y_fin, 'text': buffer_texto,
                        'tipo_detectado': buffer_tipo, 'id_detectado': buffer_id,
                        'y_local': buffer_y_local, 'pagina': buffer_pagina
                    })
                buffer_texto = text
                buffer_x = x
                buffer_y_fin = y
                buffer_x_end = x_end
                buffer_es_identificador = True
                buffer_tipo = tipo_detectado
                buffer_id = id_detectado
                buffer_y_local = linea.get('y_local', linea['y'])
                buffer_pagina = linea.get('pagina')
                continue

            # Si el buffer es un identificador, concatenar contenido sin evaluar puntos
            if buffer_es_identificador:
                buffer_texto += " " + text
                buffer_y_fin = y
                buffer_x_end = x_end
                buffer_es_identificador = False  # Ya no es solo identificador
                continue

            if not buffer_texto:
                buffer_texto = text
                buffer_x = x
                buffer_y_fin = y
                buffer_x_end = x_end
                buffer_es_identificador = False
                buffer_y_local = linea.get('y_local', linea['y'])
                buffer_pagina = linea.get('pagina')
                continue

            # Calcular puntos para decidir si es nuevo parrafo
            puntos = 0
            y_gap = y - buffer_y_fin if buffer_y_fin else 0

            if x >= X_SANGRIA:
                puntos += 1
            if y_gap > Y_GAP_NORMAL:
                puntos += 1
            if buffer_x_end and buffer_x_end < X_MARGEN_DERECHO:
                puntos += 1
            if text.strip() and text.strip()[0].isupper():
                puntos += 1
            if buffer_texto.rstrip().endswith('.'):
                puntos += 1
            if is_bold:
                puntos += 1

            if puntos >= 4:
                lineas_consolidadas.append({
                    'x': buffer_x, 'y_fin': buffer_y_fin, 'text': buffer_texto,
                    'tipo_detectado': buffer_tipo, 'id_detectado': buffer_id,
                    'y_local': buffer_y_local, 'pagina': buffer_pagina
                })
                buffer_texto = text
                buffer_x = x
                buffer_y_fin = y
                buffer_x_end = x_end
                buffer_tipo = None
                buffer_id = None
                buffer_y_local = linea.get('y_local', linea['y'])
                buffer_pagina = linea.get('pagina')
            else:
                buffer_texto += " " + text
                buffer_y_fin = y
                buffer_x_end = x_end

        if buffer_texto:
            lineas_consolidadas.append({
                'x': buffer_x, 'y_fin': buffer_y_fin, 'text': buffer_texto,
                'tipo_detectado': buffer_tipo, 'id_detectado': buffer_id,
                'y_local': buffer_y_local, 'pagina': buffer_pagina
            })

        return lineas_consolidadas

    def _construir_parrafos(self, lineas_consolidadas: list[dict], modo: str = "normal") -> list[Parrafo]:
        """Construye parrafos con jerarquia desde lineas consolidadas."""
        parrafos = []
        numero = 0
        ultimo_por_x = {}

        def encontrar_padre_por_x(x_actual: int) -> Optional[int]:
            candidatos = [
                (x_key, num) for x_key, num in ultimo_por_x.items()
                if x_key < x_actual - X_TOLERANCE
            ]
            if not candidatos:
                return None
            candidatos.sort(key=lambda t: t[0], reverse=True)
            return candidatos[0][1]

        for linea in lineas_consolidadas:
            x, text = linea['x'], linea['text']
            if not text.strip():
                continue

            # Usar tipo/identificador ya detectado en consolidación
            tipo = linea.get('tipo_detectado') or 'texto'
            identificador = linea.get('id_detectado')

            # En modo texto_plano, todo es tipo "texto"
            if modo == "texto_plano":
                tipo, identificador = 'texto', None

            # Extraer contenido (quitar identificador del texto)
            if identificador:
                # Buscar y quitar el identificador del inicio
                import re
                patron = re.compile(rf'^{re.escape(identificador)}\.?\s*[-–]?\s*', re.IGNORECASE)
                contenido = patron.sub('', text).strip()
            else:
                contenido = text
            contenido_limpio = self._normalizar_espacios(contenido)

            # Determinar padre
            if tipo == 'fraccion':
                padre = None
            elif tipo in ('inciso', 'numeral'):
                padre = encontrar_padre_por_x(x)
            elif tipo == 'apartado':
                padre = None
            elif tipo == 'texto':
                if x < X_FRACCION + X_TOLERANCE:
                    padre = None
                else:
                    padre = encontrar_padre_por_x(x)
            else:
                padre = None

            numero += 1
            x_id = round(x)
            x_texto = x_id + 22 if identificador else x_id

            # Coordenadas para sincronizacion PDF
            y_local = linea.get('y_local')
            y_pdf = round(y_local) if y_local is not None else None
            pagina_pdf = linea.get('pagina')

            parrafos.append(Parrafo(
                numero=numero,
                tipo=tipo,
                identificador=identificador,
                contenido=contenido_limpio,
                padre_numero=padre,
                x_id=x_id,
                x_texto=x_texto,
                y=y_pdf,
                pagina=pagina_pdf
            ))

            # Actualizar tracking
            x_key = round(x / 10) * 10
            ultimo_por_x[x_key] = numero
            ultimo_por_x = {k: v for k, v in ultimo_por_x.items() if k <= x_key}

        return parrafos

    def _asociar_referencias(self, parrafos: list[Parrafo], lineas_consolidadas: list[dict],
                            referencias: list[tuple[int, str]]):
        """Asocia referencias a sus parrafos correspondientes."""
        if not referencias or not parrafos or len(parrafos) != len(lineas_consolidadas):
            return

        for ref_y, ref_texto in referencias:
            mejor_idx = -1
            mejor_y = -1

            for idx, linea_cons in enumerate(lineas_consolidadas):
                y_fin = linea_cons.get('y_fin', 0)
                if y_fin < ref_y and y_fin > mejor_y:
                    mejor_y = y_fin
                    mejor_idx = idx

            if mejor_idx >= 0:
                p = parrafos[mejor_idx]
                if p.referencias is None:
                    p.referencias = []
                p.referencias.append(ref_texto)

    # =========================================================================
    # UTILIDADES
    # =========================================================================

    def _es_referencia(self, linea: dict) -> bool:
        """Determina si una linea es referencia DOF."""
        config_ref = self.config.get("referencias")
        if not config_ref:
            return False

        is_italic = linea.get('is_italic', False)
        is_non_black = linea.get('is_non_black', False)
        font_size = linea.get('font_size', 12)
        size_max = config_ref.get('size_max', 10)

        cumple_italic = not config_ref.get('font_italic', False) or is_italic
        cumple_color = not config_ref.get('color_no_negro', False) or is_non_black
        cumple_size = font_size <= size_max

        return cumple_italic and cumple_color and cumple_size

    def _es_ruido(self, text: str, patrones: list[str]) -> bool:
        """Verifica si el texto es ruido a filtrar."""
        for patron in patrones:
            if '^' in patron or '$' in patron:
                if re.match(patron, text):
                    return True
            else:
                if patron in text:
                    return True
        return False

    def _es_fin_articulos(self, texto: str) -> bool:
        """Detecta si el texto indica fin de articulos."""
        if PATRON_TRANSITORIOS.search(texto):
            return True
        for patron in self._fin_articulos_extra:
            if patron.search(texto):
                return True
        return False
