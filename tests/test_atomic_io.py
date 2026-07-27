"""§10.4 — escrita atômica e leitura com detecção de codificação."""

from __future__ import annotations

import os
import stat

import pytest

from bloco_de_notas.services.atomic_io import (
    ReadError,
    WriteError,
    read_text_detect,
    write_atomic,
)


def test_grava_e_le_utf8(tmp_path):
    destino = tmp_path / "a.txt"
    write_atomic(destino, "conteúdo com acento")
    assert destino.read_text(encoding="utf-8") == "conteúdo com acento"
    assert read_text_detect(destino) == ("conteúdo com acento", "UTF-8")


def test_detecta_bom_e_latin1(tmp_path):
    com_bom = tmp_path / "bom.txt"
    com_bom.write_bytes("olá".encode("utf-8-sig"))
    assert read_text_detect(com_bom) == ("olá", "UTF-8-BOM")

    latin = tmp_path / "latin.txt"
    latin.write_bytes("olá".encode("iso-8859-1"))
    assert read_text_detect(latin) == ("olá", "ISO-8859-1")


def test_ler_arquivo_inexistente_levanta_read_error(tmp_path):
    with pytest.raises(ReadError):
        read_text_detect(tmp_path / "nao-existe.txt")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora permissões de diretório")
def test_falha_de_escrita_preserva_o_arquivo_original(tmp_path):
    """A garantia central da §10.4: nunca deixar o destino truncado."""
    protegido = tmp_path / "dir"
    protegido.mkdir()
    alvo = protegido / "importante.txt"
    alvo.write_text("conteúdo original", encoding="utf-8")

    protegido.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(WriteError):
            write_atomic(alvo, "texto novo que não vai entrar")
    finally:
        protegido.chmod(stat.S_IRWXU)

    assert alvo.read_text(encoding="utf-8") == "conteúdo original"


def test_sobrescrita_bem_sucedida_substitui_todo_o_conteudo(tmp_path):
    alvo = tmp_path / "b.txt"
    write_atomic(alvo, "texto longo original")
    write_atomic(alvo, "curto")
    assert alvo.read_text(encoding="utf-8") == "curto"
