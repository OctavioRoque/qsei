"""
ui/screens/method_select_screen.py
====================================
Pantalla de selección de método numérico y dificultad.
El jugador elige qué método practicar y con qué nivel de dificultad
antes de iniciar la sesión de juego.
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from config import DIFFICULTY_LEVELS, NUMERIC_METHODS
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text, body_text,
    primary_button, secondary_button, difficulty_badge,
)

# ─── Mapa de métodos disponibles (key → etiqueta legible) ────────────────────
_AVAILABLE_METHODS: dict[str, str] = {
    "biseccion":        "Bisección",
    "falsa_posicion":   "Falsa Posición",
    "newton_raphson":   "Newton-Raphson",
    "punto_fijo":       "Punto Fijo",
    "secante":          "Secante",
}

# Solo "biseccion" está completamente implementado por ahora
_IMPLEMENTED = {"biseccion"}


class MethodSelectScreen(ft.Column):
    """
    Pantalla de selección de método y dificultad.

    Parámetros
    ----------
    player_id       ID del jugador activo.
    on_start_session  Callback (player_id, method_key, difficulty) → None
    on_back           Callback () → None   (regresa a la pantalla de inicio)
    router            AppRouter (no se usa directamente, pero se preserva)
    page              ft.Page
    """

    def __init__(
        self,
        player_id: int,
        on_start_session: Callable[[int, str, int], None],
        on_back: Callable[[], None],
        router,
        page: ft.Page,
    ) -> None:
        super().__init__()
        self._player_id = player_id
        self._on_start_session = on_start_session
        self._on_back = on_back
        self._page = page

        # Estado de selección
        self._selected_method: str = "biseccion"
        self._selected_difficulty: int = 3          # dificultad 1–10

        # Controles dinámicos
        self._method_buttons: dict[str, ft.Container] = {}
        self._diff_buttons: dict[int, ft.Container] = {}
        self._status_text = ft.Text("", color=Colors.ERROR, size=Typography.SIZE_XS)

        self._build()

    # ── Construcción de la UI ─────────────────────────────────────────────────

    def _build(self) -> None:
        """Construye la pantalla completa."""

        # ── Sección: elegir método ──
        method_cards = []
        for key, label in _AVAILABLE_METHODS.items():
            implemented = key in _IMPLEMENTED
            container = self._make_method_card(key, label, implemented)
            self._method_buttons[key] = container
            method_cards.append(container)

        methods_section = ft.Column(
            [
                ft.Text(
                    "Método Numérico",
                    size=Typography.SIZE_MD,
                    weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY,
                ),
                ft.Text(
                    "Elige el método que deseas practicar",
                    size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY,
                ),
                ft.Container(height=Spacing.SM),
                ft.Row(method_cards, wrap=True, spacing=Spacing.MD, run_spacing=Spacing.SM),
            ],
            spacing=Spacing.SM,
        )

        # ── Sección: elegir dificultad ──
        diff_cards = []
        for level in DIFFICULTY_LEVELS:
            # Usamos el valor medio del rango como representativo
            diff_value = (level.min_diff + level.max_diff) // 2
            container = self._make_diff_card(level, diff_value)
            self._diff_buttons[diff_value] = container
            diff_cards.append(container)

        diff_section = ft.Column(
            [
                ft.Text(
                    "Dificultad",
                    size=Typography.SIZE_MD,
                    weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY,
                ),
                ft.Text(
                    "¿Qué tan retador quieres que sea?",
                    size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY,
                ),
                ft.Container(height=Spacing.SM),
                ft.Row(diff_cards, spacing=Spacing.MD, wrap=True),
            ],
            spacing=Spacing.SM,
        )

        # ── Botones de acción ──
        action_row = ft.Row(
            [
                secondary_button("← Volver", lambda _: self._on_back()),
                primary_button(
                    "¡Empezar sesión!",
                    self._on_start,
                    icon=ft.icons.PLAY_ARROW_ROUNDED,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ── Layout completo ──
        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("🎓", size=48),
                                ft.Column(
                                    [
                                        title_text("Selecciona tu desafío", size=22),
                                        subtitle_text("Elige método y dificultad para comenzar"),
                                    ],
                                    spacing=4,
                                ),
                            ],
                            spacing=Spacing.MD,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Divider(color=Colors.BORDER, height=32),
                        card(methods_section, padding=Spacing.LG),
                        ft.Container(height=Spacing.MD),
                        card(diff_section, padding=Spacing.LG),
                        ft.Container(height=Spacing.MD),
                        self._status_text,
                        action_row,
                    ],
                    spacing=Spacing.MD,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding(left=Spacing.LG, top=Spacing.LG, right=Spacing.LG, bottom=Spacing.LG),
                expand=True,
            )
        ]
        self.expand = True
        self.spacing = 0

        # Marcar selecciones iniciales
        self._refresh_method_highlights()
        self._refresh_diff_highlights()

    # ── Tarjetas de método ────────────────────────────────────────────────────

    def _make_method_card(self, key: str, label: str, implemented: bool) -> ft.Container:
        """Crea una tarjeta clickeable para un método numérico."""

        badge = (
            ft.Container(
                content=ft.Text("disponible", size=10, color=Colors.SUCCESS),
                bgcolor="#0D2E1A",
                border_radius=Radius.SM,
                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
            )
            if implemented
            else ft.Container(
                content=ft.Text("próximamente", size=10, color=Colors.TEXT_MUTED),
                bgcolor=Colors.BG_SURFACE,
                border_radius=Radius.SM,
                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
            )
        )

        container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        label,
                        size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD,
                        color=Colors.TEXT_PRIMARY if implemented else Colors.TEXT_MUTED,
                    ),
                    badge,
                ],
                spacing=Spacing.XS,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            width=180,
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD, right=Spacing.MD, bottom=Spacing.MD),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            on_click=(lambda e, k=key: self._select_method(k)) if implemented else None,
            data=key,
        )
        return container

    def _make_diff_card(self, level, diff_value: int) -> ft.Container:
        """Crea una tarjeta clickeable para un nivel de dificultad."""
        container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        level.label_es,
                        size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD,
                        color=Colors.TEXT_PRIMARY,
                    ),
                    ft.Text(
                        f"Nivel {level.min_diff}–{level.max_diff}",
                        size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY,
                    ),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=120,
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD, right=Spacing.MD, bottom=Spacing.MD),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            on_click=lambda e, dv=diff_value: self._select_difficulty(dv),
            data=diff_value,
        )
        return container

    # ── Selección y highlights ────────────────────────────────────────────────

    def _select_method(self, key: str) -> None:
        self._selected_method = key
        self._status_text.value = ""
        self._refresh_method_highlights()
        self._page.update()

    def _select_difficulty(self, diff_value: int) -> None:
        self._selected_difficulty = diff_value
        self._status_text.value = ""
        self._refresh_diff_highlights()
        self._page.update()

    def _refresh_method_highlights(self) -> None:
        for key, container in self._method_buttons.items():
            if key == self._selected_method:
                container.border = ft.border.all(2, Colors.PRIMARY)
                container.bgcolor = "#0A1A35"
            else:
                container.border = ft.border.all(1, Colors.BORDER)
                container.bgcolor = Colors.BG_CARD

    def _refresh_diff_highlights(self) -> None:
        for dv, container in self._diff_buttons.items():
            if dv == self._selected_difficulty:
                container.border = ft.border.all(2, Colors.PRIMARY)
                container.bgcolor = "#0A1A35"
            else:
                container.border = ft.border.all(1, Colors.BORDER)
                container.bgcolor = Colors.BG_CARD

    # ── Acción principal ──────────────────────────────────────────────────────

    def _on_start(self, e: ft.ControlEvent) -> None:
        """Valida la selección e inicia la sesión."""
        if not self._selected_method:
            self._status_text.value = "⚠️ Selecciona un método para continuar."
            self._page.update()
            return

        self._on_start_session(
            self._player_id,
            self._selected_method,
            self._selected_difficulty,
        )