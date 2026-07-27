"""§13 — restauração automática da última sessão."""

from __future__ import annotations

import json

from conftest import type_text


def test_restaura_cursor_rolagem_e_fonte(qtbot, paths, launch):
    """§13.7 a §13.10"""
    primeira = launch(paths)
    texto = "\n".join(f"linha {n}" for n in range(200))
    primeira.window.editor.setPlainText(texto)
    primeira.window.editor.set_cursor_position(500)
    primeira.window.editor.set_font_size(20)
    primeira.window.editor.set_word_wrap_enabled(True)
    primeira.window.editor.set_scroll_position(40)
    primeira.window.close()

    segunda = launch(paths)
    qtbot.wait(50)  # a rolagem é restaurada após o layout do texto

    assert segunda.window.editor.toPlainText() == texto
    assert segunda.window.editor.cursor_position() == 500
    assert segunda.window.editor.font_size == 20
    assert segunda.window.editor.is_word_wrap_enabled()
    assert segunda.window.editor.scroll_position() == 40


def test_restauracao_nao_pergunta_nada(qtbot, paths, dialogs, launch):
    """§13: a restauração é automática."""
    primeira = launch(paths, dialogs)
    type_text(qtbot, primeira, "conteudo")
    primeira.window.close()

    segunda_dialogs = launch(paths).dialogs
    assert segunda_dialogs.questions == []


def test_sem_sessao_abre_documento_temporario_vazio(paths, launch):
    app = launch(paths)
    assert app.service.document.is_temporary
    assert app.window.editor.toPlainText() == ""


def test_sessao_corrompida_nao_impede_a_abertura(paths, launch):
    paths.ensure_dirs()
    paths.session_file.write_text("{{{ corrompido", encoding="utf-8")

    app = launch(paths)
    assert app.service.document.is_temporary
    assert app.window.editor.toPlainText() == ""


def test_recuperacao_mais_recente_vence_o_arquivo(qtbot, paths, dialogs, launch, tmp_path):
    """§13.5"""
    alvo = tmp_path / "documento.txt"
    alvo.write_text("versão do arquivo", encoding="utf-8")

    primeira = launch(paths, dialogs)
    dialogs.open_path = alvo
    assert primeira.service.open_dialog()
    primeira.window.editor.setPlainText("versão da recuperação, mais nova")
    primeira.window.close()

    segunda = launch(paths)
    assert segunda.window.editor.toPlainText() == "versão da recuperação, mais nova"
    assert segunda.service.document.is_dirty_vs_file
    assert segunda.service.document.file_path == alvo


def test_arquivo_alterado_por_fora_vence_recuperacao_antiga(
    qtbot, paths, dialogs, launch, tmp_path
):
    """O inverso da §13.5: outro programa gravou depois do último autosave."""
    import os
    import time

    alvo = tmp_path / "compartilhado.txt"
    alvo.write_text("conteúdo inicial", encoding="utf-8")

    primeira = launch(paths, dialogs)
    dialogs.open_path = alvo
    assert primeira.service.open_dialog()
    primeira.window.editor.setPlainText("edição no editor")
    primeira.window.close()

    # Outro programa grava depois: mtime mais novo que a recuperação.
    time.sleep(0.01)
    alvo.write_text("gravado por outro programa", encoding="utf-8")
    futuro = time.time() + 60
    os.utime(alvo, (futuro, futuro))

    segunda = launch(paths)
    assert segunda.window.editor.toPlainText() == "gravado por outro programa"


def test_sessao_aponta_para_o_documento_atual(qtbot, editor_app, paths):
    type_text(qtbot, editor_app, "texto")
    editor_app.service.flush_recovery()

    sessao = json.loads(paths.session_file.read_text(encoding="utf-8"))
    assert sessao["document_id"] == editor_app.service.document.id
    assert sessao["original_path"] is None
