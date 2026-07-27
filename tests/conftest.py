"""Infraestrutura comum dos testes.

Duas peças fazem a suíte inteira funcionar sem interface gráfica e sem tocar
nos dados reais do usuário:

* `paths` — aponta o aplicativo para um diretório descartável;
* `FakeDialogs` — responde às perguntas no lugar do usuário e **registra o que
  foi perguntado**, o que permite afirmar que fechar pelo `X` não pergunta nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Precisa valer antes de qualquer import do Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bloco_de_notas.application import EditorApplication  # noqa: E402
from bloco_de_notas.paths import AppPaths  # noqa: E402
from bloco_de_notas.services.dialogs import SaveChoice  # noqa: E402


class FakeDialogs:
    """Substituto programável do `DialogPort`."""

    def __init__(self) -> None:
        #: resposta devolvida em "Deseja salvar o documento atual?"
        self.save_choice = SaveChoice.CANCEL
        #: caminho devolvido pelo "Salvar como"; None simula cancelar o diálogo
        self.save_path: Path | None = None
        #: caminho devolvido pelo "Abrir"
        self.open_path: Path | None = None

        self.questions: list[str] = []
        self.save_path_requests: list[Path] = []
        self.open_requests: list[Path] = []
        self.errors: list[tuple[str, str]] = []

    def ask_save_discard_cancel(self, document_name: str) -> SaveChoice:
        self.questions.append(document_name)
        return self.save_choice

    def ask_save_path(self, suggested: Path) -> Path | None:
        self.save_path_requests.append(suggested)
        return self.save_path

    def ask_open_path(self, start_dir: Path) -> Path | None:
        self.open_requests.append(start_dir)
        return self.open_path

    def show_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))

    @property
    def asked_anything(self) -> bool:
        return bool(self.questions)


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths.for_base(tmp_path)


@pytest.fixture
def dialogs() -> FakeDialogs:
    return FakeDialogs()


@pytest.fixture
def launch(qapp, qtbot):
    """Abre o aplicativo. Chamar de novo com os mesmos `paths` simula reiniciá-lo."""
    created: list[EditorApplication] = []

    def _launch(
        paths: AppPaths,
        dialogs: FakeDialogs | None = None,
        file_path: Path | None = None,
    ) -> EditorApplication:
        editor = EditorApplication(paths, dialogs=dialogs or FakeDialogs())
        qtbot.addWidget(editor.window)
        editor.start(file_path)
        created.append(editor)
        return editor

    yield _launch

    for editor in created:
        # Impede que temporizadores de autosave sobrevivam ao teste.
        editor.service.autosave.cancel_pending()


@pytest.fixture
def editor_app(paths, dialogs, launch) -> EditorApplication:
    return launch(paths, dialogs)


def type_text(qtbot, editor_app: EditorApplication, text: str) -> None:
    """Escreve no editor como o usuário faria, disparando os sinais reais."""
    editor_app.window.editor.setFocus()
    qtbot.keyClicks(editor_app.window.editor, text)
