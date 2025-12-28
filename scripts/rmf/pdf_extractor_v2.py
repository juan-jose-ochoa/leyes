"""
Extractor mejorado de RMF desde PDF.

Fuente única de verdad: Extrae TODO del PDF oficial.
- Estructura (títulos, capítulos, secciones, subsecciones)
- Reglas con títulos correctos
- Fracciones parseadas (I., II., a), b), 1., 2.)
- Referencias legales

Autor: Claude
Fecha: 2025-12-27
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

import fitz  # PyMuPDF


class TipoFraccion(str, Enum):
    """Tipos de fracción."""
    ROMANO = "romano"      # I., II., III., IV., ...
    LETRA = "letra"        # a), b), c), ...
    NUMERO = "numero"      # 1., 2., 3., ...
    PARRAFO = "parrafo"    # Párrafos sin numeración


@dataclass
class Fraccion:
    """Fracción de una regla."""
    tipo: str
    numero: str
    contenido: str
    nivel: int = 1
    hijos: list["Fraccion"] = field(default_factory=list)

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
    """Regla completa de la RMF."""
    numero: str
    titulo: str
    contenido: str
    pagina: int
    fracciones: list[Fraccion] = field(default_factory=list)
    referencias: Optional[str] = None
    nota_reforma: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "titulo": self.titulo,
            "contenido": self.contenido,
            "pagina": self.pagina,
            "fracciones": [f.to_dict() for f in self.fracciones],
            "referencias": self.referencias,
            "nota_reforma": self.nota_reforma
        }


@dataclass
class Division:
    """División estructural (título, capítulo, sección, subsección)."""
    tipo: str
    numero: str
    nombre: str
    pagina: Optional[int] = None


@dataclass
class IndiceRMF:
    """Índice completo de la RMF."""
    titulos: list[Division] = field(default_factory=list)
    capitulos: list[Division] = field(default_factory=list)
    secciones: list[Division] = field(default_factory=list)
    subsecciones: list[Division] = field(default_factory=list)
    reglas: list[Regla] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "estructura": {
                "titulos": [asdict(t) for t in self.titulos],
                "capitulos": [asdict(c) for c in self.capitulos],
                "secciones": [asdict(s) for s in self.secciones],
                "subsecciones": [asdict(ss) for ss in self.subsecciones],
            },
            "reglas": [r.to_dict() for r in self.reglas],
            "stats": {
                "total_titulos": len(self.titulos),
                "total_capitulos": len(self.capitulos),
                "total_secciones": len(self.secciones),
                "total_subsecciones": len(self.subsecciones),
                "total_reglas": len(self.reglas),
            }
        }


class PDFExtractorV2:
    """Extractor mejorado del PDF de RMF."""

    # Patrones para estructura
    PATRON_TITULO = re.compile(r'Título\s+(\d{1,2})\.\s+(.+?)(?:\n|$)', re.IGNORECASE)
    PATRON_CAPITULO = re.compile(r'Capítulo\s+(\d+\.\d+)\.?\s+(.+?)(?:\n|$)', re.IGNORECASE)
    PATRON_SECCION = re.compile(r'Sección\s+(\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)', re.IGNORECASE)
    PATRON_SUBSECCION = re.compile(r'Subsección\s+(\d+\.\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)', re.IGNORECASE)

    # Patrones para reglas
    # "Regla X.Y." o "Regla X.Y.Z." - encabezado formal
    PATRON_REGLA_HEADER = re.compile(r'Regla\s+(\d+\.\d+(?:\.\d+)?)\.')

    # Línea con solo número: "X.Y." o "X.Y.Z." seguido de contenido
    PATRON_REGLA_NUMERO = re.compile(r'^(\d+\.\d+(?:\.\d+)?)\.\s*$', re.MULTILINE)

    # Nota de reforma: "- Reformada en la..."
    PATRON_REFORMA = re.compile(r'^-\s*(Reformada|Adicionada|Derogada).+?(?:DOF.+?\d{4}\.?)$', re.MULTILINE | re.IGNORECASE)

    # Patrones para fracciones
    PATRON_ROMANO = re.compile(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$', re.MULTILINE)
    PATRON_LETRA = re.compile(r'^([a-z])\)\s*$', re.MULTILINE)
    PATRON_NUMERO_FRAC = re.compile(r'^(\d+)\.\s*$', re.MULTILINE)

    # Patrón de referencias al final de regla
    PATRON_REFERENCIAS = re.compile(
        r'^((?:CFF|LISR|LIVA|LIEPS|LIC|LFD|RCFF|RLISR|RMF|Decreto|RISAT|Ley)[\s\d\-,\.;A-Za-z]+)$',
        re.MULTILINE
    )

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(str(self.pdf_path))
        self._cache: dict[int, str] = {}
        self._texto_completo: Optional[str] = None

    def _get_page_text(self, page_num: int) -> str:
        """Obtiene texto de una página con caché."""
        if page_num not in self._cache:
            if 0 <= page_num < len(self.doc):
                self._cache[page_num] = self.doc[page_num].get_text()
            else:
                return ""
        return self._cache[page_num]

    def _get_full_text(self) -> str:
        """Obtiene todo el texto del PDF."""
        if self._texto_completo is None:
            partes = []
            for i in range(len(self.doc)):
                partes.append(f"\n[PAGE:{i+1}]\n")
                partes.append(self._get_page_text(i))
            self._texto_completo = ''.join(partes)
        return self._texto_completo

    def _limpiar_nota(self, texto: str) -> str:
        """Elimina notas de pie de página y marcas de agua."""
        # Eliminar la nota estándar de compilación
        texto = re.sub(
            r'NOTA:\s*Este documento constituye una compilación.+?Diario Oficial de la Federación\.',
            '',
            texto,
            flags=re.DOTALL
        )
        # Eliminar "Página X de Y"
        texto = re.sub(r'Página\s+\d+\s+de\s+\d+', '', texto)
        return texto

    def extraer_estructura(self) -> tuple[list[Division], list[Division], list[Division], list[Division]]:
        """Extrae la estructura del índice de las primeras páginas."""
        titulos = []
        capitulos = []
        secciones = []
        subsecciones = []

        # El índice está en páginas 2-7
        texto_indice = ""
        for page_num in range(1, 8):
            texto_indice += self._get_page_text(page_num) + "\n"

        # También buscar en todo el documento para capturar encabezados
        texto_completo = self._get_full_text()

        # Extraer títulos
        seen = set()
        for match in self.PATRON_TITULO.finditer(texto_completo):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen and int(num) <= 12:
                seen.add(num)
                titulos.append(Division(tipo='titulo', numero=num, nombre=nombre))

        # Ordenar títulos
        titulos.sort(key=lambda t: int(t.numero))

        # Extraer capítulos
        seen = set()
        for match in self.PATRON_CAPITULO.finditer(texto_completo):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen:
                seen.add(num)
                capitulos.append(Division(tipo='capitulo', numero=num, nombre=nombre))

        # Extraer secciones
        seen = set()
        for match in self.PATRON_SECCION.finditer(texto_completo):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen:
                seen.add(num)
                secciones.append(Division(tipo='seccion', numero=num, nombre=nombre))

        # Extraer subsecciones
        seen = set()
        for match in self.PATRON_SUBSECCION.finditer(texto_completo):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen:
                seen.add(num)
                subsecciones.append(Division(tipo='subseccion', numero=num, nombre=nombre))

        return titulos, capitulos, secciones, subsecciones

    def _parse_fracciones(self, texto: str) -> tuple[list[Fraccion], str]:
        """Parsea las fracciones y retorna contenido limpio.

        Returns:
            tuple: (fracciones, contenido_limpio)
            - Si hay fracciones, contenido_limpio es el texto ANTES de la primera fracción
            - Si no hay fracciones, contenido_limpio es el texto original
        """
        fracciones = []
        lineas = texto.split('\n')

        # Encontrar dónde empieza la primera fracción
        primera_fraccion_idx = None

        i = 0
        while i < len(lineas):
            linea = lineas[i].strip()

            # Detectar fracción romana (I., II., III., ...)
            match_romano = re.match(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$', linea)
            if match_romano:
                if primera_fraccion_idx is None:
                    primera_fraccion_idx = i

                numero = match_romano.group(1)
                # El contenido está en las siguientes líneas hasta la próxima fracción
                contenido_lines = []
                i += 1
                while i < len(lineas):
                    next_line = lineas[i].strip()
                    # Parar si encontramos otra fracción o referencias
                    if re.match(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$', next_line):
                        break
                    if re.match(r'^[a-z]\)\s*$', next_line):
                        break
                    if re.match(r'^(CFF|LISR|LIVA|LIEPS|LFD)', next_line):
                        break
                    contenido_lines.append(next_line)
                    i += 1

                contenido = ' '.join(contenido_lines).strip()
                if contenido:
                    fracciones.append(Fraccion(
                        tipo=TipoFraccion.ROMANO.value,
                        numero=numero,
                        contenido=contenido,
                        nivel=1
                    ))
                continue

            # Detectar inciso letra (a), b), c), ...)
            match_letra = re.match(r'^([a-z])\)\s*$', linea)
            if match_letra:
                if primera_fraccion_idx is None:
                    primera_fraccion_idx = i

                numero = match_letra.group(1)
                contenido_lines = []
                i += 1
                while i < len(lineas):
                    next_line = lineas[i].strip()
                    if re.match(r'^[a-z]\)\s*$', next_line):
                        break
                    if re.match(r'^(X{0,3}(?:IX|IV|V?I{0,3}))\.\s*$', next_line):
                        break
                    if re.match(r'^\d+\.\s*$', next_line):
                        break
                    if re.match(r'^(CFF|LISR|LIVA|LIEPS|LFD)', next_line):
                        break
                    contenido_lines.append(next_line)
                    i += 1

                contenido = ' '.join(contenido_lines).strip()
                if contenido:
                    fracciones.append(Fraccion(
                        tipo=TipoFraccion.LETRA.value,
                        numero=numero,
                        contenido=contenido,
                        nivel=2
                    ))
                continue

            i += 1

        # Generar contenido limpio (sin fracciones)
        if fracciones and primera_fraccion_idx is not None:
            # Solo conservar el texto antes de la primera fracción
            contenido_limpio = '\n'.join(lineas[:primera_fraccion_idx]).strip()
        else:
            contenido_limpio = texto

        return fracciones, contenido_limpio

    def _extraer_regla(self, numero: str, texto_pagina: str, pagina: int,
                       siguiente_numero: Optional[str] = None) -> Optional[Regla]:
        """Extrae una regla completa del texto."""

        # Buscar el encabezado "Regla X.Y."
        patron_header = re.compile(rf'Regla\s+{re.escape(numero)}\.')
        match_header = patron_header.search(texto_pagina)

        if not match_header:
            return None

        pos_header = match_header.end()

        # Buscar nota de reforma después del header
        texto_despues_header = texto_pagina[pos_header:]
        nota_reforma = None
        match_reforma = self.PATRON_REFORMA.search(texto_despues_header[:500])
        if match_reforma:
            nota_reforma = match_reforma.group(0).strip()

        # Buscar el título: está entre la nota de reforma (o header) y el número standalone
        patron_num_standalone = re.compile(rf'^{re.escape(numero)}\.\s*$', re.MULTILINE)
        match_num = patron_num_standalone.search(texto_despues_header)

        if not match_num:
            return None

        # El título está entre la reforma (o header) y el número standalone
        pos_inicio_busqueda = match_reforma.end() if match_reforma else 0
        texto_entre = texto_despues_header[pos_inicio_busqueda:match_num.start()]

        # Limpiar y extraer título
        lineas_entre = [l.strip() for l in texto_entre.split('\n') if l.strip()]
        titulo = None
        for linea in lineas_entre:
            # Ignorar líneas que no son títulos
            if linea.startswith('-'):
                continue
            if 'Página' in linea:
                continue
            if re.match(r'^(CFF|LISR|LIVA|LIEPS|RMF|DOF)', linea):
                continue
            if len(linea) < 3:
                continue
            titulo = linea
            break

        if not titulo:
            titulo = f"Regla {numero}"

        # Extraer contenido después del número standalone
        pos_contenido = match_num.end()
        texto_contenido = texto_despues_header[pos_contenido:]

        # Buscar el final del contenido (siguiente regla o fin)
        fin_contenido = len(texto_contenido)

        # Buscar siguiente "Regla X.Y."
        if siguiente_numero:
            patron_siguiente = re.compile(rf'Regla\s+{re.escape(siguiente_numero)}\.')
            match_sig = patron_siguiente.search(texto_contenido)
            if match_sig:
                fin_contenido = match_sig.start()
        else:
            # Buscar cualquier "Regla X.Y."
            match_cualquier = re.search(r'Regla\s+\d+\.\d+(?:\.\d+)?\.', texto_contenido)
            if match_cualquier:
                fin_contenido = match_cualquier.start()

        contenido_raw = texto_contenido[:fin_contenido]

        # Separar referencias del contenido
        referencias = None
        lineas = contenido_raw.split('\n')
        contenido_lineas = []
        referencias_lineas = []

        for linea in lineas:
            linea_strip = linea.strip()
            # Detectar línea de referencias
            if re.match(r'^(CFF|LISR|LIVA|LIEPS|LIC|LFD|RCFF|RLISR|RMF|Decreto|RISAT)', linea_strip):
                referencias_lineas.append(linea_strip)
            elif referencias_lineas and re.match(r'^[\d\-,\s\.;]+$', linea_strip):
                referencias_lineas.append(linea_strip)
            else:
                contenido_lineas.append(linea)

        contenido = '\n'.join(contenido_lineas).strip()
        contenido = self._limpiar_nota(contenido)

        if referencias_lineas:
            referencias = ' '.join(referencias_lineas)

        # Parsear fracciones y limpiar contenido
        fracciones, contenido_limpio = self._parse_fracciones(contenido)

        return Regla(
            numero=numero,
            titulo=titulo,
            contenido=contenido_limpio,
            pagina=pagina,
            fracciones=fracciones,
            referencias=referencias,
            nota_reforma=nota_reforma
        )

    def extraer_todas_reglas(self) -> list[Regla]:
        """Extrae todas las reglas del PDF."""
        reglas = []

        # Buscar números de regla standalone en cada página
        # Patrones:
        # - Dos niveles: X.Y. (solo para títulos 1, 6, 7, 8, 9, 10)
        # - Tres niveles: X.Y.Z. (para el resto)
        patron_dos_niveles = re.compile(r'^(\d{1,2})\.(\d{1,2})\.\s*$', re.MULTILINE)
        patron_tres_niveles = re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{1,3})\.\s*$', re.MULTILINE)

        # Títulos que usan reglas de dos niveles (sin capítulos)
        titulos_dos_niveles = {'1', '6', '7', '8', '9', '10'}

        reglas_info = {}

        print("  Escaneando páginas...")
        for page_num in range(len(self.doc)):
            text = self._get_page_text(page_num)
            lines = text.split('\n')

            for i, line in enumerate(lines):
                line_strip = line.strip()

                # Buscar patrón de dos niveles
                match_2 = patron_dos_niveles.match(line_strip)
                if match_2:
                    titulo_num = match_2.group(1)
                    if titulo_num in titulos_dos_niveles:
                        numero = f"{match_2.group(1)}.{match_2.group(2)}"
                        if numero not in reglas_info:
                            reglas_info[numero] = {
                                'pagina': page_num + 1,
                                'linea': i,
                                'niveles': 2
                            }
                    continue

                # Buscar patrón de tres niveles
                match_3 = patron_tres_niveles.match(line_strip)
                if match_3:
                    numero = f"{match_3.group(1)}.{match_3.group(2)}.{match_3.group(3)}"
                    if numero not in reglas_info:
                        reglas_info[numero] = {
                            'pagina': page_num + 1,
                            'linea': i,
                            'niveles': 3
                        }

        # Ordenar números
        numeros_ordenados = sorted(
            reglas_info.keys(),
            key=lambda n: tuple(int(p) for p in n.split('.'))
        )

        print(f"  Encontrados {len(numeros_ordenados)} números de regla únicos")

        # Extraer cada regla
        for i, numero in enumerate(numeros_ordenados):
            info = reglas_info[numero]
            pagina = info['pagina']

            # Siguiente número para delimitar
            siguiente = numeros_ordenados[i + 1] if i + 1 < len(numeros_ordenados) else None

            regla = self._extraer_regla_v2(numero, pagina, siguiente)

            if regla:
                reglas.append(regla)
                if (i + 1) % 100 == 0:
                    print(f"  Procesadas {i + 1}/{len(numeros_ordenados)} reglas...")
            else:
                print(f"  ADVERTENCIA: No se pudo extraer regla {numero}")

        return reglas

    def _extraer_regla_v2(self, numero: str, pagina: int,
                         siguiente_numero: Optional[str] = None) -> Optional[Regla]:
        """Extrae una regla usando el patrón de número standalone."""

        # Obtener texto de esta página y siguientes
        texto_paginas = ""
        for p in range(pagina - 1, min(pagina + 4, len(self.doc))):
            texto_paginas += f"\n[PAGE:{p+1}]\n" + self._get_page_text(p)

        # Buscar el número standalone
        patron_num = re.compile(rf'^{re.escape(numero)}\.\s*$', re.MULTILINE)
        match_num = patron_num.search(texto_paginas)

        if not match_num:
            return None

        pos_num = match_num.end()

        # Buscar título: líneas ANTES del número
        texto_antes = texto_paginas[:match_num.start()]
        lineas_antes = texto_antes.split('\n')

        titulo = None
        nota_reforma = None

        # Buscar hacia atrás por el título
        for j in range(len(lineas_antes) - 1, max(len(lineas_antes) - 15, -1), -1):
            linea = lineas_antes[j].strip()
            if not linea:
                continue
            # Ignorar líneas que no son títulos
            if linea.startswith('[PAGE:'):
                continue
            if 'Página' in linea and 'de' in linea:
                continue
            if re.match(r'^\d+\.\d+', linea):  # Es otro número
                break
            if linea.startswith('-') and ('Reformada' in linea or 'Adicionada' in linea):
                nota_reforma = linea
                continue
            if linea.startswith('Regla'):
                continue
            if re.match(r'^(CFF|LISR|LIVA|LIEPS|LFD|RMF|DOF|RCFF)', linea):
                continue
            if 'NOTA:' in linea or 'Este documento constituye' in linea:
                continue
            # Filtrar fragmentos de NOTA de pie de página
            if 'Contribuyente' in linea:
                continue
            if 'Diario Oficial' in linea:
                continue
            if 'sustentar legalmente' in linea:
                continue
            if 'Para' in linea and len(linea) < 50:  # "Para sustentar..."
                continue
            if linea.startswith('del ') and len(linea) < 30:  # "del Contribuyente..."
                continue
            if len(linea) < 3:
                continue
            # Parece un título válido
            titulo = linea
            break

        if not titulo:
            titulo = f"Regla {numero}"

        # Buscar contenido después del número
        texto_despues = texto_paginas[pos_num:]

        # Encontrar el fin del contenido
        fin_contenido = len(texto_despues)

        # Buscar siguiente número de regla
        if siguiente_numero:
            patron_sig = re.compile(rf'^{re.escape(siguiente_numero)}\.\s*$', re.MULTILINE)
            match_sig = patron_sig.search(texto_despues)
            if match_sig:
                # El contenido termina unas líneas antes del siguiente número (donde está su título)
                fin_contenido = match_sig.start()
        else:
            # Buscar cualquier número de regla
            patron_cualquier = re.compile(r'^\d{1,2}\.\d{1,2}(?:\.\d{1,3})?\.\s*$', re.MULTILINE)
            match_cualquier = patron_cualquier.search(texto_despues)
            if match_cualquier:
                fin_contenido = match_cualquier.start()

        contenido_raw = texto_despues[:fin_contenido]

        # Limpiar contenido
        contenido_raw = self._limpiar_nota(contenido_raw)
        contenido_raw = re.sub(r'\[PAGE:\d+\]', '', contenido_raw)

        # Separar referencias del contenido
        referencias = None
        lineas = contenido_raw.split('\n')
        contenido_lineas = []
        referencias_encontradas = []
        encontro_referencias = False

        for linea in reversed(lineas):
            linea_strip = linea.strip()
            if not linea_strip:
                if not encontro_referencias:
                    contenido_lineas.insert(0, linea)
                continue

            # Detectar referencias (al final)
            if re.match(r'^(CFF|LISR|LIVA|LIEPS|LIC|LFD|RCFF|RLISR|RMF|Decreto|RISAT)', linea_strip):
                referencias_encontradas.insert(0, linea_strip)
                encontro_referencias = True
            elif encontro_referencias and re.match(r'^[\d\-,\s\.;A-Za-z]+$', linea_strip) and len(linea_strip) < 100:
                referencias_encontradas.insert(0, linea_strip)
            else:
                contenido_lineas.insert(0, linea)
                encontro_referencias = False

        contenido = '\n'.join(contenido_lineas).strip()

        # Limpiar título de siguiente regla que quedó al final del contenido
        # Buscar y eliminar líneas que parecen títulos de la siguiente regla
        lineas_final = contenido.split('\n')
        while lineas_final:
            ultima = lineas_final[-1].strip()
            if not ultima:
                lineas_final.pop()
                continue
            # Si la última línea parece un título de regla (corta, capitalizada, sin puntuación al final)
            if (len(ultima) < 100 and
                ultima[0].isupper() and
                not ultima.endswith('.') and
                not re.match(r'^\d', ultima) and
                not any(x in ultima for x in ['CFF', 'LISR', 'LIVA', 'para', 'que', 'del', 'los'])):
                lineas_final.pop()
            else:
                break

        contenido = '\n'.join(lineas_final).strip()

        if referencias_encontradas:
            referencias = ' '.join(referencias_encontradas)

        # Parsear fracciones y limpiar contenido
        fracciones, contenido_limpio = self._parse_fracciones(contenido)

        return Regla(
            numero=numero,
            titulo=titulo,
            contenido=contenido_limpio,
            pagina=pagina,
            fracciones=fracciones,
            referencias=referencias,
            nota_reforma=nota_reforma
        )

    def extraer_indice_completo(self) -> IndiceRMF:
        """Extrae el índice completo de la RMF."""
        print("Extrayendo estructura...")
        titulos, capitulos, secciones, subsecciones = self.extraer_estructura()

        print(f"  Títulos: {len(titulos)}")
        print(f"  Capítulos: {len(capitulos)}")
        print(f"  Secciones: {len(secciones)}")
        print(f"  Subsecciones: {len(subsecciones)}")

        print("\nExtrayendo reglas...")
        reglas = self.extraer_todas_reglas()
        print(f"  Total reglas extraídas: {len(reglas)}")

        return IndiceRMF(
            titulos=titulos,
            capitulos=capitulos,
            secciones=secciones,
            subsecciones=subsecciones,
            reglas=reglas
        )

    def guardar_json(self, output_path: str | Path) -> IndiceRMF:
        """Extrae y guarda el índice completo en JSON."""
        indice = self.extraer_indice_completo()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(indice.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"\nGuardado en: {output_path}")
        return indice

    def close(self):
        self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main():
    """Ejecuta la extracción completa."""
    import sys

    base_dir = Path(__file__).parent.parent.parent
    pdf_path = base_dir / "doc/rmf/rmf_2025_compilada.pdf"
    output_path = base_dir / "doc/rmf/rmf_extraido_v2.json"

    if not pdf_path.exists():
        print(f"Error: No se encontró el PDF en {pdf_path}")
        sys.exit(1)

    print(f"=== Extractor RMF v2 ===")
    print(f"PDF: {pdf_path}")
    print()

    with PDFExtractorV2(pdf_path) as extractor:
        indice = extractor.guardar_json(output_path)

        # Mostrar estadísticas
        print("\n=== Resumen ===")
        print(f"Títulos:      {len(indice.titulos)}")
        print(f"Capítulos:    {len(indice.capitulos)}")
        print(f"Secciones:    {len(indice.secciones)}")
        print(f"Subsecciones: {len(indice.subsecciones)}")
        print(f"Reglas:       {len(indice.reglas)}")

        # Verificar reglas con fracciones
        con_fracciones = sum(1 for r in indice.reglas if r.fracciones)
        total_fracciones = sum(len(r.fracciones) for r in indice.reglas)
        print(f"\nReglas con fracciones: {con_fracciones}")
        print(f"Total fracciones parseadas: {total_fracciones}")

        # Mostrar ejemplo de regla 1.9
        regla_19 = next((r for r in indice.reglas if r.numero == '1.9'), None)
        if regla_19:
            print(f"\n=== Ejemplo: Regla 1.9 ===")
            print(f"Título: {regla_19.titulo}")
            print(f"Fracciones: {len(regla_19.fracciones)}")
            if regla_19.fracciones:
                print("Primeras 3 fracciones:")
                for f in regla_19.fracciones[:3]:
                    print(f"  {f.numero}. {f.contenido[:50]}...")


if __name__ == "__main__":
    main()
