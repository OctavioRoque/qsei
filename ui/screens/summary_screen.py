"""
ui/screens/summary_screen.py
==============================
Pantalla de resumen al finalizar una sesión de juego.
"""

from __future__ import annotations
from typing import Callable
import flet as ft

from game.sessions.session_manager import SessionSummary
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    card, title_text, subtitle_text,
    primary_button, secondary_button,
    score_display,
)


class SummaryScreen(ft.Column):

    def __init__(
        self,
        summary: SessionSummary,
        on_play_again: Callable[[], None],
        on_home: Callable[[], None],
        page: ft.Page,
    ) -> None:
        super().__init__()
        self._summary = summary
        self._on_play_again = on_play_again
        self._on_home = on_home
        self._page = page
        self._build()

    def _build(self) -> None:
        s = self._summary

        # ── Emoji de resultado ──
        if s.accuracy_pct >= 90:
            result_emoji, result_text, result_color = "🏆", "¡Excelente!", Colors.GOLD
        elif s.accuracy_pct >= 70:
            result_emoji, result_text, result_color = "🎯", "¡Muy bien!", Colors.SUCCESS
        elif s.accuracy_pct >= 50:
            result_emoji, result_text, result_color = "📖", "Buen intento", Colors.WARNING
        else:
            result_emoji, result_text, result_color = "💪", "¡Sigue practicando!", Colors.PRIMARY

        # ── Métricas ──
        def stat_card(label: str, value: str, icon: str) -> ft.Container:
            return ft.Container(
                content=ft.Column([
                    ft.Text(icon, size=28),
                    ft.Text(value, size=22, weight=ft.FontWeight.BOLD,
                            color=Colors.TEXT_PRIMARY),
                    ft.Text(label, size=Typography.SIZE_XS,
                            color=Colors.TEXT_SECONDARY),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=4),
                width=140,
                padding=ft.Padding(left=Spacing.MD, top=Spacing.LG,
                                   right=Spacing.MD, bottom=Spacing.LG),
                bgcolor=Colors.BG_CARD,
                border_radius=Radius.MD,
                border=ft.border.all(1, Colors.BORDER),
            )

        stats_row = ft.Row([
            stat_card("Puntuación", f"{s.total_score:,}", "🏅"),
            stat_card("XP ganado",  f"+{s.xp_earned}",   "⭐"),
            stat_card("Precisión",  f"{s.accuracy_pct:.0f}%", "🎯"),
            stat_card("Correctas",
                      f"{s.questions_correct}/{s.questions_total}", "✅"),
            stat_card("Mejor racha", str(s.best_streak), "🔥"),
            stat_card("Tiempo medio",
                      f"{s.avg_time:.1f}s", "⏱"),
        ], wrap=True, spacing=Spacing.MD, run_spacing=Spacing.MD,
           alignment=ft.MainAxisAlignment.CENTER)

        # ── Logros y récords ──
        extras: list[ft.Control] = []
        if s.level_up:
            extras.append(ft.Container(
                content=ft.Row([
                    ft.Text("🆙", size=24),
                    ft.Text(f"¡Subiste al nivel {s.new_level}!",
                            size=Typography.SIZE_MD, weight=ft.FontWeight.BOLD,
                            color=Colors.GOLD),
                ], spacing=Spacing.SM),
                bgcolor="#1A1500",
                border=ft.border.all(2, Colors.GOLD),
                border_radius=Radius.MD,
                padding=ft.Padding(left=Spacing.MD, top=Spacing.SM,
                                   right=Spacing.MD, bottom=Spacing.SM),
            ))

        for rec in s.new_records:
            extras.append(ft.Container(
                content=ft.Row([
                    ft.Text("📈", size=20),
                    ft.Text(f"¡Nuevo récord en {rec}!",
                            color=Colors.SUCCESS, size=Typography.SIZE_SM),
                ], spacing=Spacing.SM),
                bgcolor="#0D2E1A",
                border_radius=Radius.MD,
                padding=ft.Padding(left=Spacing.MD, top=Spacing.SM,
                                   right=Spacing.MD, bottom=Spacing.SM),
            ))

        for ach in s.new_achievements:
            extras.append(ft.Container(
                content=ft.Row([
                    ft.Text("🏆", size=20),
                    ft.Text(f"Logro desbloqueado: {ach}",
                            color=Colors.WARNING, size=Typography.SIZE_SM),
                ], spacing=Spacing.SM),
                bgcolor="#1A1000",
                border_radius=Radius.MD,
                padding=ft.Padding(left=Spacing.MD, top=Spacing.SM,
                                   right=Spacing.MD, bottom=Spacing.SM),
            ))

        extras_col = ft.Column(extras, spacing=Spacing.SM) if extras else ft.Container()

        # ── Método jugado ──
        method_label = s.method_key.replace("_", " ").title()
        diff_labels = {1: "Fácil", 2: "Media", 3: "Difícil",
                       4: "Media", 5: "Media", 6: "Media",
                       7: "Difícil", 8: "Difícil", 9: "Experto", 10: "Experto"}
        diff_label = diff_labels.get(s.difficulty, str(s.difficulty))

        # ── Acciones ──
        action_row = ft.Row([
            secondary_button("🏠 Inicio", lambda _: self._on_home()),
            primary_button("🔄 Jugar de nuevo",
                           lambda _: self._on_play_again(),
                           icon=ft.icons.REPLAY),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=Spacing.LG)

        self.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Text(result_emoji, size=80,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(result_text, size=32, weight=ft.FontWeight.BOLD,
                            color=result_color,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        f"{method_label}  ·  Dificultad {diff_label}",
                        size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER),
                    ft.Divider(color=Colors.BORDER, height=32),
                    stats_row,
                    ft.Container(height=Spacing.MD),
                    extras_col,
                    ft.Container(height=Spacing.MD),
                    action_row,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.SM,
                scroll=ft.ScrollMode.AUTO),
                alignment=ft.alignment.center,
                expand=True,
                padding=ft.Padding(left=Spacing.LG, top=Spacing.LG,
                                   right=Spacing.LG, bottom=Spacing.LG),
            )
        ]
        self.expand = True
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER