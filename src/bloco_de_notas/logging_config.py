"""Configuração dos logs (§32).

Registra ciclo de vida, aberturas, salvamentos, autosaves, recuperações e
erros — **nunca o conteúdo dos documentos**. As mensagens do restante do
código seguem essa regra registrando tamanhos e caminhos, jamais texto.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import AppPaths

MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(paths: AppPaths, *, verbose: bool = False) -> None:
    paths.state_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    formatter = logging.Formatter(FORMAT)

    try:
        file_handler = RotatingFileHandler(
            paths.log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # Sem log em disco o editor continua funcionando normalmente.
        pass

    if verbose:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)
