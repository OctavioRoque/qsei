"""
ui/screens/manage_questions_screen.py
=====================================
Pantalla para visualizar y editar los bancos de preguntas.
Permite seleccionar un tema, editar preguntas y guardar los cambios directamente en JSON.
"""
from __future__ import annotations
from typing import Callable
import flet as ft

from game.questions.question_bank import (
    available_topics,
    count,
    load_topic_questions,
    save_topic_questions,
)
from game.questions.question_model import BankQuestion
from ui.themes.theme import (
    Colors, Typography, Spacing, Radius,
    title_text, subtitle_text, card,
    primary_button, secondary_button,
)


class ManageQuestionsScreen(ft.Column):
    def __init__(self, on_back: Callable[[], None], page: ft.Page) -> None:
        super().__init__()
        self._on_back = on_back
        self._page = page
        self._selected_topic: str | None = None
        self._questions: list[BankQuestion] = []
        self._selected_question: BankQuestion | None = None
        self._status = ft.Text("", color=Colors.SUCCESS, size=Typography.SIZE_SM)
        self._question_field: ft.TextField | None = None
        self._solution_field: ft.TextField | None = None
        self._procedure_field: ft.TextField | None = None
        self._difficulty_field: ft.Dropdown | None = None
        self._type_field: ft.Dropdown | None = None
        self._build()

    def _build(self) -> None:
        topics = available_topics()
        topic_tiles = []
        for t in topics:
            topic_tiles.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(t.replace('_', ' ').title(), size=Typography.SIZE_SM, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{count(t)} preguntas", size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
                    ]),
                    primary_button("Editar", lambda e, topic=t: self._select_topic(topic)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.Padding(left=Spacing.MD, top=Spacing.SM, right=Spacing.MD, bottom=Spacing.SM),
                border=ft.border.all(1, Colors.BORDER),
                border_radius=Radius.MD,
                bgcolor=Colors.BG_CARD,
            ))

        questions_column = self._build_question_list()
        editor_column = self._build_editor_panel()

        header = ft.Row(
            [
                ft.Column([
                    title_text("Gestionar preguntas", size=22),
                    subtitle_text("Edita preguntas y respuestas directamente desde el banco."),
                ], spacing=4),
                ft.Row([
                    primary_button("Nuevo tema", self._prompt_new_topic),
                    secondary_button("← Volver", lambda _: self._on_back()),
                ], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.controls = [
            ft.Container(
                content=ft.Column([
                    header,
                    ft.Row([
                        card(ft.Column(topic_tiles, spacing=Spacing.SM), padding=Spacing.LG, width=280),
                        card(questions_column, padding=Spacing.LG, expand=True),
                        card(editor_column, padding=Spacing.LG, expand=True),
                    ], spacing=Spacing.MD, expand=True),
                ], spacing=Spacing.MD),
                padding=ft.Padding(left=Spacing.LG, top=Spacing.LG, right=Spacing.LG, bottom=Spacing.LG),
                expand=True,
            )
        ]
        self.expand = True
        self.spacing = 0

    def _select_topic(self, topic: str) -> None:
        self._selected_topic = topic
        self._questions = load_topic_questions(topic)
        self._selected_question = None
        self._build()
        self._page.update()

    def _prompt_new_topic(self, e: ft.ControlEvent) -> None:
        dlg = ft.AlertDialog(
            title=ft.Text("Crear nuevo tema"),
            content=ft.TextField(label="Clave del tema (sin espacios)", autofocus=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._close_dialog()),
                ft.ElevatedButton("Crear", on_click=lambda ev, d=dlg: self._create_topic(d)),
            ],
        )
        self._page.dialog = dlg
        dlg.open = True
        self._page.update()

    def _create_topic(self, dialog: ft.AlertDialog) -> None:
        tf = dialog.content
        key = (tf.value or "").strip()
        if not key:
            return
        # crear archivo vacío
        save_topic_questions(key, [])
        self._close_dialog()
        self._selected_topic = key
        self._questions = []
        self._selected_question = None
        self._build()
        self._page.update()

    def _close_dialog(self) -> None:
        if self._page.dialog:
            self._page.dialog.open = False
            self._page.update()

    def _select_question(self, question_id: str) -> None:
        self._selected_question = next((q for q in self._questions if q.id == question_id), None)
        self._build()
        self._page.update()

    def _build_question_list(self) -> ft.Column:
        if self._selected_topic is None:
            return ft.Column([
                ft.Text("Selecciona un tema para ver y editar sus preguntas.", color=Colors.TEXT_SECONDARY)
            ], spacing=Spacing.SM)

        question_cards = []
        for question in self._questions:
            preview = question.question.replace("\n", " ")
            if len(preview) > 90:
                preview = preview[:90].rstrip() + "…"
            question_cards.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"{question.id} · Dificultad {question.difficulty} · {question.type}", size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
                        secondary_button("Editar", lambda e, qid=question.id: self._select_question(qid)),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(preview, size=Typography.SIZE_SM, color=Colors.TEXT_PRIMARY),
                ], spacing=Spacing.SM),
                padding=ft.Padding(left=Spacing.MD, top=Spacing.SM, right=Spacing.MD, bottom=Spacing.SM),
                border=ft.border.all(1, Colors.BORDER),
                border_radius=Radius.MD,
                bgcolor=Colors.BG_SURFACE,
            ))

        return ft.Column([
            ft.Text(f"Preguntas de {self._selected_topic.replace('_', ' ').title()}", size=Typography.SIZE_MD, weight=ft.FontWeight.BOLD),
            ft.Container(height=Spacing.SM),
            ft.Column(question_cards, spacing=Spacing.SM),
        ], spacing=Spacing.SM)

    def _build_editor_panel(self) -> ft.Column:
        if self._selected_question is None:
            return ft.Column([
                ft.Text("Selecciona una pregunta para editarla.", color=Colors.TEXT_SECONDARY),
                ft.Container(height=Spacing.SM),
                ft.Text("Cuando edites la pregunta, solución y procedimiento se guardará directamente en el archivo JSON.", size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ], spacing=Spacing.SM)

        question = self._selected_question
        self._question_field = ft.TextField(
            label="Pregunta",
            value=question.question,
            multiline=True,
            min_lines=3,
            max_lines=8,
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
        )
        self._solution_field = ft.TextField(
            label="Respuesta correcta",
            value=question.solution,
            multiline=True,
            min_lines=2,
            max_lines=6,
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
        )
        self._procedure_field = ft.TextField(
            label="Procedimiento / pista",
            value=question.procedure or "",
            multiline=True,
            min_lines=3,
            max_lines=8,
            bgcolor=Colors.BG_SURFACE,
            color=Colors.TEXT_PRIMARY,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
        )
        self._difficulty_field = ft.Dropdown(
            label="Dificultad",
            width=180,
            options=[
                ft.dropdown.Option("1", text="1 - Fácil"),
                ft.dropdown.Option("2", text="2 - Media"),
                ft.dropdown.Option("3", text="3 - Difícil"),
            ],
            value=str(question.difficulty),
        )
        self._type_field = ft.Dropdown(
            label="Tipo de pregunta",
            width=220,
            options=[
                ft.dropdown.Option("open", text="Open"),
                ft.dropdown.Option("tabulation", text="Tabulation"),
                ft.dropdown.Option("prerequisite", text="Prerequisite"),
                ft.dropdown.Option("analysis", text="Analysis"),
            ],
            value=question.type,
        )

        save_btn = primary_button("Guardar cambios", self._save_question)

        return ft.Column([
            ft.Text(f"Editando: {question.id}", size=Typography.SIZE_MD, weight=ft.FontWeight.BOLD),
            ft.Text("Pista oculta: la respuesta correcta en el juego tendrá un color de texto ligeramente más oscuro.", size=Typography.SIZE_XS, color=Colors.TEXT_SECONDARY),
            ft.Container(height=Spacing.SM),
            self._question_field,
            self._solution_field,
            self._procedure_field,
            ft.Row([self._difficulty_field, self._type_field], spacing=Spacing.MD),
            ft.Row([save_btn, self._status], spacing=Spacing.SM),
        ], spacing=Spacing.SM)

    def _save_question(self, e: ft.ControlEvent) -> None:
        if self._selected_question is None:
            return
        self._selected_question.question = self._question_field.value.strip()
        self._selected_question.solution = self._solution_field.value.strip()
        self._selected_question.procedure = self._procedure_field.value.strip()
        self._selected_question.difficulty = int(self._difficulty_field.value)
        self._selected_question.type = self._type_field.value
        save_topic_questions(self._selected_topic or self._selected_question.topic, self._questions)
        self._status.value = "Guardado correctamente."
        self._build()
        self._page.update()
