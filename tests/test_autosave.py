"""§34.1 — autosave do documento temporário."""

from __future__ import annotations

from bloco_de_notas.models.document import DocumentStatus

from conftest import type_text


def test_autosave_cria_recuperacao_do_documento_temporario(qtbot, editor_app, paths):
    """Digitar e esperar deve produzir a recuperação, sem nenhuma ação do usuário."""
    service = editor_app.service
    documento = service.document

    assert documento.is_temporary
    assert not paths.recovery_dir.joinpath(f"{documento.id}.txt").exists()

    type_text(qtbot, editor_app, "conteudo automatico")

    # Espera o debounce real de 500 ms disparar sozinho.
    with qtbot.waitSignal(service.autosave.saved, timeout=3000):
        pass

    recuperacao = paths.recovery_dir / f"{documento.id}.txt"
    assert recuperacao.exists()
    assert recuperacao.read_text(encoding="utf-8") == "conteudo automatico"
    assert service.status is DocumentStatus.SAVED_TEMPORARILY


def test_autosave_grava_metadados_no_formato_da_especificacao(qtbot, editor_app, paths):
    import json

    type_text(qtbot, editor_app, "texto")
    editor_app.service.flush_recovery()

    documento = editor_app.service.document
    metadados = json.loads(
        (paths.recovery_dir / f"{documento.id}.json").read_text(encoding="utf-8")
    )

    assert metadados["id"] == documento.id
    assert metadados["temporary"] is True
    assert metadados["original_path"] is None
    assert metadados["encoding"] == "UTF-8"
    assert metadados["cursor_position"] == len("texto")
    # created_at/updated_at precisam ser ISO-8601 com fuso, como na §12.
    assert "T" in metadados["created_at"]
    assert metadados["updated_at"] >= metadados["created_at"]


def test_autosave_nao_grava_no_arquivo_original(qtbot, editor_app, tmp_path):
    """Decisão da §10.3: o autosave só toca a recuperação, nunca o arquivo."""
    alvo = tmp_path / "documento.txt"
    alvo.write_text("original", encoding="utf-8")

    editor_app.dialogs.open_path = alvo
    assert editor_app.service.open_dialog()

    type_text(qtbot, editor_app, " alterado")
    editor_app.service.flush_recovery()

    assert alvo.read_text(encoding="utf-8") == "original"
    assert editor_app.service.document.is_dirty_vs_file


def test_marcador_de_titulo_some_apos_o_autosave(qtbot, editor_app):
    """§22: o ● indica conteúdo que não está nem na recuperação."""
    type_text(qtbot, editor_app, "abc")
    editor_app.window._update_title()
    assert editor_app.window.windowTitle().startswith("●")

    editor_app.service.flush_recovery()
    editor_app.window._update_title()
    assert not editor_app.window.windowTitle().startswith("●")
