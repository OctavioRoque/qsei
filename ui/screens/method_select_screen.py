"""
ui/screens/method_select_screen.py
====================================
Pantalla de selección de dificultad.
Las preguntas salen de todos los temas disponibles de forma aleatoria.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text,
    primary_button, secondary_button,
)

_BANK_DIFFICULTIES = [
    {"value": 1, "label": "Fácil",    "desc": "Conceptos básicos y definiciones",  "icon": "🟢"},
    {"value": 2, "label": "Media",    "desc": "Aplicación directa del método",     "icon": "🟡"},
    {"value": 3, "label": "Difícil",  "desc": "Análisis, errores y tablas",        "icon": "🔴"},
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
        self._diff_buttons: dict[int, ft.Container] = {}
        self._status_text = ft.Text("", color=Colors.ERROR, size=Typography.SIZE_XS)

        self._build()

    def _build(self) -> None:
        # Contar preguntas disponibles por dificultad
        from game.questions.question_bank import available_topics, count as q_count
        topics = available_topics()
        topics = [t for t in topics if t not in {"all", "analisis", "comparativas"}]

        totals = {}
        for d in [1, 2, 3]:
            totals[d] = sum(q_count(t, difficulty=d) for t in topics)

        diff_cards = []
        for d in _BANK_DIFFICULTIES:
            c = self._make_diff_card(d, totals[d["value"]])
            self._diff_buttons[d["value"]] = c
            diff_cards.append(c)

        diff_section = ft.Column([
            ft.Text("Selecciona la dificultad",
                    size=Typography.SIZE_MD, weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY),
            ft.Text(
                "Las preguntas saldrán de todos los métodos numéricos de forma aleatoria.",
                size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ft.Container(height=Spacing.SM),
            ft.Column(diff_cards, spacing=Spacing.SM),
        ], spacing=Spacing.SM)

        # Temas disponibles como chips informativos
        topic_labels = {
            "biseccion": "Bisección", "newton_raphson": "Newton-Raphson",
            "punto_fijo": "Punto Fijo", "falsa_posicion": "Falsa Posición",
            "secante": "Secante", "interpolacion_lineal": "Interp. Lineal",
            "lagrange": "Lagrange", "newton_adelante": "Newton Adelante",
            "newton_atras": "Newton Atrás", "diferencias_divididas": "Dif. Divididas",
            "gauss_seidel": "Gauss-Seidel", "jacobi": "Jacobi",
            "montante": "Montante", "gauss_jordan": "Gauss-Jordán",
            "eliminacion_gaussiana": "Elim. Gaussiana",
            "euler_adelante": "Euler Adelante", "euler_atras": "Euler Atrás",
            "euler_modificado": "Euler Modificado",
            "runge_kutta_2": "RK-2", "runge_kutta_3": "RK-3",
            "runge_kutta_4": "RK-4", "simpson_13": "Simpson 1/3",
            "simpson_38": "Simpson 3/8", "metodo_grafico": "Método Gráfico",
        }
        chips = ft.Row([
            ft.Container(
                content=ft.Text(topic_labels.get(t, t), size=10,
                                color=Colors.TEXT_SECONDARY),
                bgcolor=Colors.BG_SURFACE,
                border=ft.border.all(1, Colors.BORDER),
                border_radius=Radius.XL,
                padding=ft.Padding(left=8, top=3, right=8, bottom=3),
            )
            for t in topics if t in topic_labels
        ], wrap=True, spacing=6, run_spacing=6)

        topics_section = ft.Column([
            ft.Text("Temas incluidos", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_SECONDARY),
            chips,
        ], spacing=Spacing.SM)

        action_row = ft.Row([
            secondary_button("← Volver", lambda _: self._on_back()),
            primary_button("¡Empezar!", self._on_start,
                           icon=ft.icons.PLAY_ARROW_ROUNDED),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("🎲", size=52),
                        ft.Column([
                            title_text("Modo Aleatorio", size=24),
                            subtitle_text("Preguntas de todos los métodos numéricos"),
                        ], spacing=4),
                    ], spacing=Spacing.MD,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(color=Colors.BORDER, height=28),
                    card(diff_section, padding=Spacing.LG),
                    ft.Container(height=Spacing.MD),
                    card(topics_section, padding=Spacing.LG),
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

    def _make_diff_card(self, d: dict, total_questions: int) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Text(d["icon"], size=28),
                ft.Column([
                    ft.Text(d["label"], size=Typography.SIZE_SM,
                            weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
                    ft.Text(d["desc"], size=Typography.SIZE_XS,
                            color=Colors.TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Text(f"{total_questions} preguntas",
                        size=Typography.SIZE_XS, color=Colors.TEXT_MUTED),
            ], spacing=Spacing.MD,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(left=Spacing.LG, top=Spacing.MD,
                               right=Spacing.LG, bottom=Spacing.MD),
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
        self._on_start_session(
            self._player_id,
            "all",                      # topic "all" = aleatorio
            self._selected_difficulty,
        )