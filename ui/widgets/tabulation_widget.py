"""
ui/widgets/tabulation_widget.py
================================
Widget interactivo para preguntas de tabulación con validación automática.

Flujo:
  1. Alumno llena la tabla de iteraciones celda por celda
  2. Presiona "Verificar ✓" → cada celda se colorea verde/rojo automáticamente
  3. Se muestra puntuación: "X/Y valores correctos"
  4. Puede ver la solución completa con "Ver solución completa"
  5. El score se registra según el porcentaje de celdas correctas
"""

from __future__ import annotations
import re
from typing import Callable
import flet as ft

from ui.themes.theme import Colors, Typography, Spacing, Radius, primary_button

# ── Columnas por método ────────────────────────────────────────────────────────
_METHOD_COLUMNS: dict[str, list[str]] = {
    "biseccion":             ["n", "a", "b", "c=(a+b)/2", "f(c)", "sgn", "error %"],
    "falsa_posicion":        ["n", "a", "b", "c", "f(c)", "f(a)·f(c)", "error %"],
    "newton_raphson":        ["n", "xₙ", "f(xₙ)", "f′(xₙ)", "xₙ₊₁", "error %"],
    "punto_fijo":            ["n", "xₙ", "g(xₙ)", "xₙ₊₁", "error %"],
    "secante":               ["n", "xₙ₋₁", "xₙ", "f(xₙ₋₁)", "f(xₙ)", "xₙ₊₁", "error %"],
    "gauss_seidel":          ["iter", "x₁", "x₂", "x₃", "error %"],
    "jacobi":                ["iter", "x₁", "x₂", "x₃", "error %"],
    "montante":              ["paso", "pivote", "fila", "operación", "resultado"],
    "eliminacion_gaussiana": ["paso", "ecuación", "mult.", "resultado"],
    "gauss_jordan":          ["paso", "ecuación", "mult.", "resultado"],
    "interpolacion_lineal":  ["x₀", "x₁", "y₀", "y₁", "x", "y(x)"],
    "newton_adelante":       ["i", "xᵢ", "yᵢ", "Δy", "Δ²y", "Δ³y"],
    "newton_atras":          ["i", "xᵢ", "yᵢ", "∇y", "∇²y", "∇³y"],
    "diferencias_divididas": ["i", "xᵢ", "f[xᵢ]", "f[xᵢ,xᵢ₊₁]", "f[xᵢ,...,xᵢ₊₂]"],
    "lagrange":              ["i", "xᵢ", "yᵢ", "Lᵢ(x)", "yᵢ·Lᵢ(x)"],
    "euler_adelante":        ["n", "tₙ", "yₙ", "f(tₙ,yₙ)", "yₙ₊₁"],
    "euler_atras":           ["n", "tₙ", "yₙ*", "f(tₙ₊₁,yₙ*)", "yₙ₊₁"],
    "euler_modificado":      ["n", "tₙ", "yₙ", "k₁", "k₂", "yₙ₊₁"],
    "runge_kutta_2":         ["n", "tₙ", "yₙ", "k₁", "k₂", "yₙ₊₁"],
    "runge_kutta_3":         ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "yₙ₊₁"],
    "runge_kutta_4":         ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "k₄", "yₙ₊₁"],
    "runge_kutta_superior":  ["n", "tₙ", "yₙ", "k₁", "k₂", "k₃", "k₄", "k₅", "yₙ₊₁"],
    "integracion_trapezoidal": ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "simpson_13":            ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "simpson_38":            ["i", "xᵢ", "f(xᵢ)", "coef.", "coef·f(xᵢ)"],
    "minimos_cuadrados":     ["i", "xᵢ", "yᵢ", "xᵢ²", "xᵢyᵢ"],
    "metodo_grafico":        ["x", "f(x)", "sgn"],
    "comparativas":          ["método", "convergencia", "observación"],
}
_DEFAULT_COLUMNS = ["n", "col_1", "col_2", "col_3", "col_4", "resultado"]

_NARROW_HEADERS = {"n", "i", "iter", "paso", "sgn", "coef.", "x"}
_CELL_W        = 92
_CELL_W_NARROW = 52


def _cell_width(header: str) -> int:
    return _CELL_W_NARROW if header in _NARROW_HEADERS else _CELL_W


# ── Parser de tabla de solución ───────────────────────────────────────────────

def _try_float(s: str) -> float | None:
    """Intenta convertir un string a float, soportando comas, símbolos y fracciones simples."""
    s = s.strip().lstrip("(").rstrip(")")
    s = s.replace(",", ".").replace("−", "-")
    # Fracciones simples: 4/3, -10/3, 1/2
    frac = re.fullmatch(r"(-?\d+\.?\d*)\s*/\s*(-?\d+\.?\d*)", s)
    if frac:
        try:
            return float(frac.group(1)) / float(frac.group(2))
        except (ValueError, ZeroDivisionError):
            return None
    s = re.sub(r"[^\d.\-eE+]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_sign(s: str) -> str:
    """Normaliza celdas de signo: (+) → +, (-) → -."""
    s = s.strip()
    if re.fullmatch(r"[(\[{]?\+[)\]}]?", s):
        return "+"
    if re.fullmatch(r"[(\[{]?-[)\]}]?", s):
        return "-"
    return s.lower()


def _values_match(student: str, expected: str, tol: float = 0.01) -> bool:
    """
    True si el valor del estudiante coincide con el esperado.
    - Para números: error relativo < tol (1%) O absoluto < 0.005
    - Para signos: comparación exacta normalizada
    - Para strings cortos: comparación case-insensitive
    """
    student = student.strip()
    expected = expected.strip()

    if not student:
        return False

    # Comparación de signo
    if re.fullmatch(r"[(\[{]?[+\-][)\]}]?", expected.strip()):
        return _normalize_sign(student) == _normalize_sign(expected)

    sf = _try_float(student)
    ef = _try_float(expected)

    if sf is not None and ef is not None:
        abs_err = abs(sf - ef)
        rel_err = abs_err / max(abs(ef), 1e-10)
        return abs_err < 0.005 or rel_err < tol

    # Fallback: string
    return student.lower() == expected.lower()


class SolutionParser:
    """
    Parsea el texto de solución y extrae la tabla de valores esperados.

    Soporta:
      - Tablas pipe:  | val | val | val |
      - Líneas con separador de guiones: |---|---|---|  (ignoradas)
    """

    def __init__(self, solution_text: str) -> None:
        self.rows: list[list[str]] = []   # solo filas de datos (no cabecera)
        self._parse(solution_text)

    def _parse(self, text: str) -> None:
        for line in text.split("\n"):
            if "|" not in line:
                continue
            # Saltar líneas separadoras |---|---|
            if re.fullmatch(r"[\s|:\-]+", line):
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]   # eliminar vacíos de bordes
            if not cells:
                continue
            # Es fila de datos si tiene al menos un número
            has_num = any(_try_float(c) is not None for c in cells)
            # O al menos 2 celdas con contenido (podría ser cabecera con texto)
            if has_num:
                self.rows.append(cells)

    def expected_row(self, row_idx: int) -> list[str]:
        """Retorna la fila esperada (vacía si no existe)."""
        if row_idx < len(self.rows):
            return self.rows[row_idx]
        return []

    def total_rows(self) -> int:
        return len(self.rows)

    def check_cell(
        self,
        row_idx: int,
        col_idx: int,
        student_value: str,
    ) -> bool | None:
        """
        Verifica una celda.

        Returns:
            True  → correcto
            False → incorrecto
            None  → no se puede verificar (celda esperada vacía o fuera de rango)
        """
        if not student_value.strip():
            return None
        expected_row = self.expected_row(row_idx)
        if col_idx >= len(expected_row):
            return None
        expected = expected_row[col_idx]
        if not expected or expected in {"?", "—", "-"}:
            return None
        return _values_match(student_value, expected)


# ── Widget principal ──────────────────────────────────────────────────────────

class TabulationWidget(ft.Column):
    """
    Widget de tabulación con validación automática celda a celda.

    on_reveal(is_correct: bool) se llama cuando el estudiante
    termina de verificar y cierra el widget.
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

        self._columns   = _METHOD_COLUMNS.get(method_key, _DEFAULT_COLUMNS)
        self._parser    = SolutionParser(solution)
        self._rows: list[list[ft.TextField]] = []
        self._result_field: ft.TextField | None = None
        self._rows_container = ft.Column(spacing=2)
        self._status_text = ft.Text("", size=Typography.SIZE_SM, color=Colors.TEXT_PRIMARY)
        self._initialized = False

        self.spacing = Spacing.SM
        self._build()
        self._initialized = True

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        header_row = ft.Row(
            [self._header_cell(h) for h in self._columns],
            spacing=4,
        )
        header_box = ft.Container(
            content=header_row,
            bgcolor=Colors.BG_SURFACE,
            border_radius=ft.BorderRadius(
                top_left=Radius.SM, top_right=Radius.SM,
                bottom_left=0, bottom_right=0,
            ),
            padding=ft.Padding(left=8, top=6, right=8, bottom=6),
            border=ft.border.all(1, Colors.BORDER),
        )

        table_body = ft.Container(
            content=self._rows_container,
            border=ft.border.only(
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=ft.BorderRadius(
                top_left=0, top_right=0,
                bottom_left=Radius.SM, bottom_right=Radius.SM,
            ),
            padding=ft.Padding(left=8, top=4, right=8, bottom=8),
        )

        add_btn = ft.TextButton(
            "+ Agregar fila",
            icon=ft.icons.ADD_CIRCLE_OUTLINE,
            icon_color=Colors.PRIMARY,
            style=ft.ButtonStyle(color=Colors.PRIMARY),
            on_click=lambda _: self._add_row(),
        )

        self._result_field = ft.TextField(
            label="Resultado final",
            hint_text="Ej: x ≈ 1.5234",
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            width=300,
        )

        verify_btn = primary_button(
            "Verificar ✓",
            lambda _: self._verify(),
            icon=ft.icons.CHECK_CIRCLE_OUTLINE,
        )

        # Hint: número de iteraciones esperadas
        n_expected = self._parser.total_rows()

        # Si el parser detectó cabecera de texto como primera fila, saltarla
        if n_expected > 0 and not any(
            _try_float(v) for v in self._parser.rows[0]
        ):
            self._parser.rows = self._parser.rows[1:]
            n_expected = self._parser.total_rows()

        self._can_auto_validate = n_expected > 0

        if self._can_auto_validate:
            hint = f"💡 La solución tiene {n_expected} iteración(es). Llena la tabla y presiona Verificar."
            action_btn = primary_button(
                "Verificar ✓",
                lambda _: self._verify(),
                icon=ft.icons.CHECK_CIRCLE_OUTLINE,
            )
        else:
            hint = "Llena la tabla con las iteraciones y luego ver la solución."
            action_btn = primary_button(
                "Ver solución 👁",
                lambda _: self._reveal_manual(),
            )

        self.controls = [
            ft.Text("📊 Tabla de iteraciones",
                    size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
                    color=Colors.TEXT_PRIMARY),
            ft.Text(hint,
                    size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY, italic=True),
            header_box,
            table_body,
            add_btn,
            ft.Divider(color=Colors.BORDER),
            ft.Row([
                ft.Text("Resultado:", size=Typography.SIZE_SM,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                self._result_field,
            ], spacing=Spacing.MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._status_text,
            action_btn,
        ]

        # Filas iniciales: tantas como la solución, mínimo 2
        initial = max(2, n_expected)
        for _ in range(initial):
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

    # ── Filas ─────────────────────────────────────────────────────────────────

    def _add_row(self, _=None) -> None:
        n = len(self._rows) + 1
        cells = [self._input_cell(h) for h in self._columns]

        first = self._columns[0].lower()
        if first in {"n", "i", "iter", "paso"}:
            cells[0].value = str(n)
            cells[0].read_only = True
            cells[0].bgcolor = Colors.BG_SURFACE

        self._rows.append(cells)
        self._rows_container.controls.append(
            ft.Container(
                content=ft.Row(cells, spacing=4),
                bgcolor=Colors.BG_CARD if n % 2 == 0 else Colors.BG_SURFACE,
                padding=ft.Padding(left=0, top=2, right=0, bottom=2),
            )
        )
        if self._initialized:
            self._page.update()

    # ── Verificación automática ───────────────────────────────────────────────

    def _verify(self) -> None:
        """Valida todas las celdas y colorea verde/rojo automáticamente."""
        if not self._rows:
            return

        correct = 0
        checkable = 0

        for row_idx, cells in enumerate(self._rows):
            for col_idx, cell in enumerate(cells):
                # Saltamos la columna de número de iteración (read-only)
                if cell.read_only:
                    continue

                result = self._parser.check_cell(row_idx, col_idx, cell.value or "")

                if result is True:
                    cell.border_color = Colors.SUCCESS
                    cell.focused_border_color = Colors.SUCCESS
                    cell.bgcolor = "#0D2416"
                    correct += 1
                    checkable += 1
                elif result is False:
                    cell.border_color = Colors.ERROR
                    cell.focused_border_color = Colors.ERROR
                    cell.bgcolor = "#2A0A0A"
                    checkable += 1
                else:
                    # No se puede verificar → gris neutro
                    cell.border_color = Colors.TEXT_MUTED
                    cell.focused_border_color = Colors.TEXT_MUTED

        # Verificar campo resultado
        result_correct = False
        if self._result_field and self._result_field.value:
            for exp_row in self._parser.rows:
                for exp_val in exp_row:
                    if _values_match(self._result_field.value, exp_val):
                        result_correct = True
                        break
            self._result_field.border_color = Colors.SUCCESS if result_correct else Colors.ERROR

        # Mostrar puntuación
        pct = (correct / checkable * 100) if checkable > 0 else 0
        if pct == 100:
            emoji = "🏆"
            color = Colors.SUCCESS
        elif pct >= 70:
            emoji = "🎯"
            color = Colors.WARNING
        else:
            emoji = "📖"
            color = Colors.ERROR

        self._status_text.value = (
            f"{emoji}  {correct}/{checkable} valores correctos ({pct:.0f}%)"
        )
        self._status_text.color = color

        # Calcular si se considera "correcto" (≥ 70%)
        is_correct = pct >= 70

        # Reemplazar botón Verificar por Ver solución + Continuar
        self.controls = [
            c for c in self.controls
            if not (isinstance(c, ft.ElevatedButton))
        ]
        self.controls.append(
            ft.Row([
                ft.OutlinedButton(
                    "Ver solución completa",
                    icon=ft.icons.VISIBILITY_OUTLINED,
                    style=ft.ButtonStyle(
                        color=Colors.PRIMARY,
                        side=ft.BorderSide(1, Colors.PRIMARY),
                        shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                        padding=ft.Padding(left=16, top=10, right=16, bottom=10),
                    ),
                    on_click=lambda _: self._show_solution(),
                ),
                primary_button(
                    "Continuar →",
                    lambda _: self._finish(is_correct),
                    icon=ft.icons.ARROW_FORWARD,
                ),
            ], spacing=Spacing.MD)
        )
        self._page.update()

    def _reveal_manual(self) -> None:
        """Fallback para soluciones no parseables: muestra solución + auto-eval."""
        self._show_solution()

        self.controls = [
            c for c in self.controls
            if not isinstance(c, ft.ElevatedButton)
        ]
        self.controls.append(ft.Text(
            "¿Tu tabla fue correcta?",
            size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD,
            color=Colors.TEXT_PRIMARY))
        self.controls.append(ft.Row([
            ft.ElevatedButton(
                "✅  Sí, correcto",
                on_click=lambda _: self._finish(True),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#1B4332"},
                    color=Colors.SUCCESS,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
            ft.ElevatedButton(
                "❌  No del todo",
                on_click=lambda _: self._finish(False),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#4A1515"},
                    color=Colors.ERROR,
                    shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
        ], spacing=Spacing.MD))
        self._page.update()

    def _show_solution(self) -> None:
        """Muestra la solución completa en un panel expandible."""
        sol_col = ft.Column([
            ft.Text("✅ Solución", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.SUCCESS),
            ft.Text(self._solution, size=Typography.SIZE_XS,
                    color=Colors.TEXT_PRIMARY, selectable=True,
                    font_family="monospace"),
        ], spacing=Spacing.SM)

        if self._procedure:
            sol_col.controls.extend([
                ft.Divider(color=Colors.BORDER),
                ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                ft.Text(self._procedure, size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY, selectable=True),
            ])

        sol_card = ft.Container(
            content=sol_col,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.SUCCESS),
            border_radius=Radius.MD,
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD,
                               right=Spacing.MD, bottom=Spacing.MD),
        )

        # Insertar justo antes del Row de botones final
        self.controls.insert(-1, sol_card)
        self._page.update()

    def _finish(self, is_correct: bool) -> None:
        """Termina la tabulación y notifica al padre."""
        # Deshabilitar todo
        for row_cells in self._rows:
            for cell in row_cells:
                cell.disabled = True
        if self._result_field:
            self._result_field.disabled = True
        # Quitar botones
        self.controls = [
            c for c in self.controls
            if not isinstance(c, ft.Row)
            or not any(isinstance(b, (ft.ElevatedButton, ft.OutlinedButton))
                       for b in getattr(c, "controls", []))
        ]
        self._on_reveal(is_correct)
        self._page.update()