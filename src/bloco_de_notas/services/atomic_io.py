"""Leitura e escrita de arquivos de texto.

Toda gravação do aplicativo passa por aqui e usa `QSaveFile` (§10.4): o texto
vai para um arquivo auxiliar e só substitui o destino se a escrita inteira
tiver dado certo. Uma falha no meio do caminho nunca deixa o arquivo original
truncado.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QIODevice, QSaveFile

from ..models.document import (
    DEFAULT_ENCODING,
    ENCODING_LATIN1,
    ENCODING_UTF8_BOM,
)

#: Rótulo de codificação → codec do Python.
_CODECS = {
    DEFAULT_ENCODING: "utf-8",
    ENCODING_UTF8_BOM: "utf-8-sig",
    ENCODING_LATIN1: "iso-8859-1",
}


class WriteError(Exception):
    """Falha ao gravar. Quem chama decide o que fazer — nunca perder texto."""


class ReadError(Exception):
    """Falha ao ler um arquivo escolhido pelo usuário."""


def write_atomic(path: Path, text: str, encoding: str = DEFAULT_ENCODING) -> None:
    """Grava `text` em `path` de forma atômica.

    Levanta `WriteError` com a mensagem do Qt se qualquer etapa falhar; nesse
    caso o arquivo de destino permanece exatamente como estava.
    """
    path = Path(path)
    codec = _CODECS.get(encoding, "utf-8")
    try:
        data = text.encode(codec, errors="strict")
    except UnicodeEncodeError as exc:  # pragma: no cover - só com codec exótico
        raise WriteError(f"Não foi possível codificar o texto em {encoding}.") from exc

    saver = QSaveFile(str(path))
    if not saver.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Truncate):
        raise WriteError(_describe(path, saver.errorString()))

    written = saver.write(data)
    if written != len(data):
        saver.cancelWriting()
        raise WriteError(_describe(path, saver.errorString() or "escrita incompleta"))

    # commit() faz o flush e a substituição atômica; só depois dele o
    # conteúdo novo existe no destino.
    if not saver.commit():
        raise WriteError(_describe(path, saver.errorString()))


def read_text_detect(path: Path) -> tuple[str, str]:
    """Lê um arquivo tentando as codificações da §19.

    Devolve `(texto, rótulo_da_codificação)`. ISO-8859-1 é o último recurso e
    nunca falha, então um arquivo binário vira texto ilegível em vez de erro —
    preferível a recusar-se a abrir um arquivo que o usuário pediu.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReadError(_describe(path, exc.strerror or str(exc))) from exc

    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace"), ENCODING_UTF8_BOM

    try:
        return raw.decode("utf-8"), DEFAULT_ENCODING
    except UnicodeDecodeError:
        return raw.decode("iso-8859-1"), ENCODING_LATIN1


def _describe(path: Path, message: str) -> str:
    return f"{path}: {message}"
