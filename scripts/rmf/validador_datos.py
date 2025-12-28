#!/usr/bin/env python3
"""
Validador de datos RMF - Capa de validación pre-importación.

Valida reglas ANTES de guardar a JSON o importar a DB.
Detecta y corrige problemas comunes de extracción.

Uso:
    from validador_datos import ValidadorReglas

    validador = ValidadorReglas()
    regla_limpia, problemas = validador.validar_y_corregir(regla)
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Severidad(Enum):
    ERROR = "ERROR"      # Bloquea importación
    WARNING = "WARNING"  # Permite pero registra
    INFO = "INFO"        # Informativo


@dataclass
class Problema:
    """Problema detectado en una regla."""
    severidad: Severidad
    tipo: str
    mensaje: str
    corregido: bool = False


@dataclass
class ResultadoValidacion:
    """Resultado de validar una regla."""
    numero: str
    es_valido: bool
    problemas: list[Problema] = field(default_factory=list)
    correcciones_aplicadas: int = 0

    def tiene_errores(self) -> bool:
        return any(p.severidad == Severidad.ERROR and not p.corregido for p in self.problemas)

    def resumen(self) -> str:
        if not self.problemas:
            return f"{self.numero}: OK"
        tipos = [f"{p.severidad.value}:{p.tipo}" for p in self.problemas]
        return f"{self.numero}: {', '.join(tipos)}"


class ValidadorReglas:
    """
    Valida y corrige reglas antes de persistir.

    Validaciones:
    - Overflow: contenido captura siguiente regla
    - Nota reforma: contenido incluye nota de reforma siguiente
    - Sin puntuación: contenido no termina con puntuación
    - Título basura: título es fragmento de nota de pie
    - Contenido corto: contenido sospechosamente corto
    """

    # Patrones de overflow (contenido de siguiente regla)
    PATRON_OVERFLOW_REGLA = re.compile(
        r'\n\s*Regla\s+\d{1,2}\.\d{1,2}(?:\.\d{1,3})?\.',
        re.IGNORECASE
    )
    PATRON_OVERFLOW_NUMERO = re.compile(
        r'\n\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\.\s*\n',
    )
    PATRON_OVERFLOW_REFORMA = re.compile(
        r'\n\s*-\s*(?:Reformada|Adicionada|Derogada)\s+en\s+la',
        re.IGNORECASE
    )

    # Patrones de títulos basura
    PATRONES_TITULO_BASURA = [
        r'de dar a conocer el texto actualizado',
        r'Resolución Miscelánea Fiscal',
        r'sustentar legalmente',
        r'NOTA:',
        r'Diario Oficial',
        r'Contribuyente',
        r'^de\s+',  # Empieza con "de " (fragmento)
        r'^los\s+',  # Empieza con "los " (fragmento)
        r'^la\s+',   # Empieza con "la " (fragmento)
    ]

    # Patrones de referencias al final (válido, no es overflow)
    PATRON_REFERENCIAS = re.compile(
        r'\n\s*((?:CFF|LISR|LIVA|LIEPS|LFD|RCFF|RMF|LISH?|LSS|LFT|CPEUM)[\s\d\-,;\.o°]+)+\s*$',
        re.IGNORECASE
    )

    def __init__(self, corregir_auto: bool = True):
        """
        Args:
            corregir_auto: Si True, aplica correcciones automáticas
        """
        self.corregir_auto = corregir_auto
        self.estadisticas = {
            'total': 0,
            'con_problemas': 0,
            'corregidos': 0,
            'errores_sin_corregir': 0,
        }

    def validar_y_corregir(self, regla: dict) -> tuple[dict, ResultadoValidacion]:
        """
        Valida una regla y opcionalmente la corrige.

        Args:
            regla: Dict con numero, titulo, contenido, fracciones, etc.

        Returns:
            tuple: (regla_corregida, resultado_validacion)
        """
        self.estadisticas['total'] += 1
        numero = regla.get('numero', '?')
        resultado = ResultadoValidacion(numero=numero, es_valido=True)

        # Copia para modificar
        regla_corregida = regla.copy()

        # 1. Validar y corregir contenido
        contenido = regla.get('contenido', '')
        contenido, problemas_contenido = self._validar_contenido(contenido, numero)
        resultado.problemas.extend(problemas_contenido)
        regla_corregida['contenido'] = contenido

        # 2. Validar título
        titulo = regla.get('titulo', '')
        titulo, problemas_titulo = self._validar_titulo(titulo, numero)
        resultado.problemas.extend(problemas_titulo)
        regla_corregida['titulo'] = titulo

        # 3. Validar fracciones
        fracciones = regla.get('fracciones', [])
        fracciones_limpias, problemas_fracciones = self._validar_fracciones(fracciones, numero)
        resultado.problemas.extend(problemas_fracciones)
        regla_corregida['fracciones'] = fracciones_limpias

        # Actualizar estadísticas
        if resultado.problemas:
            self.estadisticas['con_problemas'] += 1
            resultado.correcciones_aplicadas = sum(1 for p in resultado.problemas if p.corregido)
            if resultado.correcciones_aplicadas > 0:
                self.estadisticas['corregidos'] += 1

        resultado.es_valido = not resultado.tiene_errores()
        if not resultado.es_valido:
            self.estadisticas['errores_sin_corregir'] += 1

        return regla_corregida, resultado

    def _validar_contenido(self, contenido: str, numero: str) -> tuple[str, list[Problema]]:
        """Valida y corrige el contenido de una regla."""
        problemas = []
        original = contenido

        # 1. Detectar overflow por "Regla X.X"
        match = self.PATRON_OVERFLOW_REGLA.search(contenido)
        if match:
            problemas.append(Problema(
                severidad=Severidad.ERROR,
                tipo="overflow_regla",
                mensaje=f"Contenido incluye siguiente regla en pos {match.start()}"
            ))
            if self.corregir_auto:
                contenido = contenido[:match.start()].rstrip()
                problemas[-1].corregido = True

        # 2. Detectar overflow por número standalone
        match = self.PATRON_OVERFLOW_NUMERO.search(contenido)
        if match:
            # Verificar que no sea el mismo número de la regla
            num_encontrado = match.group(1)
            if num_encontrado != numero:
                problemas.append(Problema(
                    severidad=Severidad.ERROR,
                    tipo="overflow_numero",
                    mensaje=f"Contenido incluye número {num_encontrado}"
                ))
                if self.corregir_auto:
                    contenido = contenido[:match.start()].rstrip()
                    problemas[-1].corregido = True

        # 3. Detectar overflow por nota de reforma
        match = self.PATRON_OVERFLOW_REFORMA.search(contenido)
        if match:
            # Verificar que hay texto significativo antes
            texto_antes = contenido[:match.start()].strip()
            if len(texto_antes) > 50:  # Hay contenido real antes
                problemas.append(Problema(
                    severidad=Severidad.ERROR,
                    tipo="overflow_reforma",
                    mensaje=f"Contenido incluye nota de reforma siguiente"
                ))
                if self.corregir_auto:
                    contenido = texto_antes
                    problemas[-1].corregido = True

        # 4. Limpiar referencias al final (moverlas a campo separado si es necesario)
        # Por ahora solo las dejamos, no son overflow

        # 5. Verificar puntuación final
        contenido_limpio = contenido.rstrip()
        if contenido_limpio and contenido_limpio[-1] not in '.;:!?")':
            # Verificar si termina en referencia (es válido)
            if not self.PATRON_REFERENCIAS.search(contenido):
                problemas.append(Problema(
                    severidad=Severidad.WARNING,
                    tipo="sin_puntuacion",
                    mensaje=f"Contenido no termina con puntuación"
                ))

        # 6. Verificar longitud
        if len(contenido_limpio) < 10 and contenido_limpio:
            problemas.append(Problema(
                severidad=Severidad.WARNING,
                tipo="contenido_corto",
                mensaje=f"Contenido muy corto ({len(contenido_limpio)} chars)"
            ))

        return contenido.strip(), problemas

    def _validar_titulo(self, titulo: str, numero: str) -> tuple[str, list[Problema]]:
        """Valida y corrige el título de una regla."""
        problemas = []

        if not titulo:
            return titulo, problemas

        # Detectar títulos basura
        for patron in self.PATRONES_TITULO_BASURA:
            if re.search(patron, titulo, re.IGNORECASE):
                problemas.append(Problema(
                    severidad=Severidad.ERROR,
                    tipo="titulo_basura",
                    mensaje=f"Título es fragmento/basura: '{titulo[:40]}...'"
                ))
                if self.corregir_auto:
                    titulo = f"Regla {numero}"
                    problemas[-1].corregido = True
                break

        # Verificar longitud mínima
        if len(titulo) < 5 and not titulo.startswith('Regla'):
            problemas.append(Problema(
                severidad=Severidad.WARNING,
                tipo="titulo_corto",
                mensaje=f"Título muy corto: '{titulo}'"
            ))

        return titulo, problemas

    def _validar_fracciones(self, fracciones: list, numero: str) -> tuple[list, list[Problema]]:
        """Valida y corrige fracciones de una regla."""
        problemas = []
        fracciones_limpias = []

        for i, frac in enumerate(fracciones):
            frac_limpia = frac.copy() if isinstance(frac, dict) else frac
            contenido = frac.get('contenido', '') if isinstance(frac, dict) else ''

            # Detectar overflow en fracción
            match = self.PATRON_OVERFLOW_REGLA.search(contenido)
            if match:
                problemas.append(Problema(
                    severidad=Severidad.ERROR,
                    tipo="fraccion_overflow",
                    mensaje=f"Fracción {i+1} incluye siguiente regla"
                ))
                if self.corregir_auto and isinstance(frac_limpia, dict):
                    frac_limpia['contenido'] = contenido[:match.start()].rstrip()
                    problemas[-1].corregido = True

            fracciones_limpias.append(frac_limpia)

        return fracciones_limpias, problemas

    def validar_lote(self, reglas: list[dict]) -> tuple[list[dict], list[ResultadoValidacion]]:
        """
        Valida un lote de reglas.

        Returns:
            tuple: (reglas_corregidas, resultados)
        """
        reglas_corregidas = []
        resultados = []

        for regla in reglas:
            regla_limpia, resultado = self.validar_y_corregir(regla)
            reglas_corregidas.append(regla_limpia)
            resultados.append(resultado)

        return reglas_corregidas, resultados

    def resumen(self) -> str:
        """Retorna resumen de estadísticas."""
        s = self.estadisticas
        return (
            f"Validación: {s['total']} reglas, "
            f"{s['con_problemas']} con problemas, "
            f"{s['corregidos']} corregidos, "
            f"{s['errores_sin_corregir']} errores sin corregir"
        )


def validar_json(input_path: str, output_path: str = None) -> dict:
    """
    Valida un archivo JSON de reglas.

    Args:
        input_path: Ruta al JSON de entrada
        output_path: Ruta al JSON de salida (opcional)

    Returns:
        dict: Estadísticas de validación
    """
    import json

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    validador = ValidadorReglas(corregir_auto=True)
    reglas = data.get('reglas', [])

    print(f"Validando {len(reglas)} reglas...")

    reglas_limpias, resultados = validador.validar_lote(reglas)

    # Mostrar problemas
    problemas_por_tipo = {}
    for r in resultados:
        for p in r.problemas:
            key = f"{p.severidad.value}:{p.tipo}"
            if key not in problemas_por_tipo:
                problemas_por_tipo[key] = []
            problemas_por_tipo[key].append(r.numero)

    print(f"\n{validador.resumen()}")
    print("\nProblemas por tipo:")
    for tipo, numeros in sorted(problemas_por_tipo.items()):
        print(f"  {tipo}: {len(numeros)} reglas")
        if len(numeros) <= 5:
            print(f"    {', '.join(numeros)}")
        else:
            print(f"    {', '.join(numeros[:5])}... y {len(numeros)-5} más")

    # Guardar si se especificó output
    if output_path:
        data['reglas'] = reglas_limpias
        data['validacion'] = {
            'total': validador.estadisticas['total'],
            'con_problemas': validador.estadisticas['con_problemas'],
            'corregidos': validador.estadisticas['corregidos'],
            'problemas_por_tipo': {k: len(v) for k, v in problemas_por_tipo.items()}
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\nGuardado en: {output_path}")

    return validador.estadisticas


if __name__ == "__main__":
    import sys
    from pathlib import Path

    base_dir = Path(__file__).parent.parent.parent
    input_path = base_dir / "doc/rmf/rmf_hibrido.json"
    output_path = base_dir / "doc/rmf/rmf_validado.json"

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])

    validar_json(str(input_path), str(output_path))
