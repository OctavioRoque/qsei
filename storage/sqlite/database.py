"""
storage/sqlite/database.py
==========================
Gestor de la base de datos SQLite.
Crea el esquema completo y expone métodos de acceso de bajo nivel.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config import DB_PATH

logger = logging.getLogger(__name__)


# ─── SQL: creación de tablas ──────────────────────────────────────────────────
_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─── Perfil del jugador ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS players (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    display_name    TEXT    NOT NULL,
    avatar_id       INTEGER NOT NULL DEFAULT 0,
    level           INTEGER NOT NULL DEFAULT 1,
    xp              INTEGER NOT NULL DEFAULT 0,
    total_score     INTEGER NOT NULL DEFAULT 0,
    games_played    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─── Sesiones de juego ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    method_key      TEXT    NOT NULL,   -- e.g. "biseccion"
    difficulty      INTEGER NOT NULL,
    score           INTEGER NOT NULL DEFAULT 0,
    xp_earned       INTEGER NOT NULL DEFAULT 0,
    questions_total INTEGER NOT NULL DEFAULT 0,
    questions_correct INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL   NOT NULL DEFAULT 0.0,
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    ended_at        TEXT
);

-- ─── Respuestas individuales ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question_hash   TEXT    NOT NULL,   -- hash del ejercicio generado
    exercise_type   TEXT    NOT NULL,
    method_key      TEXT    NOT NULL,
    difficulty      INTEGER NOT NULL,
    is_correct      INTEGER NOT NULL,   -- 0 | 1
    student_answer  TEXT,               -- JSON serializado
    correct_answer  TEXT,               -- JSON serializado
    time_seconds    REAL    NOT NULL DEFAULT 0.0,
    score_earned    INTEGER NOT NULL DEFAULT 0,
    answered_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─── Estadísticas por método ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS method_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    method_key      TEXT    NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    correct         INTEGER NOT NULL DEFAULT 0,
    best_score      INTEGER NOT NULL DEFAULT 0,
    avg_time        REAL    NOT NULL DEFAULT 0.0,
    mastery_pct     REAL    NOT NULL DEFAULT 0.0,  -- 0.0–100.0
    last_played     TEXT,
    UNIQUE(player_id, method_key)
);

-- ─── Logros ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS achievements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT    NOT NULL UNIQUE,
    name_es         TEXT    NOT NULL,
    description_es  TEXT    NOT NULL,
    icons            TEXT    NOT NULL DEFAULT "🏆",
    xp_reward       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_achievements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    achievement_key TEXT    NOT NULL REFERENCES achievements(key),
    unlocked_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(player_id, achievement_key)
);

-- ─── Récords ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    method_key      TEXT    NOT NULL,
    difficulty      INTEGER NOT NULL,
    best_score      INTEGER NOT NULL DEFAULT 0,
    best_time       REAL,
    set_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(player_id, method_key, difficulty)
);

-- ─── Rachas ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS streaks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE UNIQUE,
    current_streak  INTEGER NOT NULL DEFAULT 0,
    best_streak     INTEGER NOT NULL DEFAULT 0,
    last_answer_at  TEXT
);

-- ─── Configuración / Settings ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT    PRIMARY KEY,
    value           TEXT    NOT NULL
);

-- ─── Índices de rendimiento ────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_player  ON sessions(player_id);
CREATE INDEX IF NOT EXISTS idx_answers_session  ON answers(session_id);
CREATE INDEX IF NOT EXISTS idx_method_stats_player ON method_stats(player_id);
"""

_SEED_ACHIEVEMENTS = """
INSERT OR IGNORE INTO achievements (key, name_es, description_es, icons, xp_reward) VALUES
    ('first_correct',       'Primera Correcta',         'Responde tu primera pregunta correctamente',      '🎯', 10),
    ('streak_5',            'Racha de Fuego',            'Responde 5 preguntas seguidas correctamente',     '🔥', 50),
    ('streak_10',           'Imparable',                 'Responde 10 preguntas seguidas correctamente',   '⚡', 100),
    ('streak_25',           'Leyenda',                   'Responde 25 preguntas seguidas correctamente',   '👑', 250),
    ('biseccion_master',    'Maestro de Bisección',      'Domina el método de bisección al 90%%',           '✂️', 75),
    ('nr_master',           'Newton-Raphson Pro',        'Domina Newton-Raphson al 90%%',                   '🔬', 75),
    ('speed_demon',         'Velocista',                 'Responde en menos de 10 segundos correctamente', '💨', 30),
    ('perfect_session',     'Sesión Perfecta',           'Completa una sesión sin errores (mín. 5 pregs.)', '💎', 150),
    ('level_5',             'Ingeniero Aprendiz',        'Alcanza el nivel 5',                              '📐', 100),
    ('level_10',            'Ingeniero Competente',      'Alcanza el nivel 10',                             '🔧', 200),
    ('level_20',            'Ingeniero Senior',          'Alcanza el nivel 20',                             '🏗️', 500),
    ('all_methods_tried',   'Explorador',                'Prueba todos los métodos numéricos al menos una vez', '🗺️', 200);
"""


class DatabaseManager:
    """
    Singleton que gestiona la conexión SQLite y las migraciones.

    Uso::

        db = DatabaseManager.get_instance()
        with db.connection() as conn:
            conn.execute("SELECT ...")
    """

    _instance: "DatabaseManager | None" = None

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # ── Singleton ────────────────────────────────────────────────────────────
    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Inicialización ───────────────────────────────────────────────────────
    def _initialize(self) -> None:
        """Aplica el esquema y seeds iniciales."""
        with self.connection() as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.executescript(_SEED_ACHIEVEMENTS)
        logger.info("Base de datos inicializada en %s", self._db_path)

    # ── Context manager ──────────────────────────────────────────────────────
    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Entrega una conexión con row_factory = sqlite3.Row y
        hace commit/rollback automáticamente.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Helpers genéricos ────────────────────────────────────────────────────
    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Ejecuta DML y retorna el lastrowid."""
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid or 0

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        with self.connection() as conn:
            conn.executemany(sql, params_list)
