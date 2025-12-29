"""
Extractor de índice y reglas del PDF de la RMF.

Permite:
1. Extraer estructura completa (títulos, capítulos, secciones, subsecciones)
2. Extraer lista de todas las reglas
3. Extraer contenido de una regla específica
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class ElementoIndice:
    """Elemento del índice (título, capítulo, sección, subsección)."""
    tipo: str
    numero: str
    nombre: str
    pagina: Optional[int] = None


@dataclass
class ReglaIndice:
    """Regla encontrada en el PDF."""
    numero: str
    titulo: Optional[str] = None
    pagina: int = 0
    contenido: Optional[str] = None
    referencias: Optional[str] = None
    es_dos_niveles: bool = False  # True para reglas X.Y, False para X.Y.Z


@dataclass
class IndiceRMF:
    """Índice completo extraído del PDF."""
    titulos: list[ElementoIndice] = field(default_factory=list)
    capitulos: list[ElementoIndice] = field(default_factory=list)
    secciones: list[ElementoIndice] = field(default_factory=list)
    subsecciones: list[ElementoIndice] = field(default_factory=list)
    reglas: list[ReglaIndice] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'titulos': [asdict(t) for t in self.titulos],
            'capitulos': [asdict(c) for c in self.capitulos],
            'secciones': [asdict(s) for s in self.secciones],
            'subsecciones': [asdict(ss) for ss in self.subsecciones],
            'reglas': [asdict(r) for r in self.reglas],
            'stats': {
                'total_titulos': len(self.titulos),
                'total_capitulos': len(self.capitulos),
                'total_secciones': len(self.secciones),
                'total_subsecciones': len(self.subsecciones),
                'total_reglas': len(self.reglas),
            }
        }


class PDFExtractor:
    """Extractor de índice y contenido del PDF de la RMF."""

    # Patrones para el índice (páginas iniciales)
    PATRON_TITULO_INDICE = re.compile(r'^(\d{1,2})\.\s+(.+?)$', re.MULTILINE)
    PATRON_CAPITULO_INDICE = re.compile(r'Capítulo\s+(\d+\.\d+)\.?\s+(.+?)(?:\n|$)')
    PATRON_SECCION_INDICE = re.compile(r'Sección\s+(\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)')
    PATRON_SUBSECCION_INDICE = re.compile(r'Subsección\s+(\d+\.\d+\.\d+\.\d+)\.?\s+(.+?)(?:\n|$)')

    # Patrón para reglas en el contenido
    # Formato 1: dos niveles (X.Y) - para títulos sin capítulos (ej: 1.1, 1.11)
    #            Solo números pequeños (1-99) para evitar falsos positivos como tasas (1.0476)
    # Formato 2: tres niveles (X.Y.Z) - para títulos con capítulos (ej: 2.1.1, 3.5.23)
    PATRON_REGLA_DOS_NIVELES = re.compile(r'(?:^|\n)(\d{1,2}\.\d{1,2})\.\s+', re.MULTILINE)
    PATRON_REGLA_TRES_NIVELES = re.compile(r'(?:^|\n)(\d+\.\d+\.\d+)\.\s+', re.MULTILINE)

    # Patrón para extraer título de regla (línea anterior al número)
    PATRON_TITULO_REGLA = re.compile(r'^([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü\s,]+)\n\d+\.\d+\.', re.MULTILINE)

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(str(self.pdf_path))
        self._cache_paginas: dict[int, str] = {}

    def _get_page_text(self, page_num: int) -> str:
        """Obtiene el texto de una página con caché."""
        if page_num not in self._cache_paginas:
            if 0 <= page_num < len(self.doc):
                self._cache_paginas[page_num] = self.doc[page_num].get_text()
            else:
                return ""
        return self._cache_paginas[page_num]

    def extraer_indice_estructura(self) -> IndiceRMF:
        """Extrae la estructura del índice de las primeras páginas."""
        indice = IndiceRMF()

        # El índice está en páginas 2-7 (índices 1-6)
        texto_indice = ""
        for page_num in range(1, 8):
            texto_indice += self._get_page_text(page_num) + "\n"

        # Extraer títulos (solo los 12 títulos de la RMF)
        # Los títulos válidos son: 1-12
        seen_titulos = set()
        for match in self.PATRON_TITULO_INDICE.finditer(texto_indice):
            num = match.group(1)
            nombre = match.group(2).strip()
            # Filtros:
            # 1. Solo números 1-12
            # 2. No debe contener "." (son definiciones de acrónimos)
            # 3. No debe empezar con mayúsculas seguidas de punto (acrónimos)
            if (len(num) <= 2 and
                int(num) <= 12 and
                num not in seen_titulos and
                '.' not in nombre[:20] and
                not re.match(r'^[A-Z]{2,}\.', nombre)):
                seen_titulos.add(num)
                indice.titulos.append(ElementoIndice(
                    tipo='titulo',
                    numero=num,
                    nombre=nombre
                ))

        # Extraer capítulos
        seen_capitulos = set()
        for match in self.PATRON_CAPITULO_INDICE.finditer(texto_indice):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen_capitulos:
                seen_capitulos.add(num)
                indice.capitulos.append(ElementoIndice(
                    tipo='capitulo',
                    numero=num,
                    nombre=nombre
                ))

        # Extraer secciones
        seen_secciones = set()
        for match in self.PATRON_SECCION_INDICE.finditer(texto_indice):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen_secciones:
                seen_secciones.add(num)
                indice.secciones.append(ElementoIndice(
                    tipo='seccion',
                    numero=num,
                    nombre=nombre
                ))

        # Extraer subsecciones
        seen_subsecciones = set()
        for match in self.PATRON_SUBSECCION_INDICE.finditer(texto_indice):
            num = match.group(1)
            nombre = match.group(2).strip()
            if num not in seen_subsecciones:
                seen_subsecciones.add(num)
                indice.subsecciones.append(ElementoIndice(
                    tipo='subseccion',
                    numero=num,
                    nombre=nombre
                ))

        return indice

    def extraer_todas_reglas(self) -> list[ReglaIndice]:
        """Extrae todas las reglas del PDF completo."""
        reglas = {}  # numero -> ReglaIndice

        for page_num in range(len(self.doc)):
            text = self._get_page_text(page_num)

            # Buscar reglas de dos niveles (Título 1: 1.1, 1.2... 1.11)
            for match in self.PATRON_REGLA_DOS_NIVELES.finditer(text):
                num = match.group(1)
                if num not in reglas:
                    reglas[num] = ReglaIndice(
                        numero=num,
                        pagina=page_num + 1  # 1-indexed
                    )

            # Buscar reglas de tres niveles (otros títulos: 2.1.1, 3.5.23...)
            for match in self.PATRON_REGLA_TRES_NIVELES.finditer(text):
                num = match.group(1)
                if num not in reglas:
                    reglas[num] = ReglaIndice(
                        numero=num,
                        pagina=page_num + 1  # 1-indexed
                    )

        # Ordenar por número
        def parse_num(n):
            return tuple(int(p) for p in n.split('.'))

        return sorted(reglas.values(), key=lambda r: parse_num(r.numero))

    def extraer_regla_contenido(self, numero: str) -> Optional[ReglaIndice]:
        """Extrae el contenido completo de una regla específica."""
        # Buscar la página donde inicia la regla
        for page_num in range(len(self.doc)):
            text = self._get_page_text(page_num)

            # Buscar el inicio de la regla
            pattern = re.compile(rf'\n({re.escape(numero)})\.\s+(.+?)(?=\n\d+\.\d+\.\d+\.|$)', re.DOTALL)
            match = pattern.search(text)

            if match:
                # Buscar el título (línea anterior al número)
                titulo = None
                lines = text[:match.start()].split('\n')
                if lines:
                    # Buscar hacia atrás una línea que parezca título
                    for i in range(len(lines) - 1, max(len(lines) - 5, -1), -1):
                        line = lines[i].strip()
                        if line and re.match(r'^[A-ZÁÉÍÓÚÑÜ]', line) and not re.match(r'^\d', line):
                            if 'CFF' not in line and 'RMF' not in line and 'Página' not in line:
                                titulo = line
                                break

                contenido = match.group(2).strip()

                # Si el contenido continúa en páginas siguientes, intentar obtener más
                if page_num + 1 < len(self.doc):
                    next_text = self._get_page_text(page_num + 1)
                    # Si la siguiente página no empieza con una nueva regla, agregar contenido
                    if not re.match(r'^\s*\d+\.\d+\.\d+\.', next_text):
                        # Buscar hasta la siguiente regla
                        next_match = re.search(r'\n\d+\.\d+\.\d+\.', next_text)
                        if next_match:
                            contenido += "\n" + next_text[:next_match.start()].strip()
                        else:
                            contenido += "\n" + next_text[:1000].strip()  # Limitar

                return ReglaIndice(
                    numero=numero,
                    titulo=titulo,
                    pagina=page_num + 1,
                    contenido=contenido[:5000]  # Limitar tamaño
                )

        return None

    def extraer_reglas_dos_niveles_contenido(self) -> list[ReglaIndice]:
        """
        Extrae todas las reglas de dos niveles (X.Y) con su contenido completo.

        Estas reglas pertenecen a títulos sin capítulos (Títulos 1, 6, 7, 8, 9, 10).
        El título de la regla aparece ANTES del número de regla.

        Estructura en PDF:
            <título de regla>
            X.Y.  <contenido>
            <referencias (CFF, LISR, etc.)>
            <título de siguiente regla>
            X.Y+1.  <contenido siguiente>
        """
        reglas = []

        # Primero, encontrar todas las reglas de dos niveles y sus páginas
        reglas_info = {}
        for page_num in range(len(self.doc)):
            text = self._get_page_text(page_num)
            for match in self.PATRON_REGLA_DOS_NIVELES.finditer(text):
                num = match.group(1)
                if num not in reglas_info:
                    reglas_info[num] = page_num

        # Ordenar por número
        numeros_ordenados = sorted(
            reglas_info.keys(),
            key=lambda n: tuple(int(p) for p in n.split('.'))
        )

        # Extraer contenido de cada regla
        for i, numero in enumerate(numeros_ordenados):
            page_num = reglas_info[numero]
            text = self._get_page_text(page_num)

            # Determinar el siguiente número de regla (para saber dónde termina)
            siguiente_num = numeros_ordenados[i + 1] if i + 1 < len(numeros_ordenados) else None

            # Patrón para encontrar esta regla
            patron_inicio = re.compile(
                rf'(?:^|\n)({re.escape(numero)})\.\s+',
                re.MULTILINE
            )

            match = patron_inicio.search(text)
            if not match:
                continue

            pos_inicio = match.end()

            # Buscar el título (líneas anteriores al número)
            titulo = None
            texto_antes = text[:match.start()]
            lineas_antes = texto_antes.split('\n')

            # El título suele estar 1-3 líneas antes del número
            for j in range(len(lineas_antes) - 1, max(len(lineas_antes) - 5, -1), -1):
                linea = lineas_antes[j].strip()
                if linea:
                    # Ignorar líneas que no parecen títulos
                    if any(x in linea for x in ['Página', 'CFF', 'LISR', 'LIVA', 'RMF', 'DOF']):
                        continue
                    if re.match(r'^\d+\.', linea):  # Es un número de regla
                        continue
                    if re.match(r'^[a-z]', linea):  # Empieza en minúscula
                        continue
                    if len(linea) < 5:  # Muy corta
                        continue
                    # Parece un título válido
                    titulo = linea
                    break

            # Si no encontramos título en esta página, buscar en la anterior
            if not titulo and page_num > 0:
                texto_pag_anterior = self._get_page_text(page_num - 1)
                lineas_pag_anterior = texto_pag_anterior.split('\n')
                for j in range(len(lineas_pag_anterior) - 1, max(len(lineas_pag_anterior) - 10, -1), -1):
                    linea = lineas_pag_anterior[j].strip()
                    if linea:
                        if any(x in linea for x in ['Página', 'CFF', 'LISR', 'LIVA', 'RMF', 'DOF']):
                            continue
                        if re.match(r'^\d+\.', linea):
                            continue
                        if re.match(r'^[a-z]', linea):
                            continue
                        if len(linea) < 5:
                            continue
                        titulo = linea
                        break

            # Buscar el fin del contenido (siguiente regla o fin de página)
            contenido = ""
            referencias = ""

            # Patrón para siguiente regla (dos o tres niveles)
            patron_siguiente = re.compile(r'\n(\d{1,2}\.\d{1,2})\.\s+', re.MULTILINE)

            texto_despues = text[pos_inicio:]
            match_siguiente = patron_siguiente.search(texto_despues)

            if match_siguiente:
                # Hay otra regla en esta página
                contenido_raw = texto_despues[:match_siguiente.start()].strip()
            else:
                # No hay otra regla en esta página, buscar en siguientes
                contenido_raw = texto_despues.strip()

                # Buscar en páginas siguientes hasta encontrar la siguiente regla
                for pag_extra in range(page_num + 1, min(page_num + 5, len(self.doc))):
                    texto_extra = self._get_page_text(pag_extra)
                    match_sig_pag = patron_siguiente.search(texto_extra)

                    if match_sig_pag:
                        contenido_raw += "\n" + texto_extra[:match_sig_pag.start()].strip()
                        break
                    else:
                        # Si no encuentra regla, agregar un poco de texto
                        contenido_raw += "\n" + texto_extra[:500].strip()
                        # Pero si encontramos un nuevo título, parar
                        if re.search(r'Título\s+\d+\.', texto_extra):
                            break

            # Separar contenido de referencias
            # Las referencias suelen estar al final: "CFF 32-B, LIC 142"
            lineas_contenido = contenido_raw.split('\n')
            contenido_lineas = []
            referencias_lineas = []

            for linea in lineas_contenido:
                linea_strip = linea.strip()
                # Si la línea parece ser solo referencias (CFF, LISR, LIVA, etc.)
                if re.match(r'^(CFF|LISR|LIVA|LIEPS|LIC|RMF|Decreto|RCFF|RLISR)\s*[\d\-,\s]+', linea_strip):
                    referencias_lineas.append(linea_strip)
                elif re.match(r'^[\d\-,\s]+$', linea_strip) and referencias_lineas:
                    # Continuación de referencias
                    referencias_lineas.append(linea_strip)
                else:
                    contenido_lineas.append(linea)

            contenido = '\n'.join(contenido_lineas).strip()
            referencias = ', '.join(referencias_lineas) if referencias_lineas else None

            # Limpiar contenido excesivo
            if len(contenido) > 10000:
                contenido = contenido[:10000] + "..."

            regla = ReglaIndice(
                numero=numero,
                titulo=titulo,
                pagina=page_num + 1,
                contenido=contenido,
                referencias=referencias,
                es_dos_niveles=True
            )
            reglas.append(regla)

        return reglas

    def extraer_indice_completo(self) -> IndiceRMF:
        """Extrae el índice completo incluyendo estructura y reglas."""
        indice = self.extraer_indice_estructura()
        indice.reglas = self.extraer_todas_reglas()
        return indice

    def guardar_indice_json(self, output_path: str | Path) -> None:
        """Extrae y guarda el índice completo en formato JSON."""
        indice = self.extraer_indice_completo()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(indice.to_dict(), f, ensure_ascii=False, indent=2)

    def guardar_reglas_dos_niveles_json(self, output_path: str | Path) -> None:
        """Extrae y guarda las reglas de dos niveles con contenido."""
        reglas = self.extraer_reglas_dos_niveles_contenido()

        data = {
            'total': len(reglas),
            'reglas': [asdict(r) for r in reglas]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return reglas

    def close(self):
        """Cierra el documento PDF."""
        self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main():
    """Extrae el índice del PDF de RMF 2025 y lo guarda como JSON."""
    import sys

    # Paths por defecto
    base_dir = Path(__file__).parent.parent.parent
    pdf_path = base_dir / "doc/rmf/rmf_2025_compilada.pdf"
    output_indice = base_dir / "doc/rmf/indice_rmf_2025.json"
    output_dos_niveles = base_dir / "doc/rmf/reglas_dos_niveles.json"

    if not pdf_path.exists():
        print(f"Error: No se encontró el PDF en {pdf_path}")
        sys.exit(1)

    print(f"Extrayendo índice de: {pdf_path}")

    with PDFExtractor(pdf_path) as extractor:
        # Extraer índice completo
        indice = extractor.extraer_indice_completo()

        print(f"\n=== Índice RMF 2025 ===")
        print(f"Títulos:      {len(indice.titulos)}")
        print(f"Capítulos:    {len(indice.capitulos)}")
        print(f"Secciones:    {len(indice.secciones)}")
        print(f"Subsecciones: {len(indice.subsecciones)}")
        print(f"Reglas:       {len(indice.reglas)}")

        # Guardar índice
        extractor.guardar_indice_json(output_indice)
        print(f"\nÍndice guardado en: {output_indice}")

        # Extraer y guardar reglas de dos niveles con contenido
        print("\n=== Extrayendo reglas de dos niveles ===")
        reglas_2n = extractor.guardar_reglas_dos_niveles_json(output_dos_niveles)

        # Mostrar resumen por título
        por_titulo = {}
        for r in reglas_2n:
            t = r.numero.split('.')[0]
            por_titulo[t] = por_titulo.get(t, 0) + 1

        print(f"Total reglas de dos niveles: {len(reglas_2n)}")
        for t in sorted(por_titulo.keys(), key=int):
            print(f"  Título {t}: {por_titulo[t]} reglas")

        print(f"\nReglas de dos niveles guardadas en: {output_dos_niveles}")


if __name__ == "__main__":
    main()
