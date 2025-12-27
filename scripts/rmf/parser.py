"""
Fase 2: Parsing "Deber Ser".

Parsea los párrafos según la estructura esperada de la RMF:
- Títulos (X.)
- Capítulos (X.Y.)
- Secciones (X.Y.Z.)
- Reglas (X.Y.Z. Contenido...)
  - Fracciones (I., II., III.)
  - Incisos (a), b), c))
  - Referencias (CFF, LISR, etc. al final)

Detecta problemas estructurales y marca reglas que
requieren segunda pasada.
"""

import re
from typing import List, Optional, Tuple
from pathlib import Path

from .models import (
    ParrafoExtraido,
    Fraccion,
    Inciso,
    ReglaParseada,
    Division,
    Problema,
    ResultadoParseo,
    TipoProblema,
    TipoDivision,
)


# =============================================================================
# PATRONES REGEX
# =============================================================================

# Capítulo: "Capítulo 2.1. Disposiciones generales"
PATRON_CAPITULO = re.compile(
    r'^Cap[íi]tulo\s+(\d+\.\d+)\.?\s*(.*)$',
    re.IGNORECASE
)

# Sección: "Sección 2.6.1. Disposiciones generales"
PATRON_SECCION = re.compile(
    r'^Secci[óo]n\s+(\d+\.\d+\.\d+)\.?\s*(.*)$',
    re.IGNORECASE
)

# Regla con contenido: "2.1.1. Para los efectos..."
PATRON_REGLA = re.compile(r'^(\d+\.\d+\.\d+)\.?\s+(.*)$')

# Regla con prefijo: "Regla 2.1.6."
PATRON_REGLA_ALT = re.compile(
    r'^Regla\s+(\d+\.\d+\.\d+)\.?\s*$',
    re.IGNORECASE
)

# Número de regla solo: "2.1.10."
PATRON_REGLA_SOLO = re.compile(r'^(\d+\.\d+\.\d+)\.?\s*$')

# Nota de reforma/derogación
PATRON_NOTA_REFORMA = re.compile(
    r'^-?\s*(Reformada|Derogada|Adicionada|Se deroga)\s+en\s+la\s+',
    re.IGNORECASE
)

# Fracción romana: "I. Contenido..." o "XI. Contenido..."
# Patrón soporta I-XXX (números romanos del 1 al 30)
PATRON_FRACCION = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s+(.*)$')

# Fracción romana sola en línea: "XI." sin contenido después
# El contenido viene en la siguiente línea
PATRON_FRACCION_SOLO = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$')

# Inciso: "a) Contenido..." o "b) Contenido..."
PATRON_INCISO = re.compile(r'^([a-z])\)\s+(.*)$')

# Para limpiar números de página inline
PATRON_PAGINA_INLINE = re.compile(r'\s*Página\s+\d+\s+de\s+\d+\s*', re.IGNORECASE)

# Patrón para detectar párrafos intermedios que introducen más fracciones
# Ej: "Asimismo, se consideran operaciones financieras derivadas de deuda, entre otras, las siguientes:"
PATRON_PARRAFO_INTERMEDIO = re.compile(
    r'(.*?[.,:;])\s*'  # Contenido previo que termina en puntuación
    r'([A-Z][^.]*(?:las siguientes|los siguientes|lo siguiente|las que siguen|los que siguen):\s*)$',
    re.IGNORECASE | re.DOTALL
)

# Patrón para detectar fracción inline al final del texto introductorio
# Ej: "...las siguientes: I. Las de cobertura cambiaria..."
PATRON_FRACCION_INLINE = re.compile(
    r'^(.*?(?:las siguientes|los siguientes|lo siguiente):\s*)'  # Intro hasta "las siguientes:"
    r'(X{0,3}(?:IX|IV|V?I{0,3}))\.\s+'  # Número romano (I-XXX)
    r'(.*)$',  # Contenido de la fracción
    re.IGNORECASE | re.DOTALL
)

# Patrón para detectar regla embebida con título al final (título solo en línea)
# Ej: "Documentación en copia simple 2.1.14."
# Solo se usa cuando el número corresponde a la siguiente regla esperada
PATRON_TITULO_FINAL = re.compile(
    r'^([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü].*?)\s+(\d+\.\d+\.\d+)\.\s*$'
)

# Patrón para detectar regla embebida con título Y contenido en la misma línea
# Ej: "Tasa mensual de recargos 2.1.20. Para los efectos del artículo 21..."
PATRON_TITULO_INLINE = re.compile(
    r'^([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü][^.]*?)\s+(\d+\.\d+\.\d+)\.\s+([A-Z].+)$'
)

# Siglas de leyes conocidas (para detectar referencias)
SIGLAS_LEYES = (
    'CFF', 'LISR', 'LIVA', 'LIESPS', 'LIEPS', 'LIF', 'LA',
    'RMF', 'RGCE', 'RCFF', 'RLISR', 'RLIVA', 'RLIESPS',
    'DECRETO', 'DOF', 'LGSM', 'Ley del ISR', 'Ley del IVA',
    'Ley General de Salud'
)

# Nombres oficiales de los Títulos de la RMF
NOMBRES_TITULOS_RMF = {
    "1": "Disposiciones Generales",
    "2": "Código Fiscal de la Federación",
    "3": "Impuesto sobre la Renta",
    "4": "Impuesto al Valor Agregado",
    "5": "Impuesto Especial sobre Producción y Servicios",
    "6": "Contribuciones de Mejoras",
    "7": "Derechos",
    "8": "Impuesto sobre Automóviles Nuevos",
    "9": "Ley de Ingresos de la Federación",
    "10": "Ley de Ingresos sobre Hidrocarburos",
    "11": "De los Decretos, Acuerdos, Convenios y Resoluciones de carácter general",
    "12": "De la Prestación de Servicios Digitales",
}


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def extraer_capitulo_de_regla(numero_regla: str) -> str:
    """Extrae el número de capítulo de una regla (2.1.5 -> 2.1)."""
    partes = numero_regla.split('.')
    if len(partes) >= 2:
        return f"{partes[0]}.{partes[1]}"
    return ""


def es_referencia_final(texto: str, es_italica: bool = False) -> bool:
    """
    Detecta si una línea es la referencia legal al final de una regla.

    Criterios:
    1. Itálica + empieza con sigla de ley = referencia segura
    2. Empieza con sigla de ley + no tiene frases de contenido
    3. Termina con fecha (DD/MM/YYYY) para referencias largas

    Args:
        texto: Texto a evaluar
        es_italica: Si el texto está en formato itálica

    Returns:
        True si es referencia, False si es contenido
    """
    texto_stripped = texto.strip()
    texto_upper = texto_stripped.upper()

    # Debe empezar con una sigla de ley
    empieza_con_sigla = any(
        texto_upper.startswith(sigla.upper())
        for sigla in SIGLAS_LEYES
    )

    if not empieza_con_sigla:
        return False

    # Itálica + sigla = referencia segura
    if es_italica:
        return True

    # Si tiene frases típicas de contenido, NO es referencia
    texto_lower = texto.lower()
    frases_contenido = (
        'para los efectos', 'se podrá', 'los contribuyentes',
        'tratándose de', 'cuando el', 'si el'
    )
    if any(frase in texto_lower for frase in frases_contenido):
        return False

    # Referencia larga que termina con fecha
    if re.search(r'\d{1,2}/\d{1,2}/\d{4}$', texto_stripped):
        return True

    # Para referencias sin fecha, aplicar límite de longitud
    if len(texto) > 200:
        return False

    return True


def consolidar_parrafos(partes: List[str]) -> str:
    """
    Une fragmentos que son continuación del mismo párrafo.
    Limpia números de página incrustados.
    """
    if not partes:
        return ""

    resultado = []
    buffer = ""

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        # Limpiar números de página incrustados
        parte = PATRON_PAGINA_INLINE.sub(' ', parte).strip()
        if not parte:
            continue

        if not buffer:
            buffer = parte
        elif buffer[-1] in '.;:?!':
            resultado.append(buffer)
            buffer = parte
        else:
            buffer = buffer + ' ' + parte

    if buffer:
        resultado.append(buffer)

    return '\n\n'.join(resultado)


# =============================================================================
# PARSER RMF
# =============================================================================

class ParserRMF:
    """
    Parser de la Resolución Miscelánea Fiscal.

    Implementa la primera pasada ("deber ser"):
    - Detecta estructura jerárquica (Títulos, Capítulos, Secciones)
    - Parsea reglas con fracciones e incisos
    - Identifica referencias al final
    - Detecta problemas estructurales
    - Marca reglas que requieren segunda pasada

    Usage:
        parser = ParserRMF()
        resultado = parser.parsear(paragraphs, "RMF 2025")
    """

    def __init__(self):
        """Inicializa el parser."""
        self._reset()

    def _reset(self):
        """Reinicia el estado del parser."""
        self.divisiones: List[Division] = []
        self.reglas: List[ReglaParseada] = []

        self.titulo_actual: Optional[Division] = None
        self.capitulo_actual: Optional[Division] = None
        self.seccion_actual: Optional[Division] = None

        self.orden_division = 0
        self.orden_regla = 0

    def parsear(
        self,
        paragraphs: List[ParrafoExtraido],
        nombre_doc: str
    ) -> ResultadoParseo:
        """
        Parsea los párrafos de la RMF en estructura jerárquica.

        Args:
            paragraphs: Lista de ParrafoExtraido
            nombre_doc: Nombre del documento

        Returns:
            ResultadoParseo con reglas, divisiones y métricas
        """
        self._reset()

        i = 0
        while i < len(paragraphs):
            parrafo = paragraphs[i]
            texto = parrafo.texto

            # === CAPÍTULO ===
            match = PATRON_CAPITULO.match(texto)
            if match:
                i = self._procesar_capitulo(match, paragraphs, i)
                continue

            # === SECCIÓN ===
            match = PATRON_SECCION.match(texto)
            if match:
                i = self._procesar_seccion(match, paragraphs, i)
                continue

            # === REGLA ===
            match = PATRON_REGLA.match(texto)
            match_alt = PATRON_REGLA_ALT.match(texto) if not match else None
            match_solo = PATRON_REGLA_SOLO.match(texto) if not match and not match_alt else None

            if match or match_alt or match_solo:
                i = self._procesar_regla(
                    match or match_alt or match_solo,
                    paragraphs,
                    i,
                    tiene_contenido=bool(match),
                )
                continue

            # === REGLA CON TÍTULO AL FINAL (ej: "Documentación en copia simple 2.1.14.") ===
            # O con contenido inline (ej: "Tasa mensual de recargos 2.1.20. Para los efectos...")
            # Solo procesar si es la siguiente regla esperada
            if self.reglas:
                ultima_regla = self.reglas[-1].numero
                match_embebida = self._es_inicio_regla_embebida(texto, ultima_regla)
                if match_embebida:
                    i = self._procesar_regla_titulo_final(match_embebida, paragraphs, i)
                    continue

            i += 1

        # Deduplicar y crear placeholders
        self._deduplicar_reglas()
        self._crear_placeholders()

        # Crear resultado
        resultado = ResultadoParseo(
            documento=nombre_doc,
            reglas=self.reglas,
            divisiones=self.divisiones,
        )
        resultado.calcular_metricas()

        return resultado

    def _procesar_capitulo(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> int:
        """
        Procesa un capítulo y lo agrega a divisiones.

        También infiere el Título padre si no existe.

        Returns:
            Nuevo índice después del procesamiento
        """
        numero = match.group(1)
        nombre = match.group(2) or ""

        # Si el nombre está en la siguiente línea
        if not nombre and idx + 1 < len(paragraphs):
            next_text = paragraphs[idx + 1].texto
            if (not PATRON_CAPITULO.match(next_text) and
                not PATRON_SECCION.match(next_text) and
                not PATRON_REGLA.match(next_text)):
                nombre = next_text
                idx += 1

        # Inferir Título del número de capítulo
        titulo_numero = numero.split('.')[0]
        if (self.titulo_actual is None or
            self.titulo_actual.numero != titulo_numero):
            self._crear_titulo_inferido(titulo_numero)

        # Crear capítulo
        self.orden_division += 1
        path = self.titulo_actual.path_texto if self.titulo_actual else ""

        self.capitulo_actual = Division(
            tipo=TipoDivision.CAPITULO,
            numero=numero,
            nombre=nombre.strip(),
            numero_orden=self.orden_division,
            orden_global=self.orden_division,
            path_texto=f"{path} > CAPITULO {numero}" if path else f"CAPITULO {numero}",
            padre_tipo=TipoDivision.TITULO,
            padre_numero=self.titulo_actual.numero if self.titulo_actual else None,
            nivel=1,
        )
        self.divisiones.append(self.capitulo_actual)
        self.seccion_actual = None

        return idx + 1

    def _procesar_seccion(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> int:
        """
        Procesa una sección y la agrega a divisiones.

        Returns:
            Nuevo índice después del procesamiento
        """
        numero = match.group(1)
        nombre = match.group(2) or ""

        # Si el nombre está en la siguiente línea
        if not nombre and idx + 1 < len(paragraphs):
            next_text = paragraphs[idx + 1].texto
            if (not PATRON_SECCION.match(next_text) and
                not PATRON_REGLA.match(next_text)):
                nombre = next_text
                idx += 1

        self.orden_division += 1
        path = (self.capitulo_actual.path_texto if self.capitulo_actual
                else self.titulo_actual.path_texto if self.titulo_actual
                else "")

        self.seccion_actual = Division(
            tipo=TipoDivision.SECCION,
            numero=numero,
            nombre=nombre.strip(),
            numero_orden=self.orden_division,
            orden_global=self.orden_division,
            path_texto=f"{path} > SECCION {numero}" if path else f"SECCION {numero}",
            padre_tipo=TipoDivision.CAPITULO if self.capitulo_actual else TipoDivision.TITULO,
            padre_numero=(self.capitulo_actual.numero if self.capitulo_actual
                         else self.titulo_actual.numero if self.titulo_actual
                         else None),
            nivel=2,
        )
        self.divisiones.append(self.seccion_actual)

        return idx + 1

    def _procesar_regla(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int,
        tiene_contenido: bool = True
    ) -> int:
        """
        Procesa una regla y la agrega a la lista.

        Args:
            match: Match del patrón de regla
            paragraphs: Lista completa de párrafos
            idx: Índice actual
            tiene_contenido: Si el match incluye contenido en la misma línea

        Returns:
            Nuevo índice después del procesamiento
        """
        numero = match.group(1)
        contenido_primera_linea = match.group(2).strip() if tiene_contenido else ""

        # Buscar título en párrafo anterior
        titulo = self._extraer_titulo_anterior(paragraphs, idx)

        # Inferir capítulo si no coincide
        self._inferir_capitulo_si_necesario(numero)

        # Recolectar contenido y referencias
        contenido_partes = []
        if contenido_primera_linea:
            contenido_partes.append(contenido_primera_linea)

        referencias = None
        fracciones = []

        idx += 1
        while idx < len(paragraphs):
            parrafo = paragraphs[idx]
            texto = parrafo.texto
            es_italica = parrafo.es_italica

            # ¿Termina la regla?
            if self._es_fin_de_regla(texto):
                break

            # Ignorar notas de reforma
            if PATRON_NOTA_REFORMA.match(texto):
                idx += 1
                continue

            # Detectar referencia
            if es_referencia_final(texto, es_italica):
                referencias = texto
                idx += 1
                continue

            # Detectar regla embebida con formato "Título X.X.X."
            # Solo si el número es el siguiente esperado
            if self._es_inicio_regla_embebida(texto, numero):
                # No avanzar idx - el main loop procesará esta línea
                break

            # Detectar fracción (con contenido en misma línea)
            match_fraccion = PATRON_FRACCION.match(texto)
            if match_fraccion:
                nuevas_fracciones, idx = self._procesar_fraccion(match_fraccion, paragraphs, idx)
                fracciones.extend(nuevas_fracciones)
                continue

            # Detectar fracción sola (número sin contenido, ej: "XI.")
            match_fraccion_solo = PATRON_FRACCION_SOLO.match(texto)
            if match_fraccion_solo:
                nuevas_fracciones, idx = self._procesar_fraccion_solo(match_fraccion_solo, paragraphs, idx)
                fracciones.extend(nuevas_fracciones)
                continue

            # Detectar inciso (a), b), c), etc.)
            match_inciso = PATRON_INCISO.match(texto)
            if match_inciso:
                inciso = Inciso(
                    letra=match_inciso.group(1),
                    contenido=match_inciso.group(2),
                    orden=ord(match_inciso.group(1)) - ord('a') + 1,
                )
                # Si hay una fracción activa, agregar el inciso a ella
                if fracciones:
                    fracciones[-1].incisos.append(inciso)
                else:
                    # Inciso sin fracción padre - crear fracción virtual
                    fraccion_virtual = Fraccion(
                        numero="",
                        contenido="",
                        orden=0,
                        incisos=[inciso],
                    )
                    fracciones.append(fraccion_virtual)
                idx += 1
                continue

            # Contenido normal
            contenido_partes.append(texto)
            idx += 1

        # Consolidar y crear regla
        contenido = consolidar_parrafos(contenido_partes)

        # Extraer fracciones inline del contenido (ej: "...las siguientes: I. Las de...")
        contenido, fracciones_inline = self._extraer_fracciones_inline(contenido)
        if fracciones_inline:
            # Insertar al inicio de las fracciones
            fracciones = fracciones_inline + fracciones

        # Renumerar orden de fracciones
        for i, f in enumerate(fracciones, 1):
            f.orden = i

        self.orden_regla += 1
        division_actual = self.seccion_actual or self.capitulo_actual or self.titulo_actual

        regla = ReglaParseada(
            numero=numero,
            titulo=titulo if titulo else self._extraer_titulo_de_contenido(contenido),
            contenido=contenido,
            referencias=referencias,
            fracciones=fracciones,
            division_path=division_actual.path_texto if division_actual else "",
            titulo_padre=self.titulo_actual.numero if self.titulo_actual else None,
            capitulo_padre=self.capitulo_actual.numero if self.capitulo_actual else None,
            seccion_padre=self.seccion_actual.numero if self.seccion_actual else None,
            orden_global=self.orden_regla,
        )

        # Validar y detectar problemas
        self._validar_regla(regla)

        self.reglas.append(regla)
        return idx

    def _procesar_regla_titulo_final(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> int:
        """
        Procesa una regla con formato "Título X.X.X." o "Título X.X.X. Contenido..."

        El título está ANTES del número, no después.
        Ej: "Documentación en copia simple 2.1.14."
        Ej: "Tasa mensual de recargos 2.1.20. Para los efectos..."

        Args:
            match: Match de PATRON_TITULO_FINAL o PATRON_TITULO_INLINE
            paragraphs: Lista completa de párrafos
            idx: Índice actual

        Returns:
            Nuevo índice después del procesamiento
        """
        titulo = match.group(1).strip()
        numero = match.group(2)

        # Si tiene grupo 3, es formato inline (título + contenido en misma línea)
        contenido_primera_linea = ""
        if len(match.groups()) >= 3 and match.group(3):
            contenido_primera_linea = match.group(3).strip()

        # Inferir capítulo si no coincide
        self._inferir_capitulo_si_necesario(numero)

        # Recolectar contenido y referencias
        contenido_partes = []
        if contenido_primera_linea:
            contenido_partes.append(contenido_primera_linea)

        referencias = None
        fracciones = []

        idx += 1
        while idx < len(paragraphs):
            parrafo = paragraphs[idx]
            texto = parrafo.texto
            es_italica = parrafo.es_italica

            # ¿Termina la regla?
            if self._es_fin_de_regla(texto):
                break

            # Detectar regla embebida siguiente
            if self._es_inicio_regla_embebida(texto, numero):
                break

            # Ignorar notas de reforma
            if PATRON_NOTA_REFORMA.match(texto):
                idx += 1
                continue

            # Detectar referencia
            if es_referencia_final(texto, es_italica):
                referencias = texto
                idx += 1
                continue

            # Detectar fracción (con contenido en misma línea)
            match_fraccion = PATRON_FRACCION.match(texto)
            if match_fraccion:
                nuevas_fracciones, idx = self._procesar_fraccion(match_fraccion, paragraphs, idx)
                fracciones.extend(nuevas_fracciones)
                continue

            # Detectar fracción sola (número sin contenido, ej: "XI.")
            match_fraccion_solo = PATRON_FRACCION_SOLO.match(texto)
            if match_fraccion_solo:
                nuevas_fracciones, idx = self._procesar_fraccion_solo(match_fraccion_solo, paragraphs, idx)
                fracciones.extend(nuevas_fracciones)
                continue

            # Detectar inciso
            match_inciso = PATRON_INCISO.match(texto)
            if match_inciso:
                inciso = Inciso(
                    letra=match_inciso.group(1),
                    contenido=match_inciso.group(2),
                    orden=ord(match_inciso.group(1)) - ord('a') + 1,
                )
                if fracciones:
                    fracciones[-1].incisos.append(inciso)
                else:
                    fraccion_virtual = Fraccion(
                        numero="",
                        contenido="",
                        orden=0,
                        incisos=[inciso],
                    )
                    fracciones.append(fraccion_virtual)
                idx += 1
                continue

            # Contenido normal
            contenido_partes.append(texto)
            idx += 1

        # Consolidar y crear regla
        contenido = consolidar_parrafos(contenido_partes)

        # Renumerar orden de fracciones
        for i, f in enumerate(fracciones, 1):
            f.orden = i

        self.orden_regla += 1
        division_actual = self.seccion_actual or self.capitulo_actual or self.titulo_actual

        regla = ReglaParseada(
            numero=numero,
            titulo=titulo,  # Ya tenemos el título del match
            contenido=contenido,
            referencias=referencias,
            fracciones=fracciones,
            division_path=division_actual.path_texto if division_actual else "",
            titulo_padre=self.titulo_actual.numero if self.titulo_actual else None,
            capitulo_padre=self.capitulo_actual.numero if self.capitulo_actual else None,
            seccion_padre=self.seccion_actual.numero if self.seccion_actual else None,
            orden_global=self.orden_regla,
        )

        # Validar
        self._validar_regla(regla)
        self.reglas.append(regla)

        return idx

    def _extraer_titulo_anterior(
        self,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> str:
        """
        Busca título de la regla en el párrafo anterior.

        En RMF, el título suele estar ANTES del número.
        """
        if idx == 0:
            return ""

        parrafo_anterior = paragraphs[idx - 1]
        texto = parrafo_anterior.texto
        es_italica = parrafo_anterior.es_italica

        # Verificar que no sea referencia
        empieza_con_sigla = any(
            texto.upper().startswith(s)
            for s in SIGLAS_LEYES
        )
        es_referencia = (es_italica and empieza_con_sigla) or es_referencia_final(texto)

        # Verificar que no sea otra estructura
        es_numero = PATRON_REGLA.match(texto) or PATRON_REGLA_SOLO.match(texto)
        es_romano = texto.startswith(('I.', 'II.', 'III.', 'IV.', 'V.', 'VI.', 'VII.', 'VIII.', 'IX.', 'X.'))
        es_corto = len(texto) < 150

        # Verificar que no parezca contenido
        texto_lower = texto.lower()
        es_contenido = texto_lower.startswith((
            'para los efectos', 'los contribuyentes', 'cuando', 'tratándose'
        ))

        if not es_referencia and not es_numero and not es_romano and es_corto and not es_contenido:
            # Limpiar de la regla anterior si existe
            if self.reglas:
                contenido_anterior = self.reglas[-1].contenido
                if contenido_anterior.endswith(texto):
                    self.reglas[-1].contenido = contenido_anterior[:-len(texto)].rstrip('\n').rstrip()
                elif f"\n\n{texto}" in contenido_anterior:
                    self.reglas[-1].contenido = contenido_anterior.replace(f"\n\n{texto}", "").rstrip()
            return texto

        return ""

    def _es_fin_de_regla(self, texto: str) -> bool:
        """Determina si el texto indica fin de la regla actual."""
        if PATRON_REGLA.match(texto):
            return True
        if PATRON_REGLA_ALT.match(texto):
            return True
        if PATRON_REGLA_SOLO.match(texto):
            return True
        if PATRON_CAPITULO.match(texto):
            return True
        if PATRON_SECCION.match(texto):
            return True
        return False

    def _procesar_fraccion(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> Tuple[List[Fraccion], int]:
        """
        Procesa una fracción con su contenido multilínea.

        Detecta párrafos intermedios que introducen nuevos grupos de fracciones
        (ej: "Asimismo, se consideran... las siguientes:").

        Returns:
            Tuple de (lista de fracciones/párrafos, nuevo índice)
        """
        numero_romano = match.group(1)
        contenido_partes = [match.group(2)]

        idx += 1

        # Recolectar contenido de continuación hasta encontrar otra estructura
        while idx < len(paragraphs):
            texto = paragraphs[idx].texto

            # ¿Termina el contenido de esta fracción?
            if (PATRON_FRACCION.match(texto) or
                PATRON_FRACCION_SOLO.match(texto) or
                PATRON_INCISO.match(texto) or
                self._es_fin_de_regla(texto) or
                es_referencia_final(texto, paragraphs[idx].es_italica)):
                break

            contenido_partes.append(texto)
            idx += 1

        # Consolidar contenido
        contenido_completo = ' '.join(contenido_partes).strip()

        # Detectar si hay un párrafo intermedio al final
        match_intermedio = PATRON_PARRAFO_INTERMEDIO.match(contenido_completo)

        resultado = []

        if match_intermedio:
            # Separar contenido de la fracción y párrafo intermedio
            contenido_fraccion = match_intermedio.group(1).strip()
            parrafo_intermedio = match_intermedio.group(2).strip()

            # Crear fracción
            resultado.append(Fraccion(
                numero=numero_romano,
                contenido=contenido_fraccion,
                orden=self._romano_a_entero(numero_romano),
                tipo="fraccion",
            ))

            # Crear párrafo intermedio (orden será asignado después)
            resultado.append(Fraccion(
                numero=None,
                contenido=parrafo_intermedio,
                orden=0,  # Se ajustará al insertar
                tipo="parrafo",
            ))
        else:
            # Fracción normal sin párrafo intermedio
            resultado.append(Fraccion(
                numero=numero_romano,
                contenido=contenido_completo,
                orden=self._romano_a_entero(numero_romano),
                tipo="fraccion",
            ))

        return resultado, idx

    def _procesar_fraccion_solo(
        self,
        match: re.Match,
        paragraphs: List[ParrafoExtraido],
        idx: int
    ) -> Tuple[List[Fraccion], int]:
        """
        Procesa una fracción donde el número está solo en la línea.

        Ej: "XI." seguido de contenido en la siguiente línea.

        Returns:
            Tuple de (lista de fracciones/párrafos, nuevo índice)
        """
        numero_romano = match.group(1)
        contenido_partes = []  # No hay contenido en la misma línea

        idx += 1

        # Recolectar contenido hasta encontrar otra estructura
        while idx < len(paragraphs):
            texto = paragraphs[idx].texto

            # ¿Termina el contenido de esta fracción?
            if (PATRON_FRACCION.match(texto) or
                PATRON_FRACCION_SOLO.match(texto) or
                PATRON_INCISO.match(texto) or
                self._es_fin_de_regla(texto) or
                es_referencia_final(texto, paragraphs[idx].es_italica)):
                break

            contenido_partes.append(texto)
            idx += 1

        # Consolidar contenido
        contenido_completo = ' '.join(contenido_partes).strip()

        # Detectar si hay un párrafo intermedio al final
        match_intermedio = PATRON_PARRAFO_INTERMEDIO.match(contenido_completo)

        resultado = []

        if match_intermedio:
            contenido_fraccion = match_intermedio.group(1).strip()
            parrafo_intermedio = match_intermedio.group(2).strip()

            resultado.append(Fraccion(
                numero=numero_romano,
                contenido=contenido_fraccion,
                orden=self._romano_a_entero(numero_romano),
                tipo="fraccion",
            ))

            resultado.append(Fraccion(
                numero=None,
                contenido=parrafo_intermedio,
                orden=0,
                tipo="parrafo",
            ))
        else:
            resultado.append(Fraccion(
                numero=numero_romano,
                contenido=contenido_completo,
                orden=self._romano_a_entero(numero_romano),
                tipo="fraccion",
            ))

        return resultado, idx

    def _romano_a_entero(self, romano: str) -> int:
        """Convierte número romano a entero."""
        valores = {'I': 1, 'V': 5, 'X': 10}
        resultado = 0
        prev = 0

        for char in reversed(romano.upper()):
            valor = valores.get(char, 0)
            if valor < prev:
                resultado -= valor
            else:
                resultado += valor
            prev = valor

        return resultado

    def _siguiente_numero_regla(self, numero: str) -> str:
        """
        Calcula el siguiente número de regla esperado.

        Args:
            numero: Número actual (ej: "2.1.13")

        Returns:
            Siguiente número (ej: "2.1.14")
        """
        partes = numero.split('.')
        if len(partes) == 3:
            try:
                siguiente = int(partes[2]) + 1
                return f"{partes[0]}.{partes[1]}.{siguiente}"
            except ValueError:
                pass
        return ""

    def _es_inicio_regla_embebida(self, texto: str, numero_actual: str) -> Optional[re.Match]:
        """
        Detecta si un texto es el inicio de una regla embebida.

        Patrones soportados:
        1. "Título X.X.X." (título solo en línea)
        2. "Título X.X.X. Contenido..." (título y contenido en misma línea)

        Solo retorna match si el número coincide con el siguiente esperado.

        Args:
            texto: Texto a evaluar
            numero_actual: Número de la regla que se está procesando

        Returns:
            Match object si es regla embebida, None si no
        """
        siguiente_esperado = self._siguiente_numero_regla(numero_actual)
        if not siguiente_esperado:
            return None

        # Intentar patrón 1: título solo
        match = PATRON_TITULO_FINAL.match(texto)
        if match and match.group(2) == siguiente_esperado:
            return match

        # Intentar patrón 2: título + contenido inline
        match = PATRON_TITULO_INLINE.match(texto)
        if match and match.group(2) == siguiente_esperado:
            return match

        return None

    def _crear_titulo_inferido(self, numero: str):
        """Crea un Título inferido del número de capítulo."""
        self.orden_division += 1
        self.titulo_actual = Division(
            tipo=TipoDivision.TITULO,
            numero=numero,
            nombre=NOMBRES_TITULOS_RMF.get(numero, f"Título {numero}"),
            numero_orden=int(numero) if numero.isdigit() else self.orden_division,
            orden_global=self.orden_division,
            path_texto=f"TITULO {numero}",
            nivel=0,
        )
        self.divisiones.append(self.titulo_actual)
        self.capitulo_actual = None
        self.seccion_actual = None

    def _inferir_capitulo_si_necesario(self, numero_regla: str):
        """Infiere capítulo si la regla no pertenece al actual."""
        capitulo_esperado = extraer_capitulo_de_regla(numero_regla)
        if not capitulo_esperado:
            return

        if (self.capitulo_actual is None or
            self.capitulo_actual.numero != capitulo_esperado):

            # Inferir título primero
            titulo_numero = capitulo_esperado.split('.')[0]
            if (self.titulo_actual is None or
                self.titulo_actual.numero != titulo_numero):
                self._crear_titulo_inferido(titulo_numero)

            # Crear capítulo inferido
            self.orden_division += 1
            path = self.titulo_actual.path_texto if self.titulo_actual else ""

            self.capitulo_actual = Division(
                tipo=TipoDivision.CAPITULO,
                numero=capitulo_esperado,
                nombre="(Capítulo inferido)",
                numero_orden=self.orden_division,
                orden_global=self.orden_division,
                path_texto=f"{path} > CAPITULO {capitulo_esperado}" if path else f"CAPITULO {capitulo_esperado}",
                padre_tipo=TipoDivision.TITULO,
                padre_numero=self.titulo_actual.numero if self.titulo_actual else None,
                nivel=1,
            )
            self.divisiones.append(self.capitulo_actual)
            self.seccion_actual = None

    def _extraer_titulo_de_contenido(self, contenido: str) -> str:
        """Fallback: extrae título de la primera oración del contenido."""
        if not contenido:
            return ""

        primer_parrafo = contenido.split('\n\n')[0] if '\n\n' in contenido else contenido
        if len(primer_parrafo) > 200:
            return primer_parrafo[:200] + "..."
        return primer_parrafo

    def _extraer_fracciones_inline(self, contenido: str) -> Tuple[str, List[Fraccion]]:
        """
        Extrae fracciones que están inline en el contenido.

        Detecta patrones como "...las siguientes: I. Las de cobertura..."
        y los separa en contenido limpio + lista de fracciones.

        Returns:
            Tuple de (contenido limpio, lista de fracciones extraídas)
        """
        if not contenido:
            return contenido, []

        match = PATRON_FRACCION_INLINE.match(contenido)
        if not match:
            return contenido, []

        # Separar intro de la fracción inline
        intro = match.group(1).strip()
        numero_romano = match.group(2)
        contenido_fraccion = match.group(3).strip()

        fraccion = Fraccion(
            numero=numero_romano,
            contenido=contenido_fraccion,
            orden=self._romano_a_entero(numero_romano),
            tipo="fraccion",
        )

        return intro, [fraccion]

    def _validar_regla(self, regla: ReglaParseada):
        """
        Valida una regla y detecta problemas estructurales.

        Problemas detectados:
        - Título ausente
        - Contenido incoherente (empieza minúscula)
        - Fracciones incompletas
        """
        # Título ausente
        if not regla.titulo:
            regla.agregar_problema(Problema(
                tipo=TipoProblema.TITULO_AUSENTE,
                descripcion="No se encontró título para la regla",
                ubicacion=regla.numero,
                severidad="warning",
            ))

        # Contenido incoherente
        if regla.contenido:
            primer_char = regla.contenido[0] if regla.contenido else ''
            if primer_char.islower():
                regla.agregar_problema(Problema(
                    tipo=TipoProblema.CONTENIDO_INCOHERENTE,
                    descripcion="El contenido inicia con minúscula",
                    ubicacion=regla.numero,
                    severidad="warning",
                ))

        # Fracciones no consecutivas
        if regla.fracciones:
            numeros = [f.orden for f in regla.fracciones]
            for i, num in enumerate(numeros[1:], 1):
                if num != numeros[i-1] + 1:
                    regla.agregar_problema(Problema(
                        tipo=TipoProblema.FRACCIONES_INCOMPLETAS,
                        descripcion=f"Falta fracción entre {numeros[i-1]} y {num}",
                        ubicacion=regla.numero,
                        severidad="error",
                    ))
                    break

    def _deduplicar_reglas(self):
        """Elimina reglas duplicadas, manteniendo la de mayor contenido."""
        reglas_unicas = {}
        for regla in self.reglas:
            num = regla.numero
            if num not in reglas_unicas:
                reglas_unicas[num] = regla
            else:
                # Mantener la de contenido más largo
                if len(regla.contenido) > len(reglas_unicas[num].contenido):
                    reglas_unicas[num] = regla

        duplicados = len(self.reglas) - len(reglas_unicas)
        if duplicados > 0:
            print(f"   {duplicados} reglas duplicadas eliminadas")

        self.reglas = list(reglas_unicas.values())

    def _crear_placeholders(self):
        """
        Crea reglas placeholder para números faltantes.

        Incluye checksum: si el número aparece en el contenido
        de otra regla, no crea placeholder (posible error de parseo).
        """
        from collections import defaultdict

        # Construir índice de contenido
        contenido_total = " ".join(r.contenido for r in self.reglas)

        # Agrupar por capítulo
        por_capitulo = defaultdict(list)
        for regla in self.reglas:
            if regla.tipo != "regla":
                continue
            cap = extraer_capitulo_de_regla(regla.numero)
            if cap:
                partes = regla.numero.split('.')
                if len(partes) == 3:
                    try:
                        num = int(partes[2])
                        por_capitulo[cap].append(num)
                    except ValueError:
                        pass

        placeholders = []
        orden = max((r.orden_global for r in self.reglas), default=0) + 1000

        for cap, numeros in por_capitulo.items():
            if not numeros:
                continue

            numeros_set = set(numeros)
            min_num, max_num = min(numeros), max(numeros)

            # Buscar división padre
            division_path = ""
            for div in self.divisiones:
                if div.tipo == TipoDivision.CAPITULO and div.numero == cap:
                    division_path = div.path_texto
                    break

            # Crear placeholder para cada faltante
            for n in range(min_num, max_num + 1):
                if n not in numeros_set:
                    numero_regla = f"{cap}.{n}"

                    # Checksum: verificar si aparece en contenido
                    patron = re.compile(rf'(?<!\d){re.escape(numero_regla)}\.(?!\d)')
                    if patron.search(contenido_total):
                        continue  # Posible error de parseo

                    placeholder = ReglaParseada(
                        numero=numero_regla,
                        titulo="(Regla no existe)",
                        contenido="Esta regla no existe en el documento fuente.",
                        tipo="no-existe",
                        division_path=division_path,
                        titulo_padre=cap.split('.')[0],
                        capitulo_padre=cap,
                        orden_global=orden,
                    )
                    placeholders.append(placeholder)
                    orden += 1

        self.reglas.extend(placeholders)
