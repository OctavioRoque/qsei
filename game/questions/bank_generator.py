"""
game/questions/bank_generator.py
==================================
Adaptador que envuelve el banco de preguntas estáticas con la
interfaz que espera GameSession (generator.generate(difficulty)).

Implementa el mismo contrato que BaseGenerator:
    generate(difficulty) -> ExerciseBundle

De esta forma, session_manager.py y game_screen.py no necesitan
ningún cambio: reciben un ExerciseBundle como siempre.
"""

from __future__ import annotations

import logging
import random

from engine.utils.base_solver import ExerciseBundle
from game.questions.question_bank import get_session_set, get
from game.questions.question_model import BankQuestion

logger = logging.getLogger(__name__)


class BankGenerator:
    """
    Generador basado en el banco estático de preguntas.

    Mantiene una cola de preguntas mezcladas para la sesión actual.
    Cuando la cola se agota, la recarga desde el banco.

    Parámetros
    ----------
    topic    : Clave del método/tema, e.g. "biseccion"
    total    : Preguntas a pre-cargar por sesión (default 15)
    seed     : Semilla aleatoria (None = sin fijar)
    """

    def __init__(
        self,
        topic: str,
        total: int = 15,
        seed: int | None = None,
    ) -> None:
        self._topic = topic
        self._total = total
        self._seed  = seed
        self._queue: list[BankQuestion] = []
        self._used_ids: set[str] = set()

    # ── Interfaz pública (compatible con BaseGenerator) ───────────────────

    def generate(self, difficulty: int) -> ExerciseBundle:
        """
        Devuelve la siguiente pregunta del banco como ExerciseBundle.

        Si la cola está vacía, la recarga filtrando por dificultad.
        """
        q = self._next(difficulty)
        self._used_ids.add(q.id)
        bundle = q.to_exercise_bundle()
        logger.debug("BankGenerator → %s [%s] diff=%d", q.id, q.type, q.difficulty)
        return bundle

    def reset(self) -> None:
        """Reinicia la cola para una nueva sesión."""
        self._queue.clear()
        self._used_ids.clear()

    # ── Internos ──────────────────────────────────────────────────────────

    def _next(self, difficulty: int) -> BankQuestion:
        """Obtiene la siguiente pregunta, recargando si es necesario."""
        # Filtrar cola por dificultad solicitada
        candidates = [q for q in self._queue if q.difficulty == difficulty]

        if not candidates:
            self._reload(difficulty)
            candidates = [q for q in self._queue if q.difficulty == difficulty]

        if not candidates:
            # Fallback: cualquier pregunta del tema aunque no coincida dificultad
            candidates = list(self._queue) or self._emergency_load()

        q = candidates.pop(0)
        self._queue = [x for x in self._queue if x.id != q.id]
        return q

    def _reload(self, difficulty: int) -> None:
        """Recarga el banco para una dificultad específica."""
        new_qs = get_session_set(
            topic=self._topic,
            difficulty=difficulty,
            total=self._total,
            seed=self._seed,
        )
        # Excluir ya usadas si hay suficientes nuevas
        fresh = [q for q in new_qs if q.id not in self._used_ids]
        if len(fresh) < 3:
            # Banco casi agotado → resetear historial
            self._used_ids.clear()
            fresh = new_qs

        self._queue.extend(fresh)
        logger.info(
            "BankGenerator recargó %d preguntas (topic=%s diff=%d)",
            len(fresh), self._topic, difficulty
        )

    def _emergency_load(self) -> list[BankQuestion]:
        """Carga de emergencia cuando el banco está vacío para cualquier dificultad."""
        logger.warning("BankGenerator: carga de emergencia para topic='%s'", self._topic)
        qs = get(topic=self._topic, count=10)
        self._queue = list(qs)
        return self._queue