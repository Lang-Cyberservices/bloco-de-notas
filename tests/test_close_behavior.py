"""§34.2, §34.3, §34.7 — fechar pelo `X`, sair pelo menu e fechar documento.

O ponto central destes testes é negativo: verificar que **nenhuma pergunta é
feita** ao encerrar o aplicativo, e que o conteúdo reaparece na execução
seguinte.
"""

from __future__ import annotations

from bloco_de_notas.services.dialogs import SaveChoice

from conftest import type_text


def test_fechar_pelo_x_nao_pergunta_e_restaura_na_proxima_execucao(
    qtbot, paths, dialogs, launch
):
    """§34.2"""
    primeira = launch(paths, dialogs)
    type_text(qtbot, primeira, "texto que nao pode sumir")
    doc_id = primeira.service.document.id

    # closeEvent é exatamente o que o gerenciador de janelas dispara no X.
    primeira.window.close()

    assert dialogs.questions == [], "fechar pelo X não pode perguntar nada"
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()

    segunda = launch(paths)
    assert segunda.window.editor.toPlainText() == "texto que nao pode sumir"
    assert segunda.service.document.id == doc_id


def test_sair_pelo_menu_tem_o_mesmo_comportamento_do_x(qtbot, paths, dialogs, launch):
    """§34.3 e §15: `Sair` não é descarte."""
    primeira = launch(paths, dialogs)
    type_text(qtbot, primeira, "conteudo do menu sair")
    doc_id = primeira.service.document.id

    primeira.window.action_quit.trigger()

    assert dialogs.questions == []
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()

    segunda = launch(paths)
    assert segunda.window.editor.toPlainText() == "conteudo do menu sair"


def test_fechar_preserva_recuperacao_de_documento_com_arquivo(
    qtbot, paths, dialogs, launch, tmp_path
):
    """§14: obrigatório também para documentos associados a arquivo."""
    alvo = tmp_path / "notas.txt"
    alvo.write_text("salvo em disco", encoding="utf-8")

    primeira = launch(paths, dialogs)
    dialogs.open_path = alvo
    assert primeira.service.open_dialog()
    type_text(qtbot, primeira, " mais texto nao salvo")
    doc_id = primeira.service.document.id

    primeira.window.close()

    assert dialogs.questions == []
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()
    # O arquivo do usuário não foi tocado; a alteração vive na recuperação.
    assert alvo.read_text(encoding="utf-8") == "salvo em disco"

    segunda = launch(paths)
    assert "mais texto nao salvo" in segunda.window.editor.toPlainText()
    assert segunda.service.document.is_dirty_vs_file


def test_fechar_documento_com_nao_salvar_apaga_a_recuperacao(qtbot, editor_app, paths):
    """§34.7"""
    dialogs = editor_app.dialogs
    type_text(qtbot, editor_app, "descartavel")
    editor_app.service.flush_recovery()

    doc_id = editor_app.service.document.id
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()

    dialogs.save_choice = SaveChoice.DISCARD
    assert editor_app.service.close_document()

    assert dialogs.questions, "fechar o documento deve perguntar"
    assert not (paths.recovery_dir / f"{doc_id}.txt").exists()
    assert not (paths.recovery_dir / f"{doc_id}.json").exists()

    # Continua com um documento novo e vazio, e o aplicativo segue aberto.
    novo = editor_app.service.document
    assert novo.id != doc_id
    assert novo.is_temporary
    assert editor_app.window.editor.toPlainText() == ""


def test_fechar_documento_cancelado_nao_altera_nada(qtbot, editor_app, paths):
    """§17.3"""
    type_text(qtbot, editor_app, "permanece")
    editor_app.service.flush_recovery()
    doc_id = editor_app.service.document.id

    editor_app.dialogs.save_choice = SaveChoice.CANCEL
    assert editor_app.service.close_document() is False

    assert editor_app.service.document.id == doc_id
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()
    assert editor_app.window.editor.toPlainText() == "permanece"


def test_encerrar_com_documento_vazio_nao_cria_recuperacao(paths, dialogs, launch):
    """Um documento vazio e intocado não deve sujar a pasta de recuperação."""
    app = launch(paths, dialogs)
    app.window.close()

    assert list(paths.recovery_dir.iterdir()) == []
    assert dialogs.questions == []
