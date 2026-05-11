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
        from ui.screens.home_screen import HomeScreen
        self._page.controls.clear()
        home = HomeScreen(
            on_start_game=self._show_method_select,
            on_create_profile=self._handle_create_profile,
            page=self._page,
        )
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
        from engine.nonlinear.bisection import BisectionGenerator
        from game.sessions.session_manager import GameSession
        from ui.screens.game_screen import GameScreen

        generator_map = {
            "biseccion": BisectionGenerator(),
            # más métodos se agregan aquí
        }
        generator = generator_map.get(method_key, BisectionGenerator())

        session = GameSession(
            player_id=player_id,
            method_key=method_key,
            difficulty=difficulty,
            generator=generator,
        )

        self._page.controls.clear()
        game = GameScreen(
            session=session,
            on_end_session=self._show_summary,
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

class _BootstrapHomeScreen(ft.Column):
    """
    Pantalla de inicio temporal hasta implementar HomeScreen completa.
    Permite crear perfil y empezar a jugar de inmediato.
    """

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
        self._display_field = ft.TextField(
            label="Nombre para mostrar",
            hint_text="Ej: Juan Pérez",
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color="#2A2D45",
            focused_border_color=Colors.PRIMARY,
            width=350,
        )
        self._status = ft.Text("", color=Colors.ERROR, size=12)
        self._build()

    def _build(self) -> None:
        from ui.themes.theme import title_text, subtitle_text, primary_button, secondary_button
        from storage.repositories.player_repository import PlayerRepository

        repo = PlayerRepository()
        players = repo.list_players()

        existing_btns = []
        for p in players:
            btn = ft.ElevatedButton(
                text=f"▶  {p.display_name}  (Niv. {p.level} · {p.total_score:,} pts)",
                data=p.id,
                on_click=lambda e: self._router._show_method_select(e.control.data),
                style=ft.ButtonStyle(
                    color=Colors.TEXT_PRIMARY,
                    bgcolor={ft.ControlState.DEFAULT: Colors.BG_SURFACE,
                             ft.ControlState.HOVERED: Colors.BG_CARD},
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
                width=400,
            )
            existing_btns.append(btn)

        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("🎓", size=72),
                        title_text("¿Quién quiere ser Ingeniero?", size=28),
                        subtitle_text("Domina los Métodos Numéricos jugando"),
                        ft.Divider(color=Colors.BORDER, height=40),

                        *([ft.Text("Continuar como:", size=14,
                                   color=Colors.TEXT_SECONDARY,
                                   weight=ft.FontWeight.BOLD)] if existing_btns else []),
                        *existing_btns,

                        ft.Divider(color=Colors.BORDER, height=20),
                        ft.Text("Nuevo perfil:", size=14,
                                color=Colors.TEXT_SECONDARY,
                                weight=ft.FontWeight.BOLD),
                        self._username_field,
                        self._display_field,
                        self._status,
                        primary_button("Crear y Jugar", self._on_create,
                                       icon=ft.icons.PERSON_ADD),
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
        username = self._username_field.value.strip()
        display_name = self._display_field.value.strip() or username
        if not username:
            self._status.value = "⚠️ El nombre de usuario es obligatorio."
            self._page.update()
            return
        self._router._handle_create_profile(username, display_name)


# ─── Módulos de pantalla placeholder (evitar ImportError) ────────────────────

# home_screen.py — referenciado por AppRouter
import sys, types

def _make_home_module() -> None:
    """Crea un módulo temporal para HomeScreen hasta implementarlo."""
    mod = types.ModuleType("ui.screens.home_screen")

    class HomeScreen(ft.Column):
        def __init__(self, on_start_game, on_create_profile, page): pass

    mod.HomeScreen = HomeScreen
    sys.modules["ui.screens.home_screen"] = mod


def _make_summary_module() -> None:
    mod = types.ModuleType("ui.screens.summary_screen")

    class SummaryScreen(ft.Column):
        pass

    mod.SummaryScreen = SummaryScreen
    sys.modules["ui.screens.summary_screen"] = mod


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    # Inicializar DB
    DatabaseManager.get_instance()

    # Registrar módulos placeholder (home y summary siguen siendo stubs)
    _make_home_module()
    _make_summary_module()

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

    # Mostrar bootstrap home
    home = _BootstrapHomeScreen(router, page)
    page.add(home)


if __name__ == "__main__":
    ft.app(target=main)