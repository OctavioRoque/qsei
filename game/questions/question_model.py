"""
game/questions/question_model.py
==================================
Modelo de datos para las preguntas del banco estático.

Compatible con el resto del motor: BankQuestion puede convertirse
en un ExerciseBundle de forma transparente, por lo que GameSession
y GameScreen no necesitan saber de dónde viene la pregunta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.utils.base_solver import ExerciseBundle, SolverResult, ValidationResult


@dataclass
class BankQuestion:
    """
    Pregunta cargada desde el banco estático JSON.

    Campos
    ------
    id           : "p001"
    topic        : "biseccion"
    difficulty   : 1=Fácil  2=Media  3=Difícil
    type         : "open" | "tabulation" | "prerequisite" | "analysis"
    tags         : lista de etiquetas originales, e.g. ["M", "T"]
    question     : enunciado completo
    solution     : respuesta / desarrollo
    procedure    : procedimiento detallado (puede estar vacío)
    """
    id: str
    topic: str
    difficulty: int
    type: str
    tags: list[str]
    question: str
    solution: str
    procedure: str = ""

    # ── Conversión a ExerciseBundle ──────────────────────────────────────────

    def to_exercise_bundle(self) -> ExerciseBundle:
        """
        Convierte la pregunta del banco en un ExerciseBundle compatible
        con GameSession.answer() y el motor de scoring.

        El solver_result se llena con la solución textual para que
        GameScreen pueda mostrarla en el feedback.
        """
        solver = SolverResult(
            converged=True,
            root=None,
            iterations=[],
            error_final=0.0,
            message=self.solution,
            extra={
                "procedure": self.procedure,
                "question_type": self.type,
            },
        )

        return ExerciseBundle(
            method_key=self.topic,
            exercise_type=self.type,
            difficulty=self.difficulty,
            params={"bank_id": self.id},
            question_text=self.question,
            solver_result=solver,
            correct_answer=self.solution,
            options=[],
            correct_option=None,
            hint=self.procedure[:120] if self.procedure else "",
            hash=self.id,
            steps=[],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "type": self.type,
            "tags": self.tags,
            "question": self.question,
            "solution": self.solution,
            "procedure": self.procedure,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BankQuestion":
        return cls(
            id=d["id"],
            topic=d["topic"],
            difficulty=d["difficulty"],
            type=d["type"],
            tags=d.get("tags", []),
            question=d["question"],
            solution=d["solution"],
            procedure=d.get("procedure", ""),
        )