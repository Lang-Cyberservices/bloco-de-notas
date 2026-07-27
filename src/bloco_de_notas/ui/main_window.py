"""Janela principal: menus, atalhos e reflexo do estado do documento.

A janela não lê nem grava arquivo nenhum. Ela dispara ações no
`DocumentService` e reage a dois sinais dele: `document_loaded` (recarregar o
editor) e `state_changed` (atualizar título e barra de status).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from .. import APP_NAME
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
        #: enquanto True, alterações no editor vêm do próprio programa
        #: (carregar um documento) e não devem marcar o documento como alterado
        self._loading = False

        self.editor = TextEditor(self)
        self.search_bar = SearchBar(self.editor, self)
        self.status = EditorStatusBar(self)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.search_bar)
        self.setCentralWidget(container)
        self.setStatusBar(self.status)

        self._build_menus()
        self._restore_preferences()
        self._connect()

        service.attach_source(self.editor)
        self.editor.setFocus()

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
            "&Desfazer", QKeySequence.StandardKey.Undo, self.editor.undo
        )
        self.action_redo = self._action(
            "&Refazer", QKeySequence.StandardKey.Redo, self.editor.redo
        )
        self.action_cut = self._action(
            "Rec&ortar", QKeySequence.StandardKey.Cut, self.editor.cut
        )
        self.action_copy = self._action(
            "&Copiar", QKeySequence.StandardKey.Copy, self.editor.copy
        )
        self.action_paste = self._action(
            "Co&lar", QKeySequence.StandardKey.Paste, self.editor.paste
        )
        self.action_select_all = self._action(
            "Selecionar &tudo", QKeySequence.StandardKey.SelectAll, self.editor.selectAll
        )
        self.action_find = self._action(
            "&Localizar…", QKeySequence.StandardKey.Find, self.search_bar.show_find
        )
        self.action_replace = self._action(
            "&Substituir…", QKeySequence("Ctrl+H"), self.search_bar.show_replace
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
            "&Aumentar fonte", QKeySequence.StandardKey.ZoomIn, self.editor.increase_font_size
        )
        # Ctrl+= é o que o teclado entrega sem Shift na maioria dos layouts.
        self.action_zoom_in.setShortcuts(
            [QKeySequence("Ctrl++"), QKeySequence("Ctrl+="), QKeySequence("Ctrl+Shift+=")]
        )
        self.action_zoom_out = self._action(
            "&Diminuir fonte",
            QKeySequence.StandardKey.ZoomOut,
            self.editor.decrease_font_size,
        )
        self.action_zoom_reset = self._action(
            "&Restaurar tamanho da fonte", QKeySequence("Ctrl+0"), self.editor.reset_font_size
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
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _connect(self) -> None:
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_status)
        self.editor.font_size_changed.connect(self._on_font_size_changed)
        self.editor.undoAvailable.connect(self.action_undo.setEnabled)
        self.editor.redoAvailable.connect(self.action_redo.setEnabled)
        self.editor.copyAvailable.connect(self.action_cut.setEnabled)
        self.editor.copyAvailable.connect(self.action_copy.setEnabled)

        self._service.document_loaded.connect(self._on_document_loaded)
        self._service.state_changed.connect(self._update_all)
        self._service.notification.connect(self._show_notification)

    def _restore_preferences(self) -> None:
        family = self._settings.font_family
        if family:
            self.editor.set_font_family(family)
        self.editor.set_font_size(self._settings.font_size, notify=False)

        wrap = self._settings.word_wrap
        self.editor.set_word_wrap_enabled(wrap)
        self.action_wrap.setChecked(wrap)

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
        self.editor.set_word_wrap_enabled(enabled)
        self._settings.word_wrap = enabled

    # ---------------------------------------------------------------- reflexos

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._service.on_text_changed()
        self._update_status()

    def _on_document_loaded(self) -> None:
        document = self._service.document
        self._loading = True
        try:
            self.editor.set_content(document.content)
            self.editor.set_cursor_position(document.cursor_position)
        finally:
            self._loading = False
        # A rolagem só pode ser restaurada depois que o Qt calculou o layout
        # do texto recém-carregado; antes disso o scrollbar ainda tem alcance 0.
        QTimer.singleShot(0, lambda: self.editor.set_scroll_position(document.scroll_position))
        self._update_all()

    def _on_font_size_changed(self, size: int) -> None:
        self._settings.font_size = size
        self.status.update_font_size(size)

    def _show_notification(self, message: str) -> None:
        self.status.showMessage(message, 6000)

    def _update_all(self) -> None:
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
