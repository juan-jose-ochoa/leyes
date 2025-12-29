"""
Configuración por ley para extracción.

Cada ley tiene sus propios patrones de detección y estructura.
"""

LEYES = {
    "CFF": {
        "nombre": "Código Fiscal de la Federación",
        "nombre_corto": "Código Fiscal",
        "tipo": "codigo",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
        "pdf_path": "backend/scripts/data/cff/cff_codigo_fiscal_de_la_federacion.pdf",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 17-H Bis.-" o "Artículo 9o.-" o "Artículo 4o.-A.-" o "Artículo 20-Bis."
            # Formatos encontrados en PDF:
            #   - "Artículo 4o.-" (ordinal simple)
            #   - "Artículo 4o.-A.-" (ordinal + letra, con puntos)
            #   - "Artículo 20-Bis." (número + Bis con guión)
            #   - "Artículo 17-H Bis.-" (número + letra + Bis)
            "articulo": r'^Artículo\s+(\d+)([oa])?\.?(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.[- –]',

            # Divisiones estructurales (línea completa, sin acento también)
            "titulo": r'^TITULOS?\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SEPTIMO|OCTAVO|NOVENO|DECIMO)\s*$',
            "capitulo": r'^CAPITULOS?\s+([IVX]+|UNICO)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Texto basura a eliminar (encabezados, pies de página)
        # NOTA: No usar .* sin límite - usar [^\n]* para limitar a una línea
        "basura": [
            r'CÓDIGO FISCAL DE LA FEDERACIÓN\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Secretaría General\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página "24 de 375"
            r'Párrafo\s+reformad[oa][^\n]*DOF[^\n]*',
            r'Fracción\s+reformad[oa][^\n]*DOF[^\n]*',
            r'Artículo\s+reformad[oa][^\n]*DOF[^\n]*',
            r'Inciso\s+reformad[oa][^\n]*DOF[^\n]*',
            r'Apartado\s+adicionad[oa][^\n]*DOF[^\n]*',
            r'(?:Nuevo\s+)?(?:Código|Artículo)\s+[Pp]ublicad[oa][^\n]*DOF[^\n]*',
            r'TEXTO VIGENTE\s*',
        ],
    },

    "RMF2025": {
        "nombre": "Resolución Miscelánea Fiscal para 2025",
        "nombre_corto": "Miscelánea 2025",
        "tipo": "resolucion",
        "ley_base": "RMF",
        "anio": 2025,
        "url_fuente": None,  # TODO: agregar URL del DOF
        "pdf_path": None,  # TODO: agregar path

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["libro", "titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral", "numeral_romano"],

        # Tipo de contenido principal
        "tipo_contenido": "regla",

        # Patrones de detección
        "patrones": {
            # Regla: "Regla 2.1.1.1" o "2.1.1.1."
            "articulo": r'(?:Regla\s+)?(\d+\.\d+\.\d+(?:\.\d+)?)\.',

            # Divisiones estructurales
            "libro": r'Libro\s+(Primero|Segundo|Tercero)',
            "titulo": r'Título\s+(\d+)',
            "capitulo": r'Capítulo\s+(\d+\.\d+)',
            "seccion": r'Sección\s+(\d+\.\d+\.\d+)',

            # Fracciones dentro de reglas
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Texto basura a eliminar
        "basura": [
            r'RESOLUCIÓN MISCELÁNEA FISCAL',
            r'Secretaría de Hacienda',
            r'DOF:\s+\d{2}/\d{2}/\d{4}',
        ],
    },
}


def get_config(codigo: str) -> dict:
    """Obtiene la configuración de una ley."""
    codigo = codigo.upper()
    if codigo not in LEYES:
        raise ValueError(f"Ley '{codigo}' no configurada. Disponibles: {list(LEYES.keys())}")
    return LEYES[codigo]


def listar_leyes() -> list:
    """Lista las leyes configuradas."""
    return list(LEYES.keys())
