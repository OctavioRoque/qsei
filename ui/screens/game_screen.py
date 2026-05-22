"""
ui/screens/game_screen.py
==========================
Pantalla principal del juego.
Soporta dos modos de respuesta:
  - Procedural (bisección generativa): input numérico o múltiple opción.
  - Banco estático: el alumno lee, responde libremente, ve la solución
    y se auto-evalúa (✅ / ❌).
"""

from __future__ import annotations

import time
import threading
from typing import Any, Callable

import flet as ft

from engine.utils.base_solver import ExerciseBundle, ValidationResult, SolverResult
from engine.scoring.scorer import ScoreBreakdown
from game.sessions.session_manager import GameSession
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text, body_text, math_text,
    primary_button, secondary_button, difficulty_badge,
    score_display, xp_bar, feedback_banner,
)

_BANK_TYPES = {"open", "tabulation", "prerequisite", "analysis"}


def _is_bank_question(bundle: ExerciseBundle) -> bool:
    return bool(bundle.params.get("bank_id"))


def _make_bank_validation(is_correct: bool, solution: str) -> ValidationResult:
    """Crea un ValidationResult para auto-evaluación del banco."""
    return ValidationResult(
        is_correct=is_correct,
        precision_score=1.0 if is_correct else 0.0,
        student_value=None,
        expected_value=None,
        absolute_error=0.0,
        feedback=(
            f"✅ ¡Muy bien! Solución:\n{solution}"
            if is_correct
            else f"❌ Sigue practicando. Solución:\n{solution}"
        ),
    )


class GameScreen(ft.Column):
    """
    Pantalla de juego activo.
    """

    def __init__(
        self,
        session: GameSession,
        on_end_session: Callable,
        on_back_to_menu: Callable,
        page: ft.Page,
    ) -> None:
        super().__init__()
        self._session = session
        self._on_end_session = on_end_session
        self._on_back_to_menu = on_back_to_menu
        self._page = page

        self._current_bundle: ExerciseBundle | None = None
        self._awaiting_answer = True
        self._elapsed_seconds = 0
        self._timer_running = False
        self._timer_thread: threading.Thread | None = None

        # Controles permanentes
        self._score_col = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            width=260,
        )
        self._streak_text = ft.Text(
            "🔥 0", color=Colors.WARNING,
            size=Typography.SIZE_MD, weight=ft.FontWeight.BOLD)
        self._timer_text = ft.Text(
            "⏱ 0s", color=Colors.TEXT_SECONDARY, size=Typography.SIZE_SM)
        self._lives_text = ft.Text(
            "❤️ 3", color=Colors.ERROR, size=Typography.SIZE_SM,
            weight=ft.FontWeight.BOLD)
        # Do not create a persistent home button to avoid reuse across parents.
        # Create a dedicated header end button instance instead.
        self._header_end_btn = secondary_button("Terminar sesión", self._on_end)

        # Zonas dinámicas
        self._question_area = ft.Column(spacing=Spacing.MD)
        self._answer_area   = ft.Column(spacing=Spacing.SM)
        self._feedback_area = ft.Column()
        self._action_row    = ft.Row(alignment=ft.MainAxisAlignment.END, spacing=Spacing.SM)

        self._next_btn = primary_button("Siguiente →", self._on_next, disabled=True)

        self._build_layout()

    # ── Layout estático ───────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        header = ft.Container(
            content=ft.Row([
                self._score_col,
                ft.Row([self._streak_text, self._timer_text, self._lives_text], spacing=Spacing.SM),
                ft.Row([self._header_end_btn], spacing=Spacing.SM),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(left=Spacing.LG, top=Spacing.SM,
                               right=Spacing.LG, bottom=Spacing.SM),
            bgcolor=Colors.BG_SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        )

        self.controls = [
            header,
            ft.Container(
                content=ft.Column([
                    card(self._question_area, padding=Spacing.LG),
                    card(self._answer_area,   padding=Spacing.MD),
                    self._feedback_area,
                    self._action_row,
                ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO),
                padding=ft.Padding(left=Spacing.LG, top=Spacing.MD,
                                   right=Spacing.LG, bottom=Spacing.MD),
                expand=True,
            ),
        ]
        self.spacing = 0
        self.expand = True

    # ── Inicio ────────────────────────────────────────────────────────────────

    def load_first_question(self) -> None:
        bundle = self._session.start()
        self._load_bundle(bundle)

    # ── Cargar pregunta ───────────────────────────────────────────────────────

    def _load_bundle(self, bundle: ExerciseBundle) -> None:
        self._current_bundle = bundle
        self._awaiting_answer = True
        self._elapsed_seconds = 0

        self._refresh_score()
        self._feedback_area.controls.clear()
        # Create fresh action buttons for this question to avoid reusing controls
        home_btn = secondary_button("Volver al menú", self._on_home)
        self._action_row.controls = [home_btn, self._next_btn]
        self._next_btn.disabled = True

        # ── Cabecera de la pregunta ──
        self._question_area.controls.clear()
        header_row = [difficulty_badge(bundle.difficulty)]

        method_label = bundle.method_key.replace("_", " ").title()
        header_row.append(ft.Text(
            f"📐 {method_label}",
            size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY))

        type_icons = {
            "tabulation":   "📊 Tabulación",
            "prerequisite": "🔑 Prereq.",
            "analysis":     "🧠 Análisis",
            "open":         "✏️ Abierta",
            "multiple_choice": "☑️ Opción múltiple",
            "numeric_input":   "🔢 Numérico",
            "fill_step":       "🔢 Paso a paso",
        }
        header_row.append(ft.Text(
            type_icons.get(bundle.exercise_type, bundle.exercise_type),
            size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY))

        self._question_area.controls.append(
            ft.Row(header_row, spacing=Spacing.MD))

        # Mostrar f(x) = ... solo si la pregunta tiene expresión procedural
        if bundle.params.get("expr"):
            self._question_area.controls.append(
                math_text(f"f(x) = {bundle.params['expr']}"))

        self._question_area.controls.append(
            ft.Divider(color=Colors.BORDER, height=1))
        self._question_area.controls.append(ft.Text(
            bundle.question_text,
            size=Typography.SIZE_SM, color=Colors.TEXT_PRIMARY))

        if bundle.hint:
            self._question_area.controls.append(ft.Container(
                content=ft.Text(
                    f"💡 {bundle.hint}",
                    size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY, italic=True),
                padding=ft.Padding(left=0, top=Spacing.SM, right=0, bottom=0),
            ))

        # ── Zona de respuesta según tipo ──
        self._answer_area.controls.clear()
        if _is_bank_question(bundle) and bundle.exercise_type == "multiple_choice":
            self._build_bank_mc(bundle)
        elif _is_bank_question(bundle) and bundle.exercise_type == "tabulation":
            self._build_tabulation(bundle)
        elif _is_bank_question(bundle):
            self._build_bank_input(bundle)
        elif bundle.exercise_type == "multiple_choice":
            self._build_multiple_choice(bundle)
        else:
            self._build_numeric_input(bundle)

        self._start_timer()
        self._page.update()

    # ── Tipos de respuesta ────────────────────────────────────────────────────

    def _build_tabulation(self, bundle: ExerciseBundle) -> None:
        """Pregunta de tabulación: widget interactivo con tabla editable."""
        from ui.widgets.tabulation_widget import TabulationWidget

        def on_tabulation_assessed(is_correct: bool) -> None:
            validation = _make_bank_validation(is_correct, bundle.correct_answer)

            class _PassthroughValidator:
                def validate(self, *_a, **_k):
                    return validation

            _, score = self._session.answer("tabulation_assessed", _PassthroughValidator())
            self._show_feedback(validation, score)
            self._refresh_score()
            self._next_btn.disabled = False
            self._awaiting_answer = False
            self._page.update()

        widget = TabulationWidget(
            solution=str(bundle.correct_answer),
            procedure=bundle.solver_result.extra.get("procedure", ""),
            method_key=bundle.method_key,
            on_reveal=on_tabulation_assessed,
            page=self._page,
        )
        self._answer_area.controls.append(widget)

    def _build_bank_mc(self, bundle: ExerciseBundle) -> None:
        """Opción múltiple para preguntas del banco (con reveal de procedimiento)."""
        self._answer_area.controls.append(ft.Text(
            "Elige la respuesta correcta:",
            size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY))

        for i, option in enumerate(bundle.options):
            # Truncar opciones largas para que quepan en botón
            label = option if len(option) <= 120 else option[:117] + "…"
            btn = ft.OutlinedButton(
                text=label,
                data=i,
                style=ft.ButtonStyle(
                    color=Colors.TEXT_PRIMARY,
                    side=ft.BorderSide(1, Colors.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=16, top=10, right=16, bottom=10),
                ),
                on_click=lambda e: self._submit_bank_mc(e.control.data),
                width=700,
            )
            self._answer_area.controls.append(btn)

    def _submit_bank_mc(self, chosen_idx: int) -> None:
        """Procesa la selección en un MC del banco."""
        if not self._awaiting_answer:
            return
        self._awaiting_answer = False
        self._stop_timer()

        bundle = self._current_bundle
        is_correct = chosen_idx == bundle.correct_option
        correct_text = bundle.options[bundle.correct_option]
        procedure = bundle.solver_result.extra.get("procedure", "")

        # Colorear botones: verde la correcta, rojo la elegida si falla
        for ctrl in self._answer_area.controls:
            if not isinstance(ctrl, ft.OutlinedButton):
                continue
            idx = ctrl.data
            if idx == bundle.correct_option:
                ctrl.style = ft.ButtonStyle(
                    color=Colors.SUCCESS,
                    side=ft.BorderSide(2, Colors.SUCCESS),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=16, top=10, right=16, bottom=10),
                    bgcolor={ft.ControlState.DEFAULT: "#0D2E1A"},
                )
            elif idx == chosen_idx and not is_correct:
                ctrl.style = ft.ButtonStyle(
                    color=Colors.ERROR,
                    side=ft.BorderSide(2, Colors.ERROR),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=16, top=10, right=16, bottom=10),
                    bgcolor={ft.ControlState.DEFAULT: "#4A1515"},
                )
            ctrl.disabled = True

        # Mostrar procedimiento si existe
        if procedure:
            self._answer_area.controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                            weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                    ft.Text(procedure, size=Typography.SIZE_XS,
                            color=Colors.TEXT_SECONDARY, selectable=True),
                ], spacing=Spacing.SM),
                bgcolor=Colors.BG_CARD,
                border_radius=Radius.MD,
                padding=ft.Padding(left=Spacing.MD, top=Spacing.MD,
                                   right=Spacing.MD, bottom=Spacing.MD),
                margin=ft.Padding(left=0, top=Spacing.SM, right=0, bottom=0),
            ))

        validation = _make_bank_validation(is_correct, correct_text)

        class _PassthroughValidator:
            def validate(self, *_a, **_k):
                return validation

        _, score = self._session.answer("mc_bank", _PassthroughValidator())
        self._after_answer(validation, score)

    def _build_bank_input(self, bundle: ExerciseBundle) -> None:
        """Pregunta de banco: campo libre + botón Ver Solución."""
        if bundle.exercise_type == "analysis":
            # Solo requiere leer
            self._answer_area.controls.append(ft.Text(
                "Reflexiona sobre la pregunta antes de ver la solución.",
                size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY, italic=True))
            self._answer_area.controls.append(
                primary_button("Ver solución 👁", lambda _: self._reveal_solution()))
        else:
            input_field = ft.TextField(
                label="Tu respuesta / desarrollo",
                hint_text="Escribe tu respuesta aquí...",
                multiline=True, min_lines=3, max_lines=8,
                bgcolor=Colors.BG_SURFACE, color=Colors.TEXT_PRIMARY,
                border_color=Colors.BORDER,
                focused_border_color=Colors.PRIMARY,
                border_radius=Radius.SM,
            )
            self._answer_area.controls.extend([
                input_field,
                primary_button("Ver solución 👁", lambda _: self._reveal_solution()),
            ])

    def _build_numeric_input(self, bundle: ExerciseBundle) -> None:
        input_field = ft.TextField(
            label="Tu respuesta",
            hint_text="Ej: 2.3456",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=Colors.BG_SURFACE, color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            width=300,
            on_submit=lambda e: self._submit_procedural(e.control.value),
        )
        submit_btn = primary_button(
            "Verificar",
            lambda e: self._submit_procedural(input_field.value),
            icon=ft.icons.CHECK_CIRCLE_OUTLINE,
        )
        self._answer_area.controls.append(
            ft.Row([input_field, submit_btn], spacing=Spacing.MD))

    def _build_multiple_choice(self, bundle: ExerciseBundle) -> None:
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
                on_click=lambda e: self._submit_procedural(e.control.data),
            )
            self._answer_area.controls.append(btn)

    # ── Flujo de respuesta: banco ─────────────────────────────────────────────

    def _reveal_solution(self) -> None:
        """Fase 2: muestra solución + botones de auto-evaluación."""
        if not self._awaiting_answer:
            return
        self._stop_timer()

        bundle = self._current_bundle
        solution_text = bundle.correct_answer
        procedure_text = bundle.solver_result.extra.get("procedure", "")

        self._answer_area.controls.clear()

        # Mostrar solución
        sol_col = ft.Column([
            ft.Text("📋 Solución", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.SUCCESS),
            ft.Text(str(solution_text), size=Typography.SIZE_XS,
                    color=Colors.TEXT_PRIMARY, selectable=True),
        ], spacing=Spacing.SM)

        if procedure_text:
            sol_col.controls.extend([
                ft.Divider(color=Colors.BORDER),
                ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                ft.Text(procedure_text, size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY, selectable=True),
            ])

        self._answer_area.controls.append(
            ft.Container(content=sol_col,
                         bgcolor=Colors.BG_CARD,
                         border_radius=Radius.MD,
                         padding=ft.Padding(left=Spacing.MD, top=Spacing.MD,
                                            right=Spacing.MD, bottom=Spacing.MD)))

        # Botones de auto-evaluación
        self._answer_area.controls.append(ft.Text(
            "¿Tu respuesta fue correcta?",
            size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
            color=Colors.TEXT_PRIMARY))
        self._answer_area.controls.append(ft.Row([
            ft.ElevatedButton(
                "✅  Sí, lo sabía",
                on_click=lambda _: self._self_assess(True),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#1B4332"},
                    color=Colors.SUCCESS,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
            ft.ElevatedButton(
                "❌  No, me equivoqué",
                on_click=lambda _: self._self_assess(False),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#4A1515"},
                    color=Colors.ERROR,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
        ], spacing=Spacing.MD))
        self._page.update()

    def _self_assess(self, is_correct: bool) -> None:
        """Registra la auto-evaluación y muestra el score."""
        if not self._awaiting_answer:
            return
        self._awaiting_answer = False

        bundle = self._current_bundle
        validation = _make_bank_validation(is_correct, str(bundle.correct_answer))

        # Usamos un validador pasivo que devuelve el ValidationResult ya creado
        class _PassthroughValidator:
            def validate(self, *_a, **_k):
                return validation

        _, score = self._session.answer("self_assessed", _PassthroughValidator())
        self._after_answer(validation, score)

    # ── Flujo de respuesta: procedural ────────────────────────────────────────

    def _submit_procedural(self, raw_answer: Any) -> None:
        if not self._awaiting_answer:
            return
        self._awaiting_answer = False
        self._stop_timer()

        from engine.nonlinear.bisection import BisectionValidator
        validator_map: dict[str, Any] = {
            "biseccion": BisectionValidator(),
        }
        validator = validator_map.get(
            self._session._method_key, BisectionValidator())

        bundle = self._current_bundle
        if bundle.exercise_type == "multiple_choice" and isinstance(raw_answer, int):
            raw_answer = bundle.options[raw_answer]

        validation, score = self._session.answer(raw_answer, validator)
        self._after_answer(validation, score)

    # ── Feedback ──────────────────────────────────────────────────────────────

    def _show_feedback(
        self, validation: ValidationResult, score: ScoreBreakdown
    ) -> None:
        self._feedback_area.controls.clear()

        # Para banco: feedback más compacto (la solución ya está arriba)
        if _is_bank_question(self._current_bundle):
            banner_text = (
                "✅ ¡Genial! Sigue así." if validation.is_correct
                else "📖 Revisa bien el procedimiento para la próxima."
            )
            self._feedback_area.controls.append(
                feedback_banner(validation.is_correct, banner_text))
        else:
            self._feedback_area.controls.append(
                feedback_banner(validation.is_correct, validation.feedback))

        if validation.is_correct:
            breakdown = ft.Row([
                self._mini_score("Base",     score.base),
                ft.Text("+", color=Colors.TEXT_MUTED),
                self._mini_score("Rapidez",  score.time_bonus),
                ft.Text("+", color=Colors.TEXT_MUTED),
                self._mini_score("Racha",    score.streak_bonus),
                ft.Text("=", color=Colors.TEXT_MUTED),
                self._mini_score("TOTAL",    score.total, highlight=True),
                ft.Text(f"+{score.xp_earned} XP",
                        color=Colors.PRIMARY,
                        size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD),
            ], spacing=Spacing.SM,
               alignment=ft.MainAxisAlignment.CENTER, wrap=True)
            self._feedback_area.controls.append(breakdown)

    @staticmethod
    def _mini_score(label: str, value: int, highlight: bool = False) -> ft.Column:
        return ft.Column([
            ft.Text(f"{value:,}", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD,
                    color=Colors.GOLD if highlight else Colors.TEXT_PRIMARY),
            ft.Text(label, size=Typography.SIZE_XS, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _on_next(self, e: ft.ControlEvent) -> None:
        bundle = self._session.next_question()
        self._load_bundle(bundle)

    def _on_end(self, e: ft.ControlEvent | None = None) -> None:
        self._stop_timer()
        summary = self._session.end()
        self._on_end_session(summary)

    def _on_home(self, e: ft.ControlEvent) -> None:
        self._stop_timer()
        self._session.end()
        self._on_back_to_menu()

    def _after_answer(
        self,
        validation: ValidationResult,
        score: ScoreBreakdown,
    ) -> None:
        self._show_feedback(validation, score)
        self._refresh_score()

        if self._session.lives_remaining <= 0:
            self._feedback_area.controls.append(
                ft.Text(
                    "💀 Has perdido todas las vidas. La sesión ha terminado.",
                    size=Typography.SIZE_SM,
                    color=Colors.ERROR,
                    weight=ft.FontWeight.BOLD,
                )
            )
            self._page.update()
            self._on_end(None)
            return

        self._next_btn.disabled = False
        # Ensure action buttons are present (create fresh home button to avoid reuse)
        if not self._action_row.controls or self._action_row.controls[0].text != "Volver al menú":
            home_btn = secondary_button("Volver al menú", self._on_home)
            # keep next button as second
            self._action_row.controls = [home_btn, self._next_btn]
        self._page.update()

    # ── Marcador ──────────────────────────────────────────────────────────────

    def _refresh_score(self) -> None:
        from storage.repositories.player_repository import PlayerRepository
        from engine.scoring.scorer import Scorer
        repo = PlayerRepository()
        streak = repo.get_streak(self._session._player_id)
        player = repo.get_player_by_id(self._session._player_id)
        self._streak_text.value = f"🔥 {streak.current}"
        self._timer_text.value = f"⏱ {self._elapsed_seconds}s"
        self._lives_text.value = f"❤️ {self._session.lives_remaining}"
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