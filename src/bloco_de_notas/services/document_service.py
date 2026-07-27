"""Regras do documento: abrir, salvar, descartar, recuperar (§16–§21).

Este é o único lugar que decide o destino do conteúdo do usuário. A janela
apenas dispara ações e reflete sinais; nada de `QFileDialog` ou de escrita em
disco vive na interface (§36).

Duas invariantes atravessam o arquivo inteiro:

1. **Nunca descartar antes de confirmar.** A recuperação só é apagada depois
   que o salvamento definitivo deu certo, ou depois que o usuário escolheu
   explicitamente "Não salvar".
2. **Falha nunca troca o documento.** Se gravar ou ler falhar, ou se o usuário
   cancelar o "Salvar como", tudo permanece exatamente como estava.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from ..models.document import (
    UNTITLED_NAME,
    Document,
    DocumentStatus,
    content_hash,
    now,
)
from ..models.session import SessionState
from ..paths import AppPaths
from .atomic_io import ReadError, WriteError, read_text_detect, write_atomic
from .autosave_service import AutosaveService
from .dialogs import DialogPort, SaveChoice
from .recovery_service import RecoveryRecord, RecoveryService
from .session_service import SessionService
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class ContentSource(Protocol):
    """O mínimo que o serviço precisa saber sobre a área de edição.

    O texto vivo mora no editor; o serviço o busca só quando precisa gravar,
    para não copiar o documento inteiro a cada tecla.
    """

    def content_text(self) -> str: ...

    def cursor_position(self) -> int: ...

    def scroll_position(self) -> int: ...


class DocumentService(QObject):
    #: o documento foi trocado; a interface deve recarregar texto e posições
    document_loaded = Signal()
    #: título e barra de status precisam ser atualizados
    state_changed = Signal()
    #: aviso discreto para a barra de status (§10.5)
    notification = Signal(str)

    def __init__(
        self,
        paths: AppPaths,
        recovery: RecoveryService,
        session: SessionService,
        settings: SettingsService,
        dialogs: DialogPort,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._recovery = recovery
        self._session = session
        self._settings = settings
        self._dialogs = dialogs
        self._source: ContentSource | None = None
        self._status_override: DocumentStatus | None = None

        self._autosave = AutosaveService(self._write_recovery, self)
        self._autosave.saved.connect(self._on_autosave_saved)
        self._autosave.failed.connect(self._on_autosave_failed)

        self._document = Document.create_temporary(paths.recovery_dir)

    # --------------------------------------------------------------- ligações

    def attach_source(self, source: ContentSource) -> None:
        self._source = source

    @property
    def document(self) -> Document:
        return self._document

    @property
    def autosave(self) -> AutosaveService:
        return self._autosave

    @property
    def status(self) -> DocumentStatus:
        return self._status_override or self._document.status()

    def _text(self) -> str:
        if self._source is None:
            return self._document.content
        return self._source.content_text()

    def _sync_positions(self) -> None:
        if self._source is not None:
            self._document.cursor_position = self._source.cursor_position()
            self._document.scroll_position = self._source.scroll_position()

    # ------------------------------------------------------------- alterações

    def on_text_changed(self) -> None:
        """Chamado a cada alteração no editor."""
        self._document.mark_modified()
        # Um erro de salvamento anterior continua visível na barra até que
        # algum salvamento dê certo; voltar a digitar não o apaga.
        self._autosave.content_changed()
        self.state_changed.emit()

    # --------------------------------------------------------------- autosave

    def _write_recovery(self) -> None:
        """Grava a recuperação. Chamado pelo `AutosaveService`."""
        self._sync_positions()
        text = self._text()
        self._recovery.save(self._document, text)
        self._document.content = text
        self._document.is_dirty_vs_recovery = False
        self._save_session()
        logger.info(
            "Autosave da recuperação %s (%d caracteres)", self._document.id, len(text)
        )

    def _on_autosave_saved(self) -> None:
        if self._status_override is DocumentStatus.SAVE_ERROR:
            self._status_override = None
        self.state_changed.emit()

    def _on_autosave_failed(self, message: str) -> None:
        # O texto continua no editor e a recuperação anterior continua no
        # disco; só o estado muda (§10.5).
        self._status_override = DocumentStatus.SAVE_ERROR
        self.notification.emit(f"Erro ao salvar a recuperação: {message}")
        self.state_changed.emit()

    def flush_recovery(self) -> bool:
        return self._autosave.flush()

    # ------------------------------------------------------------ sessão

    def _save_session(self) -> None:
        doc = self._document
        self._session.save(
            SessionState(
                document_id=doc.id,
                original_path=str(doc.file_path) if doc.file_path else None,
                cursor_position=doc.cursor_position,
                scroll_position=doc.scroll_position,
            )
        )

    # ------------------------------------------------- troca de documento

    def _install(self, document: Document) -> None:
        self._document = document
        self._status_override = None
        self._autosave.cancel_pending()
        self.document_loaded.emit()
        self._save_session()
        self.state_changed.emit()

    def _decide_release(self) -> SaveChoice | None:
        """Pergunta o que fazer com o documento atual, sem alterar nada.

        Devolve `None` se o usuário cancelou. Separar a *decisão* da *ação*
        permite abortar mais adiante (por exemplo, se a leitura do arquivo a
        abrir falhar) sem já ter apagado nada.
        """
        if not self._document.has_recoverable_content(self._text()):
            return SaveChoice.DISCARD  # §16.4: documento vazio, não pergunta
        choice = self._dialogs.ask_save_discard_cancel(self._document.display_name)
        return None if choice is SaveChoice.CANCEL else choice

    def _apply_release(self, choice: SaveChoice) -> bool:
        """Executa a decisão. Devolve False se o documento deve continuar aberto."""
        if choice is SaveChoice.SAVE:
            if not self.save():
                # Falha na gravação ou "Salvar como" cancelado: não troca nada.
                return False
            # O conteúdo está em definitivo no arquivo do usuário; só agora a
            # recuperação deixa de ser necessária (§11.3).
            self._recovery.delete(self._document.id)
        else:
            self._discard_current()
        self._autosave.cancel_pending()
        return True

    def _discard_current(self) -> None:
        """Escolha explícita de "Não salvar" (§16.2/§17.2): apaga a recuperação."""
        # Distinguir descarte real de documento vazio liberado automaticamente:
        # o log de recuperações é o que se consulta depois de uma perda de
        # conteúdo, e não pode registrar um descarte que não houve.
        havia_conteudo = self._document.has_recoverable_content(self._text())
        self._autosave.cancel_pending()
        self._recovery.delete(self._document.id)
        self._session.clear()
        if havia_conteudo:
            logger.info(
                "Documento %s descartado a pedido do usuário", self._document.id
            )

    # ------------------------------------------------------------ ações do menu

    def new_document(self) -> bool:
        choice = self._decide_release()
        if choice is None or not self._apply_release(choice):
            return False
        self._install(Document.create_temporary(self._paths.recovery_dir))
        logger.info("Novo documento %s", self._document.id)
        return True

    def close_document(self) -> bool:
        """Fecha o documento e abre um vazio; o aplicativo continua aberto (§17)."""
        choice = self._decide_release()
        if choice is None or not self._apply_release(choice):
            return False
        self._install(Document.create_temporary(self._paths.recovery_dir))
        logger.info("Documento fechado; novo documento %s", self._document.id)
        return True

    def open_dialog(self) -> bool:
        # Ordem da §19: confirmar o documento atual, depois escolher o arquivo.
        choice = self._decide_release()
        if choice is None:
            return False
        path = self._dialogs.ask_open_path(self._settings.last_open_dir)
        if path is None:
            return False
        return self._open_confirmed(path, choice)

    def open_path(self, path: Path) -> bool:
        choice = self._decide_release()
        if choice is None:
            return False
        return self._open_confirmed(Path(path), choice)

    def _open_confirmed(self, path: Path, choice: SaveChoice) -> bool:
        try:
            content, encoding = read_text_detect(path)
        except ReadError as exc:
            # §19: leitura falhou — o documento atual continua intacto e a
            # recuperação dele não foi tocada, porque `choice` ainda não foi
            # aplicada.
            logger.error("Falha ao abrir %s: %s", path, exc)
            self._dialogs.show_error("Erro ao abrir", str(exc))
            return False

        if not self._apply_release(choice):
            return False

        document = Document.create_for_file(
            self._paths.recovery_dir, path, content, encoding
        )
        self._install(document)
        self._settings.last_open_dir = path.parent
        logger.info("Arquivo aberto: %s (%s)", path, encoding)
        return True

    def open_cli_path(self, path: Path) -> bool:
        """Caminho vindo da linha de comando (§30)."""
        path = Path(path).expanduser()
        if path.exists():
            return self.open_path(path)

        choice = self._decide_release()
        if choice is None or not self._apply_release(choice):
            return False
        # Arquivo inexistente: associa o documento ao caminho sem criá-lo.
        self._install(
            Document.create_for_file(
                self._paths.recovery_dir, path, "", exists_on_disk=False
            )
        )
        logger.info("Documento associado ao caminho inexistente %s", path)
        return True

    # ----------------------------------------------------------------- salvar

    def save(self) -> bool:
        if self._document.is_temporary:
            return self.save_as()
        return self._write_to_file(self._document.file_path)

    def save_as(self) -> bool:
        suggested = self._document.file_path or (
            self._settings.last_save_dir / UNTITLED_NAME
        )
        path = self._dialogs.ask_save_path(suggested)
        if path is None:
            return False  # cancelado: nada muda (§34.8)
        return self._write_to_file(path)

    def _write_to_file(self, path: Path) -> bool:
        doc = self._document
        self._sync_positions()
        text = self._text()

        self._status_override = DocumentStatus.SAVING
        self.state_changed.emit()

        try:
            write_atomic(path, text, doc.save_encoding)
        except WriteError as exc:
            # Nada é perdido: o texto segue no editor e a recuperação anterior
            # continua válida em disco (§10.5).
            logger.error("Falha ao salvar %s: %s", path, exc)
            self._status_override = DocumentStatus.SAVE_ERROR
            self.state_changed.emit()
            self._dialogs.show_error("Erro ao salvar", str(exc))
            return False

        doc.file_path = Path(path)
        doc.encoding = doc.save_encoding
        doc.content = text
        doc.last_saved_hash = content_hash(text)
        doc.is_dirty_vs_file = False
        doc.touch()
        self._status_override = None
        self._settings.last_save_dir = Path(path).parent

        # A recuperação acompanha o documento enquanto ele estiver aberto
        # (§9.2, §20) — ela só some quando o documento for embora.
        try:
            self._recovery.save(doc, text)
            doc.is_dirty_vs_recovery = False
        except WriteError:
            logger.warning("Arquivo salvo, mas a recuperação não pôde ser atualizada")

        self._autosave.cancel_pending()
        self._save_session()
        self.state_changed.emit()
        logger.info("Arquivo salvo: %s (%d caracteres)", path, len(text))
        return True

    # -------------------------------------------------------------- encerrar

    def shutdown(self) -> None:
        """Fechamento pelo `X` ou por `Sair` (§14, §15).

        Nunca pergunta nada, nunca apaga a recuperação: só grava o estado e
        registra o documento como o último aberto.
        """
        self._sync_positions()
        text = self._text()
        doc = self._document

        if doc.is_temporary and not text and not doc.is_dirty_vs_file:
            # Documento vazio e intocado: não vale criar uma recuperação nova
            # a cada execução do aplicativo.
            self._session.clear()
            logger.info("Encerrando com documento vazio; sessão limpa")
            return

        try:
            self._write_recovery()
        except WriteError as exc:
            logger.error("Falha ao gravar a recuperação no encerramento: %s", exc)
        self._save_session()
        # Impede que os temporizadores sobrevivam ao laço de eventos.
        self._autosave.cancel_pending()
        logger.info("Encerrando; último documento: %s", doc.id)

    # ------------------------------------------------------------- restaurar

    def restore_session(self) -> None:
        """Reabre automaticamente o último documento (§13), sem perguntar nada."""
        state = self._session.load()
        document = self._document_from_session(state)
        self._install(document)

    def _document_from_session(self, state: SessionState) -> Document:
        if state.document_id:
            record = self._recovery.load(state.document_id)
            if record is not None:
                logger.info("Recuperação %s restaurada", record.id)
                return self._document_from_record(record, state)

        # Sem recuperação, mas havia um arquivo: reabre o arquivo.
        if state.original_path:
            path = Path(state.original_path)
            if path.exists():
                try:
                    content, encoding = read_text_detect(path)
                except ReadError:
                    logger.warning("Último arquivo ilegível: %s", path)
                else:
                    logger.info("Último arquivo reaberto: %s", path)
                    return Document.create_for_file(
                        self._paths.recovery_dir, path, content, encoding
                    )

        return Document.create_temporary(self._paths.recovery_dir)

    def _document_from_record(
        self, record: RecoveryRecord, state: SessionState
    ) -> Document:
        document = Document(
            id=record.id,
            content=record.content,
            file_path=record.original_path,
            recovery_path=record.recovery_path,
            encoding=record.encoding,
            created_at=record.created_at or record.updated_at or now(),
            updated_at=record.updated_at or now(),
            cursor_position=record.cursor_position or state.cursor_position,
            scroll_position=record.scroll_position or state.scroll_position,
        )

        if record.original_path is None:
            return document

        if not record.original_path.exists():
            # O arquivo sumiu por fora do aplicativo; a recuperação é tudo o
            # que resta e precisa continuar sendo tratada como não salva.
            document.is_dirty_vs_file = True
            return document

        try:
            file_content, _ = read_text_detect(record.original_path)
        except ReadError:
            document.is_dirty_vs_file = True
            return document

        document.last_saved_hash = content_hash(file_content)

        if file_content == record.content:
            return document

        # Conteúdos divergem: §13.5 manda priorizar a recuperação quando ela
        # for a versão mais recente.
        file_modified = datetime.fromtimestamp(
            record.original_path.stat().st_mtime
        ).astimezone()
        if record.updated_at is None or record.updated_at >= file_modified:
            document.is_dirty_vs_file = True
        else:
            # O arquivo foi alterado por outro programa depois da recuperação.
            logger.info("Arquivo %s é mais recente que a recuperação", record.original_path)
            document.content = file_content
            document.is_dirty_vs_recovery = True

        return document
