"""Barra de localizar e substituir (§24).

É uma faixa dentro da janela, não um diálogo modal: o usuário continua vendo e
editando o texto enquanto procura. Sem expressões regulares nesta versão.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QWidget,
    QTextEdit,
)

from . import theme
from .text_editor import TextEditor

#: Teto de destaques pintados de uma vez; acima disso a busca continua
#: funcionando, só não colore todas as ocorrências de um documento enorme.
MAX_HIGHLIGHTS = 5000


class SearchBar(QWidget):
    closed = Signal()

    def __init__(self, editor: TextEditor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchBar")
        self._editor = editor

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Localizar")
        self._find_input.setClearButtonEnabled(True)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Substituir por")
        self._replace_input.setClearButtonEnabled(True)

        self._case_checkbox = QCheckBox("Diferenciar maiúsculas")
        self._status = QLabel()
        self._status.setStyleSheet(f"color: {theme.TEXT_DIM};")

        previous_button = QPushButton("Anterior")
        next_button = QPushButton("Próxima")
        self._replace_button = QPushButton("Substituir")
        self._replace_all_button = QPushButton("Substituir todas")

        close_button = QToolButton()
        close_button.setText("✕")
        close_button.setToolTip("Fechar (Esc)")

        layout = QGridLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(4)
        layout.addWidget(self._find_input, 0, 0)
        layout.addWidget(previous_button, 0, 1)
        layout.addWidget(next_button, 0, 2)
        layout.addWidget(self._case_checkbox, 0, 3)
        layout.addWidget(self._status, 0, 4)
        layout.addWidget(close_button, 0, 5)
        layout.addWidget(self._replace_input, 1, 0)
        layout.addWidget(self._replace_button, 1, 1)
        layout.addWidget(self._replace_all_button, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(4, 1)

        self._replace_widgets = (
            self._replace_input,
            self._replace_button,
            self._replace_all_button,
        )

        next_button.clicked.connect(self.find_next)
        previous_button.clicked.connect(self.find_previous)
        close_button.clicked.connect(self.close_bar)
        self._replace_button.clicked.connect(self.replace_current)
        self._replace_all_button.clicked.connect(self.replace_all)
        self._find_input.textChanged.connect(self._on_query_changed)
        self._find_input.returnPressed.connect(self.find_next)
        self._replace_input.returnPressed.connect(self.replace_current)
        self._case_checkbox.toggled.connect(self._on_query_changed)

        self.hide()

    def set_editor(self, editor: TextEditor) -> None:
        """Passa a procurar em outro editor (o usuário trocou de aba)."""
        if editor is self._editor:
            return
        try:
            self._editor.set_search_selections([])
        except RuntimeError:
            pass  # o editor anterior já foi destruído junto com a aba
        self._editor = editor
        if self.isVisible():
            self._highlight_all()

    # ------------------------------------------------------------ abrir/fechar

    def show_find(self) -> None:
        self._set_replace_visible(False)
        self._open_with_selection()

    def show_replace(self) -> None:
        self._set_replace_visible(True)
        self._open_with_selection()

    def _set_replace_visible(self, visible: bool) -> None:
        for widget in self._replace_widgets:
            widget.setVisible(visible)

    def _open_with_selection(self) -> None:
        # Texto selecionado no editor vira o termo procurado: é o que o
        # usuário quase sempre quer ao apertar Ctrl+F.
        selected = self._editor.textCursor().selectedText()
        if selected and " " not in selected:
            self._find_input.setText(selected)
        self.show()
        self._find_input.setFocus()
        self._find_input.selectAll()
        self._highlight_all()

    def close_bar(self) -> None:
        self.hide()
        self._editor.set_search_selections([])
        self._editor.setFocus()
        self.closed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ busca

    def _flags(self, backward: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self._case_checkbox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _on_query_changed(self) -> None:
        self._highlight_all()

    def find_next(self) -> bool:
        return self._find(backward=False)

    def find_previous(self) -> bool:
        return self._find(backward=True)

    def _find(self, backward: bool) -> bool:
        query = self._find_input.text()
        if not query:
            return False

        found = self._editor.find(query, self._flags(backward))
        if not found:
            # Dá a volta no documento antes de desistir.
            original = self._editor.textCursor()
            wrapped = self._editor.textCursor()
            wrapped.movePosition(
                QTextCursor.MoveOperation.End
                if backward
                else QTextCursor.MoveOperation.Start
            )
            self._editor.setTextCursor(wrapped)
            found = self._editor.find(query, self._flags(backward))
            if not found:
                self._editor.setTextCursor(original)

        self._set_match_state(found)
        self._highlight_all()
        return found

    def _set_match_state(self, found: bool) -> None:
        self._find_input.setProperty("noMatch", not found)
        # Trocar uma propriedade não repinta sozinho; é preciso reavaliar o estilo.
        self._find_input.style().unpolish(self._find_input)
        self._find_input.style().polish(self._find_input)

    def _highlight_all(self) -> None:
        query = self._find_input.text()
        if not query:
            self._editor.set_search_selections([])
            self._status.clear()
            self._set_match_state(True)
            return

        selections: list[QTextEdit.ExtraSelection] = []
        document = self._editor.document()
        cursor = QTextCursor(document)
        flags = self._flags()
        count = 0

        while count < MAX_HIGHLIGHTS:
            cursor = document.find(query, cursor, flags)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(theme.MATCH_BG))
            selection.cursor = cursor
            selections.append(selection)
            count += 1

        self._editor.set_search_selections(selections)
        if count == 0:
            self._status.setText("Nenhuma ocorrência")
            self._set_match_state(False)
        else:
            plural = "ocorrência" if count == 1 else "ocorrências"
            limit = "+" if count == MAX_HIGHLIGHTS else ""
            self._status.setText(f"{count}{limit} {plural}")
            self._set_match_state(True)

    # ------------------------------------------------------------ substituição

    def _selection_matches_query(self) -> bool:
        selected = self._editor.textCursor().selectedText()
        query = self._find_input.text()
        if not selected or not query:
            return False
        if self._case_checkbox.isChecked():
            return selected == query
        return selected.lower() == query.lower()

    def replace_current(self) -> None:
        if not self._find_input.text():
            return
        # Só substitui o que já está selecionado; caso contrário, apenas
        # localiza — evita trocar algo que o usuário ainda não viu.
        if self._selection_matches_query():
            cursor = self._editor.textCursor()
            cursor.insertText(self._replace_input.text())
        self.find_next()

    def replace_all(self) -> None:
        query = self._find_input.text()
        if not query:
            return
        replacement = self._replace_input.text()

        document = self._editor.document()
        flags = self._flags()
        count = 0

        # Todas as edições precisam sair do MESMO cursor que abriu o bloco:
        # com dois cursores o Qt não agrupa, e o Ctrl+Z não desfaria nada.
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        try:
            position = 0
            while True:
                found = document.find(query, position, flags)
                if found.isNull():
                    break
                cursor.setPosition(found.selectionStart())
                cursor.setPosition(
                    found.selectionEnd(), QTextCursor.MoveMode.KeepAnchor
                )
                cursor.insertText(replacement)
                position = cursor.position()
                count += 1
        finally:
            cursor.endEditBlock()

        plural = "ocorrência substituída" if count == 1 else "ocorrências substituídas"
        self._status.setText(f"{count} {plural}")
        self._highlight_all()
