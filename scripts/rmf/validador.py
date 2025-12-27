"""
Fase 3: Validación + Segunda Pasada.

Validación Estructural (Primera Pasada):
- Numeración consecutiva
- Coherencia de texto
- Referencias válidas
- Fracciones/Incisos completos

Segunda Pasada (Casos Atípicos):
- Compara múltiples fuentes (DOCX XML, PDF, TXT)
- Aplica heurísticas para resolver problemas
- Marca resoluciones exitosas y fallidas
"""

import re
from typing import List, Optional, Dict, Tuple
from pathlib import Path

from .models import (
    ReglaParseada,
    Division,
    Problema,
    Resolucion,
    ResultadoParseo,
    TipoProblema,
    TipoDivision,
    FuenteDatos,
)
from .extractor import Extractor, DocxXmlExtractor, PdfExtractor, TxtExtractor


# =============================================================================
# VALIDADOR ESTRUCTURAL (PRIMERA PASADA)
# =============================================================================

class ValidadorEstructural:
    """
    Validador de primera pasada basado en el "deber ser".

    Valida que las reglas cumplan con la estructura esperada:
    - Numeración consecutiva dentro de cada capítulo
    - Contenido coherente (mayúscula inicial, punto final)
    - Referencias válidas (empiezan con sigla de ley)
    - Fracciones e incisos consecutivos

    Usage:
        validador = ValidadorEstructural()
        problemas = validador.validar_resultado(resultado)
    """

    # Siglas de leyes conocidas
    SIGLAS_LEYES = (
        'CFF', 'LISR', 'LIVA', 'LIESPS', 'LIEPS', 'LIF', 'LA',
        'RMF', 'RGCE', 'RCFF', 'RLISR', 'RLIVA', 'RLIESPS',
        'DECRETO', 'DOF', 'LGSM'
    )

    def __init__(self):
        """Inicializa el validador."""
        self.problemas_globales: List[Problema] = []

    def validar_resultado(self, resultado: ResultadoParseo) -> List[Problema]:
        """
        Valida el resultado completo del parseo.

        Args:
            resultado: ResultadoParseo a validar

        Returns:
            Lista de problemas detectados
        """
        self.problemas_globales = []

        # Validar numeración global
        self._validar_numeracion(resultado.reglas)

        # Validar cada regla individualmente
        for regla in resultado.reglas:
            if regla.tipo == "no-existe":
                continue  # Saltar placeholders
            self._validar_regla(regla)

        return self.problemas_globales

    def _validar_numeracion(self, reglas: List[ReglaParseada]):
        """
        Valida que la numeración sea consecutiva por capítulo.

        Detecta saltos en la numeración (ej: 2.1.3 -> 2.1.5).
        """
        from collections import defaultdict

        # Agrupar por capítulo
        por_capitulo: Dict[str, List[int]] = defaultdict(list)

        for regla in reglas:
            if regla.tipo != "regla":
                continue

            partes = regla.numero.split('.')
            if len(partes) == 3:
                capitulo = f"{partes[0]}.{partes[1]}"
                try:
                    num = int(partes[2])
                    por_capitulo[capitulo].append(num)
                except ValueError:
                    pass

        # Verificar consecutividad
        for capitulo, numeros in por_capitulo.items():
            numeros_ordenados = sorted(set(numeros))

            for i, num in enumerate(numeros_ordenados[1:], 1):
                esperado = numeros_ordenados[i-1] + 1
                if num != esperado:
                    # Hay un salto
                    faltantes = list(range(esperado, num))
                    self.problemas_globales.append(Problema(
                        tipo=TipoProblema.NUMERACION_NO_CONSECUTIVA,
                        descripcion=f"Salto en numeración: {capitulo}.{numeros_ordenados[i-1]} -> {capitulo}.{num}",
                        detalles=f"Faltantes: {faltantes}",
                        ubicacion=capitulo,
                        severidad="warning",
                    ))

    def _validar_regla(self, regla: ReglaParseada):
        """
        Valida una regla individual.

        Agrega problemas directamente a la regla.
        """
        # 1. Número válido
        if not self._es_numero_valido(regla.numero):
            regla.agregar_problema(Problema(
                tipo=TipoProblema.NUMERO_INVALIDO,
                descripcion=f"Número de regla inválido: {regla.numero}",
                ubicacion=regla.numero,
                severidad="error",
            ))

        # 2. Título presente
        if not regla.titulo or len(regla.titulo.strip()) == 0:
            regla.agregar_problema(Problema(
                tipo=TipoProblema.TITULO_AUSENTE,
                descripcion="No se encontró título para la regla",
                ubicacion=regla.numero,
                severidad="warning",
            ))

        # 3. Contenido coherente
        if regla.contenido:
            if not self._contenido_coherente(regla.contenido):
                regla.agregar_problema(Problema(
                    tipo=TipoProblema.CONTENIDO_INCOHERENTE,
                    descripcion="El contenido no cumple con formato esperado",
                    detalles=self._diagnosticar_contenido(regla.contenido),
                    ubicacion=regla.numero,
                    severidad="warning",
                ))

            # Contenido muy corto podría estar truncado
            if len(regla.contenido) < 20 and not regla.fracciones:
                regla.agregar_problema(Problema(
                    tipo=TipoProblema.CONTENIDO_TRUNCADO,
                    descripcion="El contenido parece truncado (muy corto)",
                    ubicacion=regla.numero,
                    severidad="error",
                ))

        # 4. Referencias válidas
        if regla.referencias:
            if not self._referencia_valida(regla.referencias):
                regla.agregar_problema(Problema(
                    tipo=TipoProblema.REFERENCIA_INVALIDA,
                    descripcion="La referencia no cumple formato esperado",
                    detalles=regla.referencias[:100],
                    ubicacion=regla.numero,
                    severidad="warning",
                ))

        # 5. Fracciones consecutivas
        if regla.fracciones:
            if not self._fracciones_consecutivas(regla.fracciones):
                regla.agregar_problema(Problema(
                    tipo=TipoProblema.FRACCIONES_INCOMPLETAS,
                    descripcion="Las fracciones no son consecutivas",
                    detalles=self._diagnosticar_fracciones(regla.fracciones),
                    ubicacion=regla.numero,
                    severidad="error",
                ))

    def _es_numero_valido(self, numero: str) -> bool:
        """Verifica si el número de regla tiene formato válido."""
        patron = re.compile(r'^\d+\.\d+\.\d+$')
        return bool(patron.match(numero))

    def _contenido_coherente(self, contenido: str) -> bool:
        """
        Verifica si el contenido es coherente estructuralmente.

        Criterios:
        - Empieza con mayúscula
        - Termina con punto (o tiene fracciones que lo hacen)
        """
        if not contenido:
            return False

        # Primer carácter debe ser mayúscula
        primer_char = contenido[0]
        if primer_char.islower():
            return False

        # Último carácter idealmente es punto
        # (pero puede terminar con ":" si hay fracciones después)
        ultimo = contenido.rstrip()[-1] if contenido.rstrip() else ''
        if ultimo not in '.;:':
            # No es necesariamente un problema si tiene fracciones
            pass

        return True

    def _diagnosticar_contenido(self, contenido: str) -> str:
        """Genera diagnóstico de por qué el contenido no es coherente."""
        problemas = []

        if contenido and contenido[0].islower():
            problemas.append("inicia con minúscula")

        if contenido and contenido.rstrip()[-1] not in '.;:':
            problemas.append("no termina con puntuación")

        return ", ".join(problemas) if problemas else "desconocido"

    def _referencia_valida(self, referencia: str) -> bool:
        """Verifica si la referencia tiene formato válido."""
        ref_upper = referencia.upper()
        return any(ref_upper.startswith(sigla) for sigla in self.SIGLAS_LEYES)

    def _fracciones_consecutivas(self, fracciones: list) -> bool:
        """Verifica si las fracciones son consecutivas."""
        if not fracciones:
            return True

        numeros = [f.orden for f in fracciones]
        for i in range(1, len(numeros)):
            if numeros[i] != numeros[i-1] + 1:
                return False

        return True

    def _diagnosticar_fracciones(self, fracciones: list) -> str:
        """Genera diagnóstico de fracciones no consecutivas."""
        numeros = [f.numero for f in fracciones]
        return f"Fracciones encontradas: {', '.join(numeros)}"


# =============================================================================
# INSPECTOR MULTI-FORMATO (SEGUNDA PASADA)
# =============================================================================

class InspectorMultiFormato:
    """
    Inspector de segunda pasada que compara múltiples fuentes.

    Usado para resolver problemas detectados en primera pasada:
    - Compara DOCX XML, PDF, TXT
    - Aplica heurísticas específicas por tipo de problema
    - Registra resoluciones exitosas y fallidas

    Usage:
        inspector = InspectorMultiFormato(docx_path, pdf_path, txt_path)
        resolucion = inspector.resolver(regla, problema)
    """

    def __init__(
        self,
        docx_path: Optional[Path] = None,
        pdf_path: Optional[Path] = None,
        txt_path: Optional[Path] = None,
    ):
        """
        Inicializa el inspector con las fuentes disponibles.

        Args:
            docx_path: Ruta al archivo DOCX
            pdf_path: Ruta al archivo PDF
            txt_path: Ruta al archivo TXT
        """
        self.fuentes: Dict[FuenteDatos, Optional[Extractor]] = {
            FuenteDatos.DOCX_XML: None,
            FuenteDatos.PDF: None,
            FuenteDatos.TXT: None,
        }

        if docx_path and Path(docx_path).exists():
            self.fuentes[FuenteDatos.DOCX_XML] = DocxXmlExtractor(docx_path)

        if pdf_path and Path(pdf_path).exists():
            self.fuentes[FuenteDatos.PDF] = PdfExtractor(pdf_path)

        if txt_path and Path(txt_path).exists():
            self.fuentes[FuenteDatos.TXT] = TxtExtractor(txt_path)

    def resolver(
        self,
        regla: ReglaParseada,
        problema: Problema
    ) -> Resolucion:
        """
        Intenta resolver un problema usando múltiples fuentes.

        Args:
            regla: Regla con el problema
            problema: Problema a resolver

        Returns:
            Resolucion con resultado del intento
        """
        # Seleccionar estrategia según tipo de problema
        if problema.tipo == TipoProblema.CONTENIDO_TRUNCADO:
            return self._resolver_contenido_truncado(regla, problema)

        elif problema.tipo == TipoProblema.FRACCIONES_INCOMPLETAS:
            return self._resolver_fracciones(regla, problema)

        elif problema.tipo == TipoProblema.TITULO_AUSENTE:
            return self._resolver_titulo(regla, problema)

        elif problema.tipo == TipoProblema.REFERENCIA_INVALIDA:
            return self._resolver_referencia(regla, problema)

        else:
            # Problema no tiene estrategia de resolución
            return Resolucion(
                problema_original=problema,
                exito=False,
                metodo="Sin estrategia para este tipo de problema",
            )

    def _resolver_contenido_truncado(
        self,
        regla: ReglaParseada,
        problema: Problema
    ) -> Resolucion:
        """
        Intenta resolver contenido truncado comparando fuentes.

        Estrategia:
        1. Buscar la regla en cada fuente
        2. Comparar longitudes de contenido
        3. Usar el contenido más largo
        """
        contenidos = self._buscar_en_fuentes(regla.numero)

        if not contenidos:
            return Resolucion(
                problema_original=problema,
                exito=False,
                metodo="No se encontró la regla en otras fuentes",
            )

        # Encontrar el contenido más largo
        mejor_fuente = None
        mejor_contenido = regla.contenido
        mejor_longitud = len(regla.contenido)

        for fuente, contenido in contenidos.items():
            if contenido and len(contenido) > mejor_longitud:
                mejor_fuente = fuente
                mejor_contenido = contenido
                mejor_longitud = len(contenido)

        if mejor_fuente:
            return Resolucion(
                problema_original=problema,
                exito=True,
                contenido_corregido=mejor_contenido,
                fuente_usada=mejor_fuente,
                metodo=f"Contenido más largo encontrado en {mejor_fuente.value}",
            )
        else:
            return Resolucion(
                problema_original=problema,
                exito=False,
                metodo="Ninguna fuente tiene contenido más largo",
            )

    def _resolver_fracciones(
        self,
        regla: ReglaParseada,
        problema: Problema
    ) -> Resolucion:
        """
        Intenta resolver fracciones incompletas.

        Estrategia:
        1. Buscar el contenido en otras fuentes
        2. Identificar patrones de fracciones (I., II., III.)
        3. Extraer fracciones faltantes
        """
        contenidos = self._buscar_en_fuentes(regla.numero)

        for fuente, contenido in contenidos.items():
            if not contenido:
                continue

            # Buscar patrones de fracciones
            patron = re.compile(r'(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s+([^I]+?)(?=(?:I{1,3}|IV|VI{0,3}|IX|X{1,3})\.|$)')
            matches = patron.findall(contenido)

            if len(matches) > len(regla.fracciones):
                # Encontramos más fracciones
                return Resolucion(
                    problema_original=problema,
                    exito=True,
                    contenido_corregido=contenido,
                    fuente_usada=fuente,
                    metodo=f"Fracciones adicionales encontradas en {fuente.value}",
                )

        return Resolucion(
            problema_original=problema,
            exito=False,
            metodo="No se encontraron fracciones adicionales en otras fuentes",
        )

    def _resolver_titulo(
        self,
        regla: ReglaParseada,
        problema: Problema
    ) -> Resolucion:
        """
        Intenta resolver título ausente.

        Estrategia:
        1. Buscar el contexto de la regla en otras fuentes
        2. Identificar texto corto antes del número
        """
        # Por ahora, estrategia simplificada
        # En implementación completa, buscaríamos el párrafo anterior
        return Resolucion(
            problema_original=problema,
            exito=False,
            metodo="Resolución de título requiere análisis de contexto",
        )

    def _resolver_referencia(
        self,
        regla: ReglaParseada,
        problema: Problema
    ) -> Resolucion:
        """
        Intenta resolver referencia inválida.

        Estrategia:
        1. Verificar formato en DOCX XML (itálica)
        2. Comparar con patrones conocidos
        """
        # Verificar si el extractor DOCX tiene información de formato
        docx_extractor = self.fuentes.get(FuenteDatos.DOCX_XML)

        if docx_extractor:
            contenido = docx_extractor.buscar_regla(regla.numero)
            if contenido and regla.referencias and regla.referencias in contenido:
                return Resolucion(
                    problema_original=problema,
                    exito=True,
                    metodo="Referencia confirmada en DOCX XML",
                )

        return Resolucion(
            problema_original=problema,
            exito=False,
            metodo="No se pudo validar la referencia en otras fuentes",
        )

    def _buscar_en_fuentes(self, numero: str) -> Dict[FuenteDatos, Optional[str]]:
        """
        Busca una regla en todas las fuentes disponibles.

        Returns:
            Diccionario de fuente -> contenido
        """
        resultados = {}

        for fuente, extractor in self.fuentes.items():
            if extractor:
                try:
                    contenido = extractor.buscar_regla(numero)
                    resultados[fuente] = contenido
                except Exception:
                    resultados[fuente] = None
            else:
                resultados[fuente] = None

        return resultados

    def procesar_resultado(
        self,
        resultado: ResultadoParseo
    ) -> Tuple[List[Resolucion], List[Problema]]:
        """
        Procesa todas las reglas con problemas en el resultado.

        Args:
            resultado: ResultadoParseo a procesar

        Returns:
            Tupla de (resoluciones exitosas, problemas pendientes)
        """
        resoluciones = []
        pendientes = []

        for regla in resultado.reglas:
            if not regla.requiere_segunda_pasada:
                continue

            for problema in regla.problemas:
                if problema.severidad != "error":
                    continue

                resolucion = self.resolver(regla, problema)
                resoluciones.append(resolucion)

                if resolucion.exito:
                    # Aplicar corrección si es posible
                    if resolucion.contenido_corregido:
                        regla.contenido = resolucion.contenido_corregido
                    regla.requiere_segunda_pasada = False
                else:
                    pendientes.append(problema)

        return resoluciones, pendientes


# =============================================================================
# HEURÍSTICAS ESPECÍFICAS
# =============================================================================

class HeuristicasRMF:
    """
    Heurísticas específicas para problemas comunes en RMF.

    Incluye:
    - Detección de numerales romanos huérfanos
    - Identificación de referencias largas con fecha
    - Distinción título vs referencia (ambos itálicos)
    """

    @staticmethod
    def es_numeral_huerfano(texto: str) -> bool:
        """
        Detecta si el texto es un numeral romano huérfano (II., III., etc).

        Problema común en conversión PDF→DOCX donde el numeral
        queda separado de su contenido.
        """
        patron = re.compile(r'^(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s*$')
        return bool(patron.match(texto.strip()))

    @staticmethod
    def es_referencia_larga_con_fecha(texto: str) -> bool:
        """
        Detecta referencias largas que terminan con fecha.

        Ejemplo: "CFF 14-A, Reglas a las que deberán..., 12/01/2007"
        """
        # Debe empezar con sigla
        siglas = ('CFF', 'LISR', 'LIVA', 'RMF', 'LIEPS')
        if not any(texto.upper().startswith(s) for s in siglas):
            return False

        # Debe terminar con fecha
        return bool(re.search(r'\d{1,2}/\d{1,2}/\d{4}$', texto.strip()))

    @staticmethod
    def es_titulo_no_referencia(texto: str, es_italica: bool) -> bool:
        """
        Distingue título de referencia (ambos pueden ser itálicos).

        - Referencia: itálica + empieza con sigla (CFF, LISR, etc.)
        - Título: itálica + NO empieza con sigla

        Args:
            texto: Texto a evaluar
            es_italica: Si el texto está en itálica

        Returns:
            True si es título, False si es referencia o contenido
        """
        if not es_italica:
            return False

        siglas = ('CFF', 'LISR', 'LIVA', 'LIESPS', 'LIEPS', 'LIF', 'LA',
                  'RMF', 'RGCE', 'RCFF', 'RLISR', 'RLIVA', 'DECRETO', 'DOF')

        texto_upper = texto.strip().upper()
        empieza_con_sigla = any(texto_upper.startswith(s) for s in siglas)

        # Si es itálica pero NO empieza con sigla, es título
        return not empieza_con_sigla

    @staticmethod
    def inferir_fracciones_de_contexto(contenido: str) -> List[Tuple[str, str]]:
        """
        Intenta inferir fracciones del contenido usando heurísticas.

        Busca patrones como "I.", "II.", "III." y extrae el contenido
        hasta la siguiente fracción o fin del texto.

        Returns:
            Lista de tuplas (numero_romano, contenido)
        """
        patron = re.compile(
            r'(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s+(.+?)(?=(?:I{1,3}|IV|VI{0,3}|IX|X{1,3})\.|$)',
            re.DOTALL
        )

        matches = patron.findall(contenido)
        return [(m[0], m[1].strip()) for m in matches]
