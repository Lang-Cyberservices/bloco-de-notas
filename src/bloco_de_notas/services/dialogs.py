"""Interação com o usuário, isolada atrás de um Protocol.

O `DocumentService` decide *o quê* perguntar; este módulo decide *como*. A
separação existe para que as regras das §16–§19 — as mais delicadas da
especificação — possam ser testadas com um substituto programável, sem
janelas modais travando a suíte.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from .. import APP_NAME

TEXT_FILTER = "Arquivos de texto (*.txt);;Todos os arquivos (*)"


class SaveChoice(Enum):
    SAVE = "salvar"
    DISCARD = "nao-salvar"
    CANCEL = "cancelar"


class DialogPort(Protocol):
    """O que o `DocumentService` precisa poder perguntar."""

    def ask_save_discard_cancel(self, document_name: str) -> SaveChoice: ...

    def ask_save_path(self, suggested: Path) -> Path | None: ...

    def ask_open_path(self, start_dir: Path) -> Path | None: ...

    def show_error(self, title: str, message: str) -> None: ...


class QtDialogs:
    """Implementação real, com widgets do Qt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._parent = parent

    def set_parent(self, parent: QWidget) -> None:
        """A janela só existe depois do serviço; ela é ligada aqui."""
        self._parent = parent

    def ask_save_discard_cancel(self, document_name: str) -> SaveChoice:
        box = QMessageBox(self._parent)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Deseja salvar o documento atual?")
        box.setInformativeText(
            f"As alterações em “{document_name}” serão perdidas se você não salvar."
        )
        save = box.addButton("Salvar", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Não salvar", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        # Fechar a caixa pelo Esc ou pelo X equivale a cancelar: nunca a
        # descartar o documento.
        box.setEscapeButton(cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save:
            return SaveChoice.SAVE
        if clicked is discard:
            return SaveChoice.DISCARD
        return SaveChoice.CANCEL

    def ask_save_path(self, suggested: Path) -> Path | None:
        dialog = QFileDialog(self._parent, "Salvar como", str(suggested))
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilter(TEXT_FILTER)
        # Extensão sugerida (§21): o Qt acrescenta .txt se o usuário não digitar
        # nenhuma, e já confirma a substituição de arquivos existentes.
        dialog.setDefaultSuffix("txt")
        dialog.selectFile(suggested.name)
        self._force_dark(dialog)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return None
        selected = dialog.selectedFiles()
        return Path(selected[0]) if selected else None

    def ask_open_path(self, start_dir: Path) -> Path | None:
        dialog = QFileDialog(self._parent, "Abrir", str(start_dir))
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter(TEXT_FILTER)
        self._force_dark(dialog)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return None
        selected = dialog.selectedFiles()
        return Path(selected[0]) if selected else None

    def show_error(self, title: str, message: str) -> None:
        box = QMessageBox(self._parent)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(message)
        box.exec()

    @staticmethod
    def _force_dark(dialog: QFileDialog) -> None:
        """Usa o diálogo do próprio Qt em vez do nativo do sistema.

        O seletor nativo do GTK ignora a folha de estilo e apareceria claro no
        meio da interface escura, contrariando a §7.
        """
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
