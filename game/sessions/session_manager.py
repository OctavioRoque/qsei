"""
game/sessions/session_manager.py
==================================
Orquestador de una sesión de juego completa.
Conecta: generador de ejercicios → validador → scorer → repositorio.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any

from engine.utils.base_solver import ExerciseBundle, ValidationResult
from engine.scoring.scorer import Scorer, ScoreBreakdown
from storage.repositories.player_repository import PlayerRepository
from storage.sqlite.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class AnswerRecord:
    """Registro de una respuesta durante la sesión."""
    exercise: ExerciseBundle
    validation: ValidationResult
    score: ScoreBreakdown
    time_seconds: float
    streak_at_answer: int


@dataclass
class SessionSummary:
    """Resumen al finalizar una sesión."""
    session_id: int
    player_id: int
    method_key: str
    difficulty: int
    total_score: int
    xp_earned: int
    questions_total: int
    questions_correct: int
    accuracy_pct: float
    avg_time: float
    best_streak: int
    answers: list[AnswerRecord]
    new_records: list[str]
    new_achievements: list[str]
    level_up: bool
    new_level: int


class GameSession:
    """
    Gestiona el ciclo de vida de una sesión de juego:
    1. start()    → registra sesión en DB
    2. answer()   → valida, puntúa, persiste respuesta
    3. end()      → calcula resumen, actualiza estadísticas
    """

    def __init__(
        self,
        player_id: int,
        method_key: str,
        difficulty: int,
        generator,          # cualquier BaseGenerator
        max_lives: int = 3,
    ) -> None:
        self._player_id = player_id
        self._method_key = method_key
        self._difficulty = difficulty
        self._generator = generator
        self._scorer = Scorer()
        self._repo = PlayerRepository()
        self._db = DatabaseManager.get_instance()

        self._session_id: int | None = None
        self._answers: list[AnswerRecord] = []
        self._current_exercise: ExerciseBundle | None = None
        self._question_start: float = 0.0
        self._session_start: float = 0.0
        self._active: bool = False
        self._max_lives: int = max_lives
        self._lives_remaining: int = max_lives

    # ── Ciclo principal ───────────────────────────────────────────────────────

    def start(self) -> ExerciseBundle:
        """Inicia la sesión y genera el primer ejercicio."""
        self._session_start = time.time()
        self._session_id = self._db.execute(
            """INSERT INTO sessions (player_id, method_key, difficulty)
               VALUES (?, ?, ?)""",
            (self._player_id, self._method_key, self._difficulty),
        )
        self._active = True
        logger.info("Sesión iniciada: id=%d player=%d method=%s",
                    self._session_id, self._player_id, self._method_key)
        return self.next_question()

    def next_question(self) -> ExerciseBundle:
        """Genera y devuelve el siguiente ejercicio."""
        self._current_exercise = self._generator.generate(self._difficulty)
        self._question_start = time.time()
        return self._current_exercise

    def answer(
        self,
        student_answer: Any,
        validator,          # BaseValidator compatible con el método
    ) -> tuple[ValidationResult, ScoreBreakdown]:
        """
        Procesa la respuesta del estudiante.

        Args:
            student_answer: Respuesta ingresada.
            validator:      Validador del método actual.

        Returns:
            (ValidationResult, ScoreBreakdown)
        """
        assert self._active, "La sesión no está activa."
        assert self._current_exercise is not None, "No hay ejercicio activo."

        time_taken = time.time() - self._question_start
        streak = self._repo.get_streak(self._player_id)

        # Validar
        context = self._current_exercise.params.get("question_context", {"ask_for": "root"})
        validation = validator.validate(
            student_answer,
            self._current_exercise.solver_result,
            context,
        )

        # Vida perdida al fallar
        if not validation.is_correct:
            self._lives_remaining = max(0, self._lives_remaining - 1)

        # Puntuar
        score = self._scorer.calculate(
            validation,
            self._difficulty,
            time_taken,
            streak.current,
        )

        # Actualizar racha
        new_streak = self._repo.update_streak(self._player_id, validation.is_correct)

        # Persistir respuesta
        import json
        self._db.execute(
            """INSERT INTO answers
               (session_id, question_hash, exercise_type, method_key, difficulty,
                is_correct, student_answer, correct_answer, time_seconds, score_earned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self._session_id,
                self._current_exercise.hash,
                self._current_exercise.exercise_type,
                self._current_exercise.method_key,
                self._difficulty,
                int(validation.is_correct),
                json.dumps(str(student_answer)),
                json.dumps(str(self._current_exercise.correct_answer)),
                round(time_taken, 2),
                score.total,
            ),
        )

        record = AnswerRecord(
            exercise=self._current_exercise,
            validation=validation,
            score=score,
            time_seconds=time_taken,
            streak_at_answer=new_streak.current,
        )
        self._answers.append(record)
        return validation, score

    def end(self) -> SessionSummary:
        """
        Finaliza la sesión, actualiza todos los registros y retorna el resumen.
        """
        assert self._active
        self._active = False
        duration = time.time() - self._session_start

        # Calcular métricas
        total_score = sum(a.score.total for a in self._answers)
        xp_earned = sum(a.score.xp_earned for a in self._answers)
        correct_count = sum(1 for a in self._answers if a.validation.is_correct)
        total_count = len(self._answers)
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0.0
        avg_time = (
            sum(a.time_seconds for a in self._answers) / total_count
            if total_count > 0 else 0.0
        )
        best_streak = max((a.streak_at_answer for a in self._answers), default=0)

        # Actualizar sesión en DB
        self._db.execute(
            """UPDATE sessions
               SET score = ?, xp_earned = ?, questions_total = ?,
                   questions_correct = ?, duration_seconds = ?, ended_at = datetime('now')
               WHERE id = ?""",
            (total_score, xp_earned, total_count, correct_count,
             round(duration, 2), self._session_id),
        )

        # Actualizar perfil
        player = self._repo.get_player_by_id(self._player_id)
        old_xp = player.xp
        new_total_xp = old_xp + xp_earned
        new_level, _, _ = self._scorer.level_from_xp(new_total_xp)
        level_up = new_level > player.level

        self._db.execute(
            """UPDATE players
               SET total_score = total_score + ?,
                   xp = xp + ?,
                   level = ?,
                   games_played = games_played + 1,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (total_score, xp_earned, new_level, self._player_id),
        )

        # Actualizar estadísticas por método
        for ans in self._answers:
            self._repo.upsert_method_stats(
                self._player_id,
                self._method_key,
                ans.validation.is_correct,
                ans.score.total,
                ans.time_seconds,
            )

        # Verificar récord
        new_record = self._repo.update_record(
            self._player_id, self._method_key, self._difficulty,
            total_score, avg_time,
        )
        new_records = [f"{self._method_key} dif.{self._difficulty}"] if new_record else []

        # Verificar logros
        new_achievements = self._check_achievements(
            correct_count, total_count, best_streak, accuracy, new_level
        )

        logger.info("Sesión terminada: score=%d xp=%d corrects=%d/%d",
                    total_score, xp_earned, correct_count, total_count)

        return SessionSummary(
            session_id=self._session_id,
            player_id=self._player_id,
            method_key=self._method_key,
            difficulty=self._difficulty,
            total_score=total_score,
            xp_earned=xp_earned,
            questions_total=total_count,
            questions_correct=correct_count,
            accuracy_pct=accuracy,
            avg_time=avg_time,
            best_streak=best_streak,
            answers=self._answers,
            new_records=new_records,
            new_achievements=new_achievements,
            level_up=level_up,
            new_level=new_level,
        )

    # ── Propiedades de estado ─────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_score(self) -> int:
        return sum(a.score.total for a in self._answers)

    @property
    def questions_answered(self) -> int:
        return len(self._answers)

    @property
    def lives_remaining(self) -> int:
        return self._lives_remaining

    # ── Logros ────────────────────────────────────────────────────────────────

    def _check_achievements(
        self,
        correct: int,
        total: int,
        best_streak: int,
        accuracy: float,
        new_level: int,
    ) -> list[str]:
        """Verifica y desbloquea logros al finalizar la sesión."""
        unlocked: list[str] = []

        checks = [
            ("first_correct",    correct >= 1),
            ("streak_5",         best_streak >= 5),
            ("streak_10",        best_streak >= 10),
            ("streak_25",        best_streak >= 25),
            ("perfect_session",  correct == total and total >= 5),
            ("level_5",          new_level >= 5),
            ("level_10",         new_level >= 10),
            ("level_20",         new_level >= 20),
        ]

        for key, condition in checks:
            if condition:
                if self._repo.unlock_achievement(self._player_id, key):
                    unlocked.append(key)

        return unlocked
