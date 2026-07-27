"""Ponto de entrada: argumentos, logs e ciclo de vida do Qt."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import APP_NAME, APP_ORG, APP_SLUG, __version__
from .application import EditorApplication, apply_theme
from .logging_config import setup_logging
from .paths import AppPaths
from .services.single_instance import SingleInstance

logger = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_SLUG,
        description=f"{APP_NAME} — editor de texto simples.",
    )
    parser.add_argument(
        "arquivo",
        nargs="?",
        help="arquivo a abrir; se não existir, o documento é associado ao caminho",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--verbose", action="store_true", help="também escreve os logs no terminal"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    paths = AppPaths.default()
    paths.ensure_dirs()
    setup_logging(paths, verbose=args.verbose)

    requested = Path(args.arquivo).expanduser().resolve() if args.arquivo else None

    # Antes de montar qualquer janela: se já existe uma instância, entrega o
    # caminho a ela e encerra (§31).
    instance = SingleInstance()
    if instance.send_to_existing(str(requested) if requested else ""):
        return 0

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setDesktopFileName(APP_SLUG)
    apply_theme(app)

    logger.info("%s %s iniciado", APP_NAME, __version__)

    editor = EditorApplication(paths)
    instance.listen()
    instance.message_received.connect(editor.handle_second_instance)
    editor.start(requested)

    code = app.exec()
    logger.info("%s encerrado (código %d)", APP_NAME, code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
