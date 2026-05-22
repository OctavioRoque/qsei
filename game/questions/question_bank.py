"""
game/questions/question_bank.py
==================================
Carga y administra el banco estático de preguntas JSON.

Uso básico
----------
    bank = QuestionBank()
    qs   = bank.get(topic="biseccion", difficulty=2, count=5)

    # Para una sesión completa con mezcla de tipos:
    qs = bank.get_session_set(topic="biseccion", difficulty=2, total=10)
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Literal

from game.questions.question_model import BankQuestion

logger = logging.getLogger(__name__)

# Ruta a los JSON (assets/questions/<topic>.json)
_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "questions"

# Cache en memoria: topic → lista de BankQuestion
_cache: dict[str, list[BankQuestion]] = {}

# Mapa de dificultad del juego (1-3) → nivel numérico
_DIFF_LABELS = {1: "Fácil", 2: "Media", 3: "Difícil"}


def _load_topic(topic: str) -> list[BankQuestion]:
    """Carga (o devuelve del caché) todas las preguntas de un tema."""
    if topic in _cache:
        return _cache[topic]

    path = _ASSETS_DIR / f"{topic}.json"
    if not path.exists():
        # Intenta el banco maestro
        master = _ASSETS_DIR / "all.json"
        if master.exists():
            all_qs = json.loads(master.read_text(encoding="utf-8"))
            _cache[topic] = [
                BankQuestion.from_dict(d)
                for d in all_qs
                if d["topic"] == topic
            ]
            logger.debug("Cargadas %d preguntas de '%s' desde all.json", len(_cache[topic]), topic)
            return _cache[topic]
        logger.warning("No se encontró banco para el tema '%s'", topic)
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[topic] = [BankQuestion.from_dict(d) for d in data]
    logger.info("Banco '%s': %d preguntas cargadas", topic, len(_cache[topic]))
    return _cache[topic]


def available_topics() -> list[str]:
    """Retorna los temas que tienen archivo JSON en assets/questions/."""
    return sorted(
        p.stem for p in _ASSETS_DIR.glob("*.json") if p.stem != "all"
    )


def count(topic: str, difficulty: int | None = None) -> int:
    """Número de preguntas disponibles para un tema (y dificultad opcional)."""
    qs = _load_topic(topic)
    if difficulty is not None:
        qs = [q for q in qs if q.difficulty == difficulty]
    return len(qs)


def get(
    topic: str,
    difficulty: int | None = None,
    q_type: str | None = None,
    count: int = 5,
    seed: int | None = None,
) -> list[BankQuestion]:
    """
    Obtiene preguntas del banco con filtros opcionales.

    Parámetros
    ----------
    topic       : Clave del método, e.g. "biseccion"
    difficulty  : 1=Fácil, 2=Media, 3=Difícil  (None = cualquiera)
    q_type      : "open" | "tabulation" | "prerequisite" | "analysis" | None
    count       : Cuántas preguntas devolver
    seed        : Semilla para reproducibilidad (útil en tests)

    Returns
    -------
    Lista aleatoria de BankQuestion (puede tener menos de `count` si el banco
    no tiene suficientes con esos filtros).
    """
    pool = _load_topic(topic)

    if difficulty is not None:
        pool = [q for q in pool if q.difficulty == difficulty]

    if q_type is not None:
        pool = [q for q in pool if q.type == q_type]

    if not pool:
        logger.warning(
            "Banco vacío para topic='%s' difficulty=%s type=%s",
            topic, difficulty, q_type
        )
        return []

    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:count]


def _load_all_topics() -> list[BankQuestion]:
    """Carga todas las preguntas de todos los temas disponibles."""
    questions: list[BankQuestion] = []
    for topic in available_topics():
        questions.extend(_load_topic(topic))
    return questions


def get_random_questions(
    difficulty: int | None = None,
    count: int = 5,
    seed: int | None = None,
) -> list[BankQuestion]:
    """
    Obtiene preguntas aleatorias de todos los temas.

    Si no hay suficientes preguntas para la dificultad solicitada,
    rellena con preguntas de cualquier dificultad.
    """
    pool = _load_all_topics()
    if difficulty is not None:
        filtered = [q for q in pool if q.difficulty == difficulty]
        if filtered:
            pool = filtered
        else:
            logger.warning(
                "No hay preguntas de dificultad %s en todos los temas, usando todas",
                difficulty,
            )
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:count]


def get_session_set(
    topic: str | None,
    difficulty: int,
    total: int = 10,
    seed: int | None = None,
) -> list[BankQuestion]:
    """
    Arma un set de preguntas equilibrado para una sesión completa.

    Si `topic` es None, selecciona preguntas de todos los temas.
    """
    if topic is None:
        pool = get_random_questions(difficulty=difficulty, count=total * 3, seed=seed)
    else:
        all_qs = _load_topic(topic)
        pool = [q for q in all_qs if q.difficulty == difficulty]

        if not pool:
            # Fallback: cualquier dificultad del mismo tema
            pool = list(all_qs)
            logger.warning(
                "No hay preguntas de dificultad %d para '%s', usando todas",
                difficulty, topic
            )

    rng = random.Random(seed)
    rng.shuffle(pool)

    # Dividir por tipo
    by_type: dict[str, list[BankQuestion]] = {
        "open": [],
        "tabulation": [],
        "prerequisite": [],
        "analysis": [],
    }
    for q in pool:
        by_type.setdefault(q.type, []).append(q)

    # Cuotas
    want_tab   = max(1, round(total * 0.30))
    want_pre   = max(1, round(total * 0.15))
    want_ana   = max(1, round(total * 0.05))
    want_open  = total - want_tab - want_pre - want_ana

    selected: list[BankQuestion] = []
    selected += by_type["tabulation"][:want_tab]
    selected += by_type["prerequisite"][:want_pre]
    selected += by_type["analysis"][:want_ana]
    selected += by_type["open"][:want_open]

    # Rellenar si hay déficit
    remaining = total - len(selected)
    if remaining > 0:
        used_ids = {q.id for q in selected}
        extras = [q for q in pool if q.id not in used_ids]
        selected += extras[:remaining]

    rng.shuffle(selected)
    return selected[:total]


def get_by_id(question_id: str) -> BankQuestion | None:
    """Busca una pregunta por su id en todos los temas cargados."""
    for topic_qs in _cache.values():
        for q in topic_qs:
            if q.id == question_id:
                return q
    # Intentar carga del maestro
    master = _ASSETS_DIR / "all.json"
    if master.exists():
        all_data = json.loads(master.read_text(encoding="utf-8"))
        for d in all_data:
            if d["id"] == question_id:
                return BankQuestion.from_dict(d)
    return None


def get_distractors(
    question: "BankQuestion",
    count: int = 3,
    seed: int | None = None,
) -> list[str]:
    """
    Genera distractores para una pregunta tomando las soluciones de otras
    preguntas del mismo tema y dificultad.

    Si no hay suficientes en el mismo tema/dificultad, amplía a todo el tema.
    """
    pool = _load_topic(question.topic)

    # Primero intentar misma dificultad, excluyendo la pregunta actual
    candidates = [
        q.solution for q in pool
        if q.id != question.id
        and q.difficulty == question.difficulty
        and len(q.solution) < 350
        and q.solution.strip()
    ]

    # Si no alcanza, ampliar a todo el tema
    if len(candidates) < count:
        candidates = [
            q.solution for q in pool
            if q.id != question.id
            and len(q.solution) < 350
            and q.solution.strip()
        ]

    rng = random.Random(seed)
    rng.shuffle(candidates)
    # Recortar a ~200 chars para que quepan como opciones
    return [s[:200].rstrip() for s in candidates[:count]]