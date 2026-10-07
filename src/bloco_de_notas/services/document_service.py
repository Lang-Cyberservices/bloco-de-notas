"""Regras dos documentos abertos: abrir, salvar, fechar, recuperar (§16–§21).

Este é o único lugar que decide o destino do conteúdo do usuário. A janela
apenas dispara ações e reflete sinais; nada de `QFileDialog` ou de escrita em
disco vive na interface (§36).

Duas invariantes atravessam o arquivo inteiro:

1. **Nunca descartar antes de confirmar.** A recuperação só é apagada depois
   que o salvamento definitivo deu certo, ou depois que o usuário escolheu
   explicitamente "Não salvar".
2. **Falha nunca troca o documento.** Se gravar ou ler falhar, ou se o usuário
   cancelar o "Salvar como", tudo permanece exatamente como estava.

Cada documento aberto é uma aba. `Novo` e `Abrir` acrescentam abas e por isso
nunca perguntam nada; a pergunta "Salvar / Não salvar / Cancelar" só existe ao
fechar uma aba.
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
from ..models.session import SessionState, TabState
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


class _OpenDocument:
    """Um documento aberto (uma aba) e o estado que o acompanha."""

    def __init__(self, document: Document, autosave: AutosaveService) -> None:
        self.document = document
        self.autosave = autosave
        self.source: ContentSource | None = None
        self.status_override: DocumentStatus | None = None


class DocumentService(QObject):
    #: um documento foi aberto; a interface deve criar a aba dele
    document_added = Signal(object)
    #: o documento com este id foi fechado; a interface deve remover a aba
    document_removed = Signal(str)
    #: o documento atual passou a ser outro
    current_changed = Signal()
    #: títulos e barra de status precisam ser atualizados
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

        # Sempre existe ao menos um documento aberto.
        self._open: list[_OpenDocument] = []
        self._current = self._new_entry(Document.create_temporary(paths.recovery_dir))
        self._open.append(self._current)

    # --------------------------------------------------------------- ligações

    def attach_source(self, doc_id: str, source: ContentSource) -> None:
        self._entry(doc_id).source = source

    @property
    def document(self) -> Document:
        """O documento atual (a aba ativa)."""
        return self._current.document

    @property
    def documents(self) -> list[Document]:
        """Todos os documentos abertos, na ordem das abas."""
        return [entry.document for entry in self._open]

    @property
    def current_index(self) -> int:
        return self._open.index(self._current)

    @property
    def autosave(self) -> AutosaveService:
        return self._current.autosave

    @property
    def status(self) -> DocumentStatus:
        return self._status(self._current)

    def status_of(self, doc_id: str) -> DocumentStatus:
        return self._status(self._entry(doc_id))

    def _status(self, entry: _OpenDocument) -> DocumentStatus:
        return entry.status_override or entry.document.status()

    def _entry(self, doc_id: str | None) -> _OpenDocument:
        if doc_id is None:
            return self._current
        for entry in self._open:
            if entry.document.id == doc_id:
                return entry
        raise KeyError(doc_id)

    def _new_entry(self, document: Document) -> _OpenDocument:
        # Um autosave por documento: trocar de aba antes do debounce disparar
        # não pode perder a alteração nem gravá-la no documento errado.
        autosave = AutosaveService(lambda: self._write_recovery(entry), self)
        entry = _OpenDocument(document, autosave)
        autosave.saved.connect(lambda: self._on_autosave_saved(entry))
        autosave.failed.connect(lambda message: self._on_autosave_failed(entry, message))
        return entry

    def _text(self, entry: _OpenDocument) -> str:
        if entry.source is None:
            return entry.document.content
        return entry.source.content_text()

    def _sync_positions(self, entry: _OpenDocument) -> None:
        if entry.source is not None:
            entry.document.cursor_position = entry.source.cursor_position()
            entry.document.scroll_position = entry.source.scroll_position()

    def _is_pristine(self, entry: _OpenDocument) -> bool:
        """Documento sem título, vazio e nunca tocado: não há nada a guardar."""
        doc = entry.document
        return doc.is_temporary and not doc.is_dirty_vs_file and not self._text(entry)

    # ------------------------------------------------------------- alterações

    def on_text_changed(self, doc_id: str | None = None) -> None:
        """Chamado a cada alteração no editor de um documento."""
        entry = self._entry(doc_id)
        entry.document.mark_modified()
        # Um erro de salvamento anterior continua visível na barra até que
        # algum salvamento dê certo; voltar a digitar não o apaga.
        entry.autosave.content_changed()
        self.state_changed.emit()

    # --------------------------------------------------------------- autosave

    def _persist_recovery(self, entry: _OpenDocument) -> None:
        self._sync_positions(entry)
        text = self._text(entry)
        self._recovery.save(entry.document, text)
        entry.document.content = text
        entry.document.is_dirty_vs_recovery = False

    def _write_recovery(self, entry: _OpenDocument) -> None:
        """Grava a recuperação. Chamado pelo `AutosaveService` do documento."""
        self._persist_recovery(entry)
        self._save_session()
        logger.info(
            "Autosave da recuperação %s (%d caracteres)",
            entry.document.id,
            len(entry.document.content),
        )

    def _on_autosave_saved(self, entry: _OpenDocument) -> None:
        if entry.status_override is DocumentStatus.SAVE_ERROR:
            entry.status_override = None
        self.state_changed.emit()

    def _on_autosave_failed(self, entry: _OpenDocument, message: str) -> None:
        # O texto continua no editor e a recuperação anterior continua no
        # disco; só o estado muda (§10.5).
        entry.status_override = DocumentStatus.SAVE_ERROR
        self.notification.emit(f"Erro ao salvar a recuperação: {message}")
        self.state_changed.emit()

    def flush_recovery(self) -> bool:
        return self._current.autosave.flush()

    def cancel_all_pending(self) -> None:
        for entry in self._open:
            entry.autosave.cancel_pending()

    # ------------------------------------------------------------ sessão

    def _save_session(self, *, skip_pristine: bool = False) -> None:
        entries = [
            entry
            for entry in self._open
            if not (skip_pristine and self._is_pristine(entry))
        ]
        tabs = [
            TabState(
                document_id=entry.document.id,
                original_path=(
                    str(entry.document.file_path) if entry.document.file_path else None
                ),
                cursor_position=entry.document.cursor_position,
                scroll_position=entry.document.scroll_position,
            )
            for entry in entries
        ]
        current = entries.index(self._current) if self._current in entries else 0
        self._session.save(SessionState(tabs=tabs, current_index=current))

    # ------------------------------------------------------------------ abas

    def set_current(self, doc_id: str) -> None:
        self._activate(self._entry(doc_id))

    def _activate(self, entry: _OpenDocument) -> None:
        if entry is self._current:
            return
        self._current = entry
        self.current_changed.emit()
        self._save_session()
        self.state_changed.emit()

    def move_document(self, origin: int, destination: int) -> None:
        """A aba foi arrastada; a ordem precisa valer na próxima execução."""
        self._open.insert(destination, self._open.pop(origin))
        self._save_session()

    def _add(self, document: Document, *, activate: bool = True) -> _OpenDocument:
        entry = self._new_entry(document)
        self._open.append(entry)
        self.document_added.emit(document)
        if activate:
            self._activate(entry)
        return entry

    def _remove(self, entry: _OpenDocument) -> None:
        """Tira o documento da lista. O destino do conteúdo já foi decidido."""
        entry.autosave.cancel_pending()
        if len(self._open) == 1:
            # Fechar o último documento deixa um vazio no lugar; o aplicativo
            # continua aberto (§17).
            self._add(Document.create_temporary(self._paths.recovery_dir))
        elif entry is self._current:
            index = self._open.index(entry)
            neighbour = index + 1 if index + 1 < len(self._open) else index - 1
            self._activate(self._open[neighbour])
        self._open.remove(entry)
        entry.autosave.deleteLater()
        self.document_removed.emit(entry.document.id)
        self._save_session()
        self.state_changed.emit()

    def _add_reusing_pristine(self, document: Document) -> None:
        """Abre o documento; se a aba atual era um vazio intocado, ele a substitui."""
        previous = self._current
        replace = self._is_pristine(previous)
        self._add(document)
        if replace:
            self._recovery.delete(previous.document.id)
            self._remove(previous)

    def _decide_release(self, entry: _OpenDocument) -> SaveChoice | None:
        """Pergunta o que fazer com o documento, sem alterar nada.

        Devolve `None` se o usuário cancelou.
        """
        if not entry.document.has_recoverable_content(self._text(entry)):
            return SaveChoice.DISCARD  # §16.4: documento vazio, não pergunta
        # A pergunta é sobre este documento: ele precisa estar à vista.
        self._activate(entry)
        choice = self._dialogs.ask_save_discard_cancel(entry.document.display_name)
        return None if choice is SaveChoice.CANCEL else choice

    def _apply_release(self, entry: _OpenDocument, choice: SaveChoice) -> bool:
        """Executa a decisão. Devolve False se o documento deve continuar aberto."""
        if choice is SaveChoice.SAVE:
            if not self._save(entry):
                # Falha na gravação ou "Salvar como" cancelado: não fecha nada.
                return False
            # O conteúdo está em definitivo no arquivo do usuário; só agora a
            # recuperação deixa de ser necessária (§11.3).
            self._recovery.delete(entry.document.id)
        else:
            self._discard(entry)
        entry.autosave.cancel_pending()
        return True

    def _discard(self, entry: _OpenDocument) -> None:
        """Escolha explícita de "Não salvar" (§16.2/§17.2): apaga a recuperação."""
        # Distinguir descarte real de documento vazio liberado automaticamente:
        # o log de recuperações é o que se consulta depois de uma perda de
        # conteúdo, e não pode registrar um descarte que não houve.
        havia_conteudo = entry.document.has_recoverable_content(self._text(entry))
        entry.autosave.cancel_pending()
        self._recovery.delete(entry.document.id)
        if havia_conteudo:
            logger.info(
                "Documento %s descartado a pedido do usuário", entry.document.id
            )

    # ------------------------------------------------------------ ações do menu

    def new_document(self) -> bool:
        """Abre uma aba vazia; os outros documentos continuam como estão."""
        self._add(Document.create_temporary(self._paths.recovery_dir))
        logger.info("Novo documento %s", self._current.document.id)
        return True

    def close_document(self, doc_id: str | None = None) -> bool:
        """Fecha uma aba (a atual, por padrão); o aplicativo continua aberto (§17)."""
        entry = self._entry(doc_id)
        choice = self._decide_release(entry)
        if choice is None or not self._apply_release(entry, choice):
            return False
        self._remove(entry)
        logger.info("Documento %s fechado", entry.document.id)
        return True

    def open_dialog(self) -> bool:
        path = self._dialogs.ask_open_path(self._settings.last_open_dir)
        if path is None:
            return False
        return self.open_path(path)

    def open_path(self, path: Path) -> bool:
        path = Path(path)
        if self._activate_if_open(path):
            return True

        try:
            content, encoding = read_text_detect(path)
        except ReadError as exc:
            # §19: leitura falhou — nenhuma aba foi criada nem trocada.
            logger.error("Falha ao abrir %s: %s", path, exc)
            self._dialogs.show_error("Erro ao abrir", str(exc))
            return False

        self._add_reusing_pristine(
            Document.create_for_file(self._paths.recovery_dir, path, content, encoding)
        )
        self._settings.last_open_dir = path.parent
        logger.info("Arquivo aberto: %s (%s)", path, encoding)
        return True

    def open_cli_path(self, path: Path) -> bool:
        """Caminho vindo da linha de comando (§30)."""
        path = Path(path).expanduser()
        if path.exists():
            return self.open_path(path)
        if self._activate_if_open(path):
            return True

        # Arquivo inexistente: associa o documento ao caminho sem criá-lo.
        self._add_reusing_pristine(
            Document.create_for_file(
                self._paths.recovery_dir, path, "", exists_on_disk=False
            )
        )
        logger.info("Documento associado ao caminho inexistente %s", path)
        return True

    def _activate_if_open(self, path: Path) -> bool:
        """Um arquivo já aberto ganha o foco em vez de uma segunda aba."""
        target = _resolved(path)
        for entry in self._open:
            file_path = entry.document.file_path
            if file_path is not None and _resolved(file_path) == target:
                self._activate(entry)
                return True
        return False

    # ----------------------------------------------------------------- salvar

    def save(self) -> bool:
        return self._save(self._current)

    def save_as(self) -> bool:
        return self._save_as(self._current)

    def _save(self, entry: _OpenDocument) -> bool:
        if entry.document.is_temporary:
            return self._save_as(entry)
        return self._write_to_file(entry, entry.document.file_path)

    def _save_as(self, entry: _OpenDocument) -> bool:
        suggested = entry.document.file_path or (
            self._settings.last_save_dir / UNTITLED_NAME
        )
        path = self._dialogs.ask_save_path(suggested)
        if path is None:
            return False  # cancelado: nada muda (§34.8)
        return self._write_to_file(entry, path)

    def _write_to_file(self, entry: _OpenDocument, path: Path) -> bool:
        doc = entry.document
        self._sync_positions(entry)
        text = self._text(entry)

        entry.status_override = DocumentStatus.SAVING
        self.state_changed.emit()

        try:
            write_atomic(path, text, doc.save_encoding)
        except WriteError as exc:
            # Nada é perdido: o texto segue no editor e a recuperação anterior
            # continua válida em disco (§10.5).
            logger.error("Falha ao salvar %s: %s", path, exc)
            entry.status_override = DocumentStatus.SAVE_ERROR
            self.state_changed.emit()
            self._dialogs.show_error("Erro ao salvar", str(exc))
            return False

        doc.file_path = Path(path)
        doc.encoding = doc.save_encoding
        doc.content = text
        doc.last_saved_hash = content_hash(text)
        doc.is_dirty_vs_file = False
        doc.touch()
        entry.status_override = None
        self._settings.last_save_dir = Path(path).parent

        # A recuperação acompanha o documento enquanto ele estiver aberto
        # (§9.2, §20) — ela só some quando o documento for embora.
        try:
            self._recovery.save(doc, text)
            doc.is_dirty_vs_recovery = False
        except WriteError:
            logger.warning("Arquivo salvo, mas a recuperação não pôde ser atualizada")

        entry.autosave.cancel_pending()
        self._save_session()
        self.state_changed.emit()
        logger.info("Arquivo salvo: %s (%d caracteres)", path, len(text))
        return True

    # -------------------------------------------------------------- encerrar

    def shutdown(self) -> None:
        """Fechamento pelo `X` ou por `Sair` (§14, §15).

        Nunca pergunta nada, nunca apaga a recuperação: só grava o estado de
        cada aba e registra quais estavam abertas.
        """
        for entry in self._open:
            # Impede que os temporizadores sobrevivam ao laço de eventos.
            entry.autosave.cancel_pending()
            if self._is_pristine(entry):
                # Documento vazio e intocado: não vale criar uma recuperação
                # nova a cada execução do aplicativo.
                continue
            try:
                self._persist_recovery(entry)
            except WriteError as exc:
                logger.error(
                    "Falha ao gravar a recuperação %s no encerramento: %s",
                    entry.document.id,
                    exc,
                )
        self._save_session(skip_pristine=True)
        logger.info("Encerrando com %d documento(s) aberto(s)", len(self._open))

    # ------------------------------------------------------------- restaurar

    def restore_session(self) -> None:
        """Reabre automaticamente as abas da última execução (§13), sem perguntar nada."""
        state = self._session.load()
        initial = self._current
        restored: list[_OpenDocument] = []
        current: _OpenDocument | None = None

        for index, tab in enumerate(state.tabs):
            if any(e.document.id == tab.document_id for e in restored):
                continue
            document = self._document_from_session(tab)
            if document is None:
                continue
            entry = self._add(document, activate=False)
            restored.append(entry)
            if index == state.current_index:
                current = entry

        if not restored:
            return
        self._activate(current or restored[0])
        if self._is_pristine(initial):
            self._remove(initial)

    def _document_from_session(self, state: TabState) -> Document | None:
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
                    document = Document.create_for_file(
                        self._paths.recovery_dir, path, content, encoding
                    )
                    document.cursor_position = state.cursor_position
                    document.scroll_position = state.scroll_position
                    return document

        return None

    def _document_from_record(
        self, record: RecoveryRecord, state: TabState
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


def _resolved(path: Path) -> Path:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError):
        return Path(path).absolute()
