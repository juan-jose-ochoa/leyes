"""
Máquina de Estados Finitos para extracción de artículos de leyes.

Este módulo implementa una FSM basada en tokens que detecta:
- Inicio/fin de artículos
- Encabezados estructurales (TITULO, CAPITULO, SECCION)
- Transitorios

Los tokens se construyen a partir de atributos físicos del PDF:
- Coordenadas X (para calcular centrado)
- Bold (toda la línea, no solo primer span)
- Tamaño de fuente

La FSM filtra encabezados estructurales que aparecen ENTRE artículos,
pero preserva contenido centrado+bold DENTRO de artículos (tablas, etc.).
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# =============================================================================
# HELPERS
# =============================================================================

def calcular_all_bold(spans: list[dict], threshold: float = 0.8) -> bool:
    """
    Determina si >threshold de la línea es bold.

    Args:
        spans: Lista de spans de PyMuPDF
        threshold: Porcentaje mínimo de caracteres bold (default 80%)

    Returns:
        True si la línea es mayoritariamente bold
    """
    total_chars = 0
    bold_chars = 0

    for span in spans:
        text = span.get('text', '').strip()
        n = len(text)
        if n > 0:
            total_chars += n
            if span.get('flags', 0) & 16:  # bit 4 = bold
                bold_chars += n

    return total_chars > 0 and (bold_chars / total_chars) >= threshold


# =============================================================================
# TOKEN
# =============================================================================

@dataclass
class TokenLinea:
    """
    Token que representa una línea del PDF con sus atributos físicos.

    El token encapsula toda la información necesaria para que la FSM
    tome decisiones sobre si una línea es contenido o estructura.
    """
    texto: str
    x_min: float
    x_max: float
    y: float
    all_bold: bool          # True si >80% de la línea es bold (para encabezados)
    font_size: float
    page_width: float
    first_bold: bool = False  # True si el primer span es bold (para identificadores)
    y_local: float = 0.0    # Coordenada Y local a la pagina (para sincronizacion PDF)
    pagina: int = 0         # Numero de pagina 1-indexed (para sincronizacion PDF)

    # Tolerancia para considerar una línea como centrada (en puntos)
    TOLERANCIA_CENTRADO: float = 3.0

    @property
    def centrado(self) -> bool:
        """
        Calcula si la línea está centrada en la página.

        Fórmula: expected_x = (page_width - text_width) / 2
        Centrado si: |x_min - expected_x| <= tolerancia
        """
        text_width = self.x_max - self.x_min
        if text_width <= 0:
            return False
        expected_x = (self.page_width - text_width) / 2
        return abs(self.x_min - expected_x) <= self.TOLERANCIA_CENTRADO

    @property
    def es_encabezado_estructura(self) -> bool:
        """Detecta si es un encabezado de TITULO/CAPITULO/SECCION."""
        texto_upper = self.texto.strip().upper()
        prefijos = (
            'TITULO ', 'TÍTULO ',
            'CAPITULO ', 'CAPÍTULO ',
            'SECCION ', 'SECCIÓN '
        )
        return any(texto_upper.startswith(p) for p in prefijos)

    @property
    def es_transitorios(self) -> bool:
        """Detecta si es la sección de transitorios."""
        texto_strip = self.texto.strip().upper()
        return texto_strip in ('TRANSITORIOS', 'TRANSITORIO', 'T R A N S I T O R I O S')

    @property
    def es_fin_articulos(self) -> bool:
        """
        Detecta si es una sección que marca el fin de los artículos regulares.

        Incluye:
        - Encabezados de estructura (TITULO, CAPITULO, SECCION)
        - Transitorios
        - Disposiciones de vigencia/transitorias
        """
        texto_upper = self.texto.strip().upper()

        # Encabezados de estructura
        if self.es_encabezado_estructura:
            return True

        # Transitorios
        if self.es_transitorios:
            return True

        # Disposiciones especiales (vigencia, transitorias, etc.)
        if texto_upper.startswith('DISPOSICIONES '):
            return True

        # Artículos transitorios con número en texto (PRIMERO, SEGUNDO, etc.)
        if re.match(r'^ARTÍCULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SÉPTIMO|OCTAVO|NOVENO|DÉCIMO)', texto_upper):
            return True

        return False


# =============================================================================
# ESTADOS
# =============================================================================

class EstadoExtraccion(Enum):
    """Estados de la máquina de estados para extracción de artículos."""
    BUSCANDO_ARTICULO = auto()   # Buscando inicio de artículo
    DENTRO_ARTICULO = auto()     # Procesando contenido del artículo
    ENTRE_ARTICULOS = auto()     # Después de estructura, antes de siguiente artículo
    FIN = auto()                 # Transitorios detectados, fin de extracción


# =============================================================================
# FSM
# =============================================================================

class FSMExtraccion:
    """
    Máquina de estados finitos para extracción de artículos.

    Estados:
        BUSCANDO_ARTICULO: Estado inicial, ignora todo hasta encontrar artículo
        DENTRO_ARTICULO: Acumula contenido, incluye centrado+bold (tablas)
        ENTRE_ARTICULOS: Filtra centrado+bold (nombres de división)
        FIN: Transitorios detectados, termina extracción

    Transiciones:
        BUSCANDO → DENTRO: al detectar "Artículo X"
        DENTRO → DENTRO: al detectar siguiente artículo (flush anterior)
        DENTRO → ENTRE: al detectar TITULO/CAPITULO/SECCION
        ENTRE → DENTRO: al detectar "Artículo X"
        CUALQUIERA → FIN: al detectar TRANSITORIOS

    Uso:
        fsm = FSMExtraccion(patron_articulo)
        for token in tokens:
            resultado = fsm.procesar(token)
            if resultado and resultado['accion'] == 'flush':
                # Emitir artículo
            elif resultado and resultado['accion'] == 'fin':
                break
    """

    # Patrón genérico para detectar cualquier artículo (fin del actual)
    PATRON_CUALQUIER_ARTICULO = re.compile(
        r'^(?:ARTICULO|ARTÍCULO|Artículo)\s+\d',
        re.IGNORECASE
    )

    def __init__(self, patron_articulo: re.Pattern, numero_articulo: Optional[str] = None):
        """
        Inicializa la FSM.

        Args:
            patron_articulo: Patrón regex para detectar inicio del artículo específico.
            numero_articulo: Número del artículo a extraer (opcional).
                            Si se proporciona, se usa en lugar de extraer del match.
        """
        self.estado = EstadoExtraccion.BUSCANDO_ARTICULO
        self.patron_articulo = patron_articulo
        self.numero_articulo = numero_articulo
        self.articulo_actual: Optional[str] = None
        self.lineas_articulo: list[dict] = []

    def procesar(self, token: TokenLinea) -> Optional[dict]:
        """
        Procesa un token y retorna la acción a tomar.

        Args:
            token: TokenLinea con los atributos de la línea

        Returns:
            None: Continuar sin acción
            {'accion': 'flush', 'articulo': str, 'lineas': list}: Emitir artículo
            {'accion': 'fin'}: Terminar extracción
        """
        # Ya terminamos
        if self.estado == EstadoExtraccion.FIN:
            return {'accion': 'fin'}

        # Detectar TRANSITORIOS en cualquier estado
        if token.es_transitorios and token.centrado and token.all_bold:
            resultado = self._flush_articulo()
            self.estado = EstadoExtraccion.FIN
            return resultado if resultado else {'accion': 'fin'}

        # Detectar artículo (aplica en todos los estados excepto FIN)
        match_articulo = self.patron_articulo.match(token.texto)

        # ===== BUSCANDO_ARTICULO =====
        if self.estado == EstadoExtraccion.BUSCANDO_ARTICULO:
            if match_articulo:
                self._iniciar_articulo(match_articulo, token)
            # Ignorar todo lo demás (encabezados, texto suelto)
            return None

        # ===== DENTRO_ARTICULO =====
        if self.estado == EstadoExtraccion.DENTRO_ARTICULO:
            # Mismo artículo de nuevo → ignorar (línea repetida)
            if match_articulo:
                resultado = self._flush_articulo()
                self._iniciar_articulo(match_articulo, token)
                return resultado

            # Siguiente artículo (diferente al actual) → flush y terminar
            # Verificar si es cualquier artículo y está en margen izquierdo
            if (self.PATRON_CUALQUIER_ARTICULO.match(token.texto) and
                token.x_min >= 80 and token.x_min <= 100 and
                token.first_bold):
                resultado = self._flush_articulo()
                self.estado = EstadoExtraccion.FIN
                return resultado if resultado else {'accion': 'fin'}

            # Fin de artículos (estructura, transitorios, disposiciones) → flush y terminar
            if token.es_fin_articulos and token.centrado and token.all_bold:
                resultado = self._flush_articulo()
                self.estado = EstadoExtraccion.ENTRE_ARTICULOS
                return resultado

            # Contenido normal (incluye centrado+bold de tablas internas)
            self._agregar_linea(token)
            return None

        # ===== ENTRE_ARTICULOS =====
        if self.estado == EstadoExtraccion.ENTRE_ARTICULOS:
            # Nuevo artículo → transición a DENTRO_ARTICULO
            if match_articulo:
                self._iniciar_articulo(match_articulo, token)
                return None

            # FILTRAR todo lo centrado+bold (nombres de división)
            if token.centrado and token.all_bold:
                return None  # Ignorar - este es el fix principal

            # Texto no centrado sin artículo → seguir esperando
            return None

        return None

    def _iniciar_articulo(self, match: re.Match, token: TokenLinea):
        """Inicia un nuevo artículo."""
        self.estado = EstadoExtraccion.DENTRO_ARTICULO

        # Usar número proporcionado o extraer del match si tiene grupo
        if self.numero_articulo:
            self.articulo_actual = self.numero_articulo
        else:
            try:
                self.articulo_actual = match.group(1)
            except IndexError:
                # Patrón sin grupo de captura, extraer del texto
                self.articulo_actual = "unknown"

        self.lineas_articulo = []

        # Agregar contenido después del "Artículo X.-"
        contenido_despues = token.texto[match.end():].strip().lstrip('- ').strip()
        if contenido_despues:
            self.lineas_articulo.append({
                'x': token.x_min,
                'x_end': token.x_max,
                'y': token.y,
                'y_local': token.y_local,
                'pagina': token.pagina,
                'text': contenido_despues,
                'is_bold': False,
                'font_size': token.font_size
            })

    def _agregar_linea(self, token: TokenLinea):
        """Agrega una línea al artículo actual."""
        self.lineas_articulo.append({
            'x': token.x_min,
            'x_end': token.x_max,
            'y': token.y,
            'y_local': token.y_local,
            'pagina': token.pagina,
            'text': token.texto,
            'is_bold': token.first_bold,  # Usar first_bold para detección de identificadores
            'font_size': token.font_size
        })

    def _flush_articulo(self) -> Optional[dict]:
        """Emite el artículo actual si existe."""
        if self.articulo_actual and self.lineas_articulo:
            resultado = {
                'accion': 'flush',
                'articulo': self.articulo_actual,
                'lineas': self.lineas_articulo.copy()
            }
            self.articulo_actual = None
            self.lineas_articulo = []
            return resultado
        return None

    def finalizar(self) -> Optional[dict]:
        """
        Finaliza la extracción y retorna el último artículo si existe.

        Llamar al final del procesamiento para obtener el artículo
        que estaba en proceso cuando se terminaron los tokens.
        """
        return self._flush_articulo()
