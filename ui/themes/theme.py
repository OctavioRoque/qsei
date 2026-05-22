"""
ui/themes/theme.py
==================
Sistema de diseño visual de la aplicación.
Paleta de colores, tipografía y estilos reutilizables para Flet.
"""

from __future__ import annotations
import flet as ft


# ─── Paleta de colores ────────────────────────────────────────────────────────

class Colors:
    # Fondos
    BG_DARK        = "#0D0E1A"   # fondo principal
    BG_CARD        = "#161828"   # tarjetas
    BG_SURFACE     = "#1E2136"   # superficies elevadas

    # Acento principal — azul eléctrico
    PRIMARY        = "#3D8EFF"
    PRIMARY_LIGHT  = "#70AFFF"
    PRIMARY_DARK   = "#1A6FD4"

    # Acento secundario — dorado
    GOLD           = "#FFD700"
    GOLD_DARK      = "#C9A800"

    # Semáforo
    SUCCESS        = "#00E676"
    WARNING        = "#FF9800"
    ERROR          = "#FF5252"
    INFO           = "#40C4FF"

    # Texto
    TEXT_PRIMARY   = "#EAEAF0"
    TEXT_SECONDARY = "#8A8FAD"
    TEXT_MUTED     = "#4A4F6A"

    # Dificultad
    EASY           = "#4CAF50"
    MEDIUM         = "#FF9800"
    HARD           = "#F44336"
    EXPERT         = "#CE93D8"

    # Bordes
    BORDER         = "#2A2D45"
    BORDER_FOCUS   = "#3D8EFF"


# ─── Tipografía ───────────────────────────────────────────────────────────────

class Typography:
    FONT_FAMILY_TITLE  = "Orbitron"       # para títulos grandes
    FONT_FAMILY_BODY   = "Exo 2"          # para texto general
    FONT_FAMILY_MONO   = "JetBrains Mono" # para expresiones matemáticas

    SIZE_XL    = 36
    SIZE_LG    = 24
    SIZE_MD    = 18
    SIZE_SM    = 14
    SIZE_XS    = 12


# ─── Espaciado ────────────────────────────────────────────────────────────────

class Spacing:
    XS  = 4
    SM  = 8
    MD  = 16
    LG  = 24
    XL  = 40


# ─── Radius ───────────────────────────────────────────────────────────────────

class Radius:
    SM  = 6
    MD  = 12
    LG  = 20
    XL  = 30


# ─── Componentes reutilizables ────────────────────────────────────────────────

def make_theme() -> ft.Theme:
    """Retorna el tema Flet configurado para la aplicación."""
    return ft.Theme(
        color_scheme_seed=Colors.PRIMARY,
        color_scheme=ft.ColorScheme(
            primary=Colors.PRIMARY,
            secondary=Colors.GOLD,
            surface=Colors.BG_CARD,
            on_primary=Colors.TEXT_PRIMARY,
            on_surface=Colors.TEXT_PRIMARY,
            error=Colors.ERROR,
        ),
        font_family=Typography.FONT_FAMILY_BODY,
    )


# ─── Builders de controles estilizados ────────────────────────────────────────

def card(content: ft.Control, padding: int = Spacing.MD) -> ft.Container:
    """Tarjeta con estilo oscuro y borde sutil."""
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        border_radius=Radius.MD,
    )


def title_text(text: str, size: int = Typography.SIZE_LG) -> ft.Text:
    return ft.Text(
        text,
        size=size,
        weight=ft.FontWeight.BOLD,
        color=Colors.TEXT_PRIMARY,
        font_family=Typography.FONT_FAMILY_TITLE,
    )


def subtitle_text(text: str) -> ft.Text:
    return ft.Text(
        text,
        size=Typography.SIZE_SM,
        color=Colors.TEXT_SECONDARY,
    )


def body_text(text: str, size: int = Typography.SIZE_SM) -> ft.Text:
    return ft.Text(text, size=size, color=Colors.TEXT_PRIMARY)


def math_text(expr: str) -> ft.Text:
    """Texto para expresiones matemáticas (fuente monoespaciada)."""
    return ft.Text(
        expr,
        size=Typography.SIZE_MD,
        font_family=Typography.FONT_FAMILY_MONO,
        color=Colors.PRIMARY_LIGHT,
    )


def primary_button(
    text: str,
    on_click,
    icon: str | None = None,
    disabled: bool = False,
) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            color=Colors.TEXT_PRIMARY,
            bgcolor={
                ft.ControlState.DEFAULT:  Colors.PRIMARY,
                ft.ControlState.HOVERED:  Colors.PRIMARY_LIGHT,
                ft.ControlState.DISABLED: Colors.TEXT_MUTED,
            },
            shape=ft.RoundedRectangleBorder(radius=Radius.SM),
            padding=ft.Padding(left=24, top=14, right=24, bottom=14)
        ),
    )


def secondary_button(text: str, on_click, icon: str | None = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=Colors.PRIMARY,
            side=ft.BorderSide(1, Colors.PRIMARY),
            shape=ft.RoundedRectangleBorder(radius=Radius.SM),
            padding=ft.Padding(left=24, top=14, right=24, bottom=14),
        ),
    )


def difficulty_badge(difficulty: int, display_number: int | None = None) -> ft.Container:
    """Badge de color según dificultad.

    Si `display_number` está presente, se mostrará ese número entre paréntesis
    en lugar del valor de `difficulty`. Esto permite usar el mismo badge como
    pista sutil de la opción correcta.
    """
    from config import get_difficulty_label
    level = get_difficulty_label(difficulty)
    number_text = display_number if display_number is not None else difficulty
    return ft.Container(
        content=ft.Row([
            ft.Text(
                level.label_es,
                size=Typography.SIZE_XS,
                weight=ft.FontWeight.BOLD,
                color=Colors.BG_DARK,
            ),
            ft.Text(
                f"({number_text})",
                size=10,
                weight=ft.FontWeight.BOLD,
                color="#000000",
            ),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=level.color_hex,
        padding=ft.Padding(left=10, top=4, right=10, bottom=4),
        border_radius=Radius.XL,
    )


def score_display(score: int, label: str = "PUNTOS") -> ft.Column:
    """Muestra grande de puntuación."""
    return ft.Column(
        [
            ft.Text(
                f"{score:,}",
                size=Typography.SIZE_XL,
                weight=ft.FontWeight.BOLD,
                color=Colors.GOLD,
                font_family=Typography.FONT_FAMILY_TITLE,
            ),
            ft.Text(label, size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
    )


def xp_bar(current_xp: int, needed_xp: int, level: int) -> ft.Column:
    """Barra de experiencia con nivel."""
    pct = min(current_xp / needed_xp, 1.0) if needed_xp > 0 else 0.0
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(f"Nivel {level}", size=Typography.SIZE_XS,
                            color=Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{current_xp}/{needed_xp} XP",
                            size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ProgressBar(
                value=pct,
                bgcolor=Colors.BG_SURFACE,
                color=Colors.PRIMARY,
                height=8,
                border_radius=4,
            ),
        ],
        spacing=4,
    )


def feedback_banner(is_correct: bool, feedback_text: str) -> ft.Container:
    """Banner de resultado de respuesta."""
    color = Colors.SUCCESS if is_correct else Colors.ERROR
    icon  = "✅" if is_correct else "❌"
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    f"{icon} {'¡Correcto!' if is_correct else 'Incorrecto'}",
                    size=Typography.SIZE_MD,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                ),
                ft.Text(feedback_text, size=Typography.SIZE_SM, color=Colors.TEXT_PRIMARY),
            ],
            spacing=Spacing.XS,
        ),
        padding=Spacing.MD,
        bgcolor=Colors.BG_SURFACE,
        border=ft.border.all(1, color),
        border_radius=Radius.MD,
    )