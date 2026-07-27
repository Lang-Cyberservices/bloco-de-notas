"""§34.9 — recuperação sem prazo de validade.

A §11 é categórica: recuperações não expiram. Este arquivo existe para que
qualquer tentativa futura de adicionar "limpeza automática" quebre um teste.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from bloco_de_notas.models.document import Document
from bloco_de_notas.services.recovery_service import RecoveryService


def _criar_recuperacao_antiga(paths, anos: int = 3) -> str:
    """Escreve uma recuperação com datas e mtime de anos atrás."""
    paths.ensure_dirs()
    servico = RecoveryService(paths)
    documento = Document.create_temporary(paths.recovery_dir)
    servico.save(documento, "anotação muito antiga")

    antiga = datetime.now().astimezone() - timedelta(days=365 * anos)
    meta_path = paths.recovery_dir / f"{documento.id}.json"
    metadados = json.loads(meta_path.read_text(encoding="utf-8"))
    metadados["created_at"] = antiga.isoformat()
    metadados["updated_at"] = antiga.isoformat()
    meta_path.write_text(json.dumps(metadados), encoding="utf-8")

    epoch = antiga.timestamp()
    for caminho in (paths.recovery_dir / f"{documento.id}.txt", meta_path):
        os.utime(caminho, (epoch, epoch))

    return documento.id


def test_recuperacao_antiga_continua_disponivel(paths, launch):
    """§34.9"""
    doc_id = _criar_recuperacao_antiga(paths, anos=3)
    paths.session_file.write_text(
        json.dumps({"document_id": doc_id}), encoding="utf-8"
    )

    app = launch(paths)

    assert app.window.editor.toPlainText() == "anotação muito antiga"
    assert app.service.document.id == doc_id
    # Nada foi apagado ao iniciar.
    assert (paths.recovery_dir / f"{doc_id}.txt").exists()
    assert (paths.recovery_dir / f"{doc_id}.json").exists()


def test_iniciar_o_aplicativo_nao_remove_recuperacoes_orfas(paths, launch):
    """Recuperações de documentos antigos sobrevivem a novas execuções."""
    orfa = _criar_recuperacao_antiga(paths, anos=5)

    launch(paths).window.close()
    launch(paths).window.close()

    assert (paths.recovery_dir / f"{orfa}.txt").exists()


def test_recuperacao_so_e_apagada_quando_pedido(paths):
    servico = RecoveryService(paths)
    paths.ensure_dirs()
    documento = Document.create_temporary(paths.recovery_dir)
    servico.save(documento, "conteúdo")

    assert servico.exists(documento.id)
    servico.delete(documento.id)
    assert not servico.exists(documento.id)


def test_metadados_ilegiveis_nao_impedem_a_recuperacao(paths):
    """Perder os metadados custa a posição do cursor, nunca o texto."""
    servico = RecoveryService(paths)
    paths.ensure_dirs()
    documento = Document.create_temporary(paths.recovery_dir)
    servico.save(documento, "texto preservado")
    (paths.recovery_dir / f"{documento.id}.json").write_text("{ isso não é json",
                                                             encoding="utf-8")

    registro = servico.load(documento.id)
    assert registro is not None
    assert registro.content == "texto preservado"
