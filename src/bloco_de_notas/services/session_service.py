"""Persistência de `session.json` — qual era o último documento aberto (§13)."""

from __future__ import annotations

import json
import logging

from ..models.document import DEFAULT_ENCODING
from ..models.session import SessionState
from ..paths import AppPaths
from .atomic_io import WriteError, write_atomic

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def load(self) -> SessionState:
        path = self._paths.session_file
        if not path.exists():
            return SessionState()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Sessão corrompida não pode impedir o aplicativo de abrir; a
            # recuperação em si continua intacta no disco.
            logger.warning("session.json ilegível; iniciando sem sessão anterior")
            return SessionState()
        if not isinstance(data, dict):
            return SessionState()
        return SessionState.from_dict(data)

    def save(self, state: SessionState) -> None:
        self._paths.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            write_atomic(
                self._paths.session_file,
                json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
                DEFAULT_ENCODING,
            )
        except WriteError:
            logger.warning("Não foi possível atualizar session.json")

    def clear(self) -> None:
        self.save(SessionState())
