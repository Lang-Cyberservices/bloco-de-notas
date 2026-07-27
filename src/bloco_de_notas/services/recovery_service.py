"""Recuperação persistente dos documentos (§10, §11, §12).

Cada documento tem um par de arquivos em `recovery/`: `<id>.txt` com o texto e
`<id>.json` com os metadados. Ambos em UTF-8, ambos gravados atomicamente.

REGRA CRÍTICA (§11): não existe expiração. Este módulo não tem — e não pode
ganhar — nenhuma rotina que apague recuperações por idade. `delete()` é
chamado apenas nos casos explícitos da especificação: descarte pelo usuário
("Não salvar") ou documento já salvo em definitivo e substituído.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..models.document import DEFAULT_ENCODING, Document, content_hash, now
from ..paths import AppPaths
from .atomic_io import WriteError, write_atomic

logger = logging.getLogger(__name__)


@dataclass
class RecoveryRecord:
    """Uma recuperação lida do disco."""

    id: str
    content: str
    temporary: bool
    original_path: Path | None
    recovery_path: Path
    encoding: str
    created_at: datetime | None
    updated_at: datetime | None
    cursor_position: int
    scroll_position: int


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class RecoveryService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def text_path(self, doc_id: str) -> Path:
        return self._paths.recovery_dir / f"{doc_id}.txt"

    def meta_path(self, doc_id: str) -> Path:
        return self._paths.recovery_dir / f"{doc_id}.json"

    def exists(self, doc_id: str) -> bool:
        return self.text_path(doc_id).exists()

    # ------------------------------------------------------------------ gravar

    def save(self, document: Document, content: str) -> None:
        """Grava texto e metadados da recuperação.

        Levanta `WriteError` se o texto não puder ser gravado. O texto vem
        primeiro de propósito: se os metadados falharem, o conteúdo do usuário
        já está a salvo em disco.
        """
        self._paths.recovery_dir.mkdir(parents=True, exist_ok=True)

        text_path = self.text_path(document.id)
        write_atomic(text_path, content, DEFAULT_ENCODING)

        metadata = {
            "id": document.id,
            "temporary": document.is_temporary,
            "original_path": str(document.file_path) if document.file_path else None,
            "recovery_path": str(text_path),
            "encoding": document.encoding,
            "created_at": document.created_at.isoformat(),
            "updated_at": now().isoformat(),
            "cursor_position": int(document.cursor_position),
            "scroll_position": int(document.scroll_position),
            "content_hash": content_hash(content),
        }
        try:
            write_atomic(
                self.meta_path(document.id),
                json.dumps(metadata, ensure_ascii=False, indent=2),
                DEFAULT_ENCODING,
            )
        except WriteError:
            # O texto foi salvo; perder os metadados custa a posição do cursor,
            # não o conteúdo. Não vale propagar e alarmar o usuário.
            logger.warning("Falha ao gravar metadados da recuperação %s", document.id)

    # -------------------------------------------------------------------- ler

    def load(self, doc_id: str) -> RecoveryRecord | None:
        text_path = self.text_path(doc_id)
        if not text_path.exists():
            return None

        try:
            content = text_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.exception("Não foi possível ler a recuperação %s", doc_id)
            return None

        meta: dict = {}
        meta_path = self.meta_path(doc_id)
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("Metadados ilegíveis para a recuperação %s", doc_id)

        original = meta.get("original_path")
        return RecoveryRecord(
            id=doc_id,
            content=content,
            temporary=bool(meta.get("temporary", original is None)),
            original_path=Path(original) if original else None,
            recovery_path=text_path,
            encoding=meta.get("encoding") or DEFAULT_ENCODING,
            created_at=_parse_datetime(meta.get("created_at")),
            updated_at=_parse_datetime(meta.get("updated_at")),
            cursor_position=int(meta.get("cursor_position") or 0),
            scroll_position=int(meta.get("scroll_position") or 0),
        )

    # ---------------------------------------------------------------- apagar

    def delete(self, doc_id: str) -> None:
        """Remove uma recuperação.

        Só deve ser chamado nos casos da §11. Nunca por idade, nunca em lote,
        nunca ao encerrar o aplicativo.
        """
        arquivos = (self.text_path(doc_id), self.meta_path(doc_id))
        existia = any(path.exists() for path in arquivos)
        for path in arquivos:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Não foi possível remover %s", path)
        if existia:
            logger.info("Recuperação %s removida", doc_id)
