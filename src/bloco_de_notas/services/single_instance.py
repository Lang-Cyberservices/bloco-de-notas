"""Instância única por usuário (§31).

A primeira instância abre um socket local nomeado; as seguintes se conectam a
ele, entregam o caminho recebido na linha de comando e encerram. A chave
inclui o UID para que dois usuários no mesmo computador não disputem o mesmo
socket.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .. import APP_SLUG

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_MS = 300


def server_key() -> str:
    return f"{APP_SLUG}-{os.getuid()}"


class SingleInstance(QObject):
    #: caminho enviado por uma segunda instância (string vazia = só focar)
    message_received = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server: QLocalServer | None = None

    def send_to_existing(self, payload: str) -> bool:
        """Tenta entregar `payload` a uma instância já aberta.

        Devolve True se havia outra instância e a mensagem foi entregue — o
        processo atual deve então encerrar sem abrir janela.
        """
        socket = QLocalSocket()
        socket.connectToServer(server_key())
        if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
            return False

        socket.write(payload.encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        logger.info("Instância já em execução; caminho encaminhado")
        return True

    def listen(self) -> bool:
        """Passa a atender novas instâncias."""
        # Um socket órfão de um encerramento anormal impediria o listen();
        # removê-lo é seguro porque já sabemos que ninguém respondeu.
        QLocalServer.removeServer(server_key())
        self._server = QLocalServer(self)
        if not self._server.listen(server_key()):
            logger.warning(
                "Não foi possível abrir o socket de instância única: %s",
                self._server.errorString(),
            )
            return False
        self._server.newConnection.connect(self._on_new_connection)
        return True

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        socket = self._server.nextPendingConnection()
        if socket is None:
            return

        def read_payload() -> None:
            data = bytes(socket.readAll().data()).decode("utf-8", errors="replace")
            socket.deleteLater()
            self.message_received.emit(data.strip())

        socket.readyRead.connect(read_payload)
        socket.disconnected.connect(socket.deleteLater)
