"""
Modelos de datos para el parser RMF.

Dataclasses que representan la estructura de la RMF:
- Párrafos extraídos con metadatos de formato
- Fracciones e incisos
- Reglas parseadas con metadatos de validación
- Divisiones (Títulos, Capítulos, Secciones)
- Problemas detectados y resoluciones
- Resultado final del parseo
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class TipoProblema(Enum):
    """Tipos de problemas detectados en el parseo."""
    NUMERO_INVALIDO = "numero_invalido"
    CONTENIDO_INCOHERENTE = "contenido_incoherente"
    REFERENCIA_INVALIDA = "referencia_invalida"
    FRACCIONES_INCOMPLETAS = "fracciones_incompletas"
    INCISOS_INCOMPLETOS = "incisos_incompletos"
    TITULO_AUSENTE = "titulo_ausente"
    CONTENIDO_TRUNCADO = "contenido_truncado"
    NUMERACION_NO_CONSECUTIVA = "numeracion_no_consecutiva"


class TipoDivision(Enum):
    """Tipos de divisiones en la estructura RMF."""
    TITULO = "titulo"
    CAPITULO = "capitulo"
    SECCION = "seccion"


class FuenteDatos(Enum):
    """Fuentes de datos para extracción."""
    DOCX_XML = "docx_xml"
    PDF = "pdf"
    TXT = "txt"


@dataclass
class ParrafoExtraido:
    """
    Párrafo extraído de una fuente con metadatos de formato.

    Attributes:
        texto: Contenido textual del párrafo
        es_italica: True si el texto está en itálica (usado para referencias)
        es_negrita: True si el texto está en negrita
        indice_original: Posición en el documento fuente
        fuente: De dónde se extrajo (docx_xml, pdf, txt)
    """
    texto: str
    es_italica: bool = False
    es_negrita: bool = False
    indice_original: int = 0
    fuente: FuenteDatos = FuenteDatos.DOCX_XML


@dataclass
class Inciso:
    """
    Inciso dentro de una fracción.
    Formato: a), b), c), ...
    """
    letra: str  # "a", "b", "c"
    contenido: str
    orden: int = 0


@dataclass
class Fraccion:
    """
    Fracción dentro de una regla.
    Formato: I., II., III., ...
    """
    numero: str  # "I", "II", "III", "IV", etc.
    contenido: str
    incisos: List[Inciso] = field(default_factory=list)
    orden: int = 0


@dataclass
class Problema:
    """
    Problema detectado durante el parseo.

    Attributes:
        tipo: Categoría del problema
        descripcion: Descripción legible del problema
        detalles: Información adicional (números faltantes, texto truncado, etc.)
        ubicacion: Dónde se detectó el problema (número de regla, índice, etc.)
        severidad: 'error' requiere segunda pasada, 'warning' es informativo
    """
    tipo: TipoProblema
    descripcion: str
    detalles: Optional[str] = None
    ubicacion: Optional[str] = None
    severidad: str = "error"  # "error" o "warning"


@dataclass
class Resolucion:
    """
    Resultado de intentar resolver un problema en la segunda pasada.

    Attributes:
        problema_original: El problema que se intentó resolver
        exito: True si se resolvió exitosamente
        contenido_corregido: Contenido corregido (si aplica)
        fuente_usada: Qué fuente se usó para la corrección
        metodo: Descripción del método/heurística usada
    """
    problema_original: Problema
    exito: bool
    contenido_corregido: Optional[str] = None
    fuente_usada: Optional[FuenteDatos] = None
    metodo: Optional[str] = None


@dataclass
class ReglaParseada:
    """
    Regla de la RMF parseada con metadatos de validación.

    Estructura esperada de una regla:
    - Título (párrafo corto antes del número)
    - Número (X.Y.Z.)
    - Contenido (uno o más párrafos)
    - Fracciones (I., II., III., ... opcional)
    - Incisos (a), b), c), ... dentro de fracciones)
    - Referencias (última línea, itálica, siglas de ley)

    Metadatos de validación:
    - problemas: Lista de problemas detectados
    - requiere_segunda_pasada: True si hay problemas que resolver
    - confianza: 0.0 - 1.0, qué tan seguro está el parser
    """
    numero: str
    titulo: str
    contenido: str
    referencias: Optional[str] = None
    fracciones: List[Fraccion] = field(default_factory=list)

    # Jerarquía
    division_path: str = ""
    titulo_padre: Optional[str] = None
    capitulo_padre: Optional[str] = None
    seccion_padre: Optional[str] = None
    orden_global: int = 0

    # Metadatos de validación
    problemas: List[Problema] = field(default_factory=list)
    requiere_segunda_pasada: bool = False
    confianza: float = 1.0

    # Tipo (regla normal o placeholder)
    tipo: str = "regla"  # "regla", "no-existe", "ficha", "criterio"

    def agregar_problema(self, problema: Problema):
        """Agrega un problema y marca para segunda pasada si es error."""
        self.problemas.append(problema)
        if problema.severidad == "error":
            self.requiere_segunda_pasada = True
            self.confianza = max(0.0, self.confianza - 0.2)


@dataclass
class Division:
    """
    División estructural de la RMF: Título, Capítulo o Sección.

    Jerarquía:
    - Título X (nivel 0)
      └── Capítulo X.Y (nivel 1)
            └── Sección X.Y.Z (nivel 2)
    """
    tipo: TipoDivision
    numero: str
    nombre: str
    numero_orden: int = 0
    orden_global: int = 0
    path_texto: str = ""
    padre_tipo: Optional[TipoDivision] = None
    padre_numero: Optional[str] = None
    nivel: int = 0


@dataclass
class ResultadoParseo:
    """
    Resultado final del parseo de la RMF.

    Incluye:
    - Reglas y divisiones parseadas
    - Métricas de calidad
    - Reporte detallado de problemas
    """
    # Datos principales
    documento: str
    reglas: List[ReglaParseada] = field(default_factory=list)
    divisiones: List[Division] = field(default_factory=list)

    # Métricas de calidad
    total_reglas: int = 0
    reglas_perfectas: int = 0      # Sin problemas
    reglas_corregidas: int = 0     # Corregidas en 2da pasada
    reglas_con_advertencias: int = 0
    reglas_con_errores: int = 0    # No resueltos

    # Placeholders
    total_placeholders: int = 0

    # Reporte detallado
    problemas_resueltos: List[Resolucion] = field(default_factory=list)
    problemas_pendientes: List[Problema] = field(default_factory=list)

    def calcular_metricas(self):
        """Calcula métricas basándose en las reglas."""
        self.total_reglas = len([r for r in self.reglas if r.tipo == "regla"])
        self.total_placeholders = len([r for r in self.reglas if r.tipo == "no-existe"])

        self.reglas_perfectas = len([
            r for r in self.reglas
            if r.tipo == "regla" and len(r.problemas) == 0
        ])

        self.reglas_con_advertencias = len([
            r for r in self.reglas
            if r.tipo == "regla" and any(p.severidad == "warning" for p in r.problemas)
        ])

        self.reglas_con_errores = len([
            r for r in self.reglas
            if r.tipo == "regla" and r.requiere_segunda_pasada
        ])

    @property
    def porcentaje_perfectas(self) -> float:
        """Porcentaje de reglas sin problemas."""
        if self.total_reglas == 0:
            return 0.0
        return self.reglas_perfectas / self.total_reglas * 100

    @property
    def porcentaje_exito(self) -> float:
        """Porcentaje de reglas sin errores pendientes."""
        if self.total_reglas == 0:
            return 0.0
        resueltas = self.total_reglas - self.reglas_con_errores
        return resueltas / self.total_reglas * 100
