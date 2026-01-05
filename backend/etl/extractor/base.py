"""
Clase base abstracta para extractores de leyes.

Proporciona:
- Flujo de extraccion unificado
- Calculo de jerarquia padre_numero
- Generacion de JSON con formato estandar
- Extraccion de fecha DOF

Las subclases implementan:
- Apertura/cierre de PDF (biblioteca especifica)
- Extraccion de estructura (outline vs texto)
- Extraccion de contenido (coordenadas X vs patrones)
"""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.parent.parent.parent

# Meses en espanol para parsear fechas DOF
MESES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

# Jerarquia de tipos de parrafo (menor = mas alto en jerarquia)
JERARQUIA_TIPOS = {
    'texto': 0,
    'fraccion': 1,
    'inciso': 2,
    'numeral': 3,
    'apartado': 4,
}

# Advertencia estandar para archivos JSON generados
ADVERTENCIA_JSON = [
    "=====================================================================",
    "  ARCHIVO SAGRADO - FUENTE UNICA DE VERDAD",
    "",
    "  NO MODIFICAR MANUALMENTE",
    "",
    "  Este archivo es la UNICA fuente de verdad para el contenido.",
    "  La base de datos se regenera desde aqui.",
    "",
    "  Si el contenido es incorrecto:",
    "    -> CORRIGE EL SCRIPT, no este archivo",
    "",
    "  Modificarlo manualmente es SABOTAJE al sistema.",
    "====================================================================="
]


# =============================================================================
# MAQUINA DE ESTADOS PARA DETECCION DE IDENTIFICADORES
# =============================================================================

class DetectorIdentificadores:
    """
    Máquina de estados para detectar identificadores de párrafos.

    Mantiene estado de la última fracción, apartado, inciso y numeral
    detectados para validar secuencias.

    Uso:
        detector = DetectorIdentificadores()
        tipo, ident, contenido, es_valido = detector.detectar("V. Será juzgado...")
        if es_valido:
            # usar tipo, ident, contenido
    """

    LETRAS_ROMANAS = set('IVXLCDM')
    VALORES_ROMANOS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}

    def __init__(self):
        self.reset()

    def reset(self):
        """Reinicia el estado (al iniciar nuevo artículo)."""
        self.ultima_fraccion: Optional[int] = None   # Valor numérico: 1, 2, 5, 10...
        self.ultimo_apartado: Optional[str] = None   # Letra: 'A', 'B', 'C'...
        self.ultimo_inciso: Optional[str] = None     # Letra: 'a', 'b', 'c'...
        self.ultimo_numeral: Optional[int] = None    # Número: 1, 2, 3...

    def guardar_estado(self) -> tuple:
        """Guarda el estado actual para poder restaurarlo después."""
        return (self.ultima_fraccion, self.ultimo_apartado,
                self.ultimo_inciso, self.ultimo_numeral)

    def restaurar_estado(self, estado: tuple):
        """Restaura un estado previamente guardado."""
        (self.ultima_fraccion, self.ultimo_apartado,
         self.ultimo_inciso, self.ultimo_numeral) = estado

    def detectar(self, texto: str) -> tuple[str, Optional[str], str, bool]:
        """
        Detecta el tipo de identificador y valida si es válido en secuencia.

        Returns:
            (tipo, identificador, contenido, es_valido)
            - tipo: 'fraccion', 'apartado', 'inciso', 'numeral', 'texto'
            - identificador: 'I', 'A.', 'a)', '1.', None
            - contenido: texto después del identificador
            - es_valido: True si el identificador es válido en la secuencia actual
        """
        texto = texto.strip()
        if not texto:
            return ('texto', None, texto, False)

        # Normalizar errores comunes de PDF/Word: l (L minúscula) → I en fracciones
        # Ejemplos: "lI." → "II.", "lll." → "III.", "lV." → "IV."
        texto = self._normalizar_romano_corrupto(texto)

        # 1. Inciso: a), b), c)...
        match = re.match(r'^([a-z])\)\s*(.*)', texto, re.DOTALL)
        if match:
            letra = match.group(1)
            contenido = match.group(2)
            es_valido = self._validar_inciso(letra)
            if es_valido:
                self.ultimo_inciso = letra
                self.ultimo_numeral = None  # Reiniciar numerales
            return ('inciso', letra, contenido, es_valido)

        # 2. Numeral: 1., 2., 3...
        match = re.match(r'^(\d+)\.\s*(.*)', texto, re.DOTALL)
        if match:
            num = int(match.group(1))
            contenido = match.group(2)
            es_valido = self._validar_numeral(num)
            if es_valido:
                self.ultimo_numeral = num
            return ('numeral', str(num), contenido, es_valido)

        # 3. Romano multi-caracter: II., III., IV., VI... (acepta guión opcional: III.-)
        match = re.match(r'^([IVXLCDM]{2,})\.[-–]?\s*(.*)', texto, re.DOTALL)
        if match:
            romano = match.group(1)
            contenido = match.group(2)
            valor = self._romano_a_entero(romano)
            if valor:
                es_valido = self._validar_fraccion(valor)
                if es_valido:
                    self._actualizar_fraccion(valor)
                return ('fraccion', romano, contenido, es_valido)

        # 4. Letra única seguida de punto: A., B., I., V., X... (acepta guión opcional: I.-)
        match = re.match(r'^([A-Z])\.[-–]?\s*(.*)', texto, re.DOTALL)
        if match:
            letra = match.group(1)
            contenido = match.group(2)

            if letra in self.LETRAS_ROMANAS:
                # Puede ser fracción romana o apartado
                valor_romano = self._romano_a_entero(letra)
                es_fraccion_valida = self._validar_fraccion(valor_romano)
                es_apartado_valido = self._validar_apartado(letra)

                # Priorizar según contexto:
                # - Si apartado sigue secuencia activa (H→I), priorizar apartado
                # - Si solo fracción es válida, usar fracción
                if es_apartado_valido:
                    # Apartado tiene secuencia activa, priorizar
                    self._actualizar_apartado(letra)
                    return ('apartado', letra, contenido, True)
                elif es_fraccion_valida:
                    # Solo fracción es válida (puede iniciar o continuar)
                    self._actualizar_fraccion(valor_romano)
                    return ('fraccion', letra, contenido, True)
                # Ninguno válido
                return ('texto', None, texto, False)
            else:
                # Letra no romana: solo puede ser apartado
                es_valido = self._validar_apartado(letra)
                if es_valido:
                    self._actualizar_apartado(letra)
                return ('apartado', letra, contenido, es_valido)

        # 5. Texto plano
        return ('texto', None, texto, False)

    def _romano_a_entero(self, s: str) -> Optional[int]:
        """Convierte número romano a entero."""
        total = 0
        prev = 0
        for c in reversed(s):
            if c not in self.VALORES_ROMANOS:
                return None
            curr = self.VALORES_ROMANOS[c]
            if curr < prev:
                total -= curr
            else:
                total += curr
            prev = curr
        return total if total > 0 else None

    def _validar_fraccion(self, valor: int) -> bool:
        """Valida si una fracción es válida en la secuencia actual."""
        if valor == 1:
            return True  # I siempre puede iniciar
        if self.ultima_fraccion is None:
            return False
        return valor == self.ultima_fraccion + 1

    def _actualizar_fraccion(self, valor: int):
        """Actualiza estado al detectar fracción válida."""
        self.ultima_fraccion = valor
        self.ultimo_inciso = None
        self.ultimo_numeral = None

    def _validar_apartado(self, letra: str) -> bool:
        """Valida si un apartado es válido en la secuencia actual."""
        if letra == 'A':
            return True  # A siempre puede iniciar
        if self.ultimo_apartado is None:
            return False
        return ord(letra) == ord(self.ultimo_apartado) + 1

    def _actualizar_apartado(self, letra: str):
        """Actualiza estado al detectar apartado válido."""
        self.ultimo_apartado = letra
        # NO reiniciar ultima_fraccion - apartados pueden estar dentro de fracciones
        self.ultimo_inciso = None
        self.ultimo_numeral = None

    def _validar_inciso(self, letra: str) -> bool:
        """Valida si un inciso es válido en la secuencia actual."""
        if letra == 'a':
            return True  # a) siempre puede iniciar
        if self.ultimo_inciso is None:
            return False
        return ord(letra) == ord(self.ultimo_inciso) + 1

    def _validar_numeral(self, num: int) -> bool:
        """Valida si un numeral es válido en la secuencia actual."""
        if num == 1:
            return True  # 1. siempre puede iniciar
        if self.ultimo_numeral is None:
            return False
        return num == self.ultimo_numeral + 1

    def _normalizar_romano_corrupto(self, texto: str) -> str:
        """
        Normaliza fracciones romanas corruptas por errores de PDF/Word.

        Problema común: usar 'l' (L minúscula, código 108) en vez de 'I' (i mayúscula, código 73)
        Ejemplos: "lI." → "II.", "lll." → "III.", "lV." → "IV.", "l.-" → "I.-"

        Solo aplica al inicio del texto cuando el patrón parece una fracción romana.
        """
        # Patrón: inicio con mezcla de l y caracteres romanos, seguido de punto y opcionalmente guión
        # Debe contener al menos una 'l' para aplicar normalización
        match = re.match(r'^([lIVXLCDM]+)\.([-–]?)(\s.*|$)', texto)
        if match and 'l' in match.group(1):
            corrupto = match.group(1)
            guion = match.group(2)
            resto = match.group(3)
            # Reemplazar todas las l por I
            normalizado = corrupto.replace('l', 'I')
            # Solo aplicar si el resultado es un romano válido
            if all(c in 'IVXLCDM' for c in normalizado):
                return normalizado + '.' + guion + resto
        return texto


# =============================================================================
# DATACLASSES COMPARTIDOS
# =============================================================================

@dataclass
class Parrafo:
    """Un parrafo dentro de un articulo/regla."""
    numero: int                      # Orden secuencial: 1, 2, 3...
    tipo: str                        # 'texto', 'fraccion', 'inciso', 'numeral'
    identificador: Optional[str]     # 'I', 'a)', '1.', None para texto
    contenido: str
    padre_numero: Optional[int] = None   # Numero del parrafo padre
    x_id: Optional[int] = None           # X del identificador (opcional)
    x_texto: Optional[int] = None        # X del contenido (opcional)
    referencias: Optional[str] = None    # Referencias DOF (texto: "CFF 29, LISR 1o.")

    def to_dict(self) -> dict:
        d = {
            "numero": self.numero,
            "tipo": self.tipo,
            "identificador": self.identificador,
            "contenido": self.contenido,
            "padre_numero": self.padre_numero,
        }
        if self.x_id is not None:
            d["x_id"] = self.x_id
        if self.x_texto is not None:
            d["x_texto"] = self.x_texto
        if self.referencias:
            d["referencias"] = self.referencias
        return d


@dataclass
class Articulo:
    """Un articulo o regla."""
    numero: str                      # "1o", "17-H BIS", "2.1.1"
    tipo: str                        # "articulo", "regla", "transitorio"
    parrafos: list[Parrafo] = field(default_factory=list)
    orden: int = 0
    pagina: int = 0
    nombre: Optional[str] = None     # Titulo/nombre (para RMF)
    division: Optional[str] = None   # Division a la que pertenece
    referencias: Optional[str] = None  # Referencias legales (RMF: "CFF 29, LISR 1o.")

    def to_dict(self) -> dict:
        d = {
            "numero": self.numero,
            "tipo": self.tipo,
            "orden": self.orden,
            "pagina": self.pagina,
            "parrafos": [p.to_dict() for p in self.parrafos],
        }
        if self.nombre:
            d["nombre"] = self.nombre
        if self.division:
            d["division"] = self.division
        if self.referencias:
            d["referencias"] = self.referencias
        return d


@dataclass
class Division:
    """Una division estructural (titulo, capitulo, seccion)."""
    tipo: str                        # 'titulo', 'capitulo', 'seccion'
    numero: str                      # 'PRIMERO', 'I', '2.1'
    nombre: Optional[str]            # 'Disposiciones Generales'
    orden: int
    padre_orden: Optional[int] = None
    pagina: int = 0

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "nombre": self.nombre,
            "orden": self.orden,
            "padre_orden": self.padre_orden,
        }


# =============================================================================
# CLASE BASE ABSTRACTA
# =============================================================================

class ExtractorBase(ABC):
    """
    Clase base abstracta para extractores de leyes.

    Flujo de extraccion:
        1. abrir_pdf()           -> Abre PDF con biblioteca especifica
        2. extraer_estructura()  -> Extrae divisiones (titulos/capitulos)
        3. extraer_contenido()   -> Extrae articulos con parrafos
        4. _asignar_padres()     -> Calcula padre_numero si falta
        5. extraer_fecha_dof()   -> Extrae fecha de ultima reforma
        6. _generar_json()       -> Genera JSON con formato estandar
        7. cerrar_pdf()          -> Cierra PDF

    Subclases deben implementar:
        - abrir_pdf()
        - cerrar_pdf()
        - extraer_estructura()
        - extraer_contenido()
        - _extraer_texto_pagina() (para fecha DOF)
    """

    def __init__(self, codigo: str, config: dict):
        """
        Inicializa el extractor.

        Args:
            codigo: Codigo de la ley (CFF, LISR, RMF, etc.)
            config: Configuracion de la ley desde config.py
        """
        self.codigo = codigo.upper()
        self.config = config
        self.pdf_path = BASE_DIR / config["pdf_path"]
        self.pdf = None

        # Configuraciones opcionales
        self.filtro_y = config.get("filtro_y", {})
        self.patron_fecha = config.get("fecha_dof_patron")

    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================

    def extraer(self) -> dict:
        """
        Metodo principal que orquesta el proceso completo de extraccion.

        Returns:
            dict: Contenido JSON listo para guardar
        """
        print(f"\n{'='*60}")
        print(f"EXTRACTOR: {self.codigo}")
        print(f"{'='*60}")

        # 1. Abrir PDF
        print("\n1. Abriendo PDF...")
        self.abrir_pdf()
        print(f"   PDF: {self.pdf_path.name} ({self._get_num_paginas()} paginas)")

        # 2. Extraer estructura (divisiones)
        print("\n2. Extrayendo estructura...")
        divisiones = self.extraer_estructura()
        print(f"   Divisiones: {len(divisiones)}")

        # 3. Extraer contenido (articulos)
        print("\n3. Extrayendo contenido...")
        articulos = self.extraer_contenido()
        print(f"   Articulos: {len(articulos)}")

        # 4. Asignar padre_numero donde falte
        print("\n4. Calculando jerarquia de parrafos...")
        parrafos_con_padre_asignado = 0
        for articulo in articulos:
            antes = sum(1 for p in articulo.parrafos if p.padre_numero is None and p.tipo not in ('texto', 'fraccion'))
            self._asignar_padres(articulo.parrafos)
            despues = sum(1 for p in articulo.parrafos if p.padre_numero is None and p.tipo not in ('texto', 'fraccion'))
            parrafos_con_padre_asignado += (antes - despues)
        print(f"   Parrafos procesados: {parrafos_con_padre_asignado} padres asignados")

        # 5. Extraer fecha DOF
        print("\n5. Extrayendo fecha DOF...")
        fecha_dof = self.extraer_fecha_dof()
        if fecha_dof:
            print(f"   Fecha DOF: {fecha_dof}")
        else:
            print("   AVISO: No se encontro fecha DOF")

        # 6. Generar JSON
        print("\n6. Generando JSON...")
        resultado = self._generar_json(divisiones, articulos, fecha_dof)

        # 7. Estadisticas
        self._imprimir_estadisticas(articulos)

        # 8. Cerrar PDF
        self.cerrar_pdf()

        print(f"\n{'='*60}")
        print("EXTRACCION COMPLETADA")
        print(f"{'='*60}")

        return resultado

    def guardar(self, contenido: dict, archivo: str = "contenido.json"):
        """
        Guarda el JSON en el directorio del PDF.

        Args:
            contenido: Diccionario a guardar
            archivo: Nombre del archivo (default: contenido.json)
        """
        output_path = self.pdf_path.parent / archivo
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
        print(f"   Guardado: {output_path}")

    # =========================================================================
    # METODOS ABSTRACTOS (implementar en subclases)
    # =========================================================================

    @abstractmethod
    def abrir_pdf(self):
        """Abre el PDF con PyMuPDF (fitz)."""
        pass

    @abstractmethod
    def cerrar_pdf(self):
        """Cierra el PDF."""
        pass

    @abstractmethod
    def _get_num_paginas(self) -> int:
        """Retorna numero de paginas del PDF."""
        pass

    @abstractmethod
    def _extraer_texto_pagina(self, pagina: int) -> str:
        """Extrae texto de una pagina especifica."""
        pass

    @abstractmethod
    def extraer_estructura(self) -> list[Division]:
        """
        Extrae la estructura jerarquica (titulos, capitulos, secciones).

        Returns:
            Lista de Division ordenadas
        """
        pass

    @abstractmethod
    def extraer_contenido(self) -> list[Articulo]:
        """
        Extrae articulos/reglas con sus parrafos.

        Returns:
            Lista de Articulo con sus Parrafo
        """
        pass

    # =========================================================================
    # METODOS COMUNES (implementados en base)
    # =========================================================================

    def extraer_fecha_dof(self) -> Optional[str]:
        """
        Extrae la fecha DOF del encabezado de la primera pagina.

        Busca patrones como:
        - "28 de diciembre de 2025"
        - Patron personalizado de config["fecha_dof_patron"]

        Returns:
            Fecha en formato ISO (YYYY-MM-DD) o None
        """
        if not self.patron_fecha:
            # Patron por defecto
            patron = r'(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})'
        else:
            patron = self.patron_fecha

        try:
            # Buscar en primeras 3 paginas
            for pag in range(min(3, self._get_num_paginas())):
                texto = self._extraer_texto_pagina(pag)
                match = re.search(patron, texto, re.IGNORECASE)
                if match:
                    grupos = match.groups()
                    # Determinar formato del patron
                    if grupos[1].lower() in MESES:
                        # Formato: dia, mes_texto, anio
                        dia = int(grupos[0])
                        mes = MESES[grupos[1].lower()]
                        anio = int(grupos[2])
                    else:
                        # Formato numerico: dia, mes, anio
                        dia = int(grupos[0])
                        mes = int(grupos[1])
                        anio = int(grupos[2])
                    return f"{anio:04d}-{mes:02d}-{dia:02d}"
        except Exception as e:
            print(f"   AVISO: Error extrayendo fecha DOF: {e}")

        return None

    def _asignar_padres(self, parrafos: list[Parrafo]):
        """
        Asigna padre_numero a parrafos que no lo tienen.

        Algoritmo:
        - texto/fraccion: padre = None (raiz)
        - inciso: padre = ultima fraccion
        - numeral: padre = ultimo inciso (o fraccion si no hay inciso)

        El algoritmo mantiene un registro del ultimo parrafo de cada nivel
        y asigna como padre el elemento mas cercano de nivel superior.
        """
        if not parrafos:
            return

        # Verificar si ya todos tienen padre_numero
        # (extractores como el general ya lo calculan)
        todos_tienen_padre = all(
            p.padre_numero is not None or p.tipo in ('texto', 'fraccion')
            for p in parrafos
        )
        if todos_tienen_padre:
            return

        # Registro del ultimo parrafo por nivel jerarquico
        # {nivel: numero_parrafo}
        ultimo_por_nivel: dict[int, int] = {}

        for p in parrafos:
            # Si ya tiene padre asignado, solo actualizar registro
            if p.padre_numero is not None:
                nivel = JERARQUIA_TIPOS.get(p.tipo, 0)
                ultimo_por_nivel[nivel] = p.numero
                # Limpiar niveles inferiores (nueva rama)
                ultimo_por_nivel = {k: v for k, v in ultimo_por_nivel.items() if k <= nivel}
                continue

            tipo = p.tipo
            nivel = JERARQUIA_TIPOS.get(tipo, 0)

            # Determinar padre segun nivel
            if nivel <= 1:
                # texto (0) y fraccion (1) son raiz
                p.padre_numero = None
            else:
                # Buscar padre: el ultimo elemento de nivel estrictamente inferior
                padre_encontrado = None
                for n in range(nivel - 1, 0, -1):  # Desde nivel-1 hasta 1 (no 0=texto)
                    if n in ultimo_por_nivel:
                        padre_encontrado = ultimo_por_nivel[n]
                        break
                p.padre_numero = padre_encontrado

            # Actualizar registro
            ultimo_por_nivel[nivel] = p.numero
            # Limpiar niveles inferiores (iniciamos nueva rama desde este nivel)
            ultimo_por_nivel = {k: v for k, v in ultimo_por_nivel.items() if k <= nivel}

    def _generar_json(self, divisiones: list[Division], articulos: list[Articulo],
                      fecha_dof: Optional[str]) -> dict:
        """
        Genera el JSON de contenido con formato estandar.

        Args:
            divisiones: Lista de divisiones estructurales
            articulos: Lista de articulos extraidos
            fecha_dof: Fecha de ultima reforma

        Returns:
            dict listo para serializar a JSON
        """
        resultado = {
            "_advertencia": ADVERTENCIA_JSON,
            "_generado_por": f"extractor/{self.__class__.__name__}",
            "ley": self.codigo,
            "tipo_contenido": self.config.get("tipo_contenido", "articulo"),
            "articulos": [a.to_dict() for a in articulos],
        }

        if fecha_dof:
            resultado["ultima_reforma_dof"] = fecha_dof

        if self.config.get("url_fuente"):
            resultado["fuente"] = self.config["url_fuente"]

        return resultado

    def _imprimir_estadisticas(self, articulos: list[Articulo]):
        """Imprime estadisticas de la extraccion."""
        total_parrafos = sum(len(a.parrafos) for a in articulos)
        tipos_parrafo = {}
        parrafos_con_padre = 0

        for a in articulos:
            for p in a.parrafos:
                tipos_parrafo[p.tipo] = tipos_parrafo.get(p.tipo, 0) + 1
                if p.padre_numero is not None:
                    parrafos_con_padre += 1

        print(f"\n   Estadisticas:")
        print(f"   - Articulos: {len(articulos)}")
        print(f"   - Parrafos: {total_parrafos}")
        print(f"   - Con padre_numero: {parrafos_con_padre}")
        print(f"   - Por tipo:")
        for tipo, count in sorted(tipos_parrafo.items(), key=lambda x: -x[1]):
            print(f"       {tipo}: {count}")

    # =========================================================================
    # UTILIDADES COMUNES
    # =========================================================================

    def _detectar_tipo_identificador(
        self,
        texto: str,
        ultima_fraccion: Optional[int] = None,
        ultimo_apartado: Optional[str] = None
    ) -> tuple[str, Optional[str], str]:
        """
        Detecta tipo de elemento y extrae identificador.

        Reglas lógicas:
        - Inciso (a, b, c...) y numeral (1., 2., 3...): sin ambigüedad
        - Romano multi-caracter (II, III, IV...): siempre fracción
        - Letra no-romana (A, B, E, F, G, H...): siempre apartado si secuencia válida
        - Letra romana única (I, V, X, L, C, D, M): resolver por secuencia
          - I: puede iniciar secuencia (especial) o ser apartado después de H
          - Otras: requieren continuación de secuencia

        Args:
            texto: Linea de texto a analizar
            ultima_fraccion: Valor numérico de última fracción (1, 2, 3...)
            ultimo_apartado: Letra de último apartado ('A', 'B', 'C'...)

        Returns:
            (tipo, identificador, contenido_restante)
        """
        texto = texto.strip()
        LETRAS_ROMANAS = set('IVXLCDM')

        # 1. Inciso: a), b), c), etc. - sin ambigüedad
        match = re.match(r'^([a-z])\)\s*(.*)$', texto)
        if match:
            return ('inciso', match.group(1) + ')', match.group(2))

        # 2. Numeral: 1., 2., 3., etc. - sin ambigüedad
        match = re.match(r'^(\d+)\.\s+(.*)$', texto)
        if match:
            return ('numeral', match.group(1) + '.', match.group(2))

        # 3. Romano multi-caracter (II, III, IV, VI...): siempre fracción
        match = re.match(r'^([IVXLCDM]{2,})\.\s*(.*)$', texto)
        if match:
            valor = self._romano_a_entero(match.group(1))
            if valor:
                return ('fraccion', match.group(1), match.group(2))

        # 4. Letra única seguida de punto
        match = re.match(r'^([A-Z])\.\s*(.*)$', texto)
        if match:
            letra = match.group(1)
            contenido = match.group(2)
            letra_anterior = chr(ord(letra) - 1) if letra > 'A' else None

            # 4a. Letra NO romana (A, B, E, F, G, H, J, K, N, O, P, Q, R, S, T, U, W, Y, Z)
            if letra not in LETRAS_ROMANAS:
                es_apartado_valido = (
                    (ultimo_apartado is None and letra == 'A') or
                    (ultimo_apartado == letra_anterior)
                )
                if es_apartado_valido:
                    return ('apartado', letra + '.', contenido)
                return ('texto', None, texto)

            # 4b. Letra romana única (I, V, X, L, C, D, M) - resolver ambigüedad
            valor_romano = self._romano_a_entero(letra)

            # Verificar si es apartado válido (secuencia alfabética)
            es_apartado_valido = (ultimo_apartado == letra_anterior)

            # Verificar si es fracción válida
            if letra == 'I':
                # I es especial: SIEMPRE puede iniciar una nueva secuencia
                # Solo se descarta si es apartado válido (después de H)
                es_fraccion_valida = True
            else:
                # V, X, L, C, D, M: solo válidas como continuación
                es_fraccion_valida = (
                    ultima_fraccion is not None and
                    valor_romano == ultima_fraccion + 1
                )

            # Resolver
            if es_apartado_valido and not es_fraccion_valida:
                return ('apartado', letra + '.', contenido)
            if es_fraccion_valida and not es_apartado_valido:
                return ('fraccion', letra, contenido)
            if es_fraccion_valida and es_apartado_valido:
                # Ambos válidos: I después de H y sin fracción previa
                # Priorizar apartado (más restrictivo en secuencia)
                return ('apartado', letra + '.', contenido)
            # Ninguno válido: texto (ej: "artículo 84-E.")

        return ('texto', None, texto)

    def _romano_a_entero(self, romano: str) -> Optional[int]:
        """Convierte número romano a entero."""
        valores = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        if not romano or not all(c in valores for c in romano):
            return None

        resultado = 0
        prev = 0
        for c in reversed(romano):
            val = valores[c]
            if val < prev:
                resultado -= val
            else:
                resultado += val
            prev = val
        return resultado

    def _normalizar_espacios(self, texto: str) -> str:
        """Normaliza espacios multiples en texto."""
        return ' '.join(texto.split())


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def crear_extractor(codigo: str, config: dict) -> ExtractorBase:
    """
    Factory que crea el extractor apropiado segun configuracion.

    Args:
        codigo: Codigo de la ley
        config: Configuracion de la ley

    Returns:
        Instancia de ExtractorGeneral o ExtractorRMF
    """
    tipo = config.get("tipo_extractor", "general")

    if tipo == "rmf":
        from .rmf import ExtractorRMF
        return ExtractorRMF(codigo, config)
    else:
        from .general import ExtractorGeneral
        return ExtractorGeneral(codigo, config)
