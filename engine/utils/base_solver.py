"""
engine/utils/base_solver.py
============================
Clases base abstractas para todos los solvers y validadores del motor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ─── Resultado de un solver ───────────────────────────────────────────────────

@dataclass
class SolverResult:
    """
    Resultado estandarizado que devuelve cualquier solver.

    Attributes:
        converged:    True si el método convergió.
        root:         Valor de la raíz / solución principal (None si no aplica).
        iterations:   Lista de dicts con el detalle de cada iteración.
        error_final:  Error en la última iteración.
        message:      Mensaje humano explicando el resultado.
        extra:        Datos adicionales específicos del método.
    """
    converged: bool
    root: float | None
    iterations: list[dict[str, Any]]
    error_final: float
    message: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def num_iterations(self) -> int:
        return len(self.iterations)

    def last_iteration(self) -> dict[str, Any] | None:
        return self.iterations[-1] if self.iterations else None


# ─── Resultado de validación ──────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """
    Resultado de validar la respuesta de un estudiante.

    Attributes:
        is_correct:       True si la respuesta está dentro de la tolerancia.
        precision_score:  Multiplicador 0.0–1.0 según qué tan cerca estuvo.
        student_value:    Valor que ingresó el estudiante.
        expected_value:   Valor correcto.
        absolute_error:   |student - expected|.
        feedback:         Texto explicativo para mostrar al estudiante.
    """
    is_correct: bool
    precision_score: float
    student_value: float | None
    expected_value: float | None
    absolute_error: float
    feedback: str


# ─── Interfaces abstractas ────────────────────────────────────────────────────

class BaseSolver(ABC):
    """Interfaz que debe implementar todo solver numérico."""

    @abstractmethod
    def solve(self, **kwargs: Any) -> SolverResult:
        """
        Ejecuta el método numérico con los parámetros dados.
        Retorna un SolverResult estandarizado.
        """

    @property
    @abstractmethod
    def method_key(self) -> str:
        """Identificador único del método, e.g. 'biseccion'."""

    @property
    @abstractmethod
    def method_name_es(self) -> str:
        """Nombre legible en español."""


class BaseValidator(ABC):
    """Interfaz que debe implementar todo validador de respuestas."""

    def __init__(self, tolerance: float = 1e-4) -> None:
        self.tolerance = tolerance

    @abstractmethod
    def validate(
        self,
        student_answer: Any,
        solver_result: SolverResult,
        question_context: dict[str, Any],
    ) -> ValidationResult:
        """Valida la respuesta del estudiante contra el resultado correcto."""


class BaseGenerator(ABC):
    """Interfaz para generadores procedurales de ejercicios."""

    @abstractmethod
    def generate(self, difficulty: int) -> "ExerciseBundle":
        """
        Genera un ejercicio completo para el nivel de dificultad dado (1–10).
        """


# ─── Bundle de ejercicio generado ─────────────────────────────────────────────

@dataclass
class ExerciseBundle:
    """
    Paquete completo de un ejercicio generado proceduralmente.

    Attributes:
        method_key:     Método numérico aplicado.
        exercise_type:  Tipo de ejercicio (multiple_choice, numeric_input, …).
        difficulty:     Nivel de dificultad 1–10.
        params:         Parámetros usados para generar el ejercicio.
        question_text:  Enunciado en español.
        solver_result:  Resultado correcto calculado por el solver.
        correct_answer: Respuesta correcta (float, lista, etc.).
        options:        Opciones de respuesta (solo para multiple_choice).
        correct_option: Índice de la opción correcta (solo múltiple).
        hint:           Pista para el estudiante.
        hash:           Hash SHA-256 del ejercicio para deduplicación.
        steps:          Pasos del procedimiento (para step_by_step).
    """
    method_key: str
    exercise_type: str
    difficulty: int
    params: dict[str, Any]
    question_text: str
    solver_result: SolverResult
    correct_answer: Any
    options: list[str] = field(default_factory=list)
    correct_option: int | None = None
    hint: str = ""
    hash: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
