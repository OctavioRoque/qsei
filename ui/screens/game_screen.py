"""
ui/screens/game_screen.py
==========================
Pantalla principal del juego.
Muestra ejercicios, acepta respuestas y actualiza el marcador en tiempo real.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Callable

import flet as ft

from engine.utils.base_solver import ExerciseBundle
from engine.utils.base_solver import ValidationResult
from engine.scoring.scorer import ScoreBreakdown
from game.sessions.session_manager import GameSession
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text, body_text, math_text,
    primary_button, secondary_button, difficulty_badge,
    score_display, xp_bar, feedback_banner,
)


class GameScreen(ft.Column):
    """
    Pantalla de juego activo.

    Responsabilidades:
    - Mostrar el enunciado del ejercicio.
    - Aceptar la respuesta (input numérico o botones de opción múltiple).
    - Mostrar feedback inmediato.
    - Mantener marcador, racha y cronómetro visibles.
    - Delegar la lógica a GameSession.
    """

    def __init__(
        self,
        session: GameSession,
        on_end_session: Callable,
        page: ft.Page,
    ) -> None:
        super().__init__()
        self._session = session
        self._on_end_session = on_end_session
        self._page = page

        # Estado UI
        self._current_bundle: ExerciseBundle | None = None
        self._awaiting_answer = True
        self._elapsed_seconds = 0
        self._timer_thread: threading.Thread | None = None
        self._timer_running = False

        # Controles dinámicos
        self._score_col = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self._streak_text = ft.Text("🔥 0", color=Colors.WARNING, size=Typography.SIZE_MD,
                                    weight=ft.FontWeight.BOLD)
        self._timer_text = ft.Text("⏱ 0s", color=Colors.TEXT_SECONDARY,
                                   size=Typography.SIZE_SM)
        self._question_area = ft.Column(spacing=Spacing.MD)
        self._answer_area = ft.Column(spacing=Spacing.SM)
        self._feedback_area = ft.Column()
        self._next_btn = primary_button("Siguiente →", self._on_next, disabled=True)
        self._end_btn = secondary_button("Terminar sesión", self._on_end)

        self._build_layout()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        """Construye la estructura estática de la pantalla."""
        # Header: marcador + racha + temporizador
        header = ft.Container(
            content=ft.Row(
                [
                    self._score_col,
                    ft.Column(
                        [self._streak_text, self._timer_text],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self._end_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=Spacing.LG, top=Spacing.MD, right=Spacing.LG, bottom=Spacing.MD),
            bgcolor=Colors.BG_SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        )

        # Zona de pregunta
        question_card = card(self._question_area, padding=Spacing.LG)

        # Zona de respuesta
        answer_card = card(self._answer_area, padding=Spacing.MD)

        # Zona de feedback
        action_row = ft.Row(
            [self._next_btn],
            alignment=ft.MainAxisAlignment.END,
        )

        self.controls = [
            header,
            ft.Container(
                content=ft.Column(
                    [
                        question_card,
                        answer_card,
                        self._feedback_area,
                        action_row,
                    ],
                    spacing=Spacing.MD,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding(left=Spacing.LG, top=Spacing.MD, right=Spacing.LG, bottom=Spacing.MD),
                expand=True,
            ),
        ]
        self.spacing = 0
        self.expand = True

    # ── Inicio y navegación ───────────────────────────────────────────────────

    def load_first_question(self) -> None:
        """Carga el primer ejercicio al montar la pantalla."""
        bundle = self._session.start()
        self._load_bundle(bundle)

    def _load_bundle(self, bundle: ExerciseBundle) -> None:
        """Actualiza la UI con un nuevo ejercicio."""
        self._current_bundle = bundle
        self._awaiting_answer = True
        self._elapsed_seconds = 0

        # Actualizar marcador
        self._refresh_score()

        # Mostrar pregunta
        self._question_area.controls.clear()
        self._question_area.controls.extend([
            ft.Row([
                difficulty_badge(bundle.difficulty),
                ft.Text(
                    f"Método: {bundle.method_key.replace('_', ' ').title()}",
                    size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY,
                ),
                ft.Text(
                    f"Tipo: {bundle.exercise_type.replace('_', ' ')}",
                    size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY,
                ),
            ], spacing=Spacing.MD),
            math_text(f"f(x) = {bundle.params.get('expr', '?')}"),
            ft.Divider(color=Colors.BORDER, height=1),
            ft.Text(
                bundle.question_text,
                size=Typography.SIZE_SM,
                color=Colors.TEXT_PRIMARY,
            ),
        ])

        # Mostrar área de respuesta
        self._answer_area.controls.clear()
        self._feedback_area.controls.clear()
        self._next_btn.disabled = True

        if bundle.exercise_type == "multiple_choice":
            self._build_multiple_choice(bundle)
        else:
            self._build_numeric_input(bundle)

        # Mostrar hint si existe
        if bundle.hint:
            self._question_area.controls.append(
                ft.Container(
                    content=ft.Text(
                        f"💡 {bundle.hint}",
                        size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY,
                        italic=True,
                    ),
                    padding=ft.Padding(left=0, top=Spacing.SM, right=0, bottom=0),
                )
            )

        # Iniciar cronómetro
        self._start_timer()
        self._page.update()

    # ── Tipos de respuesta ────────────────────────────────────────────────────

    def _build_numeric_input(self, bundle: ExerciseBundle) -> None:
        """Campo de texto para respuesta numérica."""
        input_field = ft.TextField(
            label="Tu respuesta",
            hint_text="Ej: 2.3456",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            width=300,
            on_submit=lambda e: self._submit_answer(e.control.value),
        )
        submit_btn = primary_button(
            "Verificar",
            lambda e: self._submit_answer(input_field.value),
            icon=ft.icons.CHECK_CIRCLE_OUTLINE,
        )
        self._answer_area.controls.extend([
            ft.Row([input_field, submit_btn], spacing=Spacing.MD),
        ])

    def _build_multiple_choice(self, bundle: ExerciseBundle) -> None:
        """Botones para selección múltiple."""
        for i, option in enumerate(bundle.options):
            btn = ft.OutlinedButton(
                text=f"  {option}  ",
                data=i,
                style=ft.ButtonStyle(
                    color=Colors.TEXT_PRIMARY,
                    side=ft.BorderSide(1, Colors.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
                on_click=lambda e: self._submit_answer(e.control.data),
            )
            self._answer_area.controls.append(btn)

    # ── Lógica de respuesta ───────────────────────────────────────────────────

    def _submit_answer(self, raw_answer: Any) -> None:
        """Procesa la respuesta del estudiante."""
        if not self._awaiting_answer:
            return
        self._awaiting_answer = False
        self._stop_timer()

        # Obtener el validador del método actual
        from engine.nonlinear.bisection import BisectionValidator
        validator_map = {
            "biseccion": BisectionValidator(),
            # agregar más métodos aquí conforme se implementen
        }
        validator = validator_map.get(
            self._session._method_key,
            BisectionValidator(),
        )

        # Para múltiple choice, convertir índice → valor de la opción
        bundle = self._current_bundle
        if bundle.exercise_type == "multiple_choice" and isinstance(raw_answer, int):
            answer_value = bundle.options[raw_answer]
        else:
            answer_value = raw_answer

        validation, score = self._session.answer(answer_value, validator)

        # Mostrar feedback
        self._show_feedback(validation, score)
        self._refresh_score()

        # Habilitar botón siguiente
        self._next_btn.disabled = False
        self._page.update()

    def _show_feedback(self, validation: ValidationResult, score: ScoreBreakdown) -> None:
        """Muestra el banner de feedback y desglose de puntuación."""
        self._feedback_area.controls.clear()
        self._feedback_area.controls.append(
            feedback_banner(validation.is_correct, validation.feedback)
        )

        if validation.is_correct:
            breakdown = ft.Row(
                [
                    self._mini_score("Base", score.base),
                    ft.Text("+", color=Colors.TEXT_MUTED),
                    self._mini_score("Rapidez", score.time_bonus),
                    ft.Text("+", color=Colors.TEXT_MUTED),
                    self._mini_score("Racha", score.streak_bonus),
                    ft.Text("=", color=Colors.TEXT_MUTED),
                    self._mini_score("TOTAL", score.total, highlight=True),
                    ft.Text(
                        f"+{score.xp_earned} XP",
                        color=Colors.PRIMARY,
                        size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=Spacing.SM,
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True,
            )
            self._feedback_area.controls.append(breakdown)

    @staticmethod
    def _mini_score(label: str, value: int, highlight: bool = False) -> ft.Column:
        return ft.Column(
            [
                ft.Text(
                    f"{value:,}",
                    size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD,
                    color=Colors.GOLD if highlight else Colors.TEXT_PRIMARY,
                ),
                ft.Text(label, size=Typography.SIZE_XS, color=Colors.TEXT_MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        )

    # ── Navegación ────────────────────────────────────────────────────────────

    def _on_next(self, e: ft.ControlEvent) -> None:
        bundle = self._session.next_question()
        self._load_bundle(bundle)

    def _on_end(self, e: ft.ControlEvent) -> None:
        self._stop_timer()
        summary = self._session.end()
        self._on_end_session(summary)

    # ── Marcador ──────────────────────────────────────────────────────────────

    def _refresh_score(self) -> None:
        from storage.repositories.player_repository import PlayerRepository
        repo = PlayerRepository()
        from engine.scoring.scorer import Scorer
        streak = repo.get_streak(self._session._player_id)
        player = repo.get_player_by_id(self._session._player_id)

        self._streak_text.value = f"🔥 {streak.current}"

        lvl, xp_in, xp_needed = Scorer.level_from_xp(player.xp if player else 0)
        self._score_col.controls = [
            score_display(self._session.current_score),
            xp_bar(xp_in, xp_needed, lvl),
        ]

    # ── Cronómetro ────────────────────────────────────────────────────────────

    def _start_timer(self) -> None:
        self._timer_running = True
        self._elapsed_seconds = 0

        def _tick() -> None:
            while self._timer_running:
                time.sleep(1)
                if self._timer_running:
                    self._elapsed_seconds += 1
                    self._timer_text.value = f"⏱ {self._elapsed_seconds}s"
                    try:
                        self._page.update()
                    except Exception:
                        break

        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def _stop_timer(self) -> None:
        self._timer_running = False