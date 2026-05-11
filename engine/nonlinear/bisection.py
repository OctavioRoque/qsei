"""
engine/nonlinear/bisection.py
==============================
Solver completo del método de bisección.
Implementa: solver, validador y generador procedural de ejercicios.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable

from engine.utils.base_solver import (
    BaseSolver,
    BaseValidator,
    BaseGenerator,
    SolverResult,
    ValidationResult,
    ExerciseBundle,
)
from engine.utils.math_utils import (
    is_close,
    parse_function,
    precision_score,
    has_sign_change,
    find_bracket,
    exercise_hash,
    round_sig,
)


# ─── Solver ───────────────────────────────────────────────────────────────────

class BisectionSolver(BaseSolver):
    """
    Implementa el método de bisección para encontrar raíces
    de ecuaciones continuas en un intervalo [a, b].

    Condición de Bolzano: f(a) * f(b) < 0.
    """

    MAX_ITER: int = 200

    @property
    def method_key(self) -> str:
        return "biseccion"

    @property
    def method_name_es(self) -> str:
        return "Bisección"

    def solve(
        self,
        f: Callable[[float], float],
        a: float,
        b: float,
        tol: float = 1e-6,
        max_iter: int = 100,
    ) -> SolverResult:
        """
        Ejecuta el método de bisección.

        Args:
            f:        Función continua en [a, b].
            a:        Extremo izquierdo del intervalo.
            b:        Extremo derecho del intervalo.
            tol:      Tolerancia de convergencia.
            max_iter: Número máximo de iteraciones.

        Returns:
            SolverResult con el historial completo de iteraciones.
        """
        if not has_sign_change(f, a, b):
            return SolverResult(
                converged=False,
                root=None,
                iterations=[],
                error_final=float("inf"),
                message="f(a) y f(b) deben tener signos opuestos (Teorema de Bolzano).",
            )

        iterations: list[dict[str, Any]] = []
        prev_c: float | None = None

        for i in range(1, max_iter + 1):
            c = (a + b) / 2.0
            fc = f(c)
            fa = f(a)

            # Error relativo (desde iteración 2)
            if prev_c is not None and c != 0:
                error = abs((c - prev_c) / c) * 100.0
            else:
                error = float("inf")

            iterations.append({
                "iteration": i,
                "a": round_sig(a),
                "b": round_sig(b),
                "c": round_sig(c),
                "f_a": round_sig(fa),
                "f_c": round_sig(fc),
                "error_pct": round_sig(error) if math.isfinite(error) else None,
            })

            # Convergencia
            if abs(fc) <= tol or (prev_c is not None and abs(c - prev_c) <= tol):
                return SolverResult(
                    converged=True,
                    root=c,
                    iterations=iterations,
                    error_final=abs(fc),
                    message=f"Convergió en {i} iteraciones. Raíz ≈ {round_sig(c)}",
                )

            # Actualizar intervalo
            if fa * fc < 0:
                b = c
            else:
                a = c

            prev_c = c

        return SolverResult(
            converged=False,
            root=c,
            iterations=iterations,
            error_final=abs(f(c)),
            message=f"No convergió en {max_iter} iteraciones. Última aproximación: {round_sig(c)}",
        )


# ─── Validador ────────────────────────────────────────────────────────────────

class BisectionValidator(BaseValidator):
    """
    Valida respuestas del estudiante para ejercicios de bisección.
    Soporta validar: raíz final, valor en iteración N, error en iteración N.
    """

    def validate(
        self,
        student_answer: Any,
        solver_result: SolverResult,
        question_context: dict[str, Any],
    ) -> ValidationResult:
        """
        Valida la respuesta según el tipo de pregunta en question_context.

        question_context esperado:
            ask_for: "root" | "iteration_c" | "iteration_error"
            iteration: int  (solo para ask_for != "root")
        """
        ask_for: str = question_context.get("ask_for", "root")

        try:
            student_val = float(str(student_answer).replace(",", "."))
        except (ValueError, TypeError):
            return ValidationResult(
                is_correct=False,
                precision_score=0.0,
                student_value=None,
                expected_value=None,
                absolute_error=float("inf"),
                feedback="La respuesta ingresada no es un número válido.",
            )

        # Determinar valor esperado
        expected: float | None = None
        feedback_prefix: str = ""

        if ask_for == "root":
            expected = solver_result.root
            feedback_prefix = "La raíz aproximada"

        elif ask_for == "iteration_c":
            n = question_context.get("iteration", 1)
            if n <= len(solver_result.iterations):
                expected = solver_result.iterations[n - 1]["c"]
            feedback_prefix = f"El punto medio en la iteración {n}"

        elif ask_for == "iteration_error":
            n = question_context.get("iteration", 2)
            if n <= len(solver_result.iterations):
                err = solver_result.iterations[n - 1].get("error_pct")
                expected = err
            feedback_prefix = f"El error relativo en la iteración {n}"

        if expected is None:
            return ValidationResult(
                is_correct=False,
                precision_score=0.0,
                student_value=student_val,
                expected_value=None,
                absolute_error=float("inf"),
                feedback="No se pudo determinar el valor esperado para esta pregunta.",
            )

        abs_err = abs(student_val - expected)
        ps = precision_score(student_val, expected, self.tolerance)
        correct = is_close(student_val, expected, self.tolerance)

        if correct:
            fb = f"✅ ¡Correcto! {feedback_prefix} es {round_sig(expected):.6g}."
        elif ps >= 0.75:
            fb = (
                f"⚠️ Casi correcto. {feedback_prefix} es {round_sig(expected):.6g}. "
                f"Tu respuesta ({student_val:.6g}) tiene un error de {abs_err:.2e}. "
                "Revisa el número de cifras significativas."
            )
        else:
            fb = (
                f"❌ Incorrecto. {feedback_prefix} es {round_sig(expected):.6g}. "
                f"Tu respuesta fue {student_val:.6g} (error: {abs_err:.2e}). "
                "Recuerda: c = (a + b) / 2 en cada iteración."
            )

        return ValidationResult(
            is_correct=correct,
            precision_score=ps,
            student_value=student_val,
            expected_value=expected,
            absolute_error=abs_err,
            feedback=fb,
        )


# ─── Generador procedural ─────────────────────────────────────────────────────

# Plantillas de funciones organizadas por dificultad
_FUNCTION_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "easy": [
        {"expr": "x - {c}", "params": {"c": (1, 5)}, "var": "x"},
        {"expr": "x**2 - {c}", "params": {"c": (2, 9)}, "var": "x"},
        {"expr": "x**3 - {c}", "params": {"c": (2, 8)}, "var": "x"},
    ],
    "medium": [
        {"expr": "x**3 - x - {c}", "params": {"c": (1, 4)}, "var": "x"},
        {"expr": "x**2 - {a}*x + {b}", "params": {"a": (3, 6), "b": (1, 5)}, "var": "x"},
        {"expr": "x**3 + {a}*x**2 - {b}", "params": {"a": (1, 3), "b": (5, 15)}, "var": "x"},
        {"expr": "{a}*x - exp(x) + {b}", "params": {"a": (2, 4), "b": (1, 3)}, "var": "x"},
    ],
    "hard": [
        {"expr": "x**4 - {a}*x**3 + {b}", "params": {"a": (2, 5), "b": (1, 4)}, "var": "x"},
        {"expr": "sin(x) - {a}*x + {b}", "params": {"a": (0.5, 1.5), "b": (0.1, 0.5)}, "var": "x"},
        {"expr": "cos(x) - x", "params": {}, "var": "x"},
        {"expr": "log(x) - {a}*x + {b}", "params": {"a": (0.2, 0.8), "b": (1, 3)}, "var": "x"},
    ],
    "expert": [
        {"expr": "x**5 - {a}*x**3 + {b}*x - {c}",
         "params": {"a": (2, 5), "b": (1, 4), "c": (1, 3)}, "var": "x"},
        {"expr": "exp(-x) - sin(x) + {a}", "params": {"a": (0.1, 0.5)}, "var": "x"},
        {"expr": "x**2 * sin(x) - {a}", "params": {"a": (0.5, 2.0)}, "var": "x"},
    ],
}

_EXERCISE_TYPES = [
    "numeric_input",     # 50%: ingresar la raíz
    "multiple_choice",   # 30%: seleccionar la raíz entre opciones
    "fill_step",         # 20%: completar valor en iteración N
]

_TYPE_WEIGHTS = [0.5, 0.3, 0.2]


def _difficulty_to_tier(difficulty: int) -> str:
    if difficulty <= 3:
        return "easy"
    if difficulty <= 6:
        return "medium"
    if difficulty <= 8:
        return "hard"
    return "expert"


def _random_params(template: dict) -> dict[str, float]:
    """Genera valores aleatorios para los parámetros de la plantilla."""
    result: dict[str, float] = {}
    for key, (lo, hi) in template.get("params", {}).items():
        # Si ambos son enteros, generar entero; si no, float
        if isinstance(lo, int) and isinstance(hi, int):
            result[key] = random.randint(lo, hi)
        else:
            result[key] = round(random.uniform(lo, hi), 2)
    return result


def _build_expr(template: dict, rparams: dict) -> str:
    """Sustituye parámetros en la expresión de la plantilla."""
    expr = template["expr"]
    for k, v in rparams.items():
        expr = expr.replace(f"{{{k}}}", str(v))
    return expr


class BisectionGenerator(BaseGenerator):
    """
    Genera ejercicios procedurales de bisección con dificultad escalable.

    Para cada ejercicio:
    1. Selecciona plantilla según dificultad.
    2. Genera parámetros aleatorios.
    3. Verifica que existe una raíz en el intervalo.
    4. Resuelve con BisectionSolver.
    5. Empaqueta en ExerciseBundle.
    """

    def __init__(self) -> None:
        self._solver = BisectionSolver()
        self._validator = BisectionValidator()

    def generate(self, difficulty: int) -> ExerciseBundle:
        """
        Genera un ejercicio completo.

        Args:
            difficulty: Nivel 1–10.

        Returns:
            ExerciseBundle listo para mostrar en la UI.
        """
        tier = _difficulty_to_tier(difficulty)
        exercise_type = random.choices(_EXERCISE_TYPES, _TYPE_WEIGHTS)[0]

        # Intentar generar hasta 20 veces si no hay cambio de signo
        for _ in range(20):
            template = random.choice(_FUNCTION_TEMPLATES[tier])
            rparams = _random_params(template)
            expr = _build_expr(template, rparams)

            try:
                f = parse_function(expr)
            except ValueError:
                continue

            bracket = find_bracket(f)
            if bracket is None:
                continue

            a, b = bracket
            tol = 1e-6 if difficulty >= 7 else 1e-4

            result = self._solver.solve(f, a, b, tol=tol)
            if not result.converged or result.root is None:
                continue

            # Ejercicio válido — construir bundle
            params = {
                "expr": expr,
                "a": round(a, 4),
                "b": round(b, 4),
                "tol": tol,
                "template_params": rparams,
            }

            bundle = self._build_bundle(
                exercise_type, difficulty, params, result, expr, a, b
            )
            return bundle

        # Fallback: ejercicio trivial garantizado
        return self._fallback_bundle(difficulty)

    # ── Construcción de preguntas ─────────────────────────────────────────────

    def _build_bundle(
        self,
        exercise_type: str,
        difficulty: int,
        params: dict,
        result: SolverResult,
        expr: str,
        a: float,
        b: float,
    ) -> ExerciseBundle:

        root = result.root
        iters = result.iterations
        n_iters = len(iters)

        if exercise_type == "numeric_input":
            question_text = (
                f"Encuentra la raíz de f(x) = {expr}\n"
                f"usando el método de bisección en [{a:.4g}, {b:.4g}].\n"
                f"Tolerancia: {params['tol']:.0e}. "
                "Ingresa la raíz aproximada con 4 cifras significativas."
            )
            correct_answer = round_sig(root, 4)
            context = {"ask_for": "root"}
            options = []
            correct_option = None
            hint = (
                f"Recuerda: c = (a + b) / 2. "
                f"El método tarda {n_iters} iteraciones en converger."
            )

        elif exercise_type == "multiple_choice":
            # Generar distractores plausibles
            correct_answer = round_sig(root, 4)
            distractors = self._generate_distractors(root, a, b, n=3)
            all_options = [correct_answer] + distractors
            random.shuffle(all_options)
            correct_option = all_options.index(correct_answer)
            options = [str(o) for o in all_options]
            question_text = (
                f"Para f(x) = {expr} en [{a:.4g}, {b:.4g}], "
                f"¿cuál es la raíz aproximada encontrada por bisección "
                f"con tolerancia {params['tol']:.0e}?"
            )
            context = {"ask_for": "root"}
            hint = f"Aplica: c = (a + b) / 2 repetidamente hasta que |f(c)| < tol."

        elif exercise_type == "fill_step":
            # Pedir el valor de c en la iteración k
            k = min(3, n_iters)  # pedir iteración 3 o la última disponible
            iter_data = iters[k - 1]
            correct_answer = round_sig(iter_data["c"], 4)
            question_text = (
                f"Para f(x) = {expr} con a={a:.4g}, b={b:.4g}:\n"
                f"¿Cuál es el punto medio c en la iteración {k}?\n"
                f"(Muestra el proceso. Ingresa con 4 cifras significativas.)"
            )
            context = {"ask_for": "iteration_c", "iteration": k}
            options = []
            correct_option = None
            hint = (
                f"Iteración 1: a={iters[0]['a']}, b={iters[0]['b']} → "
                f"c₁ = {iters[0]['c']}"
            )
        else:
            # Fallback a numeric_input
            exercise_type = "numeric_input"
            question_text = f"Halla la raíz de f(x) = {expr} en [{a:.4g}, {b:.4g}]."
            correct_answer = round_sig(root, 4)
            context = {"ask_for": "root"}
            options = []
            correct_option = None
            hint = ""

        # Pasos para mostrar en el feedback
        steps = [
            {
                "n": it["iteration"],
                "a": it["a"],
                "b": it["b"],
                "c": it["c"],
                "f_c": it["f_c"],
                "error": it["error_pct"],
            }
            for it in iters[:10]   # máximo 10 pasos en el bundle
        ]

        params["question_context"] = context

        return ExerciseBundle(
            method_key="biseccion",
            exercise_type=exercise_type,
            difficulty=difficulty,
            params=params,
            question_text=question_text,
            solver_result=result,
            correct_answer=correct_answer,
            options=options,
            correct_option=correct_option,
            hint=hint,
            hash=exercise_hash(params),
            steps=steps,
        )

    @staticmethod
    def _generate_distractors(root: float, a: float, b: float, n: int = 3) -> list[float]:
        """Genera distractores plausibles alrededor de la raíz real."""
        distractors: list[float] = []
        spread = abs(b - a) * 0.3
        while len(distractors) < n:
            d = root + random.uniform(-spread, spread)
            d = round_sig(d, 4)
            if abs(d - root) > 1e-3 and d not in distractors:
                distractors.append(d)
        return distractors

    def _fallback_bundle(self, difficulty: int) -> ExerciseBundle:
        """Ejercicio de respaldo garantizado: x² - 4 en [0, 3]."""
        f = lambda x: x**2 - 4
        result = self._solver.solve(f, 0, 3)
        params = {"expr": "x**2 - 4", "a": 0, "b": 3, "tol": 1e-6,
                  "question_context": {"ask_for": "root"}}
        return ExerciseBundle(
            method_key="biseccion",
            exercise_type="numeric_input",
            difficulty=difficulty,
            params=params,
            question_text=(
                "Encuentra la raíz positiva de f(x) = x² - 4 "
                "usando bisección en [0, 3]."
            ),
            solver_result=result,
            correct_answer=2.0,
            hint="La raíz exacta es x = 2. ¿Cuántas iteraciones necesitas?",
            hash=exercise_hash(params),
        )
