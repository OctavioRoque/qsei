"""
ui/screens/game_screen.py
==========================
Pantalla de juego con:
  - Sistema de vidas (3 corazones)
  - 5 Comodines de un solo uso por partida
  - 3 Cartas especiales
  - Game Over al perder todas las vidas
  - Validación automática de tablas
"""

from __future__ import annotations
import time, threading, random
from typing import Any, Callable
import flet as ft

from engine.utils.base_solver import ExerciseBundle, ValidationResult
from engine.scoring.scorer import ScoreBreakdown
from game.sessions.session_manager import GameSession
from game.powerups import PowerupState
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, primary_button, secondary_button,
    difficulty_badge, score_display, xp_bar, feedback_banner, math_text,
)


def _is_bank(b: ExerciseBundle) -> bool:
    return bool(b.params.get("bank_id"))


def _bank_validation(ok: bool, sol: str) -> ValidationResult:
    return ValidationResult(
        is_correct=ok, precision_score=1.0 if ok else 0.0,
        student_value=None, expected_value=None, absolute_error=0.0,
        feedback=("✅ ¡Correcto!" if ok else f"❌ Solución:\n{sol}"),
    )


class _Passthrough:
    def __init__(self, v): self._v = v
    def validate(self, *_a, **_k): return self._v


# ── Powerup button ────────────────────────────────────────────────────────────

def _pwbtn(icon: str, label: str, tooltip: str, on_click) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Text(icon, size=20, text_align=ft.TextAlign.CENTER),
            ft.Text(label, size=9, color=Colors.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        tooltip=tooltip,
        width=56, height=52,
        padding=ft.Padding(4, 4, 4, 4),
        border_radius=Radius.SM,
        bgcolor=Colors.BG_SURFACE,
        border=ft.border.all(1, Colors.BORDER),
        on_click=on_click,
        data={"active": True},
    )


def _set_btn_used(btn: ft.Container) -> None:
    btn.opacity = 0.35
    btn.on_click = None
    btn.data = {"active": False}
    btn.border = ft.border.all(1, Colors.TEXT_MUTED)


# ── Main screen ───────────────────────────────────────────────────────────────

class GameScreen(ft.Column):

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

        self._bundle: ExerciseBundle | None = None
        self._awaiting = True
        self._elapsed  = 0
        self._timer_running = False
        self._timer_thread: threading.Thread | None = None
        self._timer_paused = False   # Tiempo Extra activo
        self._score_mult   = 1       # 1 o 2 (Carta Estrella)
        self._mc_buttons: list[ft.OutlinedButton] = []

        self._pw = PowerupState()

        # ── Header widgets ──
        self._score_col  = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, width=240)
        self._lives_row  = ft.Row(spacing=4)
        self._streak_txt = ft.Text("🔥 0", color=Colors.WARNING,
                                   size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD)
        self._timer_txt  = ft.Text("⏱ 0s", color=Colors.TEXT_SECONDARY,
                                   size=Typography.SIZE_SM)
        self._double_badge = ft.Container(
            content=ft.Text("⭐ ×2 PUNTOS", size=10, color=Colors.GOLD,
                            weight=ft.FontWeight.BOLD),
            bgcolor="#1A1400", border=ft.border.all(1, Colors.GOLD),
            border_radius=Radius.SM,
            padding=ft.Padding(8, 3, 8, 3), visible=False)

        # ── Powerup buttons (refs stored for state updates) ──
        self._pw_btns: dict[str, ft.Container] = {}
        pw_bar = self._build_pw_bar()

        # ── Content areas ──
        self._q_area  = ft.Column(spacing=Spacing.MD)
        self._a_area  = ft.Column(spacing=Spacing.SM)
        self._fb_area = ft.Column()
        self._next_btn = primary_button("Siguiente →", self._on_next, disabled=True)
        self._act_row  = ft.Row(
            [secondary_button("Volver al menú", self._on_home), self._next_btn],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        header = ft.Container(
            content=ft.Column([
                ft.Row([
                    self._score_col,
                    ft.Row([self._lives_row, self._streak_txt,
                            self._timer_txt, self._double_badge],
                           spacing=Spacing.SM),
                    secondary_button("Terminar", self._on_end),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                pw_bar,
            ], spacing=6),
            padding=ft.Padding(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM),
            bgcolor=Colors.BG_SURFACE,
            border=ft.border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        )

        self.controls = [
            header,
            ft.Container(
                content=ft.Column([
                    card(self._q_area, padding=Spacing.LG),
                    card(self._a_area, padding=Spacing.MD),
                    self._fb_area,
                    self._act_row,
                ], spacing=Spacing.MD, scroll=ft.ScrollMode.AUTO),
                padding=ft.Padding(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD),
                expand=True),
        ]
        self.spacing = 0
        self.expand = True

    # ── Build powerup bar ──────────────────────────────────────────────────

    def _build_pw_bar(self) -> ft.Row:
        comdns = [
            _pwbtn("🖼",  "Pista",      "Pista Visual (~70% confiable)",
                   lambda _: self._use_pista()),
            _pwbtn("📊",  "Stats",      "% de alumnos por opción",
                   lambda _: self._use_stats()),
            _pwbtn("½½",  "50/50",      "Elimina 2 respuestas incorrectas",
                   lambda _: self._use_fifty()),
            _pwbtn("⏰",  "+60s",       "Pausa el temporizador 60 s",
                   lambda _: self._use_tiempo()),
            _pwbtn("💡",  "Ayuda",      "Fórmula clave o elimina 1 opción",
                   lambda _: self._use_ayuda()),
        ]
        cartas = [
            _pwbtn("⭐", "Estrella",  "×2 puntos en la siguiente pregunta",
                   lambda _: self._use_estrella()),
            _pwbtn("⚡", "Rayo",      "Omite esta pregunta como correcta",
                   lambda _: self._use_rayo()),
            _pwbtn("🏆", "Trofeo",    "Recupera una vida",
                   lambda _: self._use_trofeo()),
        ]
        keys_c = ["pista_visual","estadisticas","fifty_fifty",
                  "tiempo_extra","ayuda_adicional"]
        keys_k = ["carta_estrella","carta_rayo","carta_trofeo"]
        for k, b in zip(keys_c, comdns):
            self._pw_btns[k] = b
        for k, b in zip(keys_k, cartas):
            self._pw_btns[k] = b

        return ft.Row([
            ft.Text("COMODINES", size=9, color=Colors.TEXT_MUTED,
                    weight=ft.FontWeight.BOLD),
            *comdns,
            ft.Container(width=1, height=40,
                         bgcolor=Colors.BORDER, margin=ft.Padding(4,0,4,0)),
            ft.Text("CARTAS", size=9, color=Colors.TEXT_MUTED,
                    weight=ft.FontWeight.BOLD),
            *cartas,
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ── Start ────────────────────────────────────────────────────────────────

    def load_first_question(self) -> None:
        self._refresh_header()
        bundle = self._session.start()
        self._load_bundle(bundle)

    # ── Load question ─────────────────────────────────────────────────────

    def _load_bundle(self, bundle: ExerciseBundle) -> None:
        self._bundle = bundle
        self._awaiting = True
        self._mc_buttons = []
        self._elapsed = 0

        self._fb_area.controls.clear()
        self._next_btn.disabled = True

        # Question header
        self._q_area.controls.clear()
        m_label = bundle.method_key.replace("_", " ").title()
        type_icons = {
            "tabulation":      "📊 Tabulación",
            "prerequisite":    "🔑 Prereq.",
            "analysis":        "🧠 Análisis",
            "open":            "✏️ Abierta",
            "multiple_choice": "☑️ Opción múltiple",
            "numeric_input":   "🔢 Numérico",
        }
        self._q_area.controls += [
            ft.Row([
                difficulty_badge(bundle.difficulty),
                ft.Text(f"📐 {m_label}", size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY),
                ft.Text(type_icons.get(bundle.exercise_type, bundle.exercise_type),
                        size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ], spacing=Spacing.MD),
        ]
        if bundle.params.get("expr"):
            self._q_area.controls.append(math_text(f"f(x) = {bundle.params['expr']}"))
        self._q_area.controls += [
            ft.Divider(color=Colors.BORDER, height=1),
            ft.Text(bundle.question_text, size=Typography.SIZE_SM,
                    color=Colors.TEXT_PRIMARY, selectable=True),
        ]

        # Answer area
        self._a_area.controls.clear()
        if _is_bank(bundle) and bundle.exercise_type == "multiple_choice":
            self._build_bank_mc(bundle)
        elif _is_bank(bundle) and bundle.exercise_type == "tabulation":
            self._build_tabulation(bundle)
        elif _is_bank(bundle):
            self._build_bank_open(bundle)
        elif bundle.exercise_type == "multiple_choice":
            self._build_mc(bundle)
        else:
            self._build_numeric(bundle)

        self._start_timer()
        self._page.update()

    # ── Answer builders ──────────────────────────────────────────────────

    def _build_bank_mc(self, b: ExerciseBundle) -> None:
        self._a_area.controls.append(
            ft.Text("Elige la respuesta correcta:",
                    size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY))
        for i, opt in enumerate(b.options):
            label = opt[:120] + "…" if len(opt) > 120 else opt
            btn = ft.OutlinedButton(
                text=label, data=i,
                style=ft.ButtonStyle(
                    color=Colors.TEXT_PRIMARY,
                    side=ft.BorderSide(1, Colors.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(16, 10, 16, 10)),
                on_click=lambda e: self._submit_bank_mc(e.control.data),
                width=680)
            self._mc_buttons.append(btn)
            self._a_area.controls.append(btn)

    def _build_tabulation(self, b: ExerciseBundle) -> None:
        from ui.widgets.tabulation_widget import TabulationWidget

        def _done(ok: bool):
            v = _bank_validation(ok, b.correct_answer)
            _, score = self._session.answer("tab", _Passthrough(v))
            self._finish_answer(v, score)

        self._a_area.controls.append(TabulationWidget(
            solution=str(b.correct_answer),
            procedure=b.solver_result.extra.get("procedure", ""),
            method_key=b.method_key,
            on_reveal=_done,
            page=self._page))

    def _build_bank_open(self, b: ExerciseBundle) -> None:
        if b.exercise_type == "analysis":
            self._a_area.controls += [
                ft.Text("Reflexiona y luego ve la solución.",
                        size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY,
                        italic=True),
                primary_button("Ver solución 👁", lambda _: self._reveal_open()),
            ]
        else:
            tf = ft.TextField(
                label="Tu respuesta", hint_text="Escribe aquí...",
                multiline=True, min_lines=3, max_lines=6,
                bgcolor=Colors.BG_SURFACE, color=Colors.TEXT_PRIMARY,
                border_color=Colors.BORDER,
                focused_border_color=Colors.PRIMARY,
                border_radius=Radius.SM)
            self._a_area.controls += [
                tf,
                primary_button("Ver solución 👁", lambda _: self._reveal_open()),
            ]

    def _build_mc(self, b: ExerciseBundle) -> None:
        for i, opt in enumerate(b.options):
            btn = ft.OutlinedButton(
                text=f"  {opt}  ", data=i,
                style=ft.ButtonStyle(
                    color=Colors.TEXT_PRIMARY,
                    side=ft.BorderSide(1, Colors.BORDER),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(20, 12, 20, 12)),
                on_click=lambda e: self._submit_procedural(e.control.data))
            self._mc_buttons.append(btn)
            self._a_area.controls.append(btn)

    def _build_numeric(self, b: ExerciseBundle) -> None:
        tf = ft.TextField(
            label="Tu respuesta", hint_text="Ej: 2.3456",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=Colors.BG_SURFACE, color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM, width=300,
            on_submit=lambda e: self._submit_procedural(e.control.value))
        self._a_area.controls.append(ft.Row([
            tf,
            primary_button("Verificar",
                           lambda e: self._submit_procedural(tf.value),
                           icon=ft.icons.CHECK_CIRCLE_OUTLINE),
        ], spacing=Spacing.MD))

    # ── Answer submission ─────────────────────────────────────────────────

    def _submit_bank_mc(self, idx: int) -> None:
        if not self._awaiting: return
        self._awaiting = False
        self._stop_timer()

        b = self._bundle
        ok = idx == b.correct_option
        proc = b.solver_result.extra.get("procedure", "")

        for btn in self._mc_buttons:
            i = btn.data
            if i == b.correct_option:
                btn.style = ft.ButtonStyle(
                    color=Colors.SUCCESS,
                    side=ft.BorderSide(2, Colors.SUCCESS),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(16, 10, 16, 10),
                    bgcolor={ft.ControlState.DEFAULT: "#0D2E1A"})
            elif i == idx and not ok:
                btn.style = ft.ButtonStyle(
                    color=Colors.ERROR,
                    side=ft.BorderSide(2, Colors.ERROR),
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(16, 10, 16, 10),
                    bgcolor={ft.ControlState.DEFAULT: "#4A1515"})
            btn.disabled = True

        if proc:
            self._a_area.controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                            weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                    ft.Text(proc, size=Typography.SIZE_XS,
                            color=Colors.TEXT_SECONDARY, selectable=True),
                ], spacing=Spacing.SM),
                bgcolor=Colors.BG_CARD, border_radius=Radius.MD,
                padding=ft.Padding(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD),
                margin=ft.Padding(0, Spacing.SM, 0, 0)))

        v = _bank_validation(ok, b.options[b.correct_option])
        _, score = self._session.answer("mc_bank", _Passthrough(v))
        self._finish_answer(v, score)

    def _reveal_open(self) -> None:
        if not self._awaiting: return
        self._stop_timer()
        b = self._bundle
        sol = b.correct_answer
        proc = b.solver_result.extra.get("procedure", "")

        self._a_area.controls.clear()
        col = ft.Column([
            ft.Text("📋 Solución", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.SUCCESS),
            ft.Text(str(sol), size=Typography.SIZE_XS,
                    color=Colors.TEXT_PRIMARY, selectable=True),
        ], spacing=Spacing.SM)
        if proc:
            col.controls += [
                ft.Divider(color=Colors.BORDER),
                ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                ft.Text(proc, size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY, selectable=True),
            ]
        self._a_area.controls.append(ft.Container(
            content=col, bgcolor=Colors.BG_CARD, border_radius=Radius.MD,
            padding=ft.Padding(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)))
        self._a_area.controls.append(
            ft.Text("¿Tu respuesta fue correcta?", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY))
        self._a_area.controls.append(ft.Row([
            ft.ElevatedButton("✅  Sí, lo sabía",
                on_click=lambda _: self._self_assess(True),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#1B4332"},
                    color=Colors.SUCCESS,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(20, 12, 20, 12))),
            ft.ElevatedButton("❌  No, me equivoqué",
                on_click=lambda _: self._self_assess(False),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#4A1515"},
                    color=Colors.ERROR,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(20, 12, 20, 12))),
        ], spacing=Spacing.MD))
        self._page.update()

    def _self_assess(self, ok: bool) -> None:
        if not self._awaiting: return
        self._awaiting = False
        b = self._bundle
        v = _bank_validation(ok, str(b.correct_answer))
        _, score = self._session.answer("self_assessed", _Passthrough(v))
        self._finish_answer(v, score)

    def _submit_procedural(self, raw: Any) -> None:
        if not self._awaiting: return
        self._awaiting = False
        self._stop_timer()
        from engine.nonlinear.bisection import BisectionValidator
        validator = BisectionValidator()
        b = self._bundle
        if b.exercise_type == "multiple_choice" and isinstance(raw, int):
            raw = b.options[raw]
        v, score = self._session.answer(raw, validator)
        self._finish_answer(v, score)

    def _finish_answer(self, v: ValidationResult, score: ScoreBreakdown) -> None:
        # Apply double-points if active
        if self._pw.double_points_next and v.is_correct:
            self._pw.double_points_next = False
            self._double_badge.visible = False
            from dataclasses import replace
            score = replace(score, total=score.total * 2,
                            xp_earned=score.xp_earned * 2)

        self._show_feedback(v, score)
        self._refresh_header()

        if self._session.lives_remaining <= 0:
            self._page.update()
            self._show_game_over()
            return

        self._next_btn.disabled = False
        self._page.update()

    # ── Feedback ─────────────────────────────────────────────────────────

    def _show_feedback(self, v: ValidationResult, score: ScoreBreakdown) -> None:
        self._fb_area.controls.clear()
        msg = "✅ ¡Genial!" if v.is_correct else "📖 Revisa el procedimiento."
        self._fb_area.controls.append(feedback_banner(v.is_correct, msg))
        if v.is_correct:
            self._fb_area.controls.append(ft.Row([
                self._mini("Base",    score.base),
                ft.Text("+", color=Colors.TEXT_MUTED),
                self._mini("Rapidez", score.time_bonus),
                ft.Text("+", color=Colors.TEXT_MUTED),
                self._mini("Racha",   score.streak_bonus),
                ft.Text("=", color=Colors.TEXT_MUTED),
                self._mini("TOTAL",   score.total, True),
                ft.Text(f"+{score.xp_earned} XP",
                        color=Colors.PRIMARY, size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD),
            ], spacing=Spacing.SM, alignment=ft.MainAxisAlignment.CENTER, wrap=True))

    @staticmethod
    def _mini(lbl: str, val: int, hi: bool = False) -> ft.Column:
        return ft.Column([
            ft.Text(f"{val:,}", size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
                    color=Colors.GOLD if hi else Colors.TEXT_PRIMARY),
            ft.Text(lbl, size=Typography.SIZE_XS, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

    # ── Header refresh ────────────────────────────────────────────────────

    def _refresh_header(self) -> None:
        from storage.repositories.player_repository import PlayerRepository
        from engine.scoring.scorer import Scorer
        repo = PlayerRepository()
        streak = repo.get_streak(self._session._player_id)
        player = repo.get_player_by_id(self._session._player_id)
        self._streak_txt.value = f"🔥 {streak.current}"
        lvl, xp_in, xp_need = Scorer.level_from_xp(player.xp if player else 0)
        self._score_col.controls = [
            score_display(self._session.current_score),
            xp_bar(xp_in, xp_need, lvl),
        ]
        # Lives hearts
        lives = self._session.lives_remaining
        self._lives_row.controls = [
            ft.Text("❤️" if i < lives else "🖤", size=16)
            for i in range(self._session._max_lives)
        ]

    # ── Navigation ────────────────────────────────────────────────────────

    def _on_next(self, _=None) -> None:
        bundle = self._session.next_question()
        self._load_bundle(bundle)

    def _on_end(self, _=None) -> None:
        self._stop_timer()
        summary = self._session.end()
        self._on_end_session(summary)

    def _on_home(self, _=None) -> None:
        self._stop_timer()
        self._session.end()
        self._on_back_to_menu()

    # ── Game Over ─────────────────────────────────────────────────────────

    def _show_game_over(self) -> None:
        overlay = ft.Container(
            content=ft.Column([
                ft.Text("💀", size=80, text_align=ft.TextAlign.CENTER),
                ft.Text("GAME OVER", size=36, weight=ft.FontWeight.BOLD,
                        color=Colors.ERROR, text_align=ft.TextAlign.CENTER,
                        font_family="Orbitron"),
                ft.Text(f"Puntuación final: {self._session.current_score:,}",
                        size=Typography.SIZE_MD, color=Colors.GOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=Spacing.LG),
                ft.Row([
                    secondary_button("🏠 Menú principal", self._on_home),
                    primary_button("🔄 Intentar de nuevo",
                                   lambda _: self._on_end()),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=Spacing.LG),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=Spacing.MD),
            expand=True,
            bgcolor=Colors.BG_DARK + "EE",   # dark semi-transparent
            alignment=ft.alignment.center,
            padding=Spacing.XL,
        )
        # Replace entire screen content
        self.controls.append(ft.Stack([overlay], expand=True))
        self._page.update()

    # ── Timer ─────────────────────────────────────────────────────────────

    def _start_timer(self) -> None:
        self._timer_running = True
        self._elapsed = 0
        self._timer_paused = False

        def _tick():
            while self._timer_running:
                time.sleep(1)
                if self._timer_running and not self._timer_paused:
                    self._elapsed += 1
                    self._timer_txt.value = f"⏱ {self._elapsed}s"
                    try:
                        self._page.update()
                    except Exception:
                        break

        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def _stop_timer(self) -> None:
        self._timer_running = False

    # ════════════════════════════════════════════════════════════════
    # COMODINES
    # ════════════════════════════════════════════════════════════════

    def _use_pista(self) -> None:
        if not self._pw.use_comodin("pista_visual"): return
        _set_btn_used(self._pw_btns["pista_visual"])
        b = self._bundle
        hint = b.hint or b.solver_result.extra.get("procedure", "")[:150]
        if not hint:
            hint = "No hay pista adicional disponible para esta pregunta."
        self._page.dialog = ft.AlertDialog(
            title=ft.Text("🖼 Pista Visual", color=Colors.PRIMARY,
                          weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Container(
                    content=ft.Text(hint, size=Typography.SIZE_SM,
                                    color=Colors.TEXT_PRIMARY, selectable=True),
                    bgcolor=Colors.BG_CARD, border_radius=Radius.MD,
                    padding=ft.Padding(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)),
                ft.Text("⚠️ Confiabilidad aproximada: 70%",
                        size=Typography.SIZE_XS, color=Colors.WARNING, italic=True),
            ], spacing=Spacing.SM, width=480),
            actions=[ft.TextButton("Cerrar",
                on_click=lambda _: self._close_dialog())],
        )
        self._page.dialog.open = True
        self._page.update()

    def _use_stats(self) -> None:
        if not self._pw.use_comodin("estadisticas"): return
        _set_btn_used(self._pw_btns["estadisticas"])
        b = self._bundle
        if b.exercise_type != "multiple_choice" or not b.options:
            self._toast("📊 Las Estadísticas solo funcionan en preguntas de opción múltiple.")
            return

        # Generar datos estadísticos (reales del DB + fallback sintético)
        stats = self._get_stats_data(b)

        bars: list[ft.Control] = []
        for i, (opt, pct) in enumerate(zip(b.options, stats)):
            label = opt[:60] + "…" if len(opt) > 60 else opt
            bars.append(ft.Column([
                ft.Container(height=max(4, int(pct * 1.2)),
                             width=60,
                             bgcolor=Colors.PRIMARY,
                             border_radius=ft.BorderRadius(4, 4, 0, 0)),
                ft.Text(f"{pct:.0f}%", size=10, color=Colors.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER, width=60),
                ft.Text(f"Op.{i+1}", size=9, color=Colors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER, width=60),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))

        self._page.dialog = ft.AlertDialog(
            title=ft.Text("📊 Estadísticas de Respuestas", color=Colors.PRIMARY,
                          weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text("% de alumnos que eligió cada opción:",
                        size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
                ft.Container(height=Spacing.SM),
                ft.Row(bars, alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.END,
                       spacing=Spacing.MD),
                ft.Container(height=Spacing.SM),
                ft.Text("⚠️ La opción más elegida suele ser la correcta, pero no siempre.",
                        size=Typography.SIZE_XS, color=Colors.WARNING, italic=True),
            ], spacing=4, width=400, height=220),
            actions=[ft.TextButton("Cerrar",
                on_click=lambda _: self._close_dialog())],
        )
        self._page.dialog.open = True
        self._page.update()

    def _get_stats_data(self, b: ExerciseBundle) -> list[float]:
        """Retorna lista de % por opción. Usa DB si hay datos, sino genera."""
        from storage.sqlite.database import DatabaseManager
        db = DatabaseManager.get_instance()
        rows = db.fetchall(
            "SELECT student_answer, COUNT(*) as n FROM answers "
            "WHERE question_hash=? GROUP BY student_answer",
            (b.hash,))
        if rows and sum(r["n"] for r in rows) >= 5:
            totals = {r["student_answer"]: r["n"] for r in rows}
            grand = sum(totals.values())
            return [totals.get(f'"{opt}"', 0) / grand * 100 for opt in b.options]
        # Generar datos plausibles
        rng = random.Random(hash(b.hash + "stats") % 99999)
        correct = b.correct_option or 0
        pcts = []
        correct_pct = rng.uniform(38, 62)
        remaining = 100 - correct_pct
        others = [i for i in range(len(b.options)) if i != correct]
        other_pcts = []
        for j, _ in enumerate(others):
            if j == len(others) - 1:
                other_pcts.append(remaining)
            else:
                p = rng.uniform(0, remaining * 0.65)
                other_pcts.append(p)
                remaining -= p
        oi = 0
        for i in range(len(b.options)):
            if i == correct:
                pcts.append(correct_pct)
            else:
                pcts.append(other_pcts[oi]); oi += 1
        return pcts

    def _use_fifty(self) -> None:
        if not self._pw.use_comodin("fifty_fifty"): return
        _set_btn_used(self._pw_btns["fifty_fifty"])
        b = self._bundle
        if b.exercise_type != "multiple_choice" or not self._mc_buttons:
            self._toast("½½ El 50/50 solo funciona en opción múltiple.")
            return
        wrong = [btn for btn in self._mc_buttons
                 if btn.data != b.correct_option and not btn.disabled]
        for btn in random.sample(wrong, min(2, len(wrong))):
            btn.opacity = 0.3
            btn.disabled = True
        self._page.update()

    def _use_tiempo(self) -> None:
        if not self._pw.use_comodin("tiempo_extra"): return
        _set_btn_used(self._pw_btns["tiempo_extra"])
        self._timer_paused = True

        def _resume():
            time.sleep(60)
            self._timer_paused = False

        threading.Thread(target=_resume, daemon=True).start()
        self._toast("⏰ ¡Temporizador pausado 60 segundos!")

    def _use_ayuda(self) -> None:
        if not self._pw.use_comodin("ayuda_adicional"): return
        _set_btn_used(self._pw_btns["ayuda_adicional"])
        b = self._bundle

        if b.exercise_type == "multiple_choice" and self._mc_buttons:
            wrong = [btn for btn in self._mc_buttons
                     if btn.data != b.correct_option and not btn.disabled]
            if wrong:
                btn = random.choice(wrong)
                btn.opacity = 0.3
                btn.disabled = True
                self._page.update()
                return

        # Mostrar fórmula/paso clave
        proc = b.solver_result.extra.get("procedure", "")
        step = proc.split("\n")[0] if proc else b.hint or "Sin ayuda adicional."
        self._page.dialog = ft.AlertDialog(
            title=ft.Text("💡 Ayuda Adicional", color=Colors.PRIMARY,
                          weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Text(step, size=Typography.SIZE_SM,
                                color=Colors.TEXT_PRIMARY, selectable=True),
                bgcolor=Colors.BG_CARD, border_radius=Radius.MD,
                padding=ft.Padding(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD),
                width=420),
            actions=[ft.TextButton("Cerrar",
                on_click=lambda _: self._close_dialog())],
        )
        self._page.dialog.open = True
        self._page.update()

    # ════════════════════════════════════════════════════════════════
    # CARTAS ESPECIALES
    # ════════════════════════════════════════════════════════════════

    def _use_estrella(self) -> None:
        if not self._pw.use_carta("carta_estrella"): return
        _set_btn_used(self._pw_btns["carta_estrella"])
        self._pw.double_points_next = True
        self._score_mult = 2
        self._double_badge.visible = True
        self._toast("⭐ ¡Próxima respuesta vale el doble!")
        self._page.update()

    def _use_rayo(self) -> None:
        if not self._awaiting: return
        if not self._pw.use_carta("carta_rayo"): return
        _set_btn_used(self._pw_btns["carta_rayo"])
        self._awaiting = False
        self._stop_timer()
        v, score = self._session.skip_as_correct()
        self._finish_answer(v, score)

    def _use_trofeo(self) -> None:
        if not self._pw.use_carta("carta_trofeo"): return
        _set_btn_used(self._pw_btns["carta_trofeo"])
        lives = self._session.restore_life()
        self._refresh_header()
        self._toast(f"🏆 ¡Vida recuperada! Vidas: {lives}")
        self._page.update()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _toast(self, msg: str) -> None:
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color=Colors.TEXT_PRIMARY),
            bgcolor=Colors.BG_SURFACE,
            duration=2500)
        self._page.snack_bar.open = True
        self._page.update()

    def _close_dialog(self) -> None:
        if self._page.dialog:
            self._page.dialog.open = False
        self._page.update()