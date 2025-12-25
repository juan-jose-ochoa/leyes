#!/usr/bin/env python3
"""
URLs conocidas de leyes y reglamentos federales de México.
Fuente: Cámara de Diputados - https://www.diputados.gob.mx/LeyesBiblio/

Estas URLs son descubiertas parseando el sitio oficial.
Se mantienen como fallback para documentos objetivo específicos.
"""

from datetime import datetime

YEAR = datetime.now().year

# URLs directas conocidas de la Cámara de Diputados
# Basadas en la estructura del sitio: /LeyesBiblio/pdf/NOMBRE.pdf

LEYES_CAMARA_DIPUTADOS = [
    # Código Fiscal de la Federación
    {
        "nombre": "Código Fiscal de la Federación",
        "nombre_corto": "CFF",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Impuesto sobre la Renta
    {
        "nombre": "Ley del Impuesto sobre la Renta",
        "nombre_corto": "LISR",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Impuesto al Valor Agregado
    {
        "nombre": "Ley del Impuesto al Valor Agregado",
        "nombre_corto": "LIVA",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Impuesto Especial sobre Producción y Servicios
    {
        "nombre": "Ley del Impuesto Especial sobre Producción y Servicios",
        "nombre_corto": "LIEPS",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIEPS.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley Federal de Derechos
    {
        "nombre": "Ley Federal de Derechos",
        "nombre_corto": "LFD",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFD.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley Federal de los Derechos del Contribuyente
    {
        "nombre": "Ley Federal de los Derechos del Contribuyente",
        "nombre_corto": "LFDC",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDC.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Servicio de Administración Tributaria
    {
        "nombre": "Ley del Servicio de Administración Tributaria",
        "nombre_corto": "LSAT",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LSAT.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley Aduanera
    {
        "nombre": "Ley Aduanera",
        "nombre_corto": "LA",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LA.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley de los Impuestos Generales de Importación y de Exportación
    {
        "nombre": "Ley de los Impuestos Generales de Importación y de Exportación",
        "nombre_corto": "LIGIE",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIGIE.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley Federal del Trabajo
    {
        "nombre": "Ley Federal del Trabajo",
        "nombre_corto": "LFT",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Seguro Social
    {
        "nombre": "Ley del Seguro Social",
        "nombre_corto": "LSS",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LSS.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Instituto del Fondo Nacional de la Vivienda para los Trabajadores
    {
        "nombre": "Ley del Instituto del Fondo Nacional de la Vivienda para los Trabajadores",
        "nombre_corto": "LINFONAVIT",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/Linfonavit.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley de los Sistemas de Ahorro para el Retiro
    {
        "nombre": "Ley de los Sistemas de Ahorro para el Retiro",
        "nombre_corto": "LSAR",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LSAR.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley del Instituto Mexicano del Seguro Social (puede ser la misma que LSS)
    {
        "nombre": "Ley del Instituto Mexicano del Seguro Social",
        "nombre_corto": "LIMSS",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LSS.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Ley de Ingresos de la Federación
    {
        "nombre": f"Ley de Ingresos de la Federación para el Ejercicio Fiscal {YEAR}",
        "nombre_corto": f"LIF_{YEAR}",
        "url": f"https://www.diputados.gob.mx/LeyesBiblio/pdf/LIF_{YEAR}.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
    # Presupuesto de Egresos
    {
        "nombre": f"Presupuesto de Egresos de la Federación para el Ejercicio Fiscal {YEAR}",
        "nombre_corto": f"PEF_{YEAR}",
        "url": f"https://www.diputados.gob.mx/LeyesBiblio/pdf/PEF_{YEAR}.pdf",
        "tipo": "ley",
        "autoridad": "CDD",
    },
]

# Reglamentos de la Cámara de Diputados
REGLAMENTOS_CAMARA_DIPUTADOS = [
    # Reglamento del CFF
    {
        "nombre": "Reglamento del Código Fiscal de la Federación",
        "nombre_corto": "RCFF",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_CFF.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de la LISR
    {
        "nombre": "Reglamento de la Ley del Impuesto sobre la Renta",
        "nombre_corto": "RLISR",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LISR.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de la LIVA
    {
        "nombre": "Reglamento de la Ley del Impuesto al Valor Agregado",
        "nombre_corto": "RLIVA",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LIVA.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de la LIEPS
    {
        "nombre": "Reglamento de la Ley del Impuesto Especial sobre Producción y Servicios",
        "nombre_corto": "RLIEPS",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LIEPS.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de la Ley Aduanera
    {
        "nombre": "Reglamento de la Ley Aduanera",
        "nombre_corto": "RLA",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_Aduanera.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de la LFT
    {
        "nombre": "Reglamento Federal de Seguridad y Salud en el Trabajo",
        "nombre_corto": "RFSST",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_FSST.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento de Inscripción IMSS
    {
        "nombre": "Reglamento de la Ley del Seguro Social en Materia de Afiliación",
        "nombre_corto": "RACERF",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LSS_MACERF.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
    # Reglamento Interior del SAT
    {
        "nombre": "Reglamento Interior del Servicio de Administración Tributaria",
        "nombre_corto": "RISAT",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_SAT.pdf",
        "tipo": "reglamento",
        "autoridad": "CDD",
    },
]

# URLs del SAT para misceláneas
# Nota: Estas URLs cambian anualmente, el script las descubre
MISCELANEAS_SAT = [
    {
        "nombre": f"Resolución Miscelánea Fiscal {YEAR}",
        "nombre_corto": f"RMF_{YEAR}",
        "url": f"https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1579314651133&ssbinary=true",  # URL ejemplo, cambia
        "tipo": "miscelanea",
        "autoridad": "SAT",
        "buscar_en": "https://www.sat.gob.mx/normatividad/98887/resolucion-miscelanea-fiscal",
    },
    {
        "nombre": f"Reglas Generales de Comercio Exterior {YEAR}",
        "nombre_corto": f"RGCE_{YEAR}",
        "url": "",  # Debe descubrirse
        "tipo": "miscelanea",
        "autoridad": "SAT",
        "buscar_en": "https://www.sat.gob.mx/normatividad/82617/reglas-generales-de-comercio-exterior",
    },
    {
        "nombre": f"Resolución de Facilidades Administrativas {YEAR}",
        "nombre_corto": f"RFA_{YEAR}",
        "url": "",  # Debe descubrirse
        "tipo": "miscelanea",
        "autoridad": "SAT",
        "buscar_en": "https://www.sat.gob.mx/normatividad/58917/resolucion-de-facilidades-administrativas",
    },
]


def obtener_todas_urls_conocidas():
    """Retorna todas las URLs conocidas como lista unificada."""
    todas = []
    todas.extend(LEYES_CAMARA_DIPUTADOS)
    todas.extend(REGLAMENTOS_CAMARA_DIPUTADOS)
    # Las misceláneas se agregan solo si tienen URL
    for misc in MISCELANEAS_SAT:
        if misc.get("url"):
            todas.append(misc)
    return todas


# Patrones de nombres de archivos en el sitio de Diputados
# Para descubrimiento automático
PATRONES_ARCHIVOS_DIPUTADOS = {
    # Leyes fiscales
    "CFF": ["CFF", "Codigo_Fiscal"],
    "LISR": ["LISR", "ISR"],
    "LIVA": ["LIVA", "IVA"],
    "LIEPS": ["LIEPS", "IEPS"],
    "LFD": ["LFD", "Ley_Federal_Derechos"],
    "LFDC": ["LFDC", "Derechos_Contribuyente"],
    "LSAT": ["LSAT", "SAT"],
    "LA": ["LA", "Aduanera"],
    "LIGIE": ["LIGIE"],
    # Leyes laborales
    "LFT": ["LFT", "Trabajo"],
    "LSS": ["LSS", "Seguro_Social"],
    "LINFONAVIT": ["Linfonavit", "INFONAVIT"],
    "LSAR": ["LSAR", "Ahorro_Retiro"],
}
