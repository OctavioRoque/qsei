"""
ui/widgets/tabulation_widget.py
================================
Widget de tabulación con validación automática celda-a-celda.

Estrategia de parseo:
  1. Pipe-table: líneas con | val | val |  →  69% de preguntas
  2. Labeled-value: patrón "label = ... = FINAL"  →  resto
  Si ninguno funciona, solo muestra la solución y deja al alumno
  verificar manualmente (este caso no debería ocurrir con el banco actual).
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
_DEFAULT_COLUMNS = ["n", "col_1", "col_2", "col_3", "col_4"]
_NARROW = {"n", "i", "iter", "paso", "sgn", "coef.", "x"}
_CW, _CWN = 92, 52


def _cw(h: str) -> int:
    return _CWN if h in _NARROW else _CW


# ── Utilidades numéricas ──────────────────────────────────────────────────────

def _to_float(s: str) -> float | None:
    s = s.strip().lstrip("(").rstrip(")")
    s = s.replace(",", ".").replace("−", "-").replace("–", "-")
    frac = re.fullmatch(r"(-?\d+\.?\d*)\s*/\s*(-?\d+\.?\d*)", s)
    if frac:
        try:
            return float(frac.group(1)) / float(frac.group(2))
        except (ValueError, ZeroDivisionError):
            return None
    s = re.sub(r"[^\d.\-eE+]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _norm_sign(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"[(\[{]?\+[)\]}]?", s): return "+"
    if re.fullmatch(r"[(\[{]?-[)\]}]?", s):  return "-"
    return s.lower()


def _match(student: str, expected: str, tol: float = 0.01) -> bool:
    student, expected = student.strip(), expected.strip()
    if not student:
        return False
    if re.fullmatch(r"[(\[{]?[+\-][)\]}]?", expected):
        return _norm_sign(student) == _norm_sign(expected)
    sf, ef = _to_float(student), _to_float(expected)
    if sf is not None and ef is not None:
        return abs(sf - ef) < 0.005 or abs(sf - ef) / max(abs(ef), 1e-10) < tol
    return student.lower() == expected.lower()


# ── Parser de soluciones ──────────────────────────────────────────────────────

class SolutionParser:
    """
    Extrae una tabla 2D (list[list[str]]) desde el texto de solución.

    Estrategia 1 — Pipe-table: líneas que contienen '|' con al menos
    un número. Filtra la línea de separadores |---|.

    Estrategia 2 — Labeled-value: agrupa líneas por bloques de iteración
    y extrae el último número de cada línea del bloque.
    """

    def __init__(self, text: str) -> None:
        self.rows: list[list[str]] = []
        self._parse(text)

    def _parse(self, text: str) -> None:
        # ── Estrategia 1: pipe-table ──
        for line in text.split("\n"):
            if "|" not in line:
                continue
            if re.fullmatch(r"[\s|:\-=]+", line):
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if any(_to_float(c) is not None for c in cells):
                self.rows.append(cells)

        # Skip si la primera fila no tiene números (cabecera textual)
        if self.rows and not any(_to_float(v) for v in self.rows[0]):
            self.rows = self.rows[1:]

        if self.rows:
            return

        # ── Estrategia 2: labeled-value ──
        self._parse_labeled(text)

    def _parse_labeled(self, text: str) -> None:
        """
        Agrupa por bloques (separados por línea en blanco o por marcadores
        'Iteración N:' / 'Paso N:') y extrae el último número de cada
        línea dentro del bloque.
        """
        iter_re = re.compile(
            r"(?:Iteraci[oó]n|Paso|Step|Iter\.?)\s*\d+", re.IGNORECASE)

        if iter_re.search(text):
            blocks = iter_re.split(text)
        else:
            blocks = re.split(r"\n\s*\n", text.strip())

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            values: list[str] = []
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Último número precedido de '=' o ':' o al final de la línea
                nums = re.findall(
                    r"(?<=[=:\s])(-?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*(?:[✓→≈✔]|$)",
                    line)
                if nums:
                    values.append(nums[-1])
            if len(values) >= 2:
                # Prepend iter number so col indices align
                self.rows.append([str(len(self.rows) + 1)] + values)

    # ── Verificación ─────────────────────────────────────────────────────────

    def total_rows(self) -> int:
        return len(self.rows)

    def check_cell(self, row: int, col: int, student: str) -> bool | None:
        """True=correcto, False=incorrecto, None=no verificable."""
        if not student.strip():
            return None
        if row >= len(self.rows):
            return None
        expected_row = self.rows[row]
        if col >= len(expected_row):
            return None
        exp = expected_row[col]
        if not exp or exp in {"?", "—", "-", ""}:
            return None
        return _match(student, exp)


# ── Widget ────────────────────────────────────────────────────────────────────

class TabulationWidget(ft.Column):
    """
    Tabla de iteraciones con validación automática.

    on_reveal(is_correct: bool) se dispara al hacer clic en "Continuar →".
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

        self._columns     = _METHOD_COLUMNS.get(method_key, _DEFAULT_COLUMNS)
        self._parser      = SolutionParser(solution)
        self._rows:  list[list[ft.TextField]] = []
        self._result_field: ft.TextField | None = None
        self._rows_container = ft.Column(spacing=2)
        self._status  = ft.Text("", size=Typography.SIZE_SM)
        self._initialized = False

        self.spacing = Spacing.SM
        self._build()
        self._initialized = True

    # ─── Build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        n_exp = self._parser.total_rows()
        can_auto = n_exp > 0

        hint = (
            f"💡 La solución tiene {n_exp} iteración(es). Llena y presiona Verificar."
            if can_auto
            else "Llena la tabla y luego presiona Ver solución."
        )

        header_box = ft.Container(
            content=ft.Row([self._hcell(h) for h in self._columns], spacing=4),
            bgcolor=Colors.BG_SURFACE,
            border_radius=ft.BorderRadius(Radius.SM, Radius.SM, 0, 0),
            padding=ft.Padding(8, 6, 8, 6),
            border=ft.border.all(1, Colors.BORDER),
        )
        body_box = ft.Container(
            content=self._rows_container,
            border=ft.border.only(
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=ft.BorderRadius(0, 0, Radius.SM, Radius.SM),
            padding=ft.Padding(8, 4, 8, 8),
        )

        self._result_field = ft.TextField(
            label="Resultado final",
            hint_text="Ej: x ≈ 1.5234",
            bgcolor=Colors.BG_SURFACE, color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM, width=300,
        )

        if can_auto:
            action_btn = primary_button(
                "Verificar ✓", lambda _: self._verify(),
                icon=ft.icons.CHECK_CIRCLE_OUTLINE)
        else:
            action_btn = primary_button(
                "Ver solución 👁", lambda _: self._reveal_manual())

        self.controls = [
            ft.Text("📊 Tabla de iteraciones", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
            ft.Text(hint, size=Typography.SIZE_XS,
                    color=Colors.TEXT_SECONDARY, italic=True),
            header_box, body_box,
            ft.TextButton("+ Agregar fila",
                          icon=ft.icons.ADD_CIRCLE_OUTLINE,
                          icon_color=Colors.PRIMARY,
                          style=ft.ButtonStyle(color=Colors.PRIMARY),
                          on_click=lambda _: self._add_row()),
            ft.Divider(color=Colors.BORDER),
            ft.Row([
                ft.Text("Resultado:", size=Typography.SIZE_SM,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                self._result_field,
            ], spacing=Spacing.MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._status,
            action_btn,
        ]

        for _ in range(max(2, n_exp)):
            self._add_row()

    # ─── Celdas ─────────────────────────────────────────────────────────────

    def _hcell(self, h: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(h, size=11, weight=ft.FontWeight.BOLD,
                            color=Colors.TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER),
            width=_cw(h), alignment=ft.alignment.center)

    def _icell(self, h: str) -> ft.TextField:
        return ft.TextField(
            hint_text="—", text_size=12,
            bgcolor=Colors.BG_CARD, color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
            border_radius=Radius.SM,
            content_padding=ft.Padding(6, 4, 6, 4),
            width=_cw(h), text_align=ft.TextAlign.CENTER)

    def _add_row(self, _=None) -> None:
        n = len(self._rows) + 1
        cells = [self._icell(h) for h in self._columns]
        first = self._columns[0].lower()
        if first in {"n", "i", "iter", "paso"}:
            cells[0].value = str(n)
            cells[0].read_only = True
            cells[0].bgcolor = Colors.BG_SURFACE
        self._rows.append(cells)
        self._rows_container.controls.append(ft.Container(
            content=ft.Row(cells, spacing=4),
            bgcolor=Colors.BG_CARD if n % 2 == 0 else Colors.BG_SURFACE,
            padding=ft.Padding(0, 2, 0, 2)))
        if self._initialized:
            self._page.update()

    # ─── Auto-validación ────────────────────────────────────────────────────

    def _verify(self) -> None:
        correct = checkable = 0

        for ri, cells in enumerate(self._rows):
            for ci, cell in enumerate(cells):
                if cell.read_only:
                    continue
                res = self._parser.check_cell(ri, ci, cell.value or "")
                if res is True:
                    cell.border_color = Colors.SUCCESS
                    cell.focused_border_color = Colors.SUCCESS
                    cell.bgcolor = "#0D2416"
                    correct += 1; checkable += 1
                elif res is False:
                    cell.border_color = Colors.ERROR
                    cell.focused_border_color = Colors.ERROR
                    cell.bgcolor = "#2A0A0A"
                    checkable += 1
                else:
                    cell.border_color = Colors.TEXT_MUTED
                    cell.focused_border_color = Colors.TEXT_MUTED

        # Campo resultado
        res_ok = False
        if self._result_field and self._result_field.value:
            for row in self._parser.rows:
                for v in row:
                    if _match(self._result_field.value, v):
                        res_ok = True; break
            self._result_field.border_color = Colors.SUCCESS if res_ok else Colors.ERROR

        pct = correct / checkable * 100 if checkable else 0
        is_correct = pct >= 70
        emoji = "🏆" if pct == 100 else "🎯" if pct >= 70 else "📖"
        self._status.value  = f"{emoji}  {correct}/{checkable} valores correctos ({pct:.0f}%)"
        self._status.color  = Colors.SUCCESS if is_correct else Colors.ERROR

        # Reemplazar botón Verificar
        self.controls = [c for c in self.controls
                         if not isinstance(c, ft.ElevatedButton)]
        self.controls.append(ft.Row([
            ft.OutlinedButton(
                "Ver solución completa",
                icon=ft.icons.VISIBILITY_OUTLINED,
                style=ft.ButtonStyle(color=Colors.PRIMARY,
                                     side=ft.BorderSide(1, Colors.PRIMARY),
                                     shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                                     padding=ft.Padding(16, 10, 16, 10)),
                on_click=lambda _: self._show_solution(),
            ),
            primary_button("Continuar →",
                           lambda _: self._finish(is_correct),
                           icon=ft.icons.ARROW_FORWARD),
        ], spacing=Spacing.MD))
        self._page.update()

    # ─── Fallback manual ────────────────────────────────────────────────────

    def _reveal_manual(self) -> None:
        self._show_solution()
        self.controls = [c for c in self.controls
                         if not isinstance(c, ft.ElevatedButton)]
        self.controls.append(ft.Column([
            ft.Text("¿Tu tabla fue correcta?", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
            ft.Row([
                ft.ElevatedButton("✅  Sí, correcto",
                    on_click=lambda _: self._finish(True),
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.DEFAULT: "#1B4332"},
                        color=Colors.SUCCESS,
                        shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                        padding=ft.Padding(20, 12, 20, 12))),
                ft.ElevatedButton("❌  No del todo",
                    on_click=lambda _: self._finish(False),
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.DEFAULT: "#4A1515"},
                        color=Colors.ERROR,
                        shape=ft.RoundedRectangleBorder(radius=Radius.SM),
                        padding=ft.Padding(20, 12, 20, 12))),
            ], spacing=Spacing.MD),
        ], spacing=Spacing.SM))
        self._page.update()

    # ─── Mostrar solución ───────────────────────────────────────────────────

    def _show_solution(self) -> None:
        col = ft.Column([
            ft.Text("✅ Solución", size=Typography.SIZE_SM,
                    weight=ft.FontWeight.BOLD, color=Colors.SUCCESS),
            ft.Text(self._solution, size=Typography.SIZE_XS,
                    color=Colors.TEXT_PRIMARY, selectable=True,
                    font_family="monospace"),
        ], spacing=Spacing.SM)
        if self._procedure:
            col.controls += [
                ft.Divider(color=Colors.BORDER),
                ft.Text("📝 Procedimiento", size=Typography.SIZE_SM,
                        weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
                ft.Text(self._procedure, size=Typography.SIZE_XS,
                        color=Colors.TEXT_SECONDARY, selectable=True),
            ]
        self.controls.insert(-1, ft.Container(
            content=col,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.SUCCESS),
            border_radius=Radius.MD,
            padding=ft.Padding(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)))
        self._page.update()

    # ─── Finalizar ──────────────────────────────────────────────────────────

    def _finish(self, is_correct: bool) -> None:
        for row_cells in self._rows:
            for c in row_cells:
                c.disabled = True
        if self._result_field:
            self._result_field.disabled = True
        self.controls = [c for c in self.controls
                         if not isinstance(c, ft.Row)
                         or not any(isinstance(b, (ft.ElevatedButton, ft.OutlinedButton))
                                    for b in getattr(c, "controls", []))]
        self._on_reveal(is_correct)
        self._page.update()