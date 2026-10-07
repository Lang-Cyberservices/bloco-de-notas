"""Montagem do aplicativo: caminhos → serviços → janela.

Existe para que `main.py` fique só com argumentos e logs, e para que os testes
possam montar o aplicativo inteiro sobre um `AppPaths` descartável.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .paths import AppPaths
from .services.dialogs import DialogPort, QtDialogs
from .services.document_service import DocumentService
from .services.recovery_service import RecoveryService
from .services.session_service import SessionService
from .services.settings_service import SettingsService
from .ui import theme
from .ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def application_icon() -> QIcon:
    """Ícone da janela, com todos os tamanhos gerados por `scripts/gerar-icone.py`."""
    recursos = Path(__file__).resolve().parent / "resources"
    icone = QIcon()
    for arquivo in sorted(recursos.glob("bloco-de-notas*.png")):
        icone.addFile(str(arquivo))
    return icone


def apply_theme(app: QApplication) -> None:
    """Tema escuro em toda a interface; o aplicativo sempre inicia nele (§7)."""
    app.setStyle("Fusion")
    app.setPalette(theme.dark_palette())
    app.setStyleSheet(theme.load_stylesheet())
    icone = application_icon()
    if not icone.isNull():
        app.setWindowIcon(icone)


class EditorApplication:
    def __init__(self, paths: AppPaths, dialogs: DialogPort | None = None) -> None:
        paths.ensure_dirs()
        self.paths = paths
        self.settings = SettingsService(paths)
        self.recovery = RecoveryService(paths)
        self.session = SessionService(paths)
        self.dialogs = dialogs if dialogs is not None else QtDialogs()

        self.service = DocumentService(
            paths=paths,
            recovery=self.recovery,
            session=self.session,
            settings=self.settings,
            dialogs=self.dialogs,
        )
        self.window = MainWindow(self.service, self.settings)

        if isinstance(self.dialogs, QtDialogs):
            self.dialogs.set_parent(self.window)

    def start(self, file_path: Path | None = None) -> None:
        """Abre o arquivo pedido ou restaura a sessão anterior (§13, §30)."""
        if file_path is not None:
            self.service.open_cli_path(file_path)
        else:
            self.service.restore_session()
        self.window.show()

    def handle_second_instance(self, payload: str) -> None:
        """Uma segunda instância pediu para abrir algo (§31)."""
        window = self.window
        window.showNormal()
        window.raise_()
        window.activateWindow()
        if payload:
            # Abre em uma aba nova; os documentos já abertos não são tocados.
            self.service.open_cli_path(Path(payload))
