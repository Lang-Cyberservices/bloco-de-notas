"""§34.4 a §34.6, §34.8 e §34.11 — fluxos de `Novo`, `Salvar` e erro de escrita."""

from __future__ import annotations

import os
import stat

import pytest
from PySide6.QtGui import QTextCursor

from bloco_de_notas.models.document import DocumentStatus
from bloco_de_notas.services.dialogs import SaveChoice

from conftest import type_text


def test_novo_salvar_grava_e_cria_documento_vazio(qtbot, editor_app, paths, tmp_path):
    """§34.4"""
    dialogs = editor_app.dialogs
    destino = tmp_path / "salvo.txt"

    type_text(qtbot, editor_app, "conteudo a salvar")
    anterior = editor_app.service.document.id

    dialogs.save_choice = SaveChoice.SAVE
    dialogs.save_path = destino
    assert editor_app.service.new_document()

    assert destino.read_text(encoding="utf-8") == "conteudo a salvar"
    # §11.3: a recuperação some só depois do salvamento bem-sucedido.
    assert not (paths.recovery_dir / f"{anterior}.txt").exists()

    novo = editor_app.service.document
    assert novo.id != anterior
    assert novo.is_temporary
    assert editor_app.window.editor.toPlainText() == ""


def test_novo_nao_salvar_apaga_o_temporario(qtbot, editor_app, paths):
    """§34.5"""
    type_text(qtbot, editor_app, "sera descartado")
    editor_app.service.flush_recovery()
    anterior = editor_app.service.document.id
    assert (paths.recovery_dir / f"{anterior}.txt").exists()

    editor_app.dialogs.save_choice = SaveChoice.DISCARD
    assert editor_app.service.new_document()

    assert not (paths.recovery_dir / f"{anterior}.txt").exists()
    assert not (paths.recovery_dir / f"{anterior}.json").exists()
    assert editor_app.service.document.id != anterior
    assert editor_app.window.editor.toPlainText() == ""


def test_novo_cancelar_nao_muda_nada(qtbot, editor_app, paths):
    """§34.6"""
    type_text(qtbot, editor_app, "intocado")
    editor_app.service.flush_recovery()
    anterior = editor_app.service.document.id

    editor_app.dialogs.save_choice = SaveChoice.CANCEL
    assert editor_app.service.new_document() is False

    assert editor_app.service.document.id == anterior
    assert (paths.recovery_dir / f"{anterior}.txt").exists()
    assert editor_app.window.editor.toPlainText() == "intocado"


def test_cancelar_salvar_como_mantem_o_documento_aberto(qtbot, editor_app, paths):
    """§34.8 — o caso que mais facilmente perderia conteúdo."""
    type_text(qtbot, editor_app, "nao pode sumir")
    anterior = editor_app.service.document.id

    editor_app.dialogs.save_choice = SaveChoice.SAVE
    editor_app.dialogs.save_path = None  # usuário cancelou o seletor de arquivos

    assert editor_app.service.new_document() is False

    assert editor_app.service.document.id == anterior
    assert editor_app.window.editor.toPlainText() == "nao pode sumir"
    # A recuperação do documento atual continua íntegra.
    editor_app.service.flush_recovery()
    assert (paths.recovery_dir / f"{anterior}.txt").exists()


def test_documento_vazio_nao_pergunta(editor_app):
    """§16.4"""
    assert editor_app.service.new_document()
    assert editor_app.dialogs.questions == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora permissões de diretório")
def test_erro_de_escrita_preserva_texto_e_recuperacao(qtbot, editor_app, paths, tmp_path):
    """§34.11"""
    protegido = tmp_path / "somente-leitura"
    protegido.mkdir()

    type_text(qtbot, editor_app, "texto valioso")
    editor_app.service.flush_recovery()
    doc_id = editor_app.service.document.id
    recuperacao = paths.recovery_dir / f"{doc_id}.txt"
    assert recuperacao.exists()

    protegido.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x: sem permissão de escrita
    try:
        editor_app.dialogs.save_path = protegido / "impossivel.txt"
        assert editor_app.service.save_as() is False
    finally:
        protegido.chmod(stat.S_IRWXU)

    assert editor_app.window.editor.toPlainText() == "texto valioso"
    assert editor_app.service.status is DocumentStatus.SAVE_ERROR
    assert editor_app.dialogs.errors, "o usuário precisa ser informado"
    # A recuperação anterior continua válida e intocada.
    assert recuperacao.read_text(encoding="utf-8") == "texto valioso"
    # E o documento continua sendo o mesmo, editável.
    assert editor_app.service.document.id == doc_id


def test_salvar_associa_o_documento_ao_arquivo(qtbot, editor_app, tmp_path):
    """§20: documento temporário salvo passa a ter caminho e título próprios."""
    destino = tmp_path / "anotacoes.txt"
    editor_app.dialogs.save_path = destino

    type_text(qtbot, editor_app, "primeira linha")
    assert editor_app.service.save()

    documento = editor_app.service.document
    assert documento.file_path == destino
    assert not documento.is_temporary
    assert not documento.is_dirty_vs_file
    assert editor_app.service.status is DocumentStatus.SAVED
    assert editor_app.window.windowTitle() == "anotacoes.txt — Bloco de Notas"
    assert destino.read_text(encoding="utf-8") == "primeira linha"


def test_salvar_documento_com_arquivo_nao_abre_dialogo(qtbot, editor_app, tmp_path):
    destino = tmp_path / "direto.txt"
    destino.write_text("inicial", encoding="utf-8")
    editor_app.dialogs.open_path = destino
    assert editor_app.service.open_dialog()

    # Ao abrir, o cursor fica no início; escrever no fim exige movê-lo.
    editor_app.window.editor.moveCursor(QTextCursor.MoveOperation.End)
    type_text(qtbot, editor_app, " e mais")
    pedidos_antes = len(editor_app.dialogs.save_path_requests)
    assert editor_app.service.save()

    assert len(editor_app.dialogs.save_path_requests) == pedidos_antes
    assert destino.read_text(encoding="utf-8") == "inicial e mais"


def test_falha_ao_abrir_nao_substitui_o_documento_atual(qtbot, editor_app, tmp_path):
    """§19"""
    type_text(qtbot, editor_app, "documento atual")
    anterior = editor_app.service.document.id

    editor_app.dialogs.save_choice = SaveChoice.DISCARD
    assert editor_app.service.open_path(tmp_path / "inexistente.txt") is False

    assert editor_app.service.document.id == anterior
    assert editor_app.window.editor.toPlainText() == "documento atual"
    assert editor_app.dialogs.errors


def test_abrir_detecta_codificacoes(editor_app, tmp_path):
    """§19: UTF-8, UTF-8 com BOM e ISO-8859-1."""
    casos = {
        "utf8.txt": ("acentuação".encode("utf-8"), "UTF-8", "acentuação"),
        "bom.txt": ("acentuação".encode("utf-8-sig"), "UTF-8-BOM", "acentuação"),
        "latin1.txt": ("acentuação".encode("iso-8859-1"), "ISO-8859-1", "acentuação"),
    }
    for nome, (bytes_, esperado, texto) in casos.items():
        caminho = tmp_path / nome
        caminho.write_bytes(bytes_)
        editor_app.dialogs.open_path = caminho
        assert editor_app.service.open_dialog()
        assert editor_app.service.document.encoding == esperado
        assert editor_app.window.editor.toPlainText() == texto


def test_arquivo_da_linha_de_comando_inexistente_nao_e_criado(paths, dialogs, launch, tmp_path):
    """§30"""
    alvo = tmp_path / "ainda-nao-existe.txt"
    app = launch(paths, dialogs, file_path=alvo)

    assert not alvo.exists()
    documento = app.service.document
    assert documento.file_path == alvo
    assert documento.is_dirty_vs_file
    assert app.window.windowTitle().endswith("ainda-nao-existe.txt — Bloco de Notas")
