"""Abas: vários documentos abertos ao mesmo tempo.

`Novo` e `Abrir` acrescentam abas e nunca perguntam nada; um documento só é
fechado quando o usuário fecha a aba dele.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabBar

from bloco_de_notas.services.dialogs import SaveChoice

from conftest import type_text


def _textos(app) -> list[str]:
    return [app.window.tabs.widget(i).toPlainText() for i in range(app.window.tabs.count())]


def _fechar_pelo_x(app, index: int) -> None:
    botao = app.window.tabs.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
    botao.click()


def test_novo_cria_aba_e_mantem_o_documento_anterior(qtbot, editor_app, paths):
    type_text(qtbot, editor_app, "primeiro")
    primeiro = editor_app.service.document.id

    editor_app.window.action_new.trigger()

    assert editor_app.dialogs.questions == [], "Novo não pode perguntar nada"
    assert editor_app.window.tabs.count() == 2
    assert editor_app.service.document.id != primeiro
    assert editor_app.window.editor.toPlainText() == ""
    assert _textos(editor_app) == ["primeiro", ""]

    type_text(qtbot, editor_app, "segundo")
    assert _textos(editor_app) == ["primeiro", "segundo"]


def test_abrir_cria_aba_e_nao_duplica_arquivo_ja_aberto(qtbot, editor_app, tmp_path):
    type_text(qtbot, editor_app, "rascunho")
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("arquivo a", encoding="utf-8")
    b.write_text("arquivo b", encoding="utf-8")

    assert editor_app.service.open_path(a)
    assert editor_app.service.open_path(b)
    assert _textos(editor_app) == ["rascunho", "arquivo a", "arquivo b"]
    assert editor_app.window.tabs.tabText(1) == "a.txt"

    # Abrir de novo só leva o foco para a aba existente.
    assert editor_app.service.open_path(a)
    assert editor_app.window.tabs.count() == 3
    assert editor_app.window.tabs.currentIndex() == 1
    assert editor_app.dialogs.questions == []


def test_abrir_reaproveita_aba_vazia_intocada(editor_app, tmp_path):
    alvo = tmp_path / "notas.txt"
    alvo.write_text("conteudo", encoding="utf-8")

    assert editor_app.service.open_path(alvo)

    assert editor_app.window.tabs.count() == 1
    assert editor_app.window.editor.toPlainText() == "conteudo"


def test_x_da_aba_fecha_so_aquela_aba(qtbot, editor_app, paths):
    ids = []
    for texto in ("um", "dois", "tres"):
        if ids:
            editor_app.service.new_document()
        type_text(qtbot, editor_app, texto)
        editor_app.service.flush_recovery()
        ids.append(editor_app.service.document.id)

    editor_app.dialogs.save_choice = SaveChoice.DISCARD
    _fechar_pelo_x(editor_app, 1)

    assert editor_app.dialogs.questions == ["Sem título"]
    assert _textos(editor_app) == ["um", "tres"]
    assert not (paths.recovery_dir / f"{ids[1]}.txt").exists()
    assert (paths.recovery_dir / f"{ids[0]}.txt").exists()
    assert (paths.recovery_dir / f"{ids[2]}.txt").exists()


def test_x_da_aba_cancelado_nao_fecha_nada(qtbot, editor_app):
    type_text(qtbot, editor_app, "um")
    editor_app.service.new_document()
    type_text(qtbot, editor_app, "dois")

    editor_app.dialogs.save_choice = SaveChoice.CANCEL
    _fechar_pelo_x(editor_app, 0)

    assert _textos(editor_app) == ["um", "dois"]
    # A aba sobre a qual a pergunta foi feita fica à vista.
    assert editor_app.window.tabs.currentIndex() == 0


def test_fechar_aba_vazia_em_segundo_plano_nao_troca_a_aba_ativa(qtbot, editor_app):
    type_text(qtbot, editor_app, "um")
    editor_app.service.new_document()
    editor_app.window.tabs.setCurrentIndex(0)

    _fechar_pelo_x(editor_app, 1)

    assert editor_app.dialogs.questions == []
    assert _textos(editor_app) == ["um"]
    assert editor_app.window.editor.toPlainText() == "um"


def test_fechar_a_ultima_aba_deixa_uma_vazia(qtbot, editor_app):
    type_text(qtbot, editor_app, "unico")
    editor_app.dialogs.save_choice = SaveChoice.DISCARD

    editor_app.window.action_close_doc.trigger()

    assert _textos(editor_app) == [""]
    assert editor_app.service.document.is_temporary


def test_trocar_de_aba_antes_do_autosave_grava_o_documento_certo(qtbot, editor_app, paths):
    type_text(qtbot, editor_app, "texto da aba A")
    id_a = editor_app.service.document.id
    editor_app.service.new_document()
    type_text(qtbot, editor_app, "texto da aba B")
    id_b = editor_app.service.document.id

    qtbot.waitUntil(
        lambda: (paths.recovery_dir / f"{id_a}.txt").exists()
        and (paths.recovery_dir / f"{id_b}.txt").exists(),
        timeout=3000,
    )

    assert (paths.recovery_dir / f"{id_a}.txt").read_text(encoding="utf-8") == "texto da aba A"
    assert (paths.recovery_dir / f"{id_b}.txt").read_text(encoding="utf-8") == "texto da aba B"


def test_fechar_a_janela_restaura_todas_as_abas(qtbot, paths, dialogs, launch, tmp_path):
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("do disco", encoding="utf-8")
    longo = "\n".join(f"linha {n}" for n in range(300))

    primeira = launch(paths, dialogs)
    primeira.window.show()
    primeira.window.editor.setPlainText(longo)
    primeira.window.editor.set_cursor_position(700)
    primeira.window.editor.set_scroll_position(60)
    assert primeira.service.open_path(arquivo)
    primeira.service.new_document()
    type_text(qtbot, primeira, "rascunho")
    primeira.window.tabs.setCurrentIndex(1)

    primeira.window.close()
    assert dialogs.questions == [], "fechar a janela não pode perguntar nada"

    segunda = launch(paths)
    assert _textos(segunda) == [longo, "do disco", "rascunho"]
    assert segunda.window.tabs.currentIndex() == 1
    assert segunda.service.document.file_path == arquivo
    assert [segunda.window.tabs.tabText(i) for i in range(3)] == [
        "Sem título",
        "arquivo.txt",
        "Sem título",
    ]

    # A primeira aba nunca foi visitada nesta execução: fechar de novo não
    # pode zerar a posição que ela tinha.
    segunda.window.close()
    terceira = launch(paths)
    terceira.window.tabs.setCurrentIndex(0)
    qtbot.wait(50)  # a rolagem é restaurada após o layout do texto
    assert terceira.window.editor.cursor_position() == 700
    assert terceira.window.editor.scroll_position() == 60


def test_ordem_das_abas_arrastadas_e_preservada(qtbot, paths, launch):
    primeira = launch(paths)
    type_text(qtbot, primeira, "um")
    primeira.service.new_document()
    type_text(qtbot, primeira, "dois")

    primeira.window.tabs.tabBar().moveTab(1, 0)
    assert _textos(primeira) == ["dois", "um"]
    primeira.window.close()

    assert _textos(launch(paths)) == ["dois", "um"]


def test_sessao_no_formato_antigo_vira_uma_aba(qtbot, paths, launch):
    primeira = launch(paths)
    type_text(qtbot, primeira, "da versao anterior")
    doc_id = primeira.service.document.id
    primeira.window.close()

    # session.json como a versão 0.1.0 gravava: um documento, sem `tabs`.
    paths.session_file.write_text(
        json.dumps(
            {
                "document_id": doc_id,
                "original_path": None,
                "cursor_position": 3,
                "scroll_position": 0,
            }
        ),
        encoding="utf-8",
    )

    segunda = launch(paths)
    assert _textos(segunda) == ["da versao anterior"]
    assert segunda.service.document.id == doc_id


def test_desfazer_e_independente_por_aba(qtbot, editor_app):
    window = editor_app.window
    type_text(qtbot, editor_app, "aba um")
    editor_app.service.new_document()

    assert not window.action_undo.isEnabled()
    type_text(qtbot, editor_app, "aba dois")
    assert window.action_undo.isEnabled()

    window.action_undo.trigger()
    assert _textos(editor_app) == ["aba um", ""]

    window.tabs.setCurrentIndex(0)
    assert window.action_undo.isEnabled()
    assert not window.action_redo.isEnabled()


def test_fonte_e_quebra_de_linha_valem_para_todas_as_abas(qtbot, editor_app):
    window = editor_app.window
    editor_app.service.new_document()

    window.action_zoom_in.trigger()
    window.action_wrap.setChecked(True)
    editor_app.service.new_document()

    editores = [window.tabs.widget(i) for i in range(window.tabs.count())]
    assert len(editores) == 3
    assert {e.font_size for e in editores} == {editores[0].font_size}
    assert editores[0].font_size == editor_app.settings.font_size
    assert all(e.is_word_wrap_enabled() for e in editores)


def test_ctrl_tab_alterna_entre_as_abas(qtbot, editor_app):
    window = editor_app.window
    window.show()
    qtbot.waitExposed(window)
    editor_app.service.new_document()
    editor_app.service.new_document()
    assert window.tabs.currentIndex() == 2

    qtbot.keyClick(window.editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert window.tabs.currentIndex() == 0
    window.action_previous_tab.trigger()
    assert window.tabs.currentIndex() == 2


def test_busca_acompanha_a_aba_ativa(qtbot, editor_app):
    window = editor_app.window
    window.editor.setPlainText("alvo aqui")
    editor_app.service.new_document()
    window.editor.setPlainText("outro alvo, mais um alvo")

    window.search_bar.show_find()
    window.search_bar._find_input.setText("alvo")
    assert len(window.editor.extraSelections()) >= 2

    window.tabs.setCurrentIndex(0)
    assert window.search_bar.find_next()
    assert window.editor.textCursor().selectedText() == "alvo"
    # Os destaques da aba que ficou para trás foram limpos.
    assert window.tabs.widget(1)._search_selections == []
