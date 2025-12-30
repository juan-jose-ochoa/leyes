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
        "pdf_path": "backend/etl/data/cff/cff_codigo_fiscal_de_la_federacion.pdf",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
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
            "capitulo": r'^CAP[IÍ]TULOS?\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',
            "seccion": r'^Secci[oó]n\s+(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        # NOTA: No usar .* sin límite - usar [^\n]* para limitar a una línea
        "ruido": [
            r'CÓDIGO FISCAL DE LA FEDERACIÓN\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Secretaría General\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página "24 de 375"
            r'TEXTO VIGENTE\s*',
        ],

        # Detección de referencias (reformas, adiciones)
        # Criterios: itálica + color (azul o gris) + tamaño pequeño + patrón
        "referencias": {
            "font_italic": True,       # Requiere fuente itálica
            "color_no_negro": True,    # Color diferente de negro puro (azul, gris, etc.)
            "size_max": 10,            # Tamaño fuente máximo (texto normal ~12)
            "patrones": [              # Patrones de texto para validar
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"Numeral.*DOF",
                r"Apartado.*DOF",
                r"Reforma\s+DOF",
                r"Compilada?\s+DOF",    # "Compilada DOF" o "Compilado DOF"
                r"Actualizada?\s+DOF",  # "Actualizada DOF" o "Actualizado DOF"
                r"^\d{2}-\d{2}-\d{4}$", # Fechas solas (DD-MM-YYYY) con características DOF
            ],
        },
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

        # Ruido a eliminar
        "ruido": [
            r'RESOLUCIÓN MISCELÁNEA FISCAL',
            r'Secretaría de Hacienda',
            r'DOF:\s+\d{2}/\d{2}/\d{4}',
        ],
    },

    "CPEUM": {
        "nombre": "Constitución Política de los Estados Unidos Mexicanos",
        "nombre_corto": "Constitución",
        "tipo": "codigo",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf",
        "pdf_path": "backend/etl/data/cpeum/cpeum_constitucion_politica.pdf",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral", "apartado"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        # NOTA: La CPEUM usa Title Case para títulos/capítulos, no MAYÚSCULAS
        "patrones": {
            # Artículo: "Artículo 1o.-" o "Artículo 10." o "Artículo 136."
            # Formatos: ordinales (1o, 2o) hasta ~9, luego cardinales (10, 11... 136)
            "articulo": r'^Artículo\s+(\d+[oa]?)\.[\-–]?',

            # Divisiones estructurales (Title Case, con acentos)
            "titulo": r'^Título\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|Séptimo|Octavo|Noveno)$',
            "capitulo": r'^Capítulo\s+([IVX]+|Único)$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
            "apartado": r'^([A-Z])\.\s+',  # Art. 123 tiene Apartado A y B
        },

        # Ruido a eliminar (encabezados, pies de página)
        # ruido: patrones regex para filtrado avanzado
        # ruido_lineas: strings simples para filtrado rápido (usado por extraer.py)
        "ruido": [
            r'CONSTITUCIÓN POLÍTICA DE LOS ESTADOS UNIDOS MEXICANOS\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN[^\n]*',
            r'Secretaría General\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página
            r'TEXTO VIGENTE\s*',
        ],
        "ruido_lineas": [
            'CONSTITUCIÓN POLÍTICA DE LOS ESTADOS UNIDOS MEXICANOS',
            'CÁMARA DE DIPUTADOS',
            'Secretaría General',
            'Servicios Parlamentarios',
            'Última Reforma',
            'Última reforma',
            'TEXTO VIGENTE',
            ' de 402',  # "X de 402" - números de página
        ],

        # Detección de referencias (reformas, adiciones)
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"Apartado.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"Denominación.*reformada.*DOF",
            ],
        },

        # Página donde terminan los artículos permanentes + transitorios originales
        # Después de esta página comienzan los transitorios de decretos de reforma
        "pagina_fin_contenido": 162,
    },

    "LISR": {
        "nombre": "Ley del Impuesto sobre la Renta",
        "nombre_corto": "ISR",
        "tipo": "ley",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf",
        "pdf_path": "backend/etl/data/lisr/lisr_ley_del_impuesto_sobre_la_renta.pdf",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 5o.", "Artículo 10.", "Artículo 25-A.", "Artículo 197 Bis."
            "articulo": r'^Artículo\s+(\d+)([oa])?\.?(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.[- –]?',

            # Divisiones estructurales (MAYÚSCULAS con números romanos)
            "titulo": r'^T[IÍ]TULO\s+([IVX]+)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+)\s*$',
            "seccion": r'^SECCI[OÓ]N\s+([IVX]+)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        "ruido": [
            r'LEY DEL IMPUESTO SOBRE LA RENTA\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN[^\n]*',
            r'Secretaría General\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página
            r'TEXTO VIGENTE\s*',
        ],
        "ruido_lineas": [
            'LEY DEL IMPUESTO SOBRE LA RENTA',
            'CÁMARA DE DIPUTADOS',
            'Secretaría General',
            'Servicios Parlamentarios',
            'Última Reforma',
            'Última reforma',
            'TEXTO VIGENTE',
            ' de 313',  # "X de 313" - números de página
        ],

        # Detección de referencias (reformas, adiciones)
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"Sección.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
            ],
        },

        # Página donde terminan los artículos permanentes
        "pagina_fin_contenido": 278,
    },

    "LIVA": {
        "nombre": "Ley del Impuesto al Valor Agregado",
        "nombre_corto": "IVA",
        "tipo": "ley",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf",
        "pdf_path": "backend/etl/data/liva/liva_ley_del_impuesto_al_valor_agregado.pdf",

        # Estructura jerárquica permitida
        # LIVA no tiene títulos, solo capítulos directamente
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 1o.", "Artículo 18-A.", "Artículo 18-H QUINTUS."
            "articulo": r'^Artículo\s+(\d+)([oa])?\.?(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quintus|Quinquies|Sexies))?\.[- –]?',

            # LIVA no tiene títulos explícitos
            "titulo": r'^$',  # No match
            # Capítulos (incluyendo "III BIS")
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        "ruido": [
            r'LEY DEL IMPUESTO AL VALOR AGREGADO\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN[^\n]*',
            r'Secretaría General\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página
            r'TEXTO VIGENTE\s*',
        ],
        "ruido_lineas": [
            'LEY DEL IMPUESTO AL VALOR AGREGADO',
            'CÁMARA DE DIPUTADOS',
            'Secretaría General',
            'Servicios Parlamentarios',
            'Última Reforma',
            'Última reforma',
            'TEXTO VIGENTE',
            ' de 128',  # "X de 128" - números de página
        ],

        # Detección de referencias (reformas, adiciones)
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"Capítulo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
            ],
        },

        # Página donde terminan los artículos permanentes + transitorios originales
        "pagina_fin_contenido": 52,
    },

    "LA": {
        "nombre": "Ley Aduanera",
        "nombre_corto": "Aduanera",
        "tipo": "ley",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LAdua.pdf",
        "pdf_path": "backend/etl/data/la/la_ley_aduanera.pdf",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "ARTICULO 1o." o "ARTICULO 14-A." o "ARTICULO 137 bis 1.-"
            # LA usa ARTICULO en mayúsculas, con ordinal (1o, 2o) o sin (10, 11)
            # Formato especial: "137 bis 1", "137 bis 2" (bis seguido de número)
            "articulo": r'^(?:ARTICULO|ARTÍCULO|Artículo)\s+(\d+)([oa])?\.?(?:[-–_\s]*([A-Z]))?(?:[-–_\s]+(bis|Bis|Ter|Quáter|Quinquies|Sexies)(?:[-–_\s]+(\d+))?)?\.[- –]?',

            # Divisiones estructurales (Title Case: "Título Primero", "Capítulo I")
            "titulo": r'^Título\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|Séptimo|Octavo|Noveno|Décimo)\s*$',
            "capitulo": r'^Capítulo\s+([IVX]+|Único)\s*$',
            "seccion": r'^Sección\s+(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        "ruido": [
            r'LEY ADUANERA\s*',
            r'CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN[^\n]*',
            r'Secretaría General\s*',
            r'Secretaría de Servicios Parlamentarios\s*',
            r'Última\s+[Rr]eforma\s+(?:publicada\s+)?DOF[^\n]*',
            r'\d+\s+de\s+\d+\s*',  # Números de página
            r'TEXTO VIGENTE\s*',
        ],
        "ruido_lineas": [
            'LEY ADUANERA',
            'CÁMARA DE DIPUTADOS',
            'Secretaría General',
            'Servicios Parlamentarios',
            'Última Reforma',
            'Última reforma',
            'TEXTO VIGENTE',
            ' de 218',  # "X de 218" - números de página
        ],

        # Detección de referencias (reformas, adiciones)
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"Capítulo.*DOF",
                r"Sección.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
            ],
        },

        # Página donde terminan los artículos permanentes
        "pagina_fin_contenido": 200,
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
