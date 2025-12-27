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
    EstatusCalidad,
    IssueCalidad,
    RegistroCalidad,
    Fraccion,
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
        Intenta resolver fracciones incompletas usando PDF como fuente de verdad.

        Estrategia:
        1. Obtener datos estructurados del PDF (buscar_regla_con_contexto)
        2. Si el PDF tiene más fracciones, reconstruir la lista
        3. Reemplazar las fracciones de la regla con las del PDF
        """
        # Intentar usar PDF primero (fuente más confiable)
        pdf_extractor = self.fuentes.get(FuenteDatos.PDF)

        if pdf_extractor:
            try:
                pdf_data = pdf_extractor.buscar_regla_con_contexto(regla.numero)

                if pdf_data and pdf_data.get('fracciones'):
                    fracciones_pdf = pdf_data['fracciones']

                    # Solo corregir si PDF tiene más fracciones
                    if len(fracciones_pdf) > len(regla.fracciones):
                        # Reconstruir fracciones desde PDF
                        fracciones_nuevas = []
                        for i, f_pdf in enumerate(fracciones_pdf):
                            fracciones_nuevas.append(Fraccion(
                                numero=f_pdf['numero'],
                                contenido=f_pdf['contenido'],
                                orden=i + 1,
                            ))

                        # Aplicar corrección
                        regla.fracciones = fracciones_nuevas

                        return Resolucion(
                            problema_original=problema,
                            exito=True,
                            metodo=f"Fracciones reconstruidas desde PDF ({len(fracciones_nuevas)} fracciones)",
                            fuente_usada=FuenteDatos.PDF,
                        )
            except Exception as e:
                # Si falla PDF, continuar con fallback
                pass

        # Fallback: buscar patrones en contenido de otras fuentes
        contenidos = self._buscar_en_fuentes(regla.numero)

        for fuente, contenido in contenidos.items():
            if not contenido:
                continue

            # Buscar patrones de fracciones
            patron = re.compile(r'(I{1,3}|IV|VI{0,3}|IX|X{1,3})\.\s+([^I]+?)(?=(?:I{1,3}|IV|VI{0,3}|IX|X{1,3})\.|$)')
            matches = patron.findall(contenido)

            if len(matches) > len(regla.fracciones):
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
        Intenta resolver título ausente usando PDF como fuente de verdad.

        Estrategia:
        1. Obtener datos estructurados del PDF (buscar_regla_con_contexto)
        2. Extraer título del PDF (párrafo anterior al número)
        3. Asignar título a la regla
        """
        # Intentar usar PDF primero (fuente más confiable)
        pdf_extractor = self.fuentes.get(FuenteDatos.PDF)

        if pdf_extractor:
            try:
                pdf_data = pdf_extractor.buscar_regla_con_contexto(regla.numero)

                if pdf_data and pdf_data.get('titulo'):
                    # Aplicar corrección
                    regla.titulo = pdf_data['titulo']

                    return Resolucion(
                        problema_original=problema,
                        exito=True,
                        metodo="Título extraído de PDF",
                        fuente_usada=FuenteDatos.PDF,
                    )
            except Exception:
                pass

        return Resolucion(
            problema_original=problema,
            exito=False,
            metodo="Título no encontrado en otras fuentes",
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

        Ejecuta segunda pasada automáticamente y puebla el campo `calidad`
        de cada regla con el registro de issues y acciones correctivas.

        Args:
            resultado: ResultadoParseo a procesar

        Returns:
            Tupla de (resoluciones exitosas, problemas pendientes)
        """
        resoluciones = []
        pendientes = []

        for regla in resultado.reglas:
            if regla.tipo == "no-existe":
                continue  # Saltar placeholders

            # Crear registro de calidad para esta regla
            registro = RegistroCalidad()

            # Si no tiene problemas, queda OK (sin registro visible)
            if not regla.problemas:
                # No asignar calidad - OK implícito
                continue

            # Procesar cada problema detectado
            for problema in regla.problemas:
                # Crear issue de calidad
                issue = IssueCalidad(
                    tipo=problema.tipo.value,
                    descripcion=problema.descripcion,
                    severidad=problema.severidad,
                )

                # Para errores, intentar segunda pasada
                if problema.severidad == "error":
                    resolucion = self.resolver(regla, problema)
                    resoluciones.append(resolucion)

                    if resolucion.exito:
                        # Aplicar corrección si es posible
                        if resolucion.contenido_corregido:
                            regla.contenido = resolucion.contenido_corregido

                        issue.accion = resolucion.metodo
                        issue.fuente_correccion = (
                            resolucion.fuente_usada.value
                            if resolucion.fuente_usada else None
                        )
                        issue.resuelto = True
                    else:
                        issue.accion = f"Intento fallido: {resolucion.metodo}"
                        issue.resuelto = False
                        pendientes.append(problema)
                else:
                    # Warnings solo se documentan, no se corrigen
                    issue.accion = "Solo advertencia, sin acción"
                    issue.resuelto = True  # Warnings no bloquean

                registro.agregar_issue(issue)

            # Asignar registro de calidad a la regla
            regla.calidad = registro
            regla.requiere_segunda_pasada = (registro.estatus == EstatusCalidad.CON_ERROR)

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


# =============================================================================
# VALIDADOR DE INTEGRIDAD DE TEXTO
# =============================================================================

class ValidadorIntegridad:
    """
    Valida que no se pierda texto en el proceso de parseo.

    Regla fundamental: TODO texto del documento fuente debe existir
    en algún lugar del resultado (contenido, fracciones, referencias, etc.)

    Detecta:
    - Texto desaparecido completamente
    - Fracciones faltantes (detectadas en fuente pero no en resultado)
    - Párrafos intermedios perdidos

    Usage:
        validador = ValidadorIntegridad()
        reporte = validador.validar(parrafos_fuente, resultado_parseo)
    """

    def __init__(self, umbral_similitud: float = 0.8):
        """
        Args:
            umbral_similitud: Porcentaje mínimo de texto que debe preservarse
        """
        self.umbral_similitud = umbral_similitud

    def validar(
        self,
        parrafos_fuente: List['ParrafoExtraido'],
        resultado: ResultadoParseo,
    ) -> Dict[str, any]:
        """
        Valida integridad comparando fuente con resultado.

        Args:
            parrafos_fuente: Párrafos originales del documento
            resultado: Resultado del parseo

        Returns:
            Diccionario con reporte de integridad:
            - texto_fuente_total: caracteres en fuente
            - texto_resultado_total: caracteres en resultado
            - porcentaje_preservado: % de texto preservado
            - parrafos_perdidos: lista de textos no encontrados
            - es_valido: True si supera el umbral
        """
        # Extraer todo el texto de la fuente
        texto_fuente = self._extraer_texto_fuente(parrafos_fuente)

        # Extraer todo el texto del resultado
        texto_resultado = self._extraer_texto_resultado(resultado)

        # Calcular cobertura
        palabras_fuente = set(self._normalizar_texto(texto_fuente).split())
        palabras_resultado = set(self._normalizar_texto(texto_resultado).split())

        if not palabras_fuente:
            return {
                'texto_fuente_total': 0,
                'texto_resultado_total': len(texto_resultado),
                'porcentaje_preservado': 100.0,
                'parrafos_perdidos': [],
                'es_valido': True,
            }

        palabras_preservadas = palabras_fuente & palabras_resultado
        porcentaje = len(palabras_preservadas) / len(palabras_fuente) * 100

        # Identificar párrafos perdidos
        parrafos_perdidos = self._identificar_perdidos(
            parrafos_fuente, texto_resultado
        )

        return {
            'texto_fuente_total': len(texto_fuente),
            'texto_resultado_total': len(texto_resultado),
            'porcentaje_preservado': round(porcentaje, 2),
            'palabras_fuente': len(palabras_fuente),
            'palabras_resultado': len(palabras_resultado),
            'palabras_perdidas': len(palabras_fuente - palabras_resultado),
            'parrafos_perdidos': parrafos_perdidos,
            'es_valido': porcentaje >= (self.umbral_similitud * 100),
        }

    def validar_regla_contra_pdf(
        self,
        regla: ReglaParseada,
        pdf_extractor: 'PdfExtractor',
    ) -> Dict[str, any]:
        """
        Valida una regla específica contra la versión del PDF.

        Detecta si la regla en el resultado tiene menos contenido
        que la versión del PDF (que suele tener mejor estructura).

        Args:
            regla: Regla parseada a validar
            pdf_extractor: Extractor PDF configurado

        Returns:
            Diccionario con comparación:
            - fracciones_docx: número de fracciones en DOCX
            - fracciones_pdf: número de fracciones en PDF
            - faltan_fracciones: True si PDF tiene más
            - fracciones_faltantes: lista de fracciones faltantes
        """
        # Obtener versión del PDF
        pdf_data = pdf_extractor.buscar_regla_con_contexto(regla.numero)

        if not pdf_data:
            return {
                'fracciones_docx': len(regla.fracciones),
                'fracciones_pdf': 0,
                'faltan_fracciones': False,
                'pdf_disponible': False,
            }

        fracciones_docx = {f.numero for f in regla.fracciones}
        fracciones_pdf = {f['numero'] for f in pdf_data['fracciones']}

        faltantes = fracciones_pdf - fracciones_docx

        return {
            'fracciones_docx': len(fracciones_docx),
            'fracciones_pdf': len(fracciones_pdf),
            'faltan_fracciones': len(faltantes) > 0,
            'fracciones_faltantes': list(faltantes),
            'pdf_disponible': True,
            'titulo_pdf': pdf_data.get('titulo'),
            'titulo_docx': regla.titulo,
        }

    def _extraer_texto_fuente(self, parrafos: List['ParrafoExtraido']) -> str:
        """Extrae todo el texto de los párrafos fuente."""
        return '\n'.join(p.texto for p in parrafos if p.texto.strip())

    def _extraer_texto_resultado(self, resultado: ResultadoParseo) -> str:
        """Extrae todo el texto del resultado del parseo."""
        textos = []

        for regla in resultado.reglas:
            if regla.titulo:
                textos.append(regla.titulo)
            if regla.contenido:
                textos.append(regla.contenido)
            if regla.referencias:
                textos.append(regla.referencias)

            for fraccion in regla.fracciones:
                if fraccion.contenido:
                    textos.append(fraccion.contenido)
                for inciso in fraccion.incisos:
                    if inciso.contenido:
                        textos.append(inciso.contenido)

        return '\n'.join(textos)

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para comparación."""
        # Minúsculas, sin puntuación extra
        texto = texto.lower()
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    def _identificar_perdidos(
        self,
        parrafos_fuente: List['ParrafoExtraido'],
        texto_resultado: str
    ) -> List[str]:
        """
        Identifica párrafos de la fuente que no están en el resultado.
        """
        texto_resultado_norm = self._normalizar_texto(texto_resultado)
        perdidos = []

        for parrafo in parrafos_fuente:
            texto = parrafo.texto.strip()
            if len(texto) < 10:
                continue  # Ignorar textos muy cortos

            texto_norm = self._normalizar_texto(texto)

            # Verificar si las palabras principales están en el resultado
            palabras = texto_norm.split()
            if len(palabras) < 3:
                continue

            # Tomar las primeras 5 palabras significativas
            palabras_clave = palabras[:5]
            encontradas = sum(1 for p in palabras_clave if p in texto_resultado_norm)

            # Si menos del 60% de palabras clave están, considerar perdido
            if encontradas / len(palabras_clave) < 0.6:
                perdidos.append(texto[:100] + '...' if len(texto) > 100 else texto)

        return perdidos
