"""Coluna de números de linha (§6).

É um widget irmão do viewport do editor, não parte do documento: os números
nunca entram em `toPlainText()`, não são selecionáveis, não são copiados e
não vão para o arquivo salvo. Toda a pintura é delegada ao editor, que é quem
conhece a geometria dos blocos de texto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:  # pragma: no cover - apenas para o verificador de tipos
    from .text_editor import TextEditor


class LineNumberArea(QWidget):
    def __init__(self, editor: TextEditor) -> None:
        super().__init__(editor)
        self._editor = editor
        # Impede que a coluna roube o foco ou o cursor de texto do editor.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_line_numbers(event)

    def wheelEvent(self, event) -> None:
        # Rolar sobre a coluna rola o texto, como o usuário espera.
        self._editor.wheelEvent(event)
