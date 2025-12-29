#!/usr/bin/env python3
"""
Validador de extracción para esquema leyesmx.

Compara la extracción actual contra la estructura esperada almacenada en BD.
NO modifica ningún archivo ni base de datos.

Uso:
    python backend/scripts/validar.py CFF
    python backend/scripts/validar.py CFF --detalle
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import psycopg2

from config import get_config

BASE_DIR = Path(__file__).parent.parent.parent

# Configuración de BD desde variables de entorno
DB_CONFIG = {
    "host": os.environ.get("LEYESMX_DB_HOST", "localhost"),
    "port": os.environ.get("LEYESMX_DB_PORT", "5432"),
    "database": os.environ.get("LEYESMX_DB_NAME", "digiapps"),
    "user": os.environ.get("LEYESMX_DB_USER", "leyesmx"),
    "password": os.environ.get("LEYESMX_DB_PASSWORD", "leyesmx"),
}


@dataclass
class DiferenciaArticulo:
    """Diferencia encontrada en un artículo."""
    titulo: str
    capitulo: str
    numero: str
    tipo: str  # 'faltante', 'extra', 'derogado_no_esperado'
    pagina: Optional[int] = None


@dataclass
class ResultadoValidacion:
    """Resultado de validación por título/capítulo."""
    titulo: str
    capitulo: str
    esperados: int
    encontrados: int
    faltantes: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.faltantes) == 0 and len(self.extras) == 0


class Validador:
    """Validador de extracción contra estructura esperada."""

    def __init__(self, codigo: str):
        self.codigo = codigo.upper()
        self.config = get_config(self.codigo)
        self.resultados: list[ResultadoValidacion] = []
        self.diferencias: list[DiferenciaArticulo] = []

        # Rutas
        if self.config.get("pdf_path"):
            self.output_dir = BASE_DIR / Path(self.config["pdf_path"]).parent
        else:
            raise ValueError("pdf_path no configurado")

        self.contenido_path = self.output_dir / "contenido.json"
        self.fuente_estructura = None  # 'bd' o 'archivo'

    def cargar_estructura_bd(self) -> bool:
        """Carga estructura esperada desde la base de datos."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                SELECT estructura_esperada, fecha_verificacion
                FROM leyesmx.leyes
                WHERE codigo = %s
            """, (self.codigo,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row and row[0]:
                self.esperada = row[0]
                self.fecha_verificacion = row[1]
                self.fuente_estructura = 'bd'
                return True
            return False
        except Exception as e:
            print(f"   Aviso: No se pudo conectar a BD ({e})")
            return False

    def cargar_estructura_archivo(self) -> bool:
        """Carga estructura esperada desde archivo JSON (fallback)."""
        archivo = self.output_dir / "estructura_esperada.json"
        if not archivo.exists():
            return False
        with open(archivo, 'r', encoding='utf-8') as f:
            self.esperada = json.load(f)
        self.fuente_estructura = 'archivo'
        return True

    def cargar_archivos(self) -> bool:
        """Carga los archivos necesarios."""
        # Primero intentar BD, luego archivo
        if not self.cargar_estructura_bd():
            print("   BD no disponible, usando archivo local...")
            if not self.cargar_estructura_archivo():
                print(f"ERROR: No hay estructura esperada en BD ni en archivo")
                print("       Ejecuta: python backend/scripts/extraer_mapa.py", self.codigo)
                return False

        if not self.contenido_path.exists():
            print(f"ERROR: {self.contenido_path.name} no existe")
            print("       Ejecuta primero: python backend/scripts/extraer.py", self.codigo)
            return False

        with open(self.contenido_path, 'r', encoding='utf-8') as f:
            self.contenido = json.load(f)

        return True

    def _normalizar(self, numero: str) -> str:
        """Normaliza número de artículo para comparación.

        Convierte ambos formatos a un formato canónico:
        - '4o A' -> '4o-A'
        - '4o-A' -> '4o-A'
        - '29 Bis' -> '29 Bis'
        - '29-Bis' -> '29 Bis'
        - '17 H Bis' -> '17-H Bis'
        """
        import re
        numero = numero.strip()

        # Normalizar espacios múltiples
        numero = re.sub(r'\s+', ' ', numero)

        # Convertir "BIS" -> "Bis", "TER" -> "Ter", etc.
        numero = re.sub(r'\b(BIS|TER|QUÁTER|QUINQUIES|SEXIES)\b',
                       lambda m: m.group(1).capitalize(), numero, flags=re.IGNORECASE)

        # Normalizar separador antes de letras sueltas (A, B, C...) pero NO antes de sufijos
        # "4o A" -> "4o-A", "14 A" -> "14-A", pero "29 Bis" se mantiene
        # Letra suelta = letra seguida de espacio+sufijo O fin de string
        def replace_letter(m):
            base = m.group(1)
            letter = m.group(2)
            after = m.group(3) or ''
            return f'{base}-{letter}{after}'

        numero = re.sub(
            r'(\d+[oa]?)\s+([A-Z])(\s+(?:Bis|Ter|Quáter|Quinquies|Sexies)|$)',
            replace_letter, numero)

        # Normalizar separador antes de sufijos (Bis, Ter...)
        # "29-Bis" -> "29 Bis", "17-H-Bis" -> "17-H Bis"
        numero = re.sub(r'-(?=Bis|Ter|Quáter|Quinquies|Sexies)', ' ', numero)

        return numero

    def obtener_articulos_extraidos(self) -> set[str]:
        """Obtiene el conjunto de artículos extraídos."""
        return {self._normalizar(a["numero"]) for a in self.contenido.get("articulos", [])}

    def obtener_articulos_esperados(self) -> dict[str, dict]:
        """Obtiene artículos esperados organizados por título/capítulo."""
        resultado = {}
        for titulo_num, titulo_data in self.esperada.get("titulos", {}).items():
            for cap_num, cap_data in titulo_data.get("capitulos", {}).items():
                key = f"{titulo_num}.{cap_num}"
                resultado[key] = {
                    "titulo": titulo_num,
                    "capitulo": cap_num,
                    "articulos": {self._normalizar(a) for a in cap_data.get("articulos", [])}
                }
        return resultado

    def validar_por_capitulo(self):
        """Valida artículos por capítulo."""
        extraidos = self.obtener_articulos_extraidos()
        esperados_por_cap = self.obtener_articulos_esperados()

        todos_esperados = set()
        for cap_data in esperados_por_cap.values():
            todos_esperados.update(cap_data["articulos"])

        # Validar cada capítulo
        for key, cap_data in esperados_por_cap.items():
            esperados = cap_data["articulos"]
            encontrados = esperados & extraidos

            faltantes = list(esperados - extraidos)
            extras = []  # Los extras se calculan globalmente

            resultado = ResultadoValidacion(
                titulo=cap_data["titulo"],
                capitulo=cap_data["capitulo"],
                esperados=len(esperados),
                encontrados=len(encontrados),
                faltantes=sorted(faltantes, key=self._sort_articulo),
                extras=extras
            )
            self.resultados.append(resultado)

            # Registrar diferencias
            for num in faltantes:
                self.diferencias.append(DiferenciaArticulo(
                    titulo=cap_data["titulo"],
                    capitulo=cap_data["capitulo"],
                    numero=num,
                    tipo="faltante"
                ))

        # Detectar artículos extra (no esperados)
        derogados = {self._normalizar(d) for d in self.esperada.get("derogados", [])}
        extras_globales = extraidos - todos_esperados - derogados

        for num in extras_globales:
            self.diferencias.append(DiferenciaArticulo(
                titulo="?",
                capitulo="?",
                numero=num,
                tipo="extra"
            ))

    def _sort_articulo(self, num: str) -> tuple:
        """Ordena artículos numéricamente."""
        import re
        match = re.match(r'(\d+)', num)
        if match:
            return (int(match.group(1)), num)
        return (999999, num)

    def ejecutar(self) -> bool:
        """Ejecuta todas las validaciones."""
        self.validar_por_capitulo()
        return all(r.ok for r in self.resultados) and len(self.diferencias) == 0

    def imprimir_reporte(self, detalle: bool = False):
        """Imprime el reporte de validación."""
        print("\n" + "=" * 70)
        print("REPORTE DE VALIDACIÓN")
        print("=" * 70)

        # Info de referencia
        if self.fuente_estructura == 'bd':
            print(f"\nReferencia: leyesmx.leyes.estructura_esperada (BD)")
            if hasattr(self, 'fecha_verificacion') and self.fecha_verificacion:
                print(f"Verificado: {self.fecha_verificacion}")
        else:
            print(f"\nReferencia: estructura_esperada.json (archivo)")
        print(f"Versión:    {self.esperada.get('version', 'N/A')}")
        print(f"Fuente:     {self.esperada.get('fuente', 'N/A')}")

        # Estadísticas esperadas
        stats = self.esperada.get("estadisticas", {})
        print(f"\nEsperado:   {stats.get('articulos_vigentes', '?')} artículos vigentes")

        # Estadísticas extraídas
        total_extraidos = len(self.contenido.get("articulos", []))
        print(f"Extraído:   {total_extraidos} artículos")

        # Resultados por capítulo
        print("\n" + "-" * 70)
        print(f"{'Título':<10} {'Capítulo':<10} {'Esperado':<10} {'Encontrado':<12} {'Estado':<10}")
        print("-" * 70)

        total_faltantes = 0
        total_extras = 0

        for r in self.resultados:
            estado = "OK" if r.ok else "FALLO"
            marca = "✓" if r.ok else "✗"
            print(f"{marca} {r.titulo:<8} {r.capitulo:<10} {r.esperados:<10} {r.encontrados:<12} {estado:<10}")

            if detalle and r.faltantes:
                print(f"  └─ Faltantes: {', '.join(r.faltantes[:5])}{'...' if len(r.faltantes) > 5 else ''}")

            total_faltantes += len(r.faltantes)

        # Extras globales
        extras = [d for d in self.diferencias if d.tipo == "extra"]
        if extras:
            print("-" * 70)
            print(f"✗ EXTRAS (no esperados): {len(extras)} artículos")
            if detalle:
                nums = sorted([d.numero for d in extras], key=self._sort_articulo)
                print(f"  └─ {', '.join(nums[:10])}{'...' if len(nums) > 10 else ''}")
            total_extras = len(extras)

        # Resumen
        print("-" * 70)
        total_ok = sum(1 for r in self.resultados if r.ok)
        total = len(self.resultados)

        print(f"\nRESUMEN:")
        print(f"  Capítulos: {total_ok}/{total} OK")
        print(f"  Faltantes: {total_faltantes}")
        print(f"  Extras:    {total_extras}")

        if total_faltantes == 0 and total_extras == 0:
            print("\n✓ VALIDACIÓN EXITOSA - Extracción coincide con estructura esperada")
        else:
            print("\n✗ VALIDACIÓN FALLIDA - Revisar diferencias")

        # Aprobaciones pendientes
        aprobaciones = self.esperada.get("aprobaciones", [])
        pendientes = [a for a in aprobaciones if a.get("estado") == "pendiente_revision"]
        if pendientes:
            print("\n⚠ ESTRUCTURA PENDIENTE DE APROBACIÓN:")
            for a in pendientes:
                print(f"  - {a.get('fecha')}: {a.get('notas')}")

        print()


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/validar.py <CODIGO> [--detalle]")
        sys.exit(1)

    codigo = sys.argv[1].upper()
    detalle = '--detalle' in sys.argv

    print("=" * 70)
    print(f"VALIDADOR LEYESMX: {codigo}")
    print("=" * 70)
    print("\nEste proceso NO modifica ningún archivo ni base de datos.")

    try:
        validador = Validador(codigo)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("\n1. Cargando archivos...")
    if not validador.cargar_archivos():
        sys.exit(1)

    if validador.fuente_estructura == 'bd':
        print(f"   estructura_esperada (BD)")
    else:
        print(f"   estructura_esperada.json (archivo)")
    print(f"   {validador.contenido_path.name} (extracción)")

    print("\n2. Validando artículos por capítulo...")
    todo_ok = validador.ejecutar()

    validador.imprimir_reporte(detalle)

    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
