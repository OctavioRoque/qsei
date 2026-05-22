"""
storage/repositories/player_repository.py
==========================================
Repositorio de jugadores: toda la lógica de acceso a la DB
para perfiles, estadísticas, rachas y logros.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from storage.sqlite.database import DatabaseManager

logger = logging.getLogger(__name__)


# ─── Modelos de datos ─────────────────────────────────────────────────────────

@dataclass
class PlayerProfile:
    id: int
    username: str
    display_name: str
    avatar_id: int
    level: int
    xp: int
    total_score: int
    games_played: int
    created_at: str
    updated_at: str


@dataclass
class MethodStats:
    method_key: str
    attempts: int
    correct: int
    best_score: int
    avg_time: float
    mastery_pct: float
    last_played: str | None

    @property
    def accuracy(self) -> float:
        return (self.correct / self.attempts * 100) if self.attempts > 0 else 0.0


@dataclass
class PlayerStreak:
    current: int
    best: int


@dataclass
class Achievement:
    key: str
    name_es: str
    description_es: str
    icons: str
    xp_reward: int
    unlocked: bool = False
    unlocked_at: str | None = None


# ─── Repositorio ─────────────────────────────────────────────────────────────

class PlayerRepository:
    """Acceso a datos de jugadores (CRUD completo)."""

    def __init__(self) -> None:
        self._db = DatabaseManager.get_instance()

    # ── Perfil ────────────────────────────────────────────────────────────────

    def create_player(self, username: str, display_name: str, avatar_id: int = 0) -> PlayerProfile:
        """Crea un nuevo jugador. Lanza ValueError si el username ya existe."""
        player_id = self._db.execute(
            "INSERT INTO players (username, display_name, avatar_id) VALUES (?, ?, ?)",
            (username.strip().lower(), display_name.strip(), avatar_id),
        )
        # Inicializar racha
        self._db.execute(
            "INSERT OR IGNORE INTO streaks (player_id) VALUES (?)", (player_id,)
        )
        logger.info("Jugador creado: %s (id=%d)", username, player_id)
        return self.get_player_by_id(player_id)

    def get_player_by_id(self, player_id: int) -> PlayerProfile | None:
        row = self._db.fetchone("SELECT * FROM players WHERE id = ?", (player_id,))
        return self._row_to_profile(row) if row else None

    def get_player_by_username(self, username: str) -> PlayerProfile | None:
        row = self._db.fetchone(
            "SELECT * FROM players WHERE username = ?", (username.strip().lower(),)
        )
        return self._row_to_profile(row) if row else None

    def list_players(self) -> list[PlayerProfile]:
        rows = self._db.fetchall("SELECT * FROM players ORDER BY total_score DESC")
        return [self._row_to_profile(r) for r in rows]

    def update_player_score_and_xp(
        self, player_id: int, delta_score: int, delta_xp: int, new_level: int
    ) -> None:
        self._db.execute(
            """UPDATE players
               SET total_score  = total_score + ?,
                   xp           = xp + ?,
                   level        = ?,
                   games_played = games_played + 0,
                   updated_at   = datetime('now')
               WHERE id = ?""",
            (delta_score, delta_xp, new_level, player_id),
        )

    def increment_games_played(self, player_id: int) -> None:
        self._db.execute(
            "UPDATE players SET games_played = games_played + 1 WHERE id = ?",
            (player_id,),
        )
    def reset_all_scores(self) -> None:
        """Elimina todos los perfiles de jugadores y sus datos asociados."""
        with self._db.connection() as conn:
            conn.execute("DELETE FROM players")
    # ── Estadísticas por método ───────────────────────────────────────────────

    def get_method_stats(self, player_id: int, method_key: str) -> MethodStats | None:
        row = self._db.fetchone(
            "SELECT * FROM method_stats WHERE player_id = ? AND method_key = ?",
            (player_id, method_key),
        )
        return self._row_to_method_stats(row) if row else None

    def upsert_method_stats(
        self,
        player_id: int,
        method_key: str,
        is_correct: bool,
        score: int,
        time_seconds: float,
    ) -> None:
        """Inserta o actualiza las estadísticas de un método."""
        existing = self.get_method_stats(player_id, method_key)

        if existing is None:
            attempts = 1
            correct = 1 if is_correct else 0
            best_score = score if is_correct else 0
            avg_time = time_seconds
            mastery = 100.0 if is_correct else 0.0
            self._db.execute(
                """INSERT INTO method_stats
                   (player_id, method_key, attempts, correct, best_score, avg_time, mastery_pct, last_played)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (player_id, method_key, attempts, correct, best_score, avg_time, mastery),
            )
        else:
            attempts = existing.attempts + 1
            correct = existing.correct + (1 if is_correct else 0)
            best_score = max(existing.best_score, score)
            avg_time = (existing.avg_time * existing.attempts + time_seconds) / attempts
            mastery = (correct / attempts) * 100.0
            self._db.execute(
                """UPDATE method_stats
                   SET attempts = ?, correct = ?, best_score = ?, avg_time = ?,
                       mastery_pct = ?, last_played = datetime('now')
                   WHERE player_id = ? AND method_key = ?""",
                (attempts, correct, best_score, avg_time, mastery, player_id, method_key),
            )

    def get_all_method_stats(self, player_id: int) -> list[MethodStats]:
        rows = self._db.fetchall(
            "SELECT * FROM method_stats WHERE player_id = ?", (player_id,)
        )
        return [self._row_to_method_stats(r) for r in rows]

    # ── Rachas ────────────────────────────────────────────────────────────────

    def get_streak(self, player_id: int) -> PlayerStreak:
        row = self._db.fetchone(
            "SELECT current_streak, best_streak FROM streaks WHERE player_id = ?",
            (player_id,),
        )
        if row:
            return PlayerStreak(current=row["current_streak"], best=row["best_streak"])
        return PlayerStreak(current=0, best=0)

    def update_streak(self, player_id: int, is_correct: bool) -> PlayerStreak:
        """Actualiza la racha. Si falla, reinicia la racha actual."""
        streak = self.get_streak(player_id)
        if is_correct:
            new_current = streak.current + 1
            new_best = max(streak.best, new_current)
        else:
            new_current = 0
            new_best = streak.best

        self._db.execute(
            """INSERT INTO streaks (player_id, current_streak, best_streak, last_answer_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(player_id) DO UPDATE SET
                   current_streak = excluded.current_streak,
                   best_streak    = excluded.best_streak,
                   last_answer_at = excluded.last_answer_at""",
            (player_id, new_current, new_best),
        )
        return PlayerStreak(current=new_current, best=new_best)

    # ── Logros ────────────────────────────────────────────────────────────────

    def get_achievements(self, player_id: int) -> list[Achievement]:
        """Retorna todos los logros con indicador de si están desbloqueados."""
        rows = self._db.fetchall(
            """SELECT a.*, pa.unlocked_at
               FROM achievements a
               LEFT JOIN player_achievements pa
                   ON a.key = pa.achievement_key AND pa.player_id = ?
               ORDER BY a.id""",
            (player_id,),
        )
        return [
            Achievement(
                key=r["key"],
                name_es=r["name_es"],
                description_es=r["description_es"],
                icons=r["icons"],
                xp_reward=r["xp_reward"],
                unlocked=r["unlocked_at"] is not None,
                unlocked_at=r["unlocked_at"],
            )
            for r in rows
        ]

    def unlock_achievement(self, player_id: int, achievement_key: str) -> bool:
        """
        Desbloquea un logro si aún no está desbloqueado.

        Returns:
            True si se desbloqueó ahora; False si ya estaba desbloqueado.
        """
        existing = self._db.fetchone(
            "SELECT id FROM player_achievements WHERE player_id = ? AND achievement_key = ?",
            (player_id, achievement_key),
        )
        if existing:
            return False
        self._db.execute(
            "INSERT INTO player_achievements (player_id, achievement_key) VALUES (?, ?)",
            (player_id, achievement_key),
        )
        logger.info("Logro desbloqueado: %s para player %d", achievement_key, player_id)
        return True

    # ── Records ───────────────────────────────────────────────────────────────

    def update_record(
        self, player_id: int, method_key: str, difficulty: int, score: int, time_seconds: float
    ) -> bool:
        """
        Actualiza el récord si el nuevo score es mayor.

        Returns:
            True si se estableció un nuevo récord.
        """
        existing = self._db.fetchone(
            "SELECT best_score FROM records WHERE player_id = ? AND method_key = ? AND difficulty = ?",
            (player_id, method_key, difficulty),
        )
        if existing is None:
            self._db.execute(
                """INSERT INTO records (player_id, method_key, difficulty, best_score, best_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (player_id, method_key, difficulty, score, time_seconds),
            )
            return True
        if score > existing["best_score"]:
            self._db.execute(
                """UPDATE records SET best_score = ?, best_time = ?, set_at = datetime('now')
                   WHERE player_id = ? AND method_key = ? AND difficulty = ?""",
                (score, time_seconds, player_id, method_key, difficulty),
            )
            return True
        return False

    # ── Conversión de filas ───────────────────────────────────────────────────

    @staticmethod
    def _row_to_profile(row: Any) -> PlayerProfile:
        return PlayerProfile(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            avatar_id=row["avatar_id"],
            level=row["level"],
            xp=row["xp"],
            total_score=row["total_score"],
            games_played=row["games_played"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_method_stats(row: Any) -> MethodStats:
        return MethodStats(
            method_key=row["method_key"],
            attempts=row["attempts"],
            correct=row["correct"],
            best_score=row["best_score"],
            avg_time=row["avg_time"],
            mastery_pct=row["mastery_pct"],
            last_played=row["last_played"],
        )