"""
Fase 1: Extracción de texto multi-formato.

Extrae texto crudo de múltiples fuentes preservando metadatos de formato:
- DOCX XML (fuente principal): Texto + formato (itálica, negrita)
- PDF (secundario): Para validación en segunda pasada
- TXT (terciario): Referencia de respaldo

La extracción incluye:
- Detección de formato itálico (usado para referencias/títulos)
- Pre-procesamiento para limpiar fragmentación PDF→DOCX
- Filtrado de elementos no-contenido (páginas, encabezados, notas)
"""

import re
import zipfile
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from .models import ParrafoExtraido, FuenteDatos


# =============================================================================
# PATRONES DE FILTRADO
# =============================================================================

# Número de página: "Página 27 de 812" o "27 de 812"
PATRON_PAGINA = re.compile(r'^(?:Página\s+)?\d+\s+de\s+\d+$', re.IGNORECASE)

# Notas del documento que no son contenido
PATRON_NOTA_DOCUMENTO = re.compile(
    r'^NOTA:\s*Este documento constituye una compilación',
    re.IGNORECASE
)

# Patrón para numerales romanos solos (huérfanos del PDF→DOCX)
PATRON_ROMANO_SOLO = re.compile(r'^(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s*$')


# =============================================================================
# CLASES BASE
# =============================================================================

class Extractor(ABC):
    """
    Clase base abstracta para extractores de texto.

    Cada extractor implementa la extracción de una fuente específica
    (DOCX, PDF, TXT) manteniendo una interfaz común.
    """

    def __init__(self, file_path: Path):
        """
        Args:
            file_path: Ruta al archivo fuente
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    @abstractmethod
    def extraer(self) -> List[ParrafoExtraido]:
        """
        Extrae todos los párrafos del documento.

        Returns:
            Lista de ParrafoExtraido con texto y metadatos de formato
        """
        pass

    @abstractmethod
    def buscar_regla(self, numero: str) -> Optional[str]:
        """
        Busca una regla específica por número.

        Usado en segunda pasada para comparar fuentes.

        Args:
            numero: Número de regla (ej: "2.1.8")

        Returns:
            Texto de la regla si se encuentra, None si no
        """
        pass

    @property
    @abstractmethod
    def fuente(self) -> FuenteDatos:
        """Tipo de fuente de este extractor."""
        pass


# =============================================================================
# EXTRACTOR DOCX XML
# =============================================================================

class DocxXmlExtractor(Extractor):
    """
    Extractor que lee directamente el XML interno del DOCX.

    Ventajas sobre python-docx:
    - Incluye texto en tablas (python-docx las omite en doc.paragraphs)
    - Preserva el orden exacto del documento
    - Es determinista
    - Detecta formato itálico (usado para referencias)

    Incluye pre-procesamiento para limpiar fragmentación del PDF→DOCX.
    """

    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self._paragraphs_cache: Optional[List[ParrafoExtraido]] = None

    @property
    def fuente(self) -> FuenteDatos:
        return FuenteDatos.DOCX_XML

    def extraer(self) -> List[ParrafoExtraido]:
        """
        Extrae TODOS los textos del DOCX leyendo directamente el XML.

        Returns:
            Lista de ParrafoExtraido con texto y flags de formato
        """
        if self._paragraphs_cache is not None:
            return self._paragraphs_cache

        with zipfile.ZipFile(self.file_path) as z:
            xml_content = z.read('word/document.xml')

        root = ET.fromstring(xml_content)
        paragraphs_raw = []

        # Namespace de Word
        ns_w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

        # Iterar sobre todos los párrafos (w:p) en orden del documento
        for idx, para in enumerate(root.iter(f'{ns_w}p')):
            result = self._extraer_parrafo(para, ns_w, idx)
            if result:
                paragraphs_raw.append(result)

        # Pre-procesar para limpiar fragmentación
        paragraphs = self._preprocesar(paragraphs_raw)

        self._paragraphs_cache = paragraphs
        return paragraphs

    def _extraer_parrafo(
        self,
        para: ET.Element,
        ns_w: str,
        indice: int
    ) -> Optional[ParrafoExtraido]:
        """
        Extrae un párrafo XML y detecta formato.

        Args:
            para: Elemento XML del párrafo (w:p)
            ns_w: Namespace de Word
            indice: Índice del párrafo en el documento

        Returns:
            ParrafoExtraido si hay texto, None si está vacío o filtrado
        """
        text_parts = []
        total_runs = 0
        italic_runs = 0
        bold_runs = 0

        for run in para.iter(f'{ns_w}r'):
            run_text = ''.join(t.text or '' for t in run.iter(f'{ns_w}t'))
            if not run_text:
                continue
            text_parts.append(run_text)
            total_runs += 1

            # Detectar formato en propiedades del run
            rPr = run.find(f'{ns_w}rPr')
            if rPr is not None:
                if rPr.find(f'{ns_w}i') is not None:
                    italic_runs += 1
                if rPr.find(f'{ns_w}b') is not None:
                    bold_runs += 1

        text = ''.join(text_parts).strip()

        if not text:
            return None

        # Filtrar elementos no-contenido
        if self._debe_filtrar(text):
            return None

        # Determinar formato predominante (>80% de runs)
        es_italica = (italic_runs / total_runs > 0.8) if total_runs > 0 else False
        es_negrita = (bold_runs / total_runs > 0.8) if total_runs > 0 else False

        return ParrafoExtraido(
            texto=text,
            es_italica=es_italica,
            es_negrita=es_negrita,
            indice_original=indice,
            fuente=FuenteDatos.DOCX_XML,
        )

    def _debe_filtrar(self, texto: str) -> bool:
        """
        Determina si un texto debe ser filtrado.

        Args:
            texto: Texto a evaluar

        Returns:
            True si debe filtrarse, False si es contenido válido
        """
        # Números de página
        if PATRON_PAGINA.match(texto):
            return True

        # Encabezados repetitivos
        if texto.startswith("Resolución Miscelánea Fiscal"):
            return True

        # Notas del documento
        if PATRON_NOTA_DOCUMENTO.match(texto):
            return True

        return False

    def _preprocesar(
        self,
        paragraphs: List[ParrafoExtraido]
    ) -> List[ParrafoExtraido]:
        """
        Pre-procesa párrafos para limpiar fragmentación del PDF→DOCX.

        1. Fusiona numerales romanos huérfanos con contenido siguiente
        2. Fusiona fragmentos cortos que son continuación

        Args:
            paragraphs: Lista de párrafos crudos

        Returns:
            Lista de párrafos procesados
        """
        if not paragraphs:
            return paragraphs

        resultado = []
        i = 0

        while i < len(paragraphs):
            parrafo = paragraphs[i]
            texto = parrafo.texto

            # Caso 1: Numeral romano huérfano (II., III., etc.)
            if PATRON_ROMANO_SOLO.match(texto):
                merged = self._fusionar_numerales_huerfanos(paragraphs, i)
                resultado.extend(merged)
                i += self._contar_elementos_consumidos(paragraphs, i, merged)
                continue

            # Caso 2: Fragmentos muy cortos que parecen continuación
            if self._es_fragmento_continuacion(texto):
                merged = self._fusionar_fragmentos(paragraphs, i)
                resultado.append(merged)
                i += self._contar_fragmentos_consumidos(paragraphs, i)
                continue

            resultado.append(parrafo)
            i += 1

        return resultado

    def _fusionar_numerales_huerfanos(
        self,
        paragraphs: List[ParrafoExtraido],
        start: int
    ) -> List[ParrafoExtraido]:
        """
        Fusiona numerales romanos huérfanos con su contenido.

        Ejemplo: ["II.", "III.", "contenido1", "contenido2"]
               → ["II. contenido1", "III. contenido2"]

        Args:
            paragraphs: Lista completa de párrafos
            start: Índice del primer numeral huérfano

        Returns:
            Lista de párrafos fusionados
        """
        # Recolectar todos los numerales consecutivos
        numerales = [paragraphs[start]]
        j = start + 1
        while j < len(paragraphs) and PATRON_ROMANO_SOLO.match(paragraphs[j].texto):
            numerales.append(paragraphs[j])
            j += 1

        # Recolectar contenidos correspondientes
        contenidos = []
        k = j
        while k < len(paragraphs) and len(contenidos) < len(numerales):
            siguiente = paragraphs[k]
            texto_sig = siguiente.texto

            # Si es estructura nueva, parar
            if (re.match(r'^\d+\.\d+\.\d+', texto_sig) or
                re.match(r'^Cap[íi]tulo|^Secci[óo]n', texto_sig, re.IGNORECASE) or
                PATRON_ROMANO_SOLO.match(texto_sig)):
                break

            contenidos.append(siguiente)
            k += 1

        # Fusionar numerales con contenidos
        resultado = []
        for idx, numeral in enumerate(numerales):
            if idx < len(contenidos):
                texto_fusionado = numeral.texto.rstrip('.') + '. ' + contenidos[idx].texto
                resultado.append(ParrafoExtraido(
                    texto=texto_fusionado,
                    es_italica=contenidos[idx].es_italica,
                    es_negrita=contenidos[idx].es_negrita,
                    indice_original=numeral.indice_original,
                    fuente=numeral.fuente,
                ))
            else:
                # No hay contenido para este numeral
                resultado.append(numeral)

        return resultado

    def _contar_elementos_consumidos(
        self,
        paragraphs: List[ParrafoExtraido],
        start: int,
        merged: List[ParrafoExtraido]
    ) -> int:
        """Cuenta cuántos elementos del original se consumieron."""
        # Contar numerales + contenidos
        j = start
        while j < len(paragraphs) and PATRON_ROMANO_SOLO.match(paragraphs[j].texto):
            j += 1
        num_numerales = j - start

        # Contenidos consumidos = min(numerales, contenidos disponibles)
        contenidos_consumidos = min(num_numerales, len(merged))

        return num_numerales + contenidos_consumidos

    def _es_fragmento_continuacion(self, texto: str) -> bool:
        """Determina si un texto parece fragmento de continuación."""
        # Excluir referencias legales
        if re.match(
            r'^(CFF|LISR|LIVA|LIESPS|LIEPS|LIF|LA|RMF|RGCE|RCFF|RLISR|RLIVA)\s+\d',
            texto, re.IGNORECASE
        ):
            return False

        # Excluir estructuras conocidas
        if (re.match(r'^\d+\.\d+\.\d+', texto) or
            re.match(r'^(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.', texto) or
            re.match(r'^Cap[íi]tulo|^Secci[óo]n', texto, re.IGNORECASE)):
            return False

        # Es fragmento si es corto y no termina en punto
        return len(texto) < 30 and not texto.endswith('.')

    def _fusionar_fragmentos(
        self,
        paragraphs: List[ParrafoExtraido],
        start: int
    ) -> ParrafoExtraido:
        """Fusiona fragmentos cortos consecutivos."""
        fragmentos = [paragraphs[start].texto]
        j = start + 1

        while j < len(paragraphs):
            siguiente = paragraphs[j]
            texto_sig = siguiente.texto

            if self._es_fragmento_continuacion(texto_sig):
                fragmentos.append(texto_sig)
                j += 1
            else:
                # Incluir el último (contenido real) y parar
                fragmentos.append(texto_sig)
                break

        texto_fusionado = ' '.join(fragmentos)

        return ParrafoExtraido(
            texto=texto_fusionado,
            es_italica=paragraphs[start].es_italica,
            es_negrita=paragraphs[start].es_negrita,
            indice_original=paragraphs[start].indice_original,
            fuente=paragraphs[start].fuente,
        )

    def _contar_fragmentos_consumidos(
        self,
        paragraphs: List[ParrafoExtraido],
        start: int
    ) -> int:
        """Cuenta cuántos fragmentos se consumieron."""
        j = start + 1
        while j < len(paragraphs):
            if self._es_fragmento_continuacion(paragraphs[j].texto):
                j += 1
            else:
                # Incluir el último (contenido real)
                j += 1
                break
        return j - start

    def buscar_regla(self, numero: str) -> Optional[str]:
        """
        Busca una regla específica por número.

        Busca el patrón "X.Y.Z." y extrae hasta la siguiente regla.
        """
        paragraphs = self.extraer()
        patron = re.compile(rf'^{re.escape(numero)}\.?\s+(.*)$')

        for i, p in enumerate(paragraphs):
            match = patron.match(p.texto)
            if match:
                # Recolectar contenido hasta siguiente regla
                contenido = [match.group(1)] if match.group(1) else []
                j = i + 1
                while j < len(paragraphs):
                    siguiente = paragraphs[j].texto
                    if re.match(r'^\d+\.\d+\.\d+', siguiente):
                        break
                    contenido.append(siguiente)
                    j += 1
                return '\n'.join(contenido)

        return None


# =============================================================================
# EXTRACTOR PDF (STUB PARA SEGUNDA PASADA)
# =============================================================================

class PdfExtractor(Extractor):
    """
    Extractor para archivos PDF.

    Usado principalmente en segunda pasada para comparar
    con otras fuentes y resolver ambigüedades.
    """

    @property
    def fuente(self) -> FuenteDatos:
        return FuenteDatos.PDF

    def extraer(self) -> List[ParrafoExtraido]:
        """
        Extrae texto del PDF.

        TODO: Implementar usando pdfplumber o pymupdf.
        Por ahora retorna lista vacía.
        """
        # Stub - implementar en segunda fase
        return []

    def buscar_regla(self, numero: str) -> Optional[str]:
        """
        Busca una regla específica en el PDF.

        TODO: Implementar búsqueda en PDF.
        """
        # Stub - implementar en segunda fase
        return None


# =============================================================================
# EXTRACTOR TXT (STUB PARA SEGUNDA PASADA)
# =============================================================================

class TxtExtractor(Extractor):
    """
    Extractor para archivos de texto plano.

    Usado como referencia de respaldo en segunda pasada.
    """

    @property
    def fuente(self) -> FuenteDatos:
        return FuenteDatos.TXT

    def extraer(self) -> List[ParrafoExtraido]:
        """
        Extrae texto del archivo TXT.

        Lee línea por línea, ignorando líneas vacías.
        """
        paragraphs = []

        with open(self.file_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if line:
                    paragraphs.append(ParrafoExtraido(
                        texto=line,
                        es_italica=False,  # TXT no tiene formato
                        es_negrita=False,
                        indice_original=idx,
                        fuente=FuenteDatos.TXT,
                    ))

        return paragraphs

    def buscar_regla(self, numero: str) -> Optional[str]:
        """
        Busca una regla específica en el TXT.
        """
        paragraphs = self.extraer()
        patron = re.compile(rf'^{re.escape(numero)}\.?\s+(.*)$')

        for i, p in enumerate(paragraphs):
            match = patron.match(p.texto)
            if match:
                contenido = [match.group(1)] if match.group(1) else []
                j = i + 1
                while j < len(paragraphs):
                    siguiente = paragraphs[j].texto
                    if re.match(r'^\d+\.\d+\.\d+', siguiente):
                        break
                    contenido.append(siguiente)
                    j += 1
                return '\n'.join(contenido)

        return None


# =============================================================================
# FACTORY
# =============================================================================

def crear_extractor(file_path: Path) -> Extractor:
    """
    Factory que crea el extractor apropiado según extensión.

    Args:
        file_path: Ruta al archivo

    Returns:
        Instancia del extractor apropiado

    Raises:
        ValueError: Si el tipo de archivo no es soportado
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == '.docx':
        return DocxXmlExtractor(file_path)
    elif suffix == '.pdf':
        return PdfExtractor(file_path)
    elif suffix == '.txt':
        return TxtExtractor(file_path)
    else:
        raise ValueError(f"Tipo de archivo no soportado: {suffix}")
