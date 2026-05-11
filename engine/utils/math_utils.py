"""
engine/utils/math_utils.py
==========================
Utilidades matemáticas compartidas por todos los módulos del motor.
"""

from __future__ import annotations

import math
import hashlib
import json
from typing import Callable
import sympy as sp


# ─── Validación numérica ─────────────────────────────────────────────────────

def is_close(
    student: float,
    expected: float,
    tolerance: float = 1e-4,
) -> bool:
    """
    Compara dos floats con tolerancia absoluta.
    NUNCA usa == para comparar flotantes.

    Args:
        student:   Respuesta del estudiante.
        expected:  Respuesta correcta.
        tolerance: Margen de error aceptable.

    Returns:
        True si |student - expected| <= tolerance.
    """
    return abs(student - expected) <= tolerance


def relative_error(approx: float, exact: float) -> float:
    """
    Calcula el error relativo porcentual.

    Returns:
        Error relativo en porcentaje (0–100+).
        Retorna inf si exact == 0.
    """
    if exact == 0:
        return float("inf")
    return abs((approx - exact) / exact) * 100.0


def absolute_error(approx: float, exact: float) -> float:
    """Calcula el error absoluto."""
    return abs(approx - exact)


def precision_score(
    student: float,
    expected: float,
    tolerance: float = 1e-4,
) -> float:
    """
    Retorna un multiplicador de precisión entre 0.0 y 1.0.

    - 1.0  → dentro de tolerancia estricta
    - 0.75 → dentro de 10× tolerancia
    - 0.5  → dentro de 100× tolerancia
    - 0.0  → fuera de rango
    """
    err = abs(student - expected)
    if err <= tolerance:
        return 1.0
    if err <= tolerance * 10:
        return 0.75
    if err <= tolerance * 100:
        return 0.5
    return 0.0


# ─── Evaluación simbólica ─────────────────────────────────────────────────────

def parse_function(expr_str: str, var: str = "x") -> Callable[[float], float]:
    """
    Convierte un string a función evaluable numéricamente.

    Args:
        expr_str: Expresión matemática, e.g. "x**3 - x - 2"
        var:      Nombre de la variable (por defecto "x").

    Returns:
        Función Python f(x) -> float.

    Raises:
        ValueError: Si la expresión no se puede parsear.
    """
    try:
        sym_var = sp.Symbol(var)
        expr = sp.sympify(expr_str)
        return sp.lambdify(sym_var, expr, modules=["math"])
    except Exception as exc:
        raise ValueError(f"No se pudo parsear '{expr_str}': {exc}") from exc


def derivative(expr_str: str, var: str = "x") -> Callable[[float], float]:
    """
    Calcula la derivada simbólica y la retorna como función evaluable.
    """
    sym_var = sp.Symbol(var)
    expr = sp.sympify(expr_str)
    deriv = sp.diff(expr, sym_var)
    return sp.lambdify(sym_var, deriv, modules=["math"])


def round_sig(value: float, sig: int = 6) -> float:
    """Redondea a `sig` cifras significativas."""
    if value == 0:
        return 0.0
    magnitude = math.floor(math.log10(abs(value)))
    factor = 10 ** (sig - 1 - magnitude)
    return round(value * factor) / factor


# ─── Generación de hashes ─────────────────────────────────────────────────────

def exercise_hash(params: dict) -> str:
    """
    Genera un hash SHA-256 de 8 caracteres para identificar un ejercicio.
    Permite deduplicar preguntas repetidas.
    """
    raw = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


# ─── Verificación de intervalos ──────────────────────────────────────────────

def has_sign_change(f: Callable[[float], float], a: float, b: float) -> bool:
    """
    Verifica si f(a) y f(b) tienen signos opuestos (condición Bolzano).
    Necesario para bisección y falsa posición.
    """
    fa, fb = f(a), f(b)
    if not (math.isfinite(fa) and math.isfinite(fb)):
        return False
    return fa * fb < 0


def find_bracket(
    f: Callable[[float], float],
    start: float = -10.0,
    end: float = 10.0,
    step: float = 0.5,
) -> tuple[float, float] | None:
    """
    Busca un intervalo [a, b] donde f cambia de signo.
    Útil para generar ejercicios con raíz garantizada.

    Returns:
        Tupla (a, b) o None si no encuentra cambio de signo.
    """
    a = start
    while a + step <= end:
        b = a + step
        if has_sign_change(f, a, b):
            return (a, b)
        a = b
    return None
