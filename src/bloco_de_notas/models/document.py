"""Modelo do documento em edição (§29).

Um documento é temporário (ainda sem arquivo escolhido pelo usuário) ou está
associado a um arquivo. Em ambos os casos ele tem uma recuperação própria —
mesmo documentos com arquivo mantêm recuperação enquanto são editados (§9.2).

Sobre `content`: o texto vivo mora no editor, não aqui. Este campo guarda a
última versão *materializada* (ao abrir e a cada autosave). Marcar alteração
é um booleano barato em vez de um hash do documento inteiro, para que digitar
em um arquivo grande não recalcule SHA-256 a cada tecla (§5).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

DEFAULT_ENCODING = "UTF-8"
ENCODING_UTF8_BOM = "UTF-8-BOM"
ENCODING_LATIN1 = "ISO-8859-1"
UNTITLED_NAME = "sem-titulo.txt"


class DocumentStatus(Enum):
    """Estados exibidos na barra de status (§23)."""

    SAVED = "Salvo"
    SAVED_TEMPORARILY = "Salvo temporariamente"
    SAVING = "Salvando"
    MODIFIED = "Alterado"
    SAVE_ERROR = "Erro ao salvar"


def content_hash(text: str) -> str:
    """Usado só nas fronteiras (salvar, comparar recuperação × arquivo)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_document_id() -> str:
    return uuid.uuid4().hex[:8]


def now() -> datetime:
    """Instante atual com fuso horário local, como pede o formato da §12."""
    return datetime.now().astimezone()


@dataclass
class Document:
    id: str
    content: str
    file_path: Path | None
    recovery_path: Path
    encoding: str = DEFAULT_ENCODING
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)
    #: hash do conteúdo tal como está gravado no arquivo do usuário
    last_saved_hash: str | None = None
    #: difere do arquivo do usuário → estado `Alterado` (§23)
    is_dirty_vs_file: bool = False
    #: ainda não foi para a recuperação → marcador `●` no título (§22)
    is_dirty_vs_recovery: bool = False
    cursor_position: int = 0
    scroll_position: int = 0

    @property
    def is_temporary(self) -> bool:
        return self.file_path is None

    @property
    def display_name(self) -> str:
        return self.file_path.name if self.file_path else "Sem título"

    @property
    def display_path(self) -> str:
        return str(self.file_path) if self.file_path else "Documento não salvo"

    @property
    def save_encoding(self) -> str:
        """Codificação usada ao gravar: UTF-8, preservando o BOM se havia um.

        Arquivos lidos como ISO-8859-1 são convertidos para UTF-8 ao salvar,
        conforme o critério de aceite "arquivos serem salvos em UTF-8".
        """
        return self.encoding if self.encoding == ENCODING_UTF8_BOM else DEFAULT_ENCODING

    def has_recoverable_content(self, text: str) -> bool:
        """Existe trabalho que seria perdido ao descartar este documento?

        Base da §16.4: um documento vazio que nunca recebeu conteúdo é
        descartado sem perguntar nada.
        """
        if self.is_temporary:
            return bool(text)
        return self.is_dirty_vs_file

    def status(self) -> DocumentStatus:
        if self.is_temporary:
            return (
                DocumentStatus.MODIFIED
                if self.is_dirty_vs_recovery
                else DocumentStatus.SAVED_TEMPORARILY
            )
        if self.is_dirty_vs_file:
            return DocumentStatus.MODIFIED
        return DocumentStatus.SAVED

    def touch(self) -> None:
        self.updated_at = now()

    def mark_modified(self) -> None:
        self.is_dirty_vs_file = True
        self.is_dirty_vs_recovery = True
        self.updated_at = now()

    @classmethod
    def create_temporary(cls, recovery_dir: Path, content: str = "") -> Document:
        doc_id = new_document_id()
        return cls(
            id=doc_id,
            content=content,
            file_path=None,
            recovery_path=recovery_dir / f"{doc_id}.txt",
        )

    @classmethod
    def create_for_file(
        cls,
        recovery_dir: Path,
        file_path: Path,
        content: str = "",
        encoding: str = DEFAULT_ENCODING,
        *,
        exists_on_disk: bool = True,
    ) -> Document:
        doc_id = new_document_id()
        return cls(
            id=doc_id,
            content=content,
            file_path=Path(file_path),
            recovery_path=recovery_dir / f"{doc_id}.txt",
            encoding=encoding,
            # Caminho informado na linha de comando que ainda não existe: o
            # conteúdo vazio não corresponde a nada em disco, então já nasce
            # "alterado" e o arquivo só é criado no primeiro salvamento (§30).
            last_saved_hash=content_hash(content) if exists_on_disk else None,
            is_dirty_vs_file=not exists_on_disk,
            is_dirty_vs_recovery=not exists_on_disk,
        )
