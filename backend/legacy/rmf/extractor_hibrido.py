#!/usr/bin/env python3
"""
Extractor Híbrido de RMF - Arquitectura Multi-Fuente
=====================================================

Este extractor combina múltiples fuentes para obtener la mejor calidad
de extracción posible, evitando el overfitting a una sola herramienta.

Arquitectura:
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTRACTOR HÍBRIDO                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │   DOCX      │  │  PyMuPDF    │  │  pdftotext  │                │
│  │   (Word)    │  │   (PDF)     │  │  (poppler)  │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         ▼                ▼                ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  Títulos    │  │  Contenido  │  │ Validación  │                │
│  │  limpios    │  │  + fraccs   │  │  cruzada    │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         └────────────────┼────────────────┘                        │
│                          ▼                                         │
│                   ┌─────────────┐                                  │
│                   │   MERGER    │                                  │
│                   │  (combina)  │                                  │
│                   └──────┬──────┘                                  │
│                          │                                         │
│                          ▼                                         │
│                   ┌─────────────┐                                  │
│                   │  Resultado  │                                  │
│                   │   Final     │                                  │
│                   └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘

Fuentes y sus fortalezas:
- DOCX: Títulos perfectamente separados del contenido
- PyMuPDF: Extracción estructurada, parsing de fracciones
- pdftotext: Contenido inline, útil para validación

Autor: Claude
Fecha: 2025-12-27
"""

import re
import json
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

import fitz  # PyMuPDF


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class Fraccion:
    """Fracción de una regla (I., II., a), b), 1., 2.)"""
    tipo: str       # 'romano', 'letra', 'numero', 'parrafo'
    numero: str     # 'I', 'a', '1', etc.
    contenido: str
    nivel: int = 1
    hijos: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "contenido": self.contenido,
            "nivel": self.nivel,
            "hijos": [h.to_dict() for h in self.hijos]
        }


@dataclass
class Regla:
    """Regla completa con metadata de fuentes."""
    numero: str
    titulo: str
    contenido: str
    pagina: int
    fracciones: list[Fraccion] = field(default_factory=list)
    referencias: Optional[str] = None
    nota_reforma: Optional[str] = None
    # Metadata de fuentes
    titulo_fuente: str = "desconocido"  # 'docx', 'pymupdf', 'pdftotext'
    contenido_validado: bool = False     # Si se validó contra otra fuente

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "titulo": self.titulo,
            "contenido": self.contenido,
            "pagina": self.pagina,
            "fracciones": [f.to_dict() for f in self.fracciones],
            "referencias": self.referencias,
            "nota_reforma": self.nota_reforma,
            "metadata": {
                "titulo_fuente": self.titulo_fuente,
                "contenido_validado": self.contenido_validado
            }
        }


@dataclass
class ResultadoExtraccion:
    """Resultado de la extracción híbrida."""
    reglas: list[Regla]
    estructura: dict
    estadisticas: dict
    advertencias: list[str]

    def to_dict(self) -> dict:
        return {
            "estructura": self.estructura,
            "reglas": [r.to_dict() for r in self.reglas],
            "estadisticas": self.estadisticas,
            "advertencias": self.advertencias
        }


# =============================================================================
# EXTRACTOR DOCX - Títulos
# =============================================================================

class ExtractorDOCX:
    """
    Extrae títulos de reglas desde el archivo DOCX.

    El DOCX tiene una estructura clara donde el título aparece
    entre la nota de reforma y el número de regla:

        Regla X.Y.Z.
        - Reformada en la...
        TÍTULO DE LA REGLA
        X.Y.Z.
        Contenido...
    """

    def __init__(self, docx_path: Path):
        self.docx_path = docx_path
        self._texto: Optional[str] = None

    def _extraer_texto(self) -> str:
        """Extrae todo el texto del DOCX."""
        if self._texto is not None:
            return self._texto

        with zipfile.ZipFile(self.docx_path, 'r') as z:
            with z.open('word/document.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()

        texto_partes = []
        for elem in root.iter():
            if elem.text:
                texto_partes.append(elem.text)

        self._texto = " ".join(texto_partes)
        return self._texto

    def extraer_titulos(self) -> dict[str, str]:
        """
        Extrae los títulos de todas las reglas.

        La estructura en el DOCX es:
            Regla X.Y.Z. - Reformada... DOF el DD de MMMM de YYYY. TÍTULO X.Y.Z. Contenido

        El título está entre la fecha (YYYY.) y el número repetido.

        Returns:
            dict: {numero_regla: titulo}
        """
        texto = self._extraer_texto()
        titulos = {}

        # Patrón principal: captura todo entre "Regla X.Y.Z." y "X.Y.Z."
        patron = re.compile(
            r'Regla\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s*'  # "Regla X.Y.Z."
            r'(.{5,350}?)\s*'  # Todo lo intermedio (reforma + título)
            r'\1\.\s+'  # Mismo número repetido
            r'[A-Z]'  # Verificar que empieza contenido
        )

        for match in patron.finditer(texto):
            numero = match.group(1)
            bloque = match.group(2).strip()

            # Extraer título del bloque
            # Caso 1: Con nota de reforma "- Reformada... YYYY[.] TÍTULO"
            # El punto después del año es opcional
            match_reforma = re.search(r'\d{4}\.?\s+([A-ZÁÉÍÓÚÑ].+)$', bloque)
            if match_reforma:
                titulo = match_reforma.group(1).strip()
            else:
                # Caso 2: Sin nota de reforma, el bloque es el título
                titulo = re.sub(r'^[-\s]+', '', bloque)

            # Limpiar título - eliminar si empieza con "Reformada" o "Adicionada"
            if titulo.startswith('Reformada') or titulo.startswith('Adicionada'):
                # Buscar el título real después de la nota
                match_titulo = re.search(r'\d{4}\.?\s+([A-ZÁÉÍÓÚÑ].+)$', titulo)
                if match_titulo:
                    titulo = match_titulo.group(1).strip()
                else:
                    continue  # Saltar si no encontramos título

            titulo = re.sub(r'\s+', ' ', titulo)

            if titulo and len(titulo) > 2 and numero not in titulos:
                titulos[numero] = titulo

        # Patrón alternativo para reglas sin el formato estándar
        # Buscar "X.Y.Z. TÍTULO X.Y.Z. contenido" directamente
        patron_alt = re.compile(
            r'(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s+'
            r'([A-ZÁÉÍÓÚÑ][^0-9]{5,120}?)\s+'
            r'\1\.\s+'
            r'[A-Za-z]'
        )

        for match in patron_alt.finditer(texto):
            numero = match.group(1)
            if numero not in titulos:
                titulo = match.group(2).strip()
                titulo = re.sub(r'\s+', ' ', titulo)
                if titulo and len(titulo) > 2:
                    titulos[numero] = titulo

        return titulos


# =============================================================================
# EXTRACTOR PyMuPDF - Contenido y Fracciones
# =============================================================================

class ExtractorPyMuPDF:
    """
    Extrae contenido y fracciones usando PyMuPDF.

    PyMuPDF es bueno para:
    - Extraer texto manteniendo estructura de párrafos
    - Identificar números de regla standalone
    - Parsear fracciones (I., II., a), b))
    """

    # Patrones de limpieza
    PATRON_NOTA_PIE = re.compile(
        r'NOTA:\s*Este documento constituye una compilación.+?'
        r'Diario Oficial de la Federación\.',
        re.DOTALL
    )
    PATRON_PAGINA = re.compile(r'Página\s+\d+\s+de\s+\d+')
    PATRON_PAGE_MARKER = re.compile(r'\[PAGE:\d+\]')

    # Patrones de fracciones
    PATRON_ROMANO = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$', re.MULTILINE)
    PATRON_LETRA = re.compile(r'^([a-z])\)\s*$', re.MULTILINE)

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(str(pdf_path))
        self._texto_completo: Optional[str] = None
        self._cache_paginas: dict[int, str] = {}

    def _get_texto_completo(self) -> str:
        """Obtiene todo el texto del PDF con marcadores de página."""
        if self._texto_completo is not None:
            return self._texto_completo

        partes = []
        for i in range(len(self.doc)):
            partes.append(f"\n[PAGE:{i+1}]\n")
            partes.append(self.doc[i].get_text())

        self._texto_completo = ''.join(partes)
        return self._texto_completo

    def _limpiar_texto(self, texto: str) -> str:
        """Elimina notas de pie y marcadores."""
        texto = self.PATRON_NOTA_PIE.sub('', texto)
        texto = self.PATRON_PAGINA.sub('', texto)
        texto = self.PATRON_PAGE_MARKER.sub('', texto)
        return texto

    def _encontrar_fin_contenido(self, texto: str, pos_siguiente: int) -> int:
        """
        Encuentra dónde termina el contenido de una regla.

        Busca hacia atrás desde la siguiente regla para encontrar
        la última línea que termina con puntuación de contenido.
        """
        texto_antes = texto[:pos_siguiente]
        lineas = texto_antes.split('\n')

        # Patrones a ignorar (no son contenido)
        patrones_ignorar = [
            lambda l: not l,  # Vacía
            lambda l: l.startswith('[PAGE:'),
            lambda l: 'Página' in l and 'de' in l,
            lambda l: 'NOTA:' in l,
            lambda l: 'Diario Oficial' in l,
            lambda l: 'Contribuyente' in l,
            lambda l: 'Resolución Miscelánea' in l,
            lambda l: 'texto actualizado' in l,
            lambda l: re.match(r'^Título\s+\d+\.', l, re.I),
            lambda l: re.match(r'^Capítulo\s+\d+\.\d+', l, re.I),
            lambda l: re.match(r'^Sección\s+\d+\.\d+\.\d+', l, re.I),
            lambda l: l.startswith('-') and 'Reformada' in l,
            lambda l: l.startswith('Regla'),
        ]

        indice_contenido = len(lineas) - 1

        for i in range(len(lineas) - 1, max(len(lineas) - 50, -1), -1):
            linea = lineas[i].strip()

            # Verificar patrones a ignorar
            ignorar = False
            for patron in patrones_ignorar:
                if patron(linea):
                    ignorar = True
                    break
            if ignorar:
                continue

            # Línea que termina con puntuación = contenido real
            if linea and linea[-1] in '.;:)"':
                indice_contenido = i
                break

            # Línea corta capitalizada sin puntuación = probable título
            if len(linea) < 120 and linea and linea[0].isupper():
                continue

            # Otros casos = contenido
            indice_contenido = i
            break

        lineas_contenido = lineas[:indice_contenido + 1]
        return len('\n'.join(lineas_contenido))

    def _extraer_titulo(self, texto: str, pos_numero: int) -> Optional[str]:
        """
        Extrae el título de una regla buscando hacia atrás desde el número.

        El título típicamente aparece en las líneas anteriores al número,
        después de cualquier nota de reforma.
        """
        texto_antes = texto[max(0, pos_numero - 500):pos_numero]
        lineas = texto_antes.split('\n')

        # Patrones a ignorar
        patrones_ignorar = [
            lambda l: not l,
            lambda l: l.startswith('[PAGE:'),
            lambda l: 'Página' in l and 'de' in l,
            lambda l: l.startswith('Regla'),
            lambda l: l.startswith('-') and ('Reformada' in l or 'Adicionada' in l),
            lambda l: 'NOTA:' in l,
            lambda l: 'Diario Oficial' in l,
            lambda l: 'Contribuyente' in l,
            lambda l: 'sustentar legalmente' in l,
            lambda l: re.match(r'^\d+\.\d+', l),  # Otro número
            lambda l: re.match(r'^(CFF|LISR|LIVA|LIEPS|RMF)', l),  # Referencias
        ]

        for linea in reversed(lineas):
            linea = linea.strip()

            # Verificar si debe ignorarse
            ignorar = False
            for patron in patrones_ignorar:
                if patron(linea):
                    ignorar = True
                    break
            if ignorar:
                continue

            # Si la línea tiene más de 5 caracteres y empieza con mayúscula, es candidato
            if len(linea) > 5 and linea[0].isupper():
                return linea

        return None

    def _parsear_fracciones(self, texto: str) -> tuple[list[Fraccion], str]:
        """Parsea fracciones y retorna contenido limpio."""
        fracciones = []
        lineas = texto.split('\n')
        primera_fraccion_idx = None

        i = 0
        while i < len(lineas):
            linea = lineas[i].strip()

            # Fracción romana
            match = self.PATRON_ROMANO.match(linea)
            if match:
                if primera_fraccion_idx is None:
                    primera_fraccion_idx = i

                numero = match.group(1)
                contenido_lines = []
                i += 1
                while i < len(lineas):
                    next_line = lineas[i].strip()
                    if self.PATRON_ROMANO.match(next_line):
                        break
                    if self.PATRON_LETRA.match(next_line):
                        break
                    if re.match(r'^(CFF|LISR|LIVA|LIEPS|LFD)', next_line):
                        break
                    contenido_lines.append(next_line)
                    i += 1

                contenido = ' '.join(contenido_lines).strip()
                if contenido:
                    fracciones.append(Fraccion(
                        tipo='romano',
                        numero=numero,
                        contenido=contenido,
                        nivel=1
                    ))
                continue

            # Inciso letra
            match = self.PATRON_LETRA.match(linea)
            if match:
                if primera_fraccion_idx is None:
                    primera_fraccion_idx = i

                numero = match.group(1)
                contenido_lines = []
                i += 1
                while i < len(lineas):
                    next_line = lineas[i].strip()
                    if self.PATRON_LETRA.match(next_line):
                        break
                    if self.PATRON_ROMANO.match(next_line):
                        break
                    if re.match(r'^(CFF|LISR|LIVA|LIEPS|LFD)', next_line):
                        break
                    contenido_lines.append(next_line)
                    i += 1

                contenido = ' '.join(contenido_lines).strip()
                if contenido:
                    fracciones.append(Fraccion(
                        tipo='letra',
                        numero=numero,
                        contenido=contenido,
                        nivel=2
                    ))
                continue

            i += 1

        # Contenido limpio = solo antes de primera fracción
        if fracciones and primera_fraccion_idx is not None:
            contenido_limpio = '\n'.join(lineas[:primera_fraccion_idx]).strip()
        else:
            contenido_limpio = texto

        return fracciones, contenido_limpio

    def extraer_reglas(self) -> dict[str, dict]:
        """
        Extrae todas las reglas con contenido y fracciones.

        Returns:
            dict: {numero: {contenido, fracciones, pagina, referencias}}
        """
        texto = self._get_texto_completo()
        reglas = {}

        # Encontrar todos los números de regla standalone
        patron_numero = re.compile(r'^(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s*$', re.MULTILINE)
        matches = list(patron_numero.finditer(texto))

        for i, match in enumerate(matches):
            numero = match.group(1)
            pos_inicio = match.end()

            # Encontrar posición del siguiente número
            if i + 1 < len(matches):
                pos_siguiente = matches[i + 1].start()
            else:
                pos_siguiente = len(texto)

            # Encontrar fin real del contenido
            fin_contenido = self._encontrar_fin_contenido(
                texto[pos_inicio:pos_siguiente],
                len(texto[pos_inicio:pos_siguiente])
            )

            contenido_raw = texto[pos_inicio:pos_inicio + fin_contenido]
            contenido_raw = self._limpiar_texto(contenido_raw)

            # Separar referencias
            referencias = None
            lineas = contenido_raw.split('\n')
            contenido_lineas = []
            refs_encontradas = []
            en_refs = False

            for linea in reversed(lineas):
                linea_strip = linea.strip()
                if not linea_strip:
                    if not en_refs:
                        contenido_lineas.insert(0, linea)
                    continue

                if re.match(r'^(CFF|LISR|LIVA|LIEPS|LIC|LFD|RCFF|RMF|RISAT)', linea_strip):
                    refs_encontradas.insert(0, linea_strip)
                    en_refs = True
                elif en_refs and len(linea_strip) < 40 and re.match(r'^[\d\-,\s\.;o°]+$', linea_strip):
                    refs_encontradas.insert(0, linea_strip)
                else:
                    contenido_lineas.insert(0, linea)
                    en_refs = False

            contenido = '\n'.join(contenido_lineas).strip()
            if refs_encontradas:
                referencias = ' '.join(refs_encontradas)

            # Parsear fracciones
            fracciones, contenido_limpio = self._parsear_fracciones(contenido)

            # Calcular página aproximada
            texto_antes = texto[:match.start()]
            pagina = texto_antes.count('[PAGE:') + 1

            # Extraer título buscando hacia atrás desde el número
            titulo = self._extraer_titulo(texto, match.start())

            reglas[numero] = {
                'contenido': contenido_limpio,
                'fracciones': fracciones,
                'pagina': pagina,
                'referencias': referencias,
                'titulo': titulo
            }

        return reglas

    def extraer_estructura(self) -> dict:
        """Extrae la estructura de títulos, capítulos, etc."""
        texto = self._get_texto_completo()

        estructura = {
            'titulos': [],
            'capitulos': [],
            'secciones': [],
            'subsecciones': []
        }

        # Patrones
        patrones = {
            'titulos': (r'Título\s+(\d{1,2})\.\s+(.+?)(?:\n|$)', 'titulo'),
            'capitulos': (r'Capítulo\s+(\d+\.\d+)\.?\s+(.+?)(?:\n|$)', 'capitulo'),
            'secciones': (r'Sección\s+(\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)', 'seccion'),
            'subsecciones': (r'Subsección\s+(\d+\.\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)', 'subseccion'),
        }

        for key, (patron_str, tipo) in patrones.items():
            patron = re.compile(patron_str, re.IGNORECASE)
            seen = set()
            for match in patron.finditer(texto):
                num = match.group(1)
                nombre = match.group(2).strip()
                if num not in seen:
                    seen.add(num)
                    estructura[key].append({
                        'tipo': tipo,
                        'numero': num,
                        'nombre': nombre
                    })

        return estructura

    def close(self):
        self.doc.close()


# =============================================================================
# VALIDADOR pdftotext
# =============================================================================

class ValidadorPdftotext:
    """
    Usa pdftotext (poppler) para validar la extracción.

    pdftotext extrae el contenido inline con el número de regla,
    lo que permite verificar que no se perdió contenido.
    """

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self._texto: Optional[str] = None

    def _extraer_texto(self) -> str:
        """Ejecuta pdftotext y obtiene el resultado."""
        if self._texto is not None:
            return self._texto

        result = subprocess.run(
            ['pdftotext', '-layout', str(self.pdf_path), '-'],
            capture_output=True,
            text=True
        )
        self._texto = result.stdout
        return self._texto

    def obtener_contenido_regla(self, numero: str) -> Optional[str]:
        """Obtiene el contenido de una regla específica."""
        texto = self._extraer_texto()

        # En pdftotext, el formato es: "X.Y.Z.    Contenido..."
        patron = re.compile(
            rf'{re.escape(numero)}\.\s+(.+?)(?=\d{{1,2}}\.\d{{1,2}}(?:\.\d{{1,3}})?\.\s|\Z)',
            re.DOTALL
        )

        match = patron.search(texto)
        if match:
            return match.group(1).strip()
        return None

    def validar_contenido(self, numero: str, contenido_pymupdf: str) -> tuple[bool, str]:
        """
        Valida que el contenido de PyMuPDF coincida con pdftotext.

        Returns:
            tuple: (es_valido, mensaje)
        """
        contenido_pdftotext = self.obtener_contenido_regla(numero)

        if contenido_pdftotext is None:
            return False, "No encontrada en pdftotext"

        # Normalizar para comparación
        def normalizar(texto: str) -> str:
            texto = re.sub(r'\s+', ' ', texto)
            texto = texto.lower()
            return texto[:500]  # Comparar primeros 500 chars

        norm_pymupdf = normalizar(contenido_pymupdf)
        norm_pdftotext = normalizar(contenido_pdftotext)

        # Verificar similitud
        if norm_pymupdf[:100] == norm_pdftotext[:100]:
            return True, "OK"

        # Buscar substring común
        if norm_pymupdf[:50] in norm_pdftotext or norm_pdftotext[:50] in norm_pymupdf:
            return True, "Parcialmente coincide"

        return False, "Contenido difiere"


# =============================================================================
# MERGER - Combina las fuentes
# =============================================================================

class MergerHibrido:
    """
    Combina los resultados de las diferentes fuentes.

    Prioridades:
    1. Títulos: DOCX > PyMuPDF
    2. Contenido: PyMuPDF (con validación de pdftotext)
    3. Fracciones: PyMuPDF
    4. Estructura: PyMuPDF
    """

    def __init__(
        self,
        titulos_docx: dict[str, str],
        reglas_pymupdf: dict[str, dict],
        estructura_pymupdf: dict,
        validador: ValidadorPdftotext
    ):
        self.titulos_docx = titulos_docx
        self.reglas_pymupdf = reglas_pymupdf
        self.estructura = estructura_pymupdf
        self.validador = validador
        self.advertencias: list[str] = []

    def merge(self) -> list[Regla]:
        """Combina todas las fuentes en reglas finales."""
        reglas = []

        for numero, datos in self.reglas_pymupdf.items():
            # Título: preferir DOCX, fallback a PyMuPDF, finalmente generar
            if numero in self.titulos_docx:
                titulo = self.titulos_docx[numero]
                titulo_fuente = "docx"
            elif datos.get('titulo'):
                titulo = datos['titulo']
                titulo_fuente = "pymupdf"
            else:
                # Generar título por defecto
                titulo = f"Regla {numero}"
                titulo_fuente = "generado"
                self.advertencias.append(f"Regla {numero}: título no encontrado")

            # Validar contenido
            es_valido, msg = self.validador.validar_contenido(numero, datos['contenido'])
            if not es_valido:
                self.advertencias.append(f"Regla {numero}: validación pdftotext - {msg}")

            regla = Regla(
                numero=numero,
                titulo=titulo,
                contenido=datos['contenido'],
                pagina=datos['pagina'],
                fracciones=datos['fracciones'],
                referencias=datos['referencias'],
                titulo_fuente=titulo_fuente,
                contenido_validado=es_valido
            )
            reglas.append(regla)

        # Ordenar por número
        reglas.sort(key=lambda r: [int(p) for p in r.numero.split('.')])

        return reglas


# =============================================================================
# EXTRACTOR HÍBRIDO PRINCIPAL
# =============================================================================

class ExtractorHibrido:
    """
    Extractor principal que coordina todas las fuentes.

    Uso:
        extractor = ExtractorHibrido(pdf_path, docx_path)
        resultado = extractor.extraer()
        resultado.guardar_json('output.json')
    """

    def __init__(self, pdf_path: Path, docx_path: Path):
        self.pdf_path = Path(pdf_path)
        self.docx_path = Path(docx_path)

    def extraer(self) -> ResultadoExtraccion:
        """Ejecuta la extracción híbrida completa."""
        print("=" * 70)
        print("EXTRACTOR HÍBRIDO RMF")
        print("=" * 70)

        # 1. Extraer títulos del DOCX
        print("\n1. Extrayendo títulos del DOCX...")
        extractor_docx = ExtractorDOCX(self.docx_path)
        titulos_docx = extractor_docx.extraer_titulos()
        print(f"   {len(titulos_docx)} títulos encontrados")

        # 2. Extraer contenido con PyMuPDF
        print("\n2. Extrayendo contenido con PyMuPDF...")
        extractor_pymupdf = ExtractorPyMuPDF(self.pdf_path)
        reglas_pymupdf = extractor_pymupdf.extraer_reglas()
        estructura = extractor_pymupdf.extraer_estructura()
        print(f"   {len(reglas_pymupdf)} reglas encontradas")
        print(f"   {len(estructura['titulos'])} títulos de estructura")
        print(f"   {len(estructura['capitulos'])} capítulos")

        # 3. Configurar validador
        print("\n3. Configurando validador pdftotext...")
        validador = ValidadorPdftotext(self.pdf_path)

        # 4. Merge
        print("\n4. Combinando fuentes...")
        merger = MergerHibrido(titulos_docx, reglas_pymupdf, estructura, validador)
        reglas = merger.merge()
        advertencias = merger.advertencias

        # 5. Validación y corrección de datos
        print("\n5. Validando y corrigiendo datos...")
        from validador_datos import ValidadorReglas
        validador_datos = ValidadorReglas(corregir_auto=True)

        reglas_validadas = []
        for regla in reglas:
            regla_dict = regla.to_dict()
            regla_limpia, resultado_val = validador_datos.validar_y_corregir(regla_dict)

            # Reconstruir objeto Regla con datos limpios
            def dict_to_fraccion(f):
                if isinstance(f, Fraccion):
                    return f
                return Fraccion(
                    tipo=f.get('tipo', 'fraccion'),
                    numero=f.get('numero', ''),
                    contenido=f.get('contenido', ''),
                    nivel=f.get('nivel', 1),
                    hijos=[dict_to_fraccion(h) for h in f.get('hijos', [])]
                )

            regla_nueva = Regla(
                numero=regla_limpia['numero'],
                titulo=regla_limpia['titulo'],
                contenido=regla_limpia['contenido'],
                pagina=regla_limpia['pagina'],
                fracciones=[dict_to_fraccion(f) for f in regla_limpia.get('fracciones', [])],
                referencias=regla_limpia.get('referencias'),
                nota_reforma=regla_limpia.get('nota_reforma'),
                titulo_fuente=regla_limpia.get('metadata', {}).get('titulo_fuente', 'desconocido'),
                contenido_validado=regla_limpia.get('metadata', {}).get('contenido_validado', False)
            )
            reglas_validadas.append(regla_nueva)

            # Añadir problemas a advertencias
            for p in resultado_val.problemas:
                if not p.corregido:
                    advertencias.append(f"Regla {regla.numero}: {p.severidad.value} - {p.tipo}")

        reglas = reglas_validadas
        print(f"   {validador_datos.resumen()}")

        # 6. Estadísticas
        print("\n6. Calculando estadísticas...")

        titulos_docx = sum(1 for r in reglas if r.titulo_fuente == "docx")
        titulos_pymupdf = sum(1 for r in reglas if r.titulo_fuente == "pymupdf")
        titulos_generados = sum(1 for r in reglas if r.titulo_fuente == "generado")
        contenido_validado = sum(1 for r in reglas if r.contenido_validado)
        total_fracciones = sum(len(r.fracciones) for r in reglas)

        estadisticas = {
            "total_reglas": len(reglas),
            "titulos": {
                "docx": titulos_docx,
                "pymupdf": titulos_pymupdf,
                "generados": titulos_generados
            },
            "contenido_validado": contenido_validado,
            "contenido_no_validado": len(reglas) - contenido_validado,
            "total_fracciones": total_fracciones,
            "advertencias": len(advertencias)
        }

        # Cerrar recursos
        extractor_pymupdf.close()

        print("\n" + "=" * 70)
        print("RESUMEN")
        print("=" * 70)
        for key, value in estadisticas.items():
            print(f"  {key}: {value}")

        if advertencias:
            print(f"\nPrimeras 10 advertencias:")
            for adv in advertencias[:10]:
                print(f"  - {adv}")

        return ResultadoExtraccion(
            reglas=reglas,
            estructura=estructura,
            estadisticas=estadisticas,
            advertencias=advertencias
        )

    def guardar_json(self, resultado: ResultadoExtraccion, output_path: Path) -> None:
        """Guarda el resultado en JSON."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(resultado.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\nGuardado en: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Punto de entrada principal."""
    base_dir = Path(__file__).parent.parent.parent

    pdf_path = base_dir / "doc/rmf/rmf_2025_compilada.pdf"
    docx_path = base_dir / "doc/rmf/rmf_2025_full_converted.docx"
    output_path = base_dir / "doc/rmf/rmf_hibrido.json"

    if not pdf_path.exists():
        print(f"Error: No se encontró el PDF en {pdf_path}")
        return 1

    if not docx_path.exists():
        print(f"Error: No se encontró el DOCX en {docx_path}")
        return 1

    extractor = ExtractorHibrido(pdf_path, docx_path)
    resultado = extractor.extraer()
    extractor.guardar_json(resultado, output_path)

    return 0


if __name__ == "__main__":
    exit(main())
