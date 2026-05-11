"""
config.py
=========
Configuración global del proyecto '¿Quién quiere ser Ingeniero?'
Centraliza todas las constantes, rutas y parámetros del sistema.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Final

# ─── Rutas base ──────────────────────────────────────────────────────────────
BASE_DIR: Final[Path] = Path(__file__).parent
SAVES_DIR: Final[Path] = BASE_DIR / "saves"
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
DB_PATH: Final[Path] = SAVES_DIR / "game_data.db"
SETTINGS_PATH: Final[Path] = SAVES_DIR / "settings.json"

# Garantizar que los directorios existan
SAVES_DIR.mkdir(parents=True, exist_ok=True)


# ─── Metadatos de la app ─────────────────────────────────────────────────────
APP_NAME: Final[str] = "¿Quién quiere ser Ingeniero?"
APP_VERSION: Final[str] = "0.1.0"
APP_WIDTH: Final[int] = 1100
APP_HEIGHT: Final[int] = 720


# ─── Configuración de juego ───────────────────────────────────────────────────
@dataclass(frozen=True)
class GameConfig:
    """Parámetros del sistema de juego."""

    # Tolerancia numérica para validación de respuestas
    default_tolerance: float = 1e-4
    strict_tolerance: float = 1e-6
    loose_tolerance: float = 1e-2

    # Rangos de dificultad (1–10)
    difficulty_min: int = 1
    difficulty_max: int = 10

    # Tiempo base en segundos para bonificación de rapidez
    # (>tiempo_base → sin bonus; <tiempo_base → bonus proporcional)
    time_bonus_base_seconds: float = 60.0

    # Factores de puntuación
    score_base_easy: int = 100
    score_base_medium: int = 250
    score_base_hard: int = 500
    score_base_expert: int = 1000

    precision_multiplier_perfect: float = 1.0   # respuesta exacta dentro de tolerancia
    precision_multiplier_close: float = 0.75     # dentro de 10× tolerancia
    precision_multiplier_wrong: float = 0.0

    streak_bonus_step: int = 50     # +50 pts por cada respuesta en racha
    streak_cap: int = 500           # máximo bonus por racha

    # XP
    xp_per_correct: int = 10
    xp_per_perfect: int = 20        # respuesta correcta + tiempo < 30s
    xp_level_base: int = 100        # XP requerido para nivel 1→2
    xp_level_multiplier: float = 1.5


GAME = GameConfig()


# ─── Niveles de dificultad ────────────────────────────────────────────────────
@dataclass(frozen=True)
class DifficultyLevel:
    name: str
    min_diff: int
    max_diff: int
    label_es: str
    color_hex: str


DIFFICULTY_LEVELS: Final[list[DifficultyLevel]] = [
    DifficultyLevel("easy",   1,  3, "Fácil",    "#4CAF50"),
    DifficultyLevel("medium", 4,  6, "Medio",    "#FF9800"),
    DifficultyLevel("hard",   7,  8, "Difícil",  "#F44336"),
    DifficultyLevel("expert", 9, 10, "Experto",  "#9C27B0"),
]


def get_difficulty_label(diff: int) -> DifficultyLevel:
    """Retorna el nivel de dificultad correspondiente a un valor 1–10."""
    for level in DIFFICULTY_LEVELS:
        if level.min_diff <= diff <= level.max_diff:
            return level
    return DIFFICULTY_LEVELS[-1]


# ─── Métodos numéricos registrados ───────────────────────────────────────────
NUMERIC_METHODS: Final[dict[str, list[str]]] = {
    "interpolacion": [
        "lineal",
        "lagrange",
        "newton_divididas",
        "newton_adelante",
        "newton_atras",
    ],
    "ecuaciones_lineales": [
        "gauss_seidel",
        "jacobi",
        "montante",
        "gauss_jordan",
        "eliminacion_gaussiana",
    ],
    "ecuaciones_no_lineales": [
        "biseccion",
        "falsa_posicion",
        "newton_raphson",
        "punto_fijo",
        "secante",
    ],
    "minimos_cuadrados": [
        "ajuste_lineal",
        "ajuste_cuadratico",
        "ajuste_cubico",
        "ajuste_funcion_cuadratica",
        "linea_recta",
    ],
}


# ─── Tipos de ejercicios ──────────────────────────────────────────────────────
EXERCISE_TYPES: Final[list[str]] = [
    "multiple_choice",      # selección múltiple
    "numeric_input",        # escribir resultado numérico
    "fill_step",            # completar paso intermedio
    "identify_error",       # identificar error en un procedimiento
    "order_steps",          # ordenar pasos del método
    "select_method",        # seleccionar el método correcto
    "step_by_step",         # resolver paso a paso
]
