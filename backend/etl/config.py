"""
Configuración por ley para extracción.

Cada ley tiene sus propios patrones de detección y estructura.

Secciones por ley:
- nombre, nombre_corto, tipo: Metadatos
- url_fuente, pdf_path: Ubicación del PDF
- fecha_dof_patron: Regex para extraer fecha DOF
- divisiones_permitidas, parrafos_permitidos: Estructura jerárquica
- patrones: Regex de detección
- filtro_y, ruido_lineas: Filtrado de contenido
- referencias: Detección de notas DOF
- excepciones: Artículos con modo especial (ej: "texto_plano")
- excepciones_pendientes: Artículos que requieren corrección manual futura
  Formato: lista de dicts con "articulo" y "descripcion"
- requiere_bold: Si los identificadores requieren estar en bold (default: True)
  False para PDFs donde fracciones/incisos no están en bold (ej: CPEUM)
"""

LEYES = {
    "CFF": {
        "nombre": "Código Fiscal de la Federación",
        "nombre_corto": "Código Fiscal",
        "tipo": "codigo",
        "categoria": "fiscal",
        "reglamentos": ['RCFF'],
        "categoria": "fiscal",
        "reglamentos": ["RCFF"],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
        "pdf_path": "backend/etl/data/cff/cff_codigo_fiscal_de_la_federacion.pdf",

        # Patrón para extraer fecha DOF del encabezado
        "fecha_dof_patron": r"[ÚU]ltima\s+[Rr]eforma\s+DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

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
            "articulo": r'^Artículo\s+(\d+)([oa])?\.?(?:[-–\s]*([A-Z]))?(?:[.\-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.[- –]',

            # Divisiones estructurales (línea completa, sin acento también)
            "titulo": r'^TITULOS?\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SEPTIMO|OCTAVO|NOVENO|DECIMO)\s*$',
            "capitulo": r'^CAP[IÍ]TULOS?\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',
            "seccion": r'^Secci[oó]n\s+(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Coordenadas X para validar identificadores (rechaza texto continuación)
        "coordenadas_x": {
            "fraccion": {"min": 70, "max": 120},
            "apartado": {"min": 80, "max": 125},
            "inciso": {"min": 100, "max": 135},
            "numeral": {"min": 80, "max": 150},
        },

        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (si aplica)
        "ruido_lineas": [],

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

        # Excepciones pendientes: artículos que requieren corrección manual
        "excepciones_pendientes": [
            {"articulo": "53", "descripcion": "II.- sin fracción I (derogada). Detector espera secuencia I->II"},
        ],
    },

    "RMF": {
        "nombre": "Resolución Miscelánea Fiscal",
        "nombre_corto": "Miscelánea Fiscal 2026",
        "tipo": "resolucion",
        "categoria": "fiscal",
                "tipo_extractor": "rmf",  # Usa ExtractorRMF en lugar de ExtractorGeneral
        "url_fuente": "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/rmf/RMF_2026-DOF-28122025.pdf",
        "pdf_path": "backend/etl/data/rmf/rmf_2026_original.pdf",

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
        # Filtro por coordenada Y para eliminar header/footer
        # RMF tiene layout diferente: header a Y=35.7, contenido desde Y=58
        "filtro_y": {
            "header_max": 50,   # y < 50: solo "Domingo 28 de diciembre de 2025" y "DIARIO OFICIAL"
            "footer_min": 750,  # y > 750: sin filtro (contenido llega hasta ~716)
        },
    },

    "CPEUM": {
        "nombre": "Constitución Política de los Estados Unidos Mexicanos",
        "nombre_corto": "Constitución",
        "tipo": "codigo",
        "categoria": "constitucional",
                "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf",
        "pdf_path": "backend/etl/data/cpeum/cpeum_constitucion_politica.pdf",

        # Patrón para extraer fecha DOF del encabezado
        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral", "apartado"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # No requiere bold para identificadores (fracciones no son bold en este PDF)
        "requiere_bold": False,

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

        # Coordenadas X para validar identificadores
        "coordenadas_x": {
            "fraccion": {"min": 80, "max": 125},
            "apartado": {"min": 80, "max": 90},
            "inciso": {"min": 100, "max": 135},
            "numeral": {"min": 125, "max": 200},
        },

        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (regex con ^$ o substring)
        "ruido_lineas": [
            r'^TEXTO VIGENTE$',  # Aparece en zona de contenido
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

        # Excepciones pendientes: artículos que requieren corrección manual
        "excepciones_pendientes": [
            {"articulo": "72", "descripcion": "Apartado I (sic DOF 24-11-1923) duplicado. Error histórico en texto legal"},
            {"articulo": "123", "descripcion": "Apartado B: XI (sic 05-12-1960) aparece dos veces, falta IX. Error histórico en texto legal"},
        ],
    },

    "LISR": {
        "nombre": "Ley del Impuesto sobre la Renta",
        "nombre_corto": "Ley del ISR",
        "tipo": "ley",
        "categoria": "fiscal",
        "reglamentos": ['RLISR'],
        "categoria": "fiscal",
        "reglamentos": ["RLISR"],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf",
        "pdf_path": "backend/etl/data/lisr/lisr_ley_del_impuesto_sobre_la_renta.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

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
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

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

        # Patrones adicionales que indican fin de artículos permanentes
        # (además de TRANSITORIOS que se detecta automáticamente)
        "fin_articulos_extra": [
            r"DISPOSICIONES\s+DE\s+VIGENCIA\s+TEMPORAL",
        ],

        # Capítulos implícitos: títulos que tienen una sección antes del primer capítulo explícito
        # El texto aparece después del nombre del título pero no tiene marcador "CAPÍTULO"
        # Se crea un capítulo virtual "0" con ese nombre
        "capitulos_implicitos": {
            "II": "DISPOSICIONES GENERALES",   # Título II: arts 9-15 antes de Cap I
            "IV": "DISPOSICIONES GENERALES",   # Título IV: arts 94-99 antes de Cap I
        },
    },

    "LIVA": {
        "nombre": "Ley del Impuesto al Valor Agregado",
        "nombre_corto": "Ley del IVA",
        "tipo": "ley",
        "categoria": "fiscal",
        "reglamentos": ['RLIVA'],
        "categoria": "fiscal",
        "reglamentos": ["RLIVA"],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf",
        "pdf_path": "backend/etl/data/liva/liva_ley_del_impuesto_al_valor_agregado.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Página donde termina el contenido (antes de TRANSITORIOS)
        # Evita que capítulos de decretos de reforma sobrescriban los correctos
        "pagina_fin_contenido": 49,

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
            # LIVA no tiene títulos - usar patrón que nunca matchea pero tiene grupo
            "titulo": r'^(TITULO_INEXISTENTE)$',
            # Capítulos (incluyendo "III BIS")
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

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
    },

    "LA": {
        "nombre": "Ley Aduanera",
        "nombre_corto": "Ley Aduanera",
        "tipo": "ley",
        "categoria": "fiscal",
                "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LAdua.pdf",
        "pdf_path": "backend/etl/data/la/la_ley_aduanera.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion", "subseccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Marcador de transitorios en outline (default: "TRANSITORIOS")
        "transitorios_marcador": "TRANSITORIOS_DE_LA_LEY",

        # Detectar subsecciones (romanos sueltos: I, II, III sin palabra SUBSECCION)
        # LA tiene secciones con subsecciones como:
        #   Sección Primera - Importaciones temporales
        #     I - Disposiciones generales
        #     II - Para retornar al extranjero en el mismo estado
        "detectar_subsecciones": True,

        # Patrones de detección
        "patrones": {
            # Artículo: "ARTICULO 1o." o "ARTICULO 14-A." o "ARTICULO 137 bis 1.-"
            # LA usa ARTICULO en mayúsculas, con ordinal (1o, 2o) o sin (10, 11)
            # Formato especial: "137 bis 1", "137 bis 2" (bis seguido de número)
            "articulo": r'^(?:ARTICULO|ARTÍCULO|Artículo)\s+(\d+)([oa])?\.?(?:[-–_\s]*([A-Z]))?(?:[-–_\s]+(bis|Bis|Ter|Quáter|Quinquies|Sexies)(?:[-–_\s]+(\d+))?)?\.[- –]?',

            # Divisiones estructurales (Title Case: "Título Primero", "Capítulo I")
            "titulo": r'^Título\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|Séptimo|Octavo|Noveno|Décimo)\s*$',
            "capitulo": r'^Capítulo\s+([IVX]+|[UÚ]nico)\s*$',
            "seccion": r'^Sección\s+(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar (encabezados, pies de página)
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

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

        # Patrones adicionales para fin de artículos
        # LA usa "T r a n s i t o r i o s" con espacios entre letras
        "fin_articulos_extra": [
            r"T\s*r\s*a\s*n\s*s\s*i\s*t\s*o\s*r\s*i\s*o\s*s?",
        ],
    },

    "LIEPS": {
        "nombre": "Ley del Impuesto Especial sobre Producción y Servicios",
        "nombre_corto": "Ley del IEPS",
        "tipo": "ley",
        "categoria": "fiscal",
        "reglamentos": ['RLIEPS'],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIEPS.pdf",
        "pdf_path": "backend/etl/data/lieps/lieps_ley_del_impuesto_especial.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 2o.-A.-" o "Artículo 5o.-A BIS.-" o "Artículo 10.-"
            # Incluye LL y Ñ para artículos como 26-LL y 26-Ñ
            "articulo": r'^Artículo\s+(\d+)([oa])?\.?(?:[-–\s]*([A-ZÑ]|LL))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?[-.]?[- –]',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "LFT": {
        "nombre": "Ley Federal del Trabajo",
        "nombre_corto": "Ley Federal del Trabajo",
        "tipo": "ley",
        "categoria": "laboral",
        "reglamentos": ['RLFT'],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf",
        "pdf_path": "backend/etl/data/lft/lft_ley_federal_del_trabajo.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # LFT tiene capítulos no centrados en el PDF
        "requiere_centrado": False,

        # Excepciones: artículos con extractor especial
        "excepciones": {
            "513": "texto_plano",  # Tabla de Enfermedades de Trabajo (estructura atípica)
        },

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 1o.-" o "Artículo 153-A" o "Artículo 153-F Bis" o "Artículo 10.-"
            # LFT usa formato especial: número-letra (153-A, 291-A, 330-A, etc.)
            "articulo": r'^Artículo\s+(\d+)([oa])?(?:[-–]([A-ZÑ]))?\.?(?:[-–\s]*(Bis|Ter|Quáter|Quinquies|Sexies))?\.?[- –]',

            # Divisiones estructurales
            # Títulos: "TITULO PRIMERO", "TITULO QUINTO BIS"
            "titulo": r'^T[IÍ]TULO\s+((?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SEPTIMO|SÉPTIMO|OCTAVO|NOVENO|DECIMO|DÉCIMO|ONCE|DOCE|TRECE|CATORCE|QUINCE|DIECISEIS)(?:\s+BIS)?)\s*$',
            # Capítulos: "CAPITULO I", "Capítulo III BIS"
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"Inciso.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "LSS": {
        "nombre": "Ley del Seguro Social",
        "nombre_corto": "Ley del Seguro Social",
        "tipo": "ley",
        "categoria": "laboral",
        "reglamentos": ['RACERF', 'RLSS'],
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LSS.pdf",
        "pdf_path": "backend/etl/data/lss/lss_ley_del_seguro_social.pdf",

        # Patrón para extraer fecha DOF (usa "Últimas Reformas" plural)
        "fecha_dof_patron": r"[ÚU]ltimas\s+[Rr]eformas\s+DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 1.-" o "Artículo 5 A.-" o "Artículo 15-A.-"
            "articulo": r'^Artículo\s+(\d+)([oa])?(?:[-–\s_]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.?[- –]',

            # Divisiones estructurales
            "titulo": r'^T[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "LINFONAVIT": {
        "nombre": "Ley del Instituto del Fondo Nacional de la Vivienda para los Trabajadores",
        "nombre_corto": "Ley del INFONAVIT",
        "tipo": "ley",
        "categoria": "laboral",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIFNVT.pdf",
        "pdf_path": "backend/etl/data/linfonavit/linfonavit_ley_del_infonavit.pdf",

        # Patrón para extraer fecha DOF del encabezado
        "fecha_dof_patron": r"[ÚU]ltima\s+[Rr]eforma\s+DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 1o.-" o "Artículo 18 Bis 1.-" (con número después de Bis)
            "articulo": r'^Artículo\s+(\d+)([oa])?(?:[-–\s_]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies)(?:[-–\s]+(\d+))?)?\.?[- –]',
            "titulo": r'^T[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SEPTIMO|OCTAVO)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',
            "seccion": r'^SECCI[OÓ]N\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "LISSSTE": {
        "nombre": "Ley del Instituto de Seguridad y Servicios Sociales de los Trabajadores del Estado",
        "nombre_corto": "Ley del ISSSTE",
        "tipo": "ley",
        "categoria": "laboral",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISSSTE.pdf",
        "pdf_path": "backend/etl/data/lissste/lissste_ley_del_issste.pdf",

        # Patrón para extraer fecha DOF del encabezado
        "fecha_dof_patron": r"[ÚU]ltima\s+[Rr]eforma\s+DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            "articulo": r'^Artículo\s+(\d+)([oa])?(?:[-–\s_]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.?[- –]',
            "titulo": r'^T[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SEPTIMO|OCTAVO)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',
            "seccion": r'^SECCI[OÓ]N\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "LFDC": {
        "nombre": "Ley Federal de los Derechos del Contribuyente",
        "nombre_corto": "Derechos del Contribuyente",
        "tipo": "ley",
        "categoria": "fiscal",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDC.pdf",
        "pdf_path": "backend/etl/data/lfdc/lfdc.pdf",

        # Formato: "Nueva Ley DOF 23-06-2005"
        "fecha_dof_patron": r"Nueva\s+Ley\s+DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso"],

        "tipo_contenido": "articulo",

        "patrones": {
            # Formato: "Artículo 1o.-" o "Artículo 10.-"
            "articulo": r'^Artículo\s+(\d+)[oa]?\.?[- –]',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
        },

                # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (si aplica)
        "ruido_lineas": [],

        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
            ],
        },
    },

    "LIF": {
        "nombre": "Ley de Ingresos de la Federación para el Ejercicio Fiscal de 2026",
        "nombre_corto": "Ley de Ingresos 2026",
        "tipo": "ley",
        "categoria": "fiscal",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIF_2026.pdf",
        "pdf_path": "backend/etl/data/lif/lif_2026.pdf",

        "ley_base": "LIF",
        "anio": 2026,

        "fecha_dof_patron": r"DOF\s+(\d{1,2})-(\d{1,2})-(\d{4})",

        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        "tipo_contenido": "articulo",

        # Excepciones: artículos con extractor especial
        "excepciones": {
            "1": "texto_plano",  # Estado de resultados presupuestal
        },

        "patrones": {
            # Formato: "Artículo 1o." o "Artículo 10."
            "articulo": r'^Artículo\s+(\d+)[oa]?\.?[- –]',
            "capitulo": r'^Cap[ií]tulo\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
            ],
        },
    },

    # ============================================================
    # REGLAMENTOS
    # ============================================================

    "RCFF": {
        "nombre": "Reglamento del Código Fiscal de la Federación",
        "nombre_corto": "Reglamento CFF",
        "tipo": "reglamento",
        "categoria": "fiscal",
        "reglamento_de": "CFF",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_CFF.pdf",
        "pdf_path": "backend/etl/data/rcff/rcff_reglamento_del_codigo_fiscal_de_la_federacion.pdf",

        "fecha_dof_patron": r"Nuevo Reglamento DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 30.-"
            "articulo": r'^Artículo\s+(\d+)([oa])?(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter|Quinquies|Sexies))?\.?[- –]',

            # Divisiones estructurales
            "titulo": r'^T[IÍ]TULO\s+([IVX]+)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "RACERF": {
        "nombre": "Reglamento de la Ley del Seguro Social en materia de Afiliación, Clasificación de Empresas, Recaudación y Fiscalización",
        "nombre_corto": "Reglamento Afiliación SS",
        "tipo": "reglamento",
        "categoria": "laboral",
        "reglamento_de": "LSS",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LSS_MACERF.pdf",
        "pdf_path": "backend/etl/data/racerf/racerf_reglamento_de_la_ley_del_seguro_social_en_materia.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",
        "divisiones_permitidas": ["titulo", "capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],
        "tipo_contenido": "articulo",
        "patrones": {
            "articulo": r'^Artículo\s+(\d+)\.\s',
            "titulo": r'^T[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+|[UÚ]NICO)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
    },

    "RLFT": {
        "nombre": "Reglamento de los Artículos 121 y 122 de la Ley Federal del Trabajo",
        "nombre_corto": "Reglamento PTU",
        "tipo": "reglamento",
        "categoria": "laboral",
        "reglamento_de": "LFT",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_Art121-122_LFT_050614.pdf",
        "pdf_path": "backend/etl/data/rlft/rlft_reglamento_de_la_ley_federal_del_trabajo.pdf",

        "fecha_dof_patron": r"Nuevo Reglamento DOF (\d{1,2})-(\d{1,2})-(\d{4})",
        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso"],
        "tipo_contenido": "articulo",
        "patrones": {
            "articulo": r'ART[IÍ]CULO\s+(\d+)[oa]?\.-\s',
            "capitulo": r'^CAP[IÍ]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
        },
                # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (si aplica)
        "ruido_lineas": [],
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [r".*DOF"],
        },
    },

    "RLIEPS": {
        "nombre": "Reglamento de la Ley del Impuesto Especial sobre Producción y Servicios",
        "nombre_corto": "Reglamento IEPS",
        "tipo": "reglamento",
        "categoria": "fiscal",
        "reglamento_de": "LIEPS",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LIEPS.pdf",
        "pdf_path": "backend/etl/data/rlieps/rlieps_reglamento_de_la_ley_del_impuesto_especial_sobre_p.pdf",

        "fecha_dof_patron": r"Nuevo Reglamento DOF (\d{1,2})-(\d{1,2})-(\d{4})",
        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso"],
        "tipo_contenido": "articulo",
        "patrones": {
            "articulo": r'^Artículo\s+(\d+)\.?\s',
            "capitulo": r'^Cap[íi]tulo\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
        },
                # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (si aplica)
        "ruido_lineas": [],
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [r".*DOF"],
        },
    },

    "RLSS": {
        "nombre": "Reglamento de la Ley del Seguro Social para Reservas Financieras y Actuariales",
        "nombre_corto": "Reglamento Reservas SS",
        "tipo": "reglamento",
        "categoria": "laboral",
        "reglamento_de": "LSS",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LSS_RFARGFA.pdf",
        "pdf_path": "backend/etl/data/rlss/rlss_reglamento_de_la_ley_del_seguro_social.pdf",

        "fecha_dof_patron": r"Nuevo Reglamento DOF (\d{1,2})-(\d{1,2})-(\d{4})",
        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso"],
        "tipo_contenido": "articulo",
        "patrones": {
            "articulo": r'Artículo\s+(\d+)\.-\s',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
        },
                # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        # Ruido adicional en zona de contenido (si aplica)
        "ruido_lineas": [],
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [r".*DOF"],
        },
    },

    "RLIVA": {
        "nombre": "Reglamento de la Ley del Impuesto al Valor Agregado",
        "nombre_corto": "Reglamento IVA",
        "tipo": "reglamento",
        "categoria": "fiscal",
        "reglamento_de": "LIVA",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LIVA_250914.pdf",
        "pdf_path": "backend/etl/data/rliva/riva_reglamento_del_impuesto_al_valor_agregado.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida (solo capítulos, sin títulos)
        "divisiones_permitidas": ["capitulo"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            "articulo": r'^Artículo\s+(\d+)(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter))?\.?\s',
            "capitulo": r'^Cap[íi]tulo\s+([IVX]+)\s*$',
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
            ],
        },
    },

    "RLISR": {
        "nombre": "Reglamento de la Ley del Impuesto sobre la Renta",
        "nombre_corto": "Reglamento ISR",
        "tipo": "reglamento",
        "categoria": "fiscal",
        "reglamento_de": "LISR",
        "url_fuente": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LISR_060516.pdf",
        "pdf_path": "backend/etl/data/rlisr/risr_reglamento_del_impuesto_sobre_la_renta.pdf",

        "fecha_dof_patron": r"Última Reforma DOF (\d{1,2})-(\d{1,2})-(\d{4})",

        # Estructura jerárquica permitida
        "divisiones_permitidas": ["titulo", "capitulo", "seccion"],
        "parrafos_permitidos": ["texto", "fraccion", "inciso", "numeral"],

        # Tipo de contenido principal
        "tipo_contenido": "articulo",

        # Patrones de detección
        "patrones": {
            # Artículo: "Artículo 1." (sin ordinal)
            "articulo": r'^Artículo\s+(\d+)(?:[-–\s]*([A-Z]))?(?:[-–\s]+(Bis|Ter|Quáter))?\.?\s',

            # Divisiones estructurales
            "titulo": r'^T[IÍ]TULO\s+([IVX]+)\s*$',
            "capitulo": r'^CAP[IÍ]TULO\s+([IVX]+(?:\s+BIS)?|[UÚ]NICO)\s*$',
            "seccion": r'^SECCI[OÓ]N\s+([IVX]+|[UÚ]NICA)\s*$',

            # Fracciones dentro de artículos
            "fraccion": r'^([IVX]+)\.\s+',
            "inciso": r'^([a-z])\)\s+',
            "numeral": r'^(\d{1,2})\.\s+',
        },

        # Ruido a eliminar
        # Filtro por coordenada Y para eliminar header/footer
        "filtro_y": {
            "header_max": 80,   # y < 80: encabezados institucionales
            "footer_min": 720,  # y > 720: números de página
        },

        "ruido_lineas": [],

        # Detección de referencias
        "referencias": {
            "font_italic": True,
            "color_no_negro": True,
            "size_max": 10,
            "patrones": [
                r"Párrafo.*DOF",
                r"Fracción.*DOF",
                r"Artículo.*DOF",
                r"reformad[oa].*DOF",
                r"adicionad[oa].*DOF",
                r"derogad[oa].*DOF",
            ],
        },
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
