"""
main.py
=======
Punto de entrada de '¿Quién quiere ser Ingeniero?'
Inicializa la app Flet y monta el router de pantallas.
"""

from __future__ import annotations

import traceback
import logging
import flet as ft

from config import APP_NAME, APP_WIDTH, APP_HEIGHT
from ui.themes.theme import Colors, make_theme
from storage.sqlite.database import DatabaseManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Router de pantallas ──────────────────────────────────────────────────────

class AppRouter:
    """
    Gestiona la navegación entre pantallas.
    Guarda el player_id activo en sesión.
    """

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._player_id: int | None = None
        self._show_home()

    def _show_home(self) -> None:
        """Pantalla de inicio / selección de perfil."""
        self._page.controls.clear()
        home = LoginScreen(self, self._page)
        self._page.add(home)
        self._page.update()

    def _show_method_select(self, player_id: int) -> None:
        """Pantalla de selección de método y dificultad."""
        self._player_id = player_id
        from ui.screens.method_select_screen import MethodSelectScreen
        self._page.controls.clear()
        screen = MethodSelectScreen(
            player_id=player_id,
            on_start_session=self._show_game,
            on_back=self._show_home,
            router=self,
            page=self._page,
        )
        self._page.add(screen)
        self._page.update()

    def _show_game(self, player_id: int, method_key: str, difficulty: int) -> None:
        """Pantalla de juego activo."""
        from game.questions.bank_generator import BankGenerator
        from game.sessions.session_manager import GameSession
        from ui.screens.game_screen import GameScreen

        generator = BankGenerator(topic=None, total=16)

        session = GameSession(
            player_id=player_id,
            method_key="aleatorio",
            difficulty=difficulty,
            generator=generator,
        )

        self._page.controls.clear()
        game = GameScreen(
            session=session,
            on_end_session=self._show_summary,
            on_back_to_menu=self._show_home,
            page=self._page,
        )
        self._page.add(game)
        self._page.update()
        game.load_first_question()

    def _show_summary(self, summary) -> None:
        """Pantalla de resumen de sesión."""
        from ui.screens.summary_screen import SummaryScreen
        self._page.controls.clear()
        screen = SummaryScreen(
            summary=summary,
            on_play_again=lambda: self._show_method_select(self._player_id),
            on_home=self._show_home,
            page=self._page,
        )
        self._page.add(screen)
        self._page.update()

    def _show_manage_questions(self) -> None:
        """Pantalla para gestionar bancos de preguntas."""
        from ui.screens.manage_questions_screen import ManageQuestionsScreen
        self._page.controls.clear()
        screen = ManageQuestionsScreen(on_back=self._show_home, page=self._page)
        self._page.add(screen)
        self._page.update()

    def _handle_create_profile(self, username: str, display_name: str) -> None:
        """Crea un perfil y va a selección de método."""
        from storage.repositories.player_repository import PlayerRepository
        repo = PlayerRepository()
        try:
            player = repo.create_player(username, display_name)
            self._show_method_select(player.id)

        except Exception as e:
            traceback.print_exc()


# ─── Pantalla de inicio mínima (bootstrap) ────────────────────────────────────

class LoginScreen(ft.Column):
    """Pantalla de login minimal: solo nombre de usuario y 'Crear y Jugar'."""

    def __init__(self, router: AppRouter, page: ft.Page) -> None:
        super().__init__()
        self._router = router
        self._page = page
        self._username_field = ft.TextField(
            label="Nombre de usuario",
            hint_text="Ej: ingenieroXYZ",
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color="#2A2D45",
            focused_border_color=Colors.PRIMARY,
            width=350,
        )
        # Usamos un único campo de nombre; se empleará como display_name
        self._status = ft.Text("", color=Colors.ERROR, size=12)
        self._build()

    def _build(self) -> None:
        from storage.repositories.player_repository import PlayerRepository
        from ui.themes.theme import (
            title_text, subtitle_text, primary_button, card,
            Typography, Spacing,
        )

        repo = PlayerRepository()
        players = repo.list_players()

        scoreboard_rows: list[ft.DataRow] = []
        for player in players:
            scoreboard_rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(player.display_name, size=Typography.SIZE_SM)),
                ft.DataCell(ft.Text(str(player.level), size=Typography.SIZE_SM)),
                ft.DataCell(ft.Text(f"{player.total_score:,}", size=Typography.SIZE_SM)),
                ft.DataCell(ft.Text(str(player.games_played), size=Typography.SIZE_SM)),
            ]))

        scoreboard_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Jugador", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nivel", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Puntos", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Partidas", weight=ft.FontWeight.BOLD)),
            ],
            rows=scoreboard_rows,
            border=ft.border.all(1, Colors.BORDER),
            heading_row_color=Colors.BG_SURFACE,
            data_row_color={ft.ControlState.HOVERED: Colors.BG_SURFACE},
            width=760,
        )

        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("🎓", size=72),
                        title_text("¿Quién quiere ser Ingeniero?", size=28),
                        subtitle_text("Domina los Métodos Numéricos jugando"),
                        ft.Divider(color=Colors.BORDER, height=40),

                        ft.Text("Nuevo perfil:", size=14,
                            color=Colors.TEXT_SECONDARY,
                            weight=ft.FontWeight.BOLD),
                        self._username_field,
                        self._status,
                        primary_button("Crear y Jugar", self._on_create,
                                   icon=ft.icons.PERSON_ADD),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Gestionar preguntas",
                            on_click=lambda e: self._router._show_manage_questions(),
                            style=ft.ButtonStyle(
                                color=Colors.TEXT_PRIMARY,
                                bgcolor={ft.ControlState.DEFAULT: Colors.BG_SURFACE,
                                         ft.ControlState.HOVERED: Colors.BG_CARD},
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                            ),
                        ),
                        ft.ElevatedButton(
                            "Borrar puntuaciones",
                            on_click=self._confirm_clear_scores,
                            style=ft.ButtonStyle(
                                color=Colors.TEXT_PRIMARY,
                                bgcolor={ft.ControlState.DEFAULT: Colors.BG_SURFACE,
                                         ft.ControlState.HOVERED: "#2A2D45"},
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                            ),
                        ),
                        ft.Divider(color=Colors.BORDER, height=30),
                        ft.Text("Tabla de puntuaciones", size=Typography.SIZE_MD,
                                weight=ft.FontWeight.BOLD,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text("Ver los jugadores guardados y sus estadísticas.",
                                size=Typography.SIZE_SM, color=Colors.TEXT_SECONDARY),
                        card(scoreboard_table, padding=Spacing.SM),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=40,
            )
        ]
        self.expand = True
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    def _on_create(self, e: ft.ControlEvent) -> None:
        from storage.repositories.player_repository import PlayerRepository
        import re

        username = self._username_field.value.strip()
        display_name = username

        if not username:
            self._status.value = "⚠️ El nombre de usuario es obligatorio."
            self._page.update()
            return

        if len(username) < 3 or len(username) > 16:
            self._status.value = "⚠️ El nombre de usuario debe tener entre 3 y 16 caracteres."
            self._page.update()
            return

        if not re.match(r"^[A-Za-z0-9_]+$", username):
            self._status.value = "⚠️ Solo se permiten letras, números y guiones bajos."
            self._page.update()
            return

        repo = PlayerRepository()
        if repo.get_player_by_username(username) is not None:
            self._status.value = "⚠️ Ese nombre de usuario ya existe. Elige otro."
            self._page.update()
            return

        self._router._handle_create_profile(username, display_name)

    def _confirm_clear_scores(self, e: ft.ControlEvent) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar borrado"),
            content=ft.Text(
                "Esto eliminará todos los usuarios y sus puntuaciones."
                " La aplicación quedará como si no se hubiera usado."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._close_dialog()),
                ft.ElevatedButton(
                    "Borrar puntuaciones",
                    on_click=lambda _: self._clear_scores(),
                    bgcolor=Colors.ERROR,
                    color=Colors.TEXT_PRIMARY,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.dialog = dialog
        dialog.open = True
        self._page.update()

    def _close_dialog(self) -> None:
        if self._page.dialog:
            self._page.dialog.open = False
            self._page.update()

    def _clear_scores(self) -> None:
        from storage.repositories.player_repository import PlayerRepository

        repo = PlayerRepository()
        repo.reset_all_scores()
        self._close_dialog()
        self._status.value = "✅ Todas las puntuaciones se han borrado."
        self._build()
        self._page.update()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    # Inicializar DB
    DatabaseManager.get_instance()

    # Configurar página
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = make_theme()
    page.bgcolor = Colors.BG_DARK
    page.window.width = APP_WIDTH
    page.window.height = APP_HEIGHT
    page.window.min_width = 800
    page.window.min_height = 600
    page.padding = 0

    # Bootstrap: mostrar pantalla de inicio directamente
    router = AppRouter.__new__(AppRouter)
    router._page = page
    router._player_id = None

    # Mostrar pantalla de login
    home = LoginScreen(router, page)
    page.add(home)


if __name__ == "__main__":
    ft.app(target=main)