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
    PATRON_REGLA = re.compile(r'(?:^|\n)(\d+\.\d+\.\d+)\.\s+', re.MULTILINE)

    # Patrón para extraer título de regla (línea anterior al número)
    PATRON_TITULO_REGLA = re.compile(r'^([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü\s,]+)\n\d+\.\d+\.\d+\.', re.MULTILINE)

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

            for match in self.PATRON_REGLA.finditer(text):
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
    output_path = base_dir / "doc/rmf/indice_rmf_2025.json"

    if not pdf_path.exists():
        print(f"Error: No se encontró el PDF en {pdf_path}")
        sys.exit(1)

    print(f"Extrayendo índice de: {pdf_path}")

    with PDFExtractor(pdf_path) as extractor:
        indice = extractor.extraer_indice_completo()

        print(f"\n=== Índice RMF 2025 ===")
        print(f"Títulos:      {len(indice.titulos)}")
        print(f"Capítulos:    {len(indice.capitulos)}")
        print(f"Secciones:    {len(indice.secciones)}")
        print(f"Subsecciones: {len(indice.subsecciones)}")
        print(f"Reglas:       {len(indice.reglas)}")

        # Guardar JSON
        extractor.guardar_indice_json(output_path)
        print(f"\nÍndice guardado en: {output_path}")


if __name__ == "__main__":
    main()
