"""§34.10 — numeração das linhas."""

from __future__ import annotations

from bloco_de_notas.ui.text_editor import TextEditor


def test_numeracao_acompanha_insercao_e_remocao_de_linhas(qtbot):
    editor = TextEditor()
    qtbot.addWidget(editor)

    editor.setPlainText("um\ndois\ntrês")
    assert editor.blockCount() == 3
    largura_inicial = editor.line_number_area_width()

    editor.setPlainText("\n".join(str(n) for n in range(150)))
    assert editor.blockCount() == 150
    # Três dígitos exigem uma coluna mais larga (§6).
    assert editor.line_number_area_width() > largura_inicial

    editor.setPlainText("uma linha só")
    assert editor.blockCount() == 1
    assert editor.line_number_area_width() == largura_inicial


def test_numeros_nao_fazem_parte_do_conteudo(qtbot, editor_app, tmp_path):
    """§34.10: o arquivo salvo não pode conter os números."""
    destino = tmp_path / "numerado.txt"
    editor_app.dialogs.save_path = destino

    texto = "primeira linha\nsegunda linha\n\nquarta linha"
    editor_app.window.editor.setPlainText(texto)
    assert editor_app.service.save()

    salvo = destino.read_text(encoding="utf-8")
    assert salvo == texto
    for numero in ("1 ", "2 ", "3 ", "4 "):
        assert not salvo.startswith(numero)


def test_numeros_nao_entram_na_selecao_nem_na_copia(qtbot):
    editor = TextEditor()
    qtbot.addWidget(editor)
    editor.setPlainText("alfa\nbeta")

    editor.selectAll()
    assert editor.textCursor().selectedText().replace(" ", "\n") == "alfa\nbeta"


def test_coluna_de_numeros_nao_recebe_foco(qtbot):
    """Não é selecionável: o widget da coluna nunca toma o foco do editor."""
    from PySide6.QtCore import Qt

    from bloco_de_notas.ui.line_number_area import LineNumberArea

    editor = TextEditor()
    qtbot.addWidget(editor)

    coluna = editor.findChild(LineNumberArea)
    assert coluna is not None
    assert coluna.focusPolicy() == Qt.FocusPolicy.NoFocus
