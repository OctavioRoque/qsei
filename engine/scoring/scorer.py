"""
engine/scoring/scorer.py
=========================
Sistema de puntuación completo.

Fórmula:
    score = (base_difficulty * precision_multiplier) + time_bonus + streak_bonus
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from config import GAME, get_difficulty_label
from engine.utils.base_solver import ValidationResult


@dataclass
class ScoreBreakdown:
    """
    Desglose completo de la puntuación obtenida en una respuesta.

    Attributes:
        base:         Puntuación base según dificultad.
        precision:    Puntuación base × multiplicador de precisión.
        time_bonus:   Bonus por rapidez (0 si tardó más del tiempo base).
        streak_bonus: Bonus acumulado por racha.
        total:        Puntuación final.
        xp_earned:    Experiencia ganada.
        is_correct:   Si la respuesta fue correcta.
        multiplier:   Multiplicador de precisión aplicado.
        time_seconds: Tiempo que tardó el estudiante.
        streak:       Racha actual en el momento de la respuesta.
    """
    base: int
    precision: float
    time_bonus: int
    streak_bonus: int
    total: int
    xp_earned: int
    is_correct: bool
    multiplier: float
    time_seconds: float
    streak: int

    def to_dict(self) -> dict:
        return {
            "base": self.base,
            "precision": round(self.precision),
            "time_bonus": self.time_bonus,
            "streak_bonus": self.streak_bonus,
            "total": self.total,
            "xp_earned": self.xp_earned,
        }


class Scorer:
    """
    Calcula la puntuación de una respuesta.

    El tiempo sólo afecta el bonus — nunca penaliza.
    Un estudiante lento sigue ganando puntos si es correcto.
    """

    def calculate(
        self,
        validation: ValidationResult,
        difficulty: int,
        time_seconds: float,
        current_streak: int,
    ) -> ScoreBreakdown:
        """
        Calcula la puntuación completa.

        Args:
            validation:     Resultado de validar la respuesta.
            difficulty:     Nivel de dificultad del ejercicio (1–10).
            time_seconds:   Segundos que tardó el estudiante.
            current_streak: Racha actual antes de esta respuesta.

        Returns:
            ScoreBreakdown con todos los componentes.
        """
        if not validation.is_correct:
            return ScoreBreakdown(
                base=0, precision=0.0, time_bonus=0, streak_bonus=0,
                total=0, xp_earned=0, is_correct=False,
                multiplier=0.0, time_seconds=time_seconds,
                streak=current_streak,
            )

        # 1. Base por dificultad
        base = self._base_score(difficulty)

        # 2. Multiplicador de precisión
        mult = validation.precision_score
        precision = base * mult

        # 3. Bonus por rapidez (bono adicional, nunca descuenta)
        time_bonus = self._time_bonus(time_seconds, difficulty)

        # 4. Bonus por racha (después de aplicar corrección)
        new_streak = current_streak + 1
        streak_bonus = self._streak_bonus(new_streak)

        total = round(precision + time_bonus + streak_bonus)
        xp = self._xp(validation.precision_score, time_seconds)

        return ScoreBreakdown(
            base=base,
            precision=precision,
            time_bonus=time_bonus,
            streak_bonus=streak_bonus,
            total=total,
            xp_earned=xp,
            is_correct=True,
            multiplier=mult,
            time_seconds=time_seconds,
            streak=new_streak,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _base_score(difficulty: int) -> int:
        """Puntaje base según nivel de dificultad."""
        tier = get_difficulty_label(difficulty)
        mapping = {
            "easy":   GAME.score_base_easy,
            "medium": GAME.score_base_medium,
            "hard":   GAME.score_base_hard,
            "expert": GAME.score_base_expert,
        }
        return mapping.get(tier.name, GAME.score_base_medium)

    @staticmethod
    def _time_bonus(time_seconds: float, difficulty: int) -> int:
        """
        Bonus de velocidad: máximo bonus si tardó < 10s, 0 si tardó > base.
        El base de tiempo escala inversamente con la dificultad.
        """
        # Más tiempo permitido para ejercicios difíciles
        time_base = GAME.time_bonus_base_seconds * (1 + (10 - difficulty) * 0.1)
        time_fast = 10.0  # menos de 10s → bonus máximo

        if time_seconds <= time_fast:
            ratio = 1.0
        elif time_seconds >= time_base:
            return 0
        else:
            # Decae linealmente de 1 a 0 entre time_fast y time_base
            ratio = 1.0 - (time_seconds - time_fast) / (time_base - time_fast)

        base = Scorer._base_score(difficulty)
        return round(base * 0.5 * ratio)   # máximo 50% extra por velocidad

    @staticmethod
    def _streak_bonus(streak: int) -> int:
        """Bonus acumulado por racha, con tope."""
        if streak <= 1:
            return 0
        raw = (streak - 1) * GAME.streak_bonus_step
        return min(raw, GAME.streak_cap)

    @staticmethod
    def _xp(precision: float, time_seconds: float) -> int:
        """XP ganado por la respuesta."""
        if precision >= 1.0 and time_seconds < 30.0:
            return GAME.xp_per_perfect
        if precision > 0:
            return GAME.xp_per_correct
        return 0

    # ── XP → Nivel ────────────────────────────────────────────────────────────

    @staticmethod
    def xp_for_level(level: int) -> int:
        """XP total requerido para alcanzar `level` desde 0."""
        total = 0
        base = GAME.xp_level_base
        mult = GAME.xp_level_multiplier
        for lvl in range(1, level):
            total += round(base * (mult ** (lvl - 1)))
        return total

    @staticmethod
    def level_from_xp(total_xp: int) -> tuple[int, int, int]:
        """
        Calcula el nivel actual, XP acumulado en el nivel y XP para subir.

        Returns:
            (level, xp_in_level, xp_needed_for_next)
        """
        level = 1
        base = GAME.xp_level_base
        mult = GAME.xp_level_multiplier
        remaining = total_xp

        while True:
            needed = round(base * (mult ** (level - 1)))
            if remaining < needed:
                return level, remaining, needed
            remaining -= needed
            level += 1
