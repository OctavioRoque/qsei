"""
ui/screens/method_select_screen.py
====================================
Pantalla de selección de método numérico y dificultad.
"""

from __future__ import annotations
import random
from typing import Callable
import flet as ft

from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text,
    primary_button, secondary_button,
)

# Verificar qué métodos tienen preguntas en el banco
def _implemented_topics() -> set[str]:
    from pathlib import Path
    q_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "questions"
    return {p.stem for p in q_dir.glob("*.json") if p.stem != "all"}

# Dificultades del banco: 1=Fácil, 2=Media, 3=Difícil
_BANK_DIFFICULTIES = [
    {"value": 1, "label": "Fácil",   "desc": "Conceptos básicos",   "color": "#4CAF50"},
    {"value": 2, "label": "Media",   "desc": "Aplicación directa",  "color": "#FF9800"},
    {"value": 3, "label": "Difícil", "desc": "Análisis profundo",   "color": "#F44336"},
]


class MethodSelectScreen(ft.Column):
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

        self._selected_difficulty: int = 1
        self._implemented = _implemented_topics()

        self._diff_buttons: dict[int, ft.Container] = {}
        self._status_text = ft.Text("", color=Colors.ERROR, size=Typography.SIZE_XS)

        self._build()

    def _build(self) -> None:
        methods_section = ft.Column([
            ft.Text("Método Aleatorio", size=Typography.SIZE_MD,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
            ft.Text(
                "Se elegirá automáticamente un método disponible en cada sesión.",
                size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ft.Text(
                f"Temas disponibles: {len(self._implemented)}",
                size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
        ], spacing=Spacing.SM)

        diff_cards = []
        for d in _BANK_DIFFICULTIES:
            c = self._make_diff_card(d)
            self._diff_buttons[d["value"]] = c
            diff_cards.append(c)

        diff_section = ft.Column([
            ft.Text("Dificultad", size=Typography.SIZE_MD,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
            ft.Text("¿Qué tan retador quieres que sea?",
                    size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ft.Container(height=Spacing.SM),
            ft.Row(diff_cards, spacing=Spacing.MD),
        ], spacing=Spacing.SM)

        action_row = ft.Row([
            secondary_button("← Volver", lambda _: self._on_back()),
            primary_button("¡Empezar sesión!", self._on_start,
                           icon=ft.icons.PLAY_ARROW_ROUNDED),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("🎓", size=48),
                        ft.Column([
                            title_text("Selecciona tu desafío", size=22),
                            subtitle_text("Método aleatorio y dificultad seleccionable"),
                        ], spacing=4),
                    ], spacing=Spacing.MD,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(color=Colors.BORDER, height=32),
                    card(methods_section, padding=Spacing.LG),
                    ft.Container(height=Spacing.MD),
                    card(diff_section, padding=Spacing.LG),
                    ft.Container(height=Spacing.MD),
                    self._status_text,
                    action_row,
                ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO),
                padding=ft.Padding(left=Spacing.LG, top=Spacing.LG,
                                   right=Spacing.LG, bottom=Spacing.LG),
                expand=True,
            )
        ]
        self.expand = True
        self.spacing = 0
        self._refresh_diff_highlights()

    def _make_diff_card(self, d: dict) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(d["label"], size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
                ft.Text(d["desc"], size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY),
            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=130,
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD,
                               right=Spacing.MD, bottom=Spacing.MD),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
            on_click=lambda e, v=d["value"]: self._select_difficulty(v),
            data=d["value"],
        )

    def _select_difficulty(self, value: int) -> None:
        self._selected_difficulty = value
        self._status_text.value = ""
        self._refresh_diff_highlights()
        self._page.update()

    def _refresh_diff_highlights(self) -> None:
        for v, c in self._diff_buttons.items():
            if v == self._selected_difficulty:
                c.border = ft.border.all(2, Colors.PRIMARY)
                c.bgcolor = "#0A1A35"
            else:
                c.border = ft.border.all(1, Colors.BORDER)
                c.bgcolor = Colors.BG_CARD

    def _on_start(self, e: ft.ControlEvent) -> None:
        if not self._implemented:
            self._status_text.value = "⚠️ No hay temas disponibles en el banco de preguntas."
            self._page.update()
            return

        self._on_start_session(
            self._player_id,
            "aleatorio",
            self._selected_difficulty,
        )