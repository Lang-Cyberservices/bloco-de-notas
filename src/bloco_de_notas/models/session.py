"""Estado da última sessão, persistido em `session.json` (§13)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionState:
    """Qual era o último documento aberto e onde o usuário estava nele."""

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
    def from_dict(cls, data: dict) -> SessionState:
        def as_int(value) -> int:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return 0

        return cls(
            document_id=data.get("document_id") or None,
            original_path=data.get("original_path") or None,
            cursor_position=as_int(data.get("cursor_position")),
            scroll_position=as_int(data.get("scroll_position")),
        )
