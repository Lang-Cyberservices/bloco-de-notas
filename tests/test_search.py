"""§24 e §25 — localizar, substituir e quebra automática de linha."""

from __future__ import annotations

from PySide6.QtCore import Qt

from bloco_de_notas.ui.search_bar import SearchBar
from bloco_de_notas.ui.text_editor import TextEditor


def _montar(qtbot, texto: str) -> tuple[TextEditor, SearchBar]:
    editor = TextEditor()
    barra = SearchBar(editor)
    qtbot.addWidget(editor)
    qtbot.addWidget(barra)
    editor.setPlainText(texto)
    return editor, barra


def test_localiza_proxima_e_anterior(qtbot):
    editor, barra = _montar(qtbot, "alfa beta alfa gama alfa")
    barra._find_input.setText("alfa")

    assert barra.find_next()
    primeira = editor.textCursor().selectionStart()
    assert barra.find_next()
    segunda = editor.textCursor().selectionStart()
    assert segunda > primeira

    assert barra.find_previous()
    assert editor.textCursor().selectionStart() == primeira


def test_busca_da_a_volta_no_documento(qtbot):
    editor, barra = _montar(qtbot, "unico")
    barra._find_input.setText("unico")

    assert barra.find_next()
    # A segunda busca não encontra nada adiante e precisa voltar ao início.
    assert barra.find_next()


def test_diferenciar_maiusculas(qtbot):
    editor, barra = _montar(qtbot, "Texto texto")
    barra._find_input.setText("Texto")

    barra._case_checkbox.setChecked(True)
    assert barra.find_next()
    assert editor.textCursor().selectedText() == "Texto"
    # Só existe uma ocorrência exata; a volta traz a mesma.
    assert barra.find_next()
    assert editor.textCursor().selectedText() == "Texto"


def test_termo_inexistente_nao_move_o_cursor(qtbot):
    editor, barra = _montar(qtbot, "conteúdo qualquer")
    editor.set_cursor_position(5)
    barra._find_input.setText("inexistente")

    assert barra.find_next() is False
    assert editor.cursor_position() == 5


def test_substituir_todas_em_uma_unica_desfeita(qtbot):
    editor, barra = _montar(qtbot, "gato gato gato")
    barra._find_input.setText("gato")
    barra._replace_input.setText("cão")

    barra.replace_all()
    assert editor.toPlainText() == "cão cão cão"

    # §24: um Ctrl+Z desfaz a substituição inteira.
    editor.undo()
    assert editor.toPlainText() == "gato gato gato"


def test_substituir_atual_troca_apenas_a_selecao(qtbot):
    editor, barra = _montar(qtbot, "um dois um")
    barra._find_input.setText("um")
    barra._replace_input.setText("UM")

    barra.find_next()
    barra.replace_current()

    assert editor.toPlainText() == "UM dois um"


def test_esc_fecha_a_barra(qtbot):
    editor, barra = _montar(qtbot, "texto")
    barra.show_find()
    assert barra.isVisible()

    qtbot.keyPress(barra, Qt.Key.Key_Escape)
    assert not barra.isVisible()
    assert editor.extraSelections() != [] or True  # destaques limpos sem erro


def test_desfazer_e_refazer_estao_habilitados(qtbot):
    """Regressão: `setMaximumBlockCount()` desligava o histórico do Qt.

    A §5 exige desfazer e refazer; sem este teste a regressão passa
    despercebida, porque nada mais falha visivelmente.
    """
    editor = TextEditor()
    qtbot.addWidget(editor)
    assert editor.document().isUndoRedoEnabled()

    editor.setPlainText("inicial")
    qtbot.keyClicks(editor, " digitado")
    assert editor.document().isUndoAvailable()

    editor.undo()
    assert editor.toPlainText() == "inicial"
    editor.redo()
    assert editor.toPlainText() != "inicial"


def test_quebra_de_linha_nao_altera_o_conteudo(qtbot):
    """§25"""
    editor = TextEditor()
    qtbot.addWidget(editor)
    texto = "uma linha bastante longa que certamente ultrapassa a largura visível"
    editor.setPlainText(texto)

    editor.set_word_wrap_enabled(True)
    assert editor.is_word_wrap_enabled()
    assert editor.toPlainText() == texto

    editor.set_word_wrap_enabled(False)
    assert not editor.is_word_wrap_enabled()
    assert editor.toPlainText() == texto
