"""
game/powerups.py
=================
Estado de comodines y cartas especiales para una sesión de juego.

Comodines (1 uso por partida):
  pista_visual    - Muestra un hint del concepto (~70% confiable)
  estadisticas    - Gráfico de respuestas de sesiones anteriores
  fifty_fifty     - Elimina 2 respuestas incorrectas (solo MC)
  tiempo_extra    - Pausa el temporizador 60 s sin penalización
  ayuda_adicional - Fórmula clave o elimina 1 opción extra

Cartas especiales (1 uso por partida cada una):
  carta_estrella  - Duplica puntos de la siguiente pregunta
  carta_rayo      - Omite pregunta contándola como correcta
  carta_trofeo    - Devuelve una vida
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PowerupState:
    # ── Comodines ────────────────────────────────────────────────────────────
    pista_visual:    bool = True
    estadisticas:    bool = True
    fifty_fifty:     bool = True
    tiempo_extra:    bool = True
    ayuda_adicional: bool = True

    # ── Cartas especiales ────────────────────────────────────────────────────
    carta_estrella: int = 1   # usos disponibles
    carta_rayo:     int = 1
    carta_trofeo:   int = 1

    # ── Efectos activos ──────────────────────────────────────────────────────
    double_points_next: bool = False   # activado por carta_estrella

    # ── API pública ──────────────────────────────────────────────────────────

    def comodin_available(self, name: str) -> bool:
        return bool(getattr(self, name, False))

    def carta_available(self, name: str) -> bool:
        return int(getattr(self, name, 0)) > 0

    def use_comodin(self, name: str) -> bool:
        """Usa el comodín. Retorna True si tenía usos disponibles."""
        if getattr(self, name, False):
            setattr(self, name, False)
            return True
        return False

    def use_carta(self, name: str) -> bool:
        """Usa una carta. Retorna True si tenía usos disponibles."""
        n = getattr(self, name, 0)
        if n > 0:
            setattr(self, name, n - 1)
            return True
        return False

    # ── Listados ─────────────────────────────────────────────────────────────

    COMODINES_META = [
        ("pista_visual",    "🖼",  "Pista Visual",    "Muestra un hint del concepto (~70% confiable)"),
        ("estadisticas",    "📊",  "Estadísticas",    "% de alumnos que eligió cada opción"),
        ("fifty_fifty",     "½½",  "50/50",           "Elimina 2 respuestas incorrectas"),
        ("tiempo_extra",    "⏰",  "+60s",            "Pausa el temporizador 60 segundos"),
        ("ayuda_adicional", "💡",  "Ayuda Extra",     "Fórmula clave o elimina otra opción"),
    ]

    CARTAS_META = [
        ("carta_estrella", "⭐", "Estrella", "x2 puntos en la siguiente pregunta"),
        ("carta_rayo",     "⚡", "Rayo",     "Omite esta pregunta como correcta"),
        ("carta_trofeo",   "🏆", "Trofeo",   "Recupera una vida"),
    ]