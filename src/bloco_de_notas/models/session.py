"""Estado da última sessão, persistido em `session.json` (§13)."""

from __future__ import annotations

from dataclasses import dataclass, field


def _as_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass
class TabState:
    """Um documento que estava aberto e onde o usuário estava nele."""

    document_id: str | None = None
    original_path: str | None = None
    cursor_position: int = 0
    scroll_position: int = 0

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "original_path": self.original_path,
            "cursor_position": self.cursor_position,
            "scroll_position": self.scroll_position,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TabState:
        return cls(
            document_id=data.get("document_id") or None,
            original_path=data.get("original_path") or None,
            cursor_position=_as_int(data.get("cursor_position")),
            scroll_position=_as_int(data.get("scroll_position")),
        )


@dataclass
class SessionState:
    """Quais abas estavam abertas, em que ordem, e qual era a ativa."""

    tabs: list[TabState] = field(default_factory=list)
    current_index: int = 0

    @property
    def current(self) -> TabState | None:
        if 0 <= self.current_index < len(self.tabs):
            return self.tabs[self.current_index]
        return None

    def to_dict(self) -> dict:
        # As chaves da aba ativa continuam no nível raiz: é o formato da
        # versão 0.1.0 (um documento só), que assim ainda consegue ler o
        # arquivo.
        data = (self.current or TabState()).to_dict()
        data["tabs"] = [tab.to_dict() for tab in self.tabs]
        data["current_index"] = self.current_index
        return data

    @classmethod
    def from_dict(cls, data: dict) -> SessionState:
        raw_tabs = data.get("tabs")
        if isinstance(raw_tabs, list):
            tabs = [TabState.from_dict(item) for item in raw_tabs if isinstance(item, dict)]
        else:
            # Formato 0.1.0: um único documento no nível raiz.
            tabs = [TabState.from_dict(data)]
        tabs = [tab for tab in tabs if tab.document_id or tab.original_path]
        index = _as_int(data.get("current_index"))
        return cls(tabs=tabs, current_index=min(index, max(0, len(tabs) - 1)))
