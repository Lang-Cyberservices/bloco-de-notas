"""Teste de fumaça do AppImage, executado dentro do container da distro alvo.

Não basta o aplicativo importar: este script exercita o ciclo que define o
produto — digitar, autosave, fechar, reabrir e encontrar o conteúdo de volta.
Se qualquer biblioteca do Qt faltar naquela distribuição, ele falha aqui em vez
de falhar na máquina do usuário.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6 import __version__ as pyside_versao  # noqa: E402
from PySide6.QtCore import QLibraryInfo, qVersion  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from bloco_de_notas.application import EditorApplication, apply_theme  # noqa: E402
from bloco_de_notas.paths import AppPaths  # noqa: E402

TEXTO = "conteúdo com acentuação — çãõ — que precisa sobreviver"


def principal() -> int:
    app = QApplication(sys.argv[:1])
    apply_theme(app)

    print(f"  Python   {sys.version.split()[0]}")
    print(f"  PySide6  {pyside_versao} (Qt {qVersion()})")
    print(f"  plugins  {QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)}")

    base = Path(tempfile.mkdtemp(prefix="smoke-"))
    caminhos = AppPaths.for_base(base)

    primeira = EditorApplication(caminhos)
    primeira.start()
    primeira.window.editor.setPlainText(TEXTO)
    primeira.window.editor.set_cursor_position(10)
    doc_id = primeira.service.document.id
    primeira.window.close()  # equivale a fechar pelo X

    recuperacao = caminhos.recovery_dir / f"{doc_id}.txt"
    if not recuperacao.exists():
        print("  FALHA: a recuperação não foi gravada")
        return 1

    segunda = EditorApplication(caminhos)
    segunda.start()
    restaurado = segunda.window.editor.toPlainText()
    if restaurado != TEXTO:
        print(f"  FALHA: restaurou {restaurado!r}")
        return 1
    if segunda.window.editor.cursor_position() != 10:
        print("  FALHA: cursor não restaurado")
        return 1

    # Salvamento definitivo em disco, com escrita atômica.
    destino = base / "salvo.txt"
    segunda.service.dialogs = None  # não deve haver diálogo neste caminho
    documento = segunda.service.document
    documento.file_path = destino
    if not segunda.service.save():
        print("  FALHA: não conseguiu salvar")
        return 1
    if destino.read_text(encoding="utf-8") != TEXTO:
        print("  FALHA: conteúdo salvo diverge")
        return 1

    segunda.window.close()
    print("  OK: digitar, autosave, fechar, restaurar e salvar funcionaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
