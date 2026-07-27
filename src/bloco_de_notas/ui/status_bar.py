"""Barra de status inferior (§23)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from ..models.document import DocumentStatus
from . import theme


def format_count(value: int) -> str:
    """Milhar com ponto, no formato brasileiro do exemplo da §23 (`1.245`)."""
    return f"{value:,}".replace(",", ".")


class EditorStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)

        self._position = QLabel()
        self._characters = QLabel()
        self._state = QLabel()
        self._font_size = QLabel()
        self._file = QLabel()

        # O caminho do arquivo fica à esquerda e encolhe primeiro quando a
        # janela é estreitada; os contadores ficam à direita, sempre legíveis.
        self._file.setObjectName("statusFile")
        self.addWidget(self._file, 1)
        for label in (self._position, self._characters, self._state, self._font_size):
            self.addPermanentWidget(self._separator())
            self.addPermanentWidget(label)

        self.update_position(1, 1)
        self.update_characters(0)
        self.update_font_size(14)

    def _separator(self) -> QLabel:
        label = QLabel("|")
        label.setStyleSheet(f"color: {theme.BORDER};")
        return label

    def update_position(self, line: int, column: int) -> None:
        self._position.setText(f"Linha {line}, Coluna {column}")

    def update_characters(self, count: int) -> None:
        self._characters.setText(f"{format_count(count)} caracteres")

    def update_state(self, status: DocumentStatus) -> None:
        self._state.setText(status.value)
        color = theme.ERROR if status is DocumentStatus.SAVE_ERROR else theme.TEXT
        self._state.setStyleSheet(f"color: {color};")

    def update_font_size(self, size: int) -> None:
        self._font_size.setText(f"Fonte {size} px")

    def update_file(self, path: str) -> None:
        self._file.setText(path)
