"""Área de edição: `QPlainTextEdit` com numeração de linhas e controle de fonte.

Este widget não sabe nada sobre arquivos, recuperação ou sessão — ele só edita
texto e conta o que está acontecendo por meio de sinais (§36: separar a
interface da lógica de persistência).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

from . import theme
from .line_number_area import LineNumberArea

DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 40
FONT_STEP = 1

#: Ordem de preferência da §5; a última opção é a monoespaçada do sistema.
FONT_CANDIDATES = ("JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono")

_GUTTER_PADDING = 12


def preferred_monospace_family() -> str:
    """Primeira fonte monoespaçada disponível, na ordem sugerida pela §5."""
    available = set(QFontDatabase.families())
    for family in FONT_CANDIDATES:
        if family in available:
            return family
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


class TextEditor(QPlainTextEdit):
    font_size_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._font_size = DEFAULT_FONT_SIZE
        self._font_family = preferred_monospace_family()
        self._search_selections: list[QTextEdit.ExtraSelection] = []
        #: rolagem a restaurar quando o editor for exibido pela primeira vez
        self._pending_scroll: int | None = None

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabChangesFocus(False)
        self.setCursorWidth(2)
        self.document().setDocumentMargin(6)
        # Não chamar setMaximumBlockCount() aqui: no Qt, defini-lo — mesmo
        # como 0 — desliga o histórico de desfazer, e a §5 exige desfazer e
        # refazer. Sem limite é o padrão do documento de qualquer forma.
        self.setUndoRedoEnabled(True)

        self._line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._update_extra_selections)

        self._apply_font()
        self._update_line_number_area_width()
        self._update_extra_selections()

    # ------------------------------------------------------------------ fonte

    @property
    def font_size(self) -> int:
        return self._font_size

    @property
    def font_family(self) -> str:
        return self._font_family

    def set_font_family(self, family: str) -> None:
        if family:
            self._font_family = family
            self._apply_font()

    def set_font_size(self, size: int, *, notify: bool = True) -> None:
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(size)))
        if size == self._font_size:
            return
        self._font_size = size
        self._apply_font()
        if notify:
            self.font_size_changed.emit(size)

    def increase_font_size(self) -> None:
        self.set_font_size(self._font_size + FONT_STEP)

    def decrease_font_size(self) -> None:
        self.set_font_size(self._font_size - FONT_STEP)

    def reset_font_size(self) -> None:
        self.set_font_size(DEFAULT_FONT_SIZE)

    def _apply_font(self) -> None:
        font = QFont(self._font_family)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        # A especificação (§8) fala em pixels, não em pontos.
        font.setPixelSize(self._font_size)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self._line_number_area.setFont(font)
        self._update_line_number_area_width()
        self.viewport().update()
        self._line_number_area.update()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.increase_font_size()
            elif delta < 0:
                self.decrease_font_size()
            event.accept()
            return
        super().wheelEvent(event)

    # ----------------------------------------------------------- quebra de linha

    def is_word_wrap_enabled(self) -> bool:
        return self.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth

    def set_word_wrap_enabled(self, enabled: bool) -> None:
        """Alterna apenas a quebra *visual*; o conteúdo nunca é alterado (§25)."""
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if enabled
            else QPlainTextEdit.LineWrapMode.NoWrap
        )

    # ------------------------------------------------------- números de linha

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return _GUTTER_PADDING + self.fontMetrics().horizontalAdvance("9") * digits + 8

    def _update_line_number_area_width(self, _block_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(
                contents.left(),
                contents.top(),
                self.line_number_area_width(),
                contents.height(),
            )
        )

    def paint_line_numbers(self, event) -> None:
        """Desenha a coluna de números; chamado pelo `LineNumberArea`."""
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(theme.GUTTER_BG))

        normal = QColor(theme.GUTTER_FG)
        current = QColor(theme.GUTTER_FG_CURRENT)
        current_block_number = self.textCursor().blockNumber()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        width = self._line_number_area.width() - _GUTTER_PADDING // 2
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_current = block_number == current_block_number
                painter.setPen(current if is_current else normal)
                painter.drawText(
                    0,
                    top,
                    width,
                    height,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    # ------------------------------------------------------- destaques visuais

    def set_search_selections(self, selections: list[QTextEdit.ExtraSelection]) -> None:
        self._search_selections = selections
        self._update_extra_selections()

    def _update_extra_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []

        if not self.isReadOnly():
            highlight = QTextEdit.ExtraSelection()
            highlight.format.setBackground(QColor(theme.CURRENT_LINE))
            highlight.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True
            )
            highlight.cursor = self.textCursor()
            highlight.cursor.clearSelection()
            selections.append(highlight)

        selections.extend(self._search_selections)
        self.setExtraSelections(selections)
        self._line_number_area.update()

    # ------------------------------------------------- posição do cursor/rolagem

    def content_text(self) -> str:
        """Texto atual. Satisfaz o `ContentSource` do `DocumentService`.

        Materializa o documento inteiro, então é chamado só nas fronteiras
        (autosave e salvamento), nunca a cada tecla.
        """
        return self.toPlainText()

    def cursor_position(self) -> int:
        return self.textCursor().position()

    def set_cursor_position(self, position: int) -> None:
        cursor = self.textCursor()
        cursor.setPosition(max(0, min(int(position), len(self.toPlainText()))))
        self.setTextCursor(cursor)

    def scroll_position(self) -> int:
        if self._pending_scroll is not None:
            return self._pending_scroll
        return self.verticalScrollBar().value()

    def restore_scroll_position(self, position: int) -> None:
        """Restaura a rolagem assim que o texto tiver layout.

        Antes de o editor ser exibido o scrollbar ainda tem alcance 0, e uma
        aba restaurada pode nunca ser visitada: até lá, `scroll_position()`
        continua devolvendo o valor guardado, para que ele não se perca.
        """
        self._pending_scroll = int(position) or None
        if self.isVisible():
            QTimer.singleShot(0, self._apply_pending_scroll)

    def _apply_pending_scroll(self) -> None:
        if self._pending_scroll is None:
            return
        self.set_scroll_position(self._pending_scroll)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._pending_scroll is not None:
            QTimer.singleShot(0, self._apply_pending_scroll)

    def set_scroll_position(self, position: int) -> None:
        self._pending_scroll = None
        bar = self.verticalScrollBar()
        bar.setValue(max(bar.minimum(), min(int(position), bar.maximum())))

    def current_line_and_column(self) -> tuple[int, int]:
        cursor = self.textCursor()
        return cursor.blockNumber() + 1, cursor.positionInBlock() + 1

    def set_content(self, text: str) -> None:
        """Substitui o conteúdo sem deixar a troca no histórico de desfazer."""
        self.setPlainText(text)
        self.document().clearUndoRedoStacks()
        self.moveCursor(QTextCursor.MoveOperation.Start)
