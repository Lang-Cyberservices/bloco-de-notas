"""Janela principal: menus, atalhos, abas e reflexo do estado dos documentos.

A janela não lê nem grava arquivo nenhum. Ela dispara ações no
`DocumentService` e reage aos sinais dele: `document_added` / `document_removed`
(criar e remover abas), `current_changed` (trocar de aba) e `state_changed`
(atualizar títulos e barra de status).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..models.document import Document
from ..services.document_service import DocumentService
from ..services.settings_service import SettingsService
from .search_bar import SearchBar
from .status_bar import EditorStatusBar
from .text_editor import TextEditor

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, service: DocumentService, settings: SettingsService) -> None:
        super().__init__()
        self._service = service
        self._settings = settings
        #: um editor por documento aberto, indexado pelo id do documento
        self._editors: dict[str, TextEditor] = {}
        # Fonte e quebra de linha são preferências globais: valem para todas
        # as abas, inclusive as que ainda serão abertas.
        self._font_family = settings.font_family
        self._font_size = settings.font_size
        self._word_wrap = settings.word_wrap

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.tabBar().setExpanding(False)
        self.status = EditorStatusBar(self)

        self._build_menus()
        for document in service.documents:
            self._add_tab(document)
        self.search_bar = SearchBar(self.editor, self)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.search_bar)
        self.setCentralWidget(container)
        self.setStatusBar(self.status)

        self._restore_preferences()
        self._connect()

        self._refresh_edit_actions()
        self.editor.setFocus()

    @property
    def editor(self) -> TextEditor:
        """O editor da aba ativa."""
        return self.tabs.currentWidget()

    # ---------------------------------------------------------------- montagem

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Arquivo")
        self.action_new = self._action("&Novo", QKeySequence.StandardKey.New, self.on_new)
        self.action_open = self._action("&Abrir…", QKeySequence.StandardKey.Open, self.on_open)
        self.action_save = self._action("&Salvar", QKeySequence.StandardKey.Save, self.on_save)
        self.action_save_as = self._action(
            "Salvar &como…", QKeySequence.StandardKey.SaveAs, self.on_save_as
        )
        self.action_close_doc = self._action(
            "&Fechar documento", QKeySequence("Ctrl+W"), self.on_close_document
        )
        self.action_quit = self._action("Sai&r", QKeySequence("Ctrl+Q"), self.close)
        file_menu.addActions([self.action_new, self.action_open])
        file_menu.addSeparator()
        file_menu.addActions([self.action_save, self.action_save_as])
        file_menu.addSeparator()
        file_menu.addActions([self.action_close_doc, self.action_quit])

        edit_menu = menu_bar.addMenu("&Editar")
        self.action_undo = self._action(
            "&Desfazer", QKeySequence.StandardKey.Undo, lambda: self.editor.undo()
        )
        self.action_redo = self._action(
            "&Refazer", QKeySequence.StandardKey.Redo, lambda: self.editor.redo()
        )
        self.action_cut = self._action(
            "Rec&ortar", QKeySequence.StandardKey.Cut, lambda: self.editor.cut()
        )
        self.action_copy = self._action(
            "&Copiar", QKeySequence.StandardKey.Copy, lambda: self.editor.copy()
        )
        self.action_paste = self._action(
            "Co&lar", QKeySequence.StandardKey.Paste, lambda: self.editor.paste()
        )
        self.action_select_all = self._action(
            "Selecionar &tudo", QKeySequence.StandardKey.SelectAll, lambda: self.editor.selectAll()
        )
        self.action_find = self._action(
            "&Localizar…", QKeySequence.StandardKey.Find, lambda: self.search_bar.show_find()
        )
        self.action_replace = self._action(
            "&Substituir…", QKeySequence("Ctrl+H"), lambda: self.search_bar.show_replace()
        )
        edit_menu.addActions([self.action_undo, self.action_redo])
        edit_menu.addSeparator()
        edit_menu.addActions([self.action_cut, self.action_copy, self.action_paste])
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_select_all)
        edit_menu.addSeparator()
        edit_menu.addActions([self.action_find, self.action_replace])

        view_menu = menu_bar.addMenu("&Visualizar")
        self.action_zoom_in = self._action(
            "&Aumentar fonte",
            QKeySequence.StandardKey.ZoomIn,
            lambda: self.editor.increase_font_size(),
        )
        # Ctrl+= é o que o teclado entrega sem Shift na maioria dos layouts.
        self.action_zoom_in.setShortcuts(
            [QKeySequence("Ctrl++"), QKeySequence("Ctrl+="), QKeySequence("Ctrl+Shift+=")]
        )
        self.action_zoom_out = self._action(
            "&Diminuir fonte",
            QKeySequence.StandardKey.ZoomOut,
            lambda: self.editor.decrease_font_size(),
        )
        self.action_zoom_reset = self._action(
            "&Restaurar tamanho da fonte",
            QKeySequence("Ctrl+0"),
            lambda: self.editor.reset_font_size(),
        )
        self.action_wrap = QAction("&Quebra automática de linha", self)
        self.action_wrap.setCheckable(True)
        self.action_wrap.toggled.connect(self.on_toggle_wrap)
        self.addAction(self.action_wrap)
        view_menu.addActions(
            [self.action_zoom_in, self.action_zoom_out, self.action_zoom_reset]
        )
        view_menu.addSeparator()
        view_menu.addAction(self.action_wrap)

        self.action_next_tab = self._action(
            "&Próxima aba", QKeySequence("Ctrl+Tab"), lambda: self._step_tab(1)
        )
        self.action_next_tab.setShortcuts(
            [QKeySequence("Ctrl+Tab"), QKeySequence("Ctrl+PgDown")]
        )
        self.action_previous_tab = self._action(
            "Aba a&nterior", QKeySequence("Ctrl+Shift+Tab"), lambda: self._step_tab(-1)
        )
        self.action_previous_tab.setShortcuts(
            [QKeySequence("Ctrl+Shift+Tab"), QKeySequence("Ctrl+PgUp")]
        )
        view_menu.addSeparator()
        view_menu.addActions([self.action_next_tab, self.action_previous_tab])

        # As ações de desfazer/refazer/recortar/copiar só fazem sentido em
        # certos estados; o Qt informa quando cada uma fica disponível.
        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)
        self.action_cut.setEnabled(False)
        self.action_copy.setEnabled(False)

    def _action(self, text: str, shortcut, slot) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        # `triggered` envia um booleano que os slots não esperam.
        action.triggered.connect(lambda _checked=False: slot())
        self.addAction(action)
        return action

    def _connect(self) -> None:
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabBar().tabMoved.connect(self._service.move_document)

        self._service.document_added.connect(self._add_tab)
        self._service.document_removed.connect(self._remove_tab)
        self._service.current_changed.connect(self._on_current_changed)
        self._service.state_changed.connect(self._update_all)
        self._service.notification.connect(self._show_notification)

    def _restore_preferences(self) -> None:
        self.action_wrap.setChecked(self._word_wrap)

        geometry = self._settings.window_geometry
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(900, 640)
        if self._settings.window_maximized:
            self.showMaximized()

        self.status.update_font_size(self.editor.font_size)

    # ------------------------------------------------------------------ ações

    def on_new(self) -> None:
        self._service.new_document()

    def on_open(self) -> None:
        self._service.open_dialog()

    def on_save(self) -> None:
        self._service.save()

    def on_save_as(self) -> None:
        self._service.save_as()

    def on_close_document(self) -> None:
        self._service.close_document()

    def on_toggle_wrap(self, enabled: bool) -> None:
        self._word_wrap = enabled
        for editor in self._editors.values():
            editor.set_word_wrap_enabled(enabled)
        self._settings.word_wrap = enabled

    # ------------------------------------------------------------------- abas

    def _add_tab(self, document: Document) -> None:
        editor = TextEditor(self.tabs)
        if self._font_family:
            editor.set_font_family(self._font_family)
        editor.set_font_size(self._font_size, notify=False)
        editor.set_word_wrap_enabled(self._word_wrap)

        # O conteúdo entra antes de ligar `textChanged`: carregar um documento
        # não é uma alteração do usuário.
        editor.set_content(document.content)
        editor.set_cursor_position(document.cursor_position)
        editor.restore_scroll_position(document.scroll_position)

        doc_id = document.id
        editor.textChanged.connect(lambda: self._on_text_changed(doc_id))
        editor.cursorPositionChanged.connect(lambda: self._on_cursor_moved(editor))
        editor.font_size_changed.connect(self._on_font_size_changed)
        editor.undoAvailable.connect(lambda _on: self._on_edit_state_changed(editor))
        editor.redoAvailable.connect(lambda _on: self._on_edit_state_changed(editor))
        editor.copyAvailable.connect(lambda _on: self._on_edit_state_changed(editor))

        self._editors[doc_id] = editor
        self._service.attach_source(doc_id, editor)
        index = self.tabs.addTab(editor, "")

        close_button = QToolButton(self.tabs)
        close_button.setObjectName("tabClose")
        close_button.setText("✕")
        close_button.setToolTip("Fechar (Ctrl+W)")
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(lambda: self._service.close_document(doc_id))
        self.tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, close_button
        )
        self._update_tab_labels()

    def _remove_tab(self, doc_id: str) -> None:
        editor = self._editors.pop(doc_id)
        self.tabs.removeTab(self.tabs.indexOf(editor))
        editor.deleteLater()

    def _doc_id_of(self, editor: QWidget | None) -> str | None:
        for doc_id, candidate in self._editors.items():
            if candidate is editor:
                return doc_id
        return None

    def _on_current_changed(self) -> None:
        """O serviço trocou o documento atual; a aba acompanha."""
        self.tabs.setCurrentWidget(self._editors[self._service.document.id])

    def _on_tab_changed(self, index: int) -> None:
        """O usuário trocou de aba; o serviço acompanha."""
        doc_id = self._doc_id_of(self.tabs.widget(index))
        if doc_id is None:
            return
        self._service.set_current(doc_id)
        self.search_bar.set_editor(self.editor)
        self._refresh_edit_actions()
        self._update_all()
        self.editor.setFocus()

    def _step_tab(self, step: int) -> None:
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def _update_tab_labels(self) -> None:
        for document in self._service.documents:
            editor = self._editors.get(document.id)
            if editor is None:
                continue
            index = self.tabs.indexOf(editor)
            marker = "● " if document.is_dirty_vs_recovery else ""
            # `&` em um rótulo de aba viraria atalho de teclado.
            name = document.display_name.replace("&", "&&")
            self.tabs.setTabText(index, f"{marker}{name}")
            self.tabs.setTabToolTip(index, document.display_path)

    def _refresh_edit_actions(self) -> None:
        editor = self.editor
        has_selection = editor.textCursor().hasSelection()
        self.action_undo.setEnabled(editor.document().isUndoAvailable())
        self.action_redo.setEnabled(editor.document().isRedoAvailable())
        self.action_cut.setEnabled(has_selection)
        self.action_copy.setEnabled(has_selection)

    def _on_edit_state_changed(self, editor: TextEditor) -> None:
        if editor is self.editor:
            self._refresh_edit_actions()

    def _on_cursor_moved(self, editor: TextEditor) -> None:
        if editor is self.editor:
            self._update_status()

    # ---------------------------------------------------------------- reflexos

    def _on_text_changed(self, doc_id: str) -> None:
        self._service.on_text_changed(doc_id)

    def _on_font_size_changed(self, size: int) -> None:
        self._font_size = size
        for editor in self._editors.values():
            editor.set_font_size(size, notify=False)
        self._settings.font_size = size
        self.status.update_font_size(size)

    def _show_notification(self, message: str) -> None:
        self.status.showMessage(message, 6000)

    def _update_all(self) -> None:
        self._update_tab_labels()
        self._update_title()
        self._update_status()

    def _update_title(self) -> None:
        document = self._service.document
        # O marcador ● significa "ainda não está nem na recuperação" (§22).
        marker = "● " if document.is_dirty_vs_recovery else ""
        self.setWindowTitle(f"{marker}{document.display_name} — {APP_NAME}")

    def _update_status(self) -> None:
        line, column = self.editor.current_line_and_column()
        self.status.update_position(line, column)
        # characterCount() inclui o separador final de parágrafo; descontá-lo
        # evita copiar o documento inteiro só para contar caracteres.
        self.status.update_characters(max(0, self.editor.document().characterCount() - 1))
        self.status.update_state(self._service.status)
        self.status.update_file(self._service.document.display_path)

    # -------------------------------------------------------------- encerrar

    def closeEvent(self, event: QCloseEvent) -> None:
        """Fecha sem perguntar nada e preservando a recuperação (§14)."""
        self._settings.window_maximized = self.isMaximized()
        if not self.isMaximized():
            self._settings.window_geometry = self.saveGeometry()
        self._settings.font_size = self.editor.font_size
        self._settings.font_family = self.editor.font_family
        self._settings.word_wrap = self.editor.is_word_wrap_enabled()
        self._settings.sync()

        self._service.shutdown()
        event.accept()
