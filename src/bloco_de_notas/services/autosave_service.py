"""Salvamento automático da recuperação (§10.1).

Dois temporizadores, um propósito:

* **debounce de 500 ms** — reiniciado a cada alteração, dispara quando o
  usuário para de digitar. É o caminho normal.
* **periódico de 5 s** — rede de segurança para quem digita sem parar; sem
  ele, uma escrita contínua adiaria o autosave indefinidamente.

Ambos chamam o mesmo `flush()`. O serviço nunca grava no arquivo do usuário —
apenas na recuperação (§10.3).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

DEBOUNCE_MS = 500
PERIODIC_MS = 5000


class AutosaveService(QObject):
    #: recuperação gravada com sucesso
    saved = Signal()
    #: falha ao gravar; carrega a mensagem para a barra de status
    failed = Signal(str)

    def __init__(self, flush_callback, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._flush_callback = flush_callback
        self._pending = False

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.flush)

        self._periodic = QTimer(self)
        self._periodic.setInterval(PERIODIC_MS)
        self._periodic.timeout.connect(self.flush)

    @property
    def has_pending_changes(self) -> bool:
        return self._pending

    def content_changed(self) -> None:
        """Chamado a cada alteração do texto; reinicia o debounce."""
        self._pending = True
        self._debounce.start()
        if not self._periodic.isActive():
            self._periodic.start()

    def flush(self) -> bool:
        """Grava a recuperação agora. Devolve True se gravou (ou nada havia)."""
        self._debounce.stop()
        if not self._pending:
            self._periodic.stop()
            return True

        try:
            self._flush_callback()
        except Exception as exc:  # noqa: BLE001 - a falha vira aviso, não crash
            # Falha de autosave nunca pode interromper a edição (§10.5).
            logger.error("Falha no autosave: %s", exc)
            self.failed.emit(str(exc))
            return False

        self._pending = False
        self._periodic.stop()
        self.saved.emit()
        return True

    def cancel_pending(self) -> None:
        """Descarta alterações pendentes (documento foi descartado ou trocado)."""
        self._pending = False
        self._debounce.stop()
        self._periodic.stop()
