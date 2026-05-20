"""
ui/widgets/tabulation_widget.py
================================
Widget interactivo para preguntas de tabulación.

El alumno:
  1. Lee el enunciado
  2. Llena la tabla de iteraciones celda por celda
  3. Escribe el resultado final
  4. Presiona "Ver solución" → se muestra la tabla correcta y el procedimiento
  5. Se auto-evalúa: ✅ / ❌
"""

from __future__ import annotations
from typing import Callable
import flet as ft

from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    primary_button, secondary_button,
)

# ── Columnas por método ────────────────────────────────────────────────────────
_METHOD_COLUMNS: dict[str, list[str]] = {
    "biseccion":            ["n", "a", "b", "c=(a+b)/2", "f(c)", "sgn", "error %"],
    "falsa_posicion":       ["n", "a", "b", "c", "f(c)", "f(a)·f(c)", "error %"],
    "newton_raphson":       ["n", "xₙ", "f(xₙ)", "f′(xₙ)", "xₙ₊₁", "error %"],
    "punto_fijo":           ["n", "xₙ", "g(xₙ)", "xₙ₊₁", "error %"],
    "secante":              ["n", "xₙ₋₁", "xₙ", "f(xₙ₋₁)", "f(xₙ)", "xₙ₊₁", "error %"],
    "gauss_seidel":         ["iter", "x₁", "x₂", "x₃", "error %"],
    "jacobi":               ["iter", "x₁", "x₂", "x₃", "error %"],
    "montante":             ["paso", "pivote", "fila", "operación", "resultado"],
    "eliminacion_gaussiana":["paso", "ecuación", "mult.", "resultado"],
    "gauss_jordan":         ["paso", "ecuación", "mult.", "resultado"],
    "interpolacion_lineal": ["x₀", "x₁", "y₀", "y₁", "x", "y(x)"],
    "newton_adelante":      ["i", "xᵢ", "yᵢ", "Δy", "Δ²y", "Δ³y"],
    "newton_atras":         ["i", "xᵢ", "yᵢ", "∇y", "∇²y", "∇³y"],
    "diferencias_divididas":["i", "xᵢ", "f[xᵢ]", "f[xᵢ,xᵢ₊₁]", "f[xᵢ,...,xᵢ₊₂]"],
    "lagrange":             ["i", "xᵢ", "yᵢ", "Lᵢ(x)", "yᵢ·Lᵢ(x)"],
    "euler_adelante":       ["n", "tₙ", "yₙ", "f(tₙ,yₙ)", "yₙ₊₁"],
    "euler_atras":          ["n", "tₙ", "yₙ*", "f(tₙ₊₁,yₙ*)", "yₙ₊₁"],
    "euler_modificado":     ["n", "tₙ", "yₙ", "k₁", "k₂", "yₙ₊₁"],
    "runge_kutta_2":        ["n", "tₙ", "yₙ", "k₁", "k₂", "yₙ₊₁"],
    "runge_kutta_3":        ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "yₙ₊₁"],
    "runge_kutta_4":        ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "k₄", "yₙ₊₁"],
    "runge_kutta_superior": ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "k₄", "k₅", "yₙ₊₁"],
    "integracion_trapezoidal": ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "simpson_13":           ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "simpson_38":           ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "minimos_cuadrados":    ["i", "xᵢ", "yᵢ", "xᵢ²", "xᵢyᵢ"],
}
_DEFAULT_COLUMNS = ["n", "col_1", "col_2", "col_3", "col_4", "resultado"]

# Ancho de celda de entrada (px)
_CELL_W = 90
_CELL_W_NARROW = 50   # para "n", "i", "iter", "paso"
_NARROW_HEADERS = {"n", "i", "iter", "paso", "sgn", "coef."}


def _cell_width(header: str) -> int:
    return _CELL_W_NARROW if header in _NARROW_HEADERS else _CELL_W


class TabulationWidget(ft.Column):
    """
    Widget completo de tabulación interactiva.

    Parámetros
    ----------
    solution   : texto de la solución (del banco JSON)
    procedure  : texto del procedimiento (del banco JSON)
    method_key : clave del método para inferir columnas
    on_reveal  : callback(is_correct: bool) llamado tras auto-evaluación
    page       : ft.Page
    """

    def __init__(
        self,
        solution: str,
        procedure: str,
        method_key: str,
        on_reveal: Callable[[bool], None],
        page: ft.Page,
    ) -> None:
        super().__init__()
        self._solution  = solution
        self._procedure = procedure
        self._method_key = method_key
        self._on_reveal = on_reveal
        self._page = page

        self._columns = _METHOD_COLUMNS.get(method_key, _DEFAULT_COLUMNS)
        self._rows: list[list[ft.TextField]] = []
        self._result_field: ft.TextField | None = None
        self._rows_container = ft.Column(spacing=4)

        self.spacing = Spacing.MD
        self._build()

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Encabezado de la tabla
        header_row = ft.Row(
            [self._header_cell(h) for h in self._columns],
            spacing=4,
        )
        header_container = ft.Container(
            content=header_row,
            bgcolor=Colors.BG_SURFACE,
            border_radius=ft.BorderRadius(
                top_left=Radius.SM, top_right=Radius.SM,
                bottom_left=0, bottom_right=0),
            padding=ft.Padding(left=8, top=6, right=8, bottom=6),
            border=ft.border.all(1, Colors.BORDER),
        )

        # Tabla scrolleable
        table_scroll = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self._rows_container,
                    border=ft.border.only(
                        left=ft.BorderSide(1, Colors.BORDER),
                        right=ft.BorderSide(1, Colors.BORDER),
                        bottom=ft.BorderSide(1, Colors.BORDER),
                    ),
                    border_radius=ft.BorderRadius(
                        top_left=0, top_right=0,
                        bottom_left=Radius.SM, bottom_right=Radius.SM),
                    padding=ft.Padding(left=8, top=4, right=8, bottom=8),
                ),
            ], spacing=0),
        )

        # Botón agregar fila
        add_btn = ft.TextButton(
            "+ Agregar iteración",
            icon=ft.icons.ADD_CIRCLE_OUTLINE,
            icon_color=Colors.PRIMARY,
            style=ft.ButtonStyle(color=Colors.PRIMARY),
            on_click=lambda _: self._add_row(),
        )

        # Campo resultado final
        self._result_field = ft.TextField(
            label="Resultado / Raíz aproximada",
            hint_text="Ej: x ≈ 1.5234",
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            width=320,
        )

        result_row = ft.Row([
            ft.Text("Resultado:", size=Typography.SIZE_SM,
                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self._result_field,
        ], spacing=Spacing.MD, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        reveal_btn = primary_button(
            "Ver solución 👁",
            lambda _: self._reveal(),
        )

        self.controls = [
            ft.Text("📊 Tabla de iteraciones",
                    size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY),
            ft.Text("Llena cada fila con los valores de cada iteración.",
                    size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY,
                    italic=True),
            header_container,
            table_scroll,
            add_btn,
            ft.Divider(color=Colors.BORDER),
            result_row,
            reveal_btn,
        ]

        # Arrancar con 2 filas
        self._add_row()
        self._add_row()

    # ── Celdas ────────────────────────────────────────────────────────────────

    def _header_cell(self, text: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=11, weight=ft.FontWeight.BOLD,
                            color=Colors.TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER),
            width=_cell_width(text),
            alignment=ft.alignment.center,
        )

    def _input_cell(self, header: str) -> ft.TextField:
        return ft.TextField(
            hint_text="—",
            text_size=12,
            bgcolor=Colors.BG_CARD,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            content_padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            width=_cell_width(header),
            text_align=ft.TextAlign.CENTER,
        )

    # ── Gestión de filas ──────────────────────────────────────────────────────

    def _add_row(self, _=None) -> None:
        n = len(self._rows) + 1
        cells = [self._input_cell(h) for h in self._columns]
        # Pre-rellenar la columna "n" / "i" / "iter" con el número de iteración
        first_header = self._columns[0].lower()
        if first_header in {"n", "i", "iter", "paso"}:
            cells[0].value = str(n)
            cells[0].read_only = True
            cells[0].bgcolor = Colors.BG_SURFACE

        self._rows.append(cells)

        row_container = ft.Container(
            content=ft.Row(cells, spacing=4),
            bgcolor=Colors.BG_CARD if n % 2 == 0 else Colors.BG_SURFACE,
            border_radius=0,
            padding=ft.Padding(left=0, top=3, right=0, bottom=3),
        )
        self._rows_container.controls.append(row_container)
        self._page.update()

    # ── Reveal ────────────────────────────────────────────────────────────────

    def _reveal(self) -> None:
        """Reemplaza la tabla editable con la solución y muestra auto-eval."""
        # Deshabilitar todos los campos
        for row_cells in self._rows:
            for cell in row_cells:
                cell.disabled = True

        if self._result_field:
            self._result_field.disabled = True

        # Quitar botones de agregar + ver solución
        self.controls = [c for c in self.controls
                         if not isinstance(c, ft.TextButton)]

        # Mostrar solución
        sol_content = ft.Column([
            ft.Text("✅ Solución correcta", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.SUCCESS),
            ft.Text(self._solution, size=Typography.SIZE_XS,
                    color=Colors.TEXT_PRIMARY, selectable=True,
                    font_family="monospace"),
        ], spacing=Spacing.SM)

        if self._procedure:
            sol_content.controls.extend([
                ft.Divider(color=Colors.BORDER),
                ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                ft.Text(self._procedure, size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY, selectable=True),
            ])

        sol_card = ft.Container(
            content=sol_content,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.SUCCESS),
            border_radius=Radius.MD,
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD,
                               right=Spacing.MD, bottom=Spacing.MD),
        )

        # Auto-evaluación
        self_eval = ft.Column([
            ft.Text("¿Tu tabla y resultado fueron correctos?",
                    size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY),
            ft.Row([
                ft.ElevatedButton(
                    "✅  Sí, correcto",
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
            ], spacing=Spacing.MD),
        ], spacing=Spacing.SM)

        # Remover el reveal_btn y agregar sol_card + self_eval
        self.controls = [c for c in self.controls
                         if not (isinstance(c, ft.ElevatedButton))]
        self.controls.extend([sol_card, self_eval])
        self._page.update()

    def _self_assess(self, is_correct: bool) -> None:
        # Remover botones de auto-eval para evitar doble clic
        self.controls = [c for c in self.controls
                         if not isinstance(c, ft.Column)
                         or not any(isinstance(x, ft.Row) for x in getattr(c, 'controls', [])
                                    if hasattr(x, 'controls') and any(
                                        isinstance(b, ft.ElevatedButton)
                                        for b in getattr(x, 'controls', [])))]
        self._on_reveal(is_correct)
        self._page.update()