"""Configurações persistentes (§26), em `~/.config/bloco-de-notas/settings.ini`."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from ..paths import AppPaths
from ..ui.text_editor import DEFAULT_FONT_SIZE, MAX_FONT_SIZE, MIN_FONT_SIZE


class SettingsService:
    def __init__(self, paths: AppPaths) -> None:
        paths.config_dir.mkdir(parents=True, exist_ok=True)
        self._settings = QSettings(
            str(paths.settings_file), QSettings.Format.IniFormat
        )

    def sync(self) -> None:
        self._settings.sync()

    # ------------------------------------------------------------------ fonte

    @property
    def font_size(self) -> int:
        value = self._settings.value("editor/font_size", DEFAULT_FONT_SIZE)
        try:
            size = int(value)
        except (TypeError, ValueError):
            return DEFAULT_FONT_SIZE
        return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))

    @font_size.setter
    def font_size(self, value: int) -> None:
        self._settings.setValue("editor/font_size", int(value))

    @property
    def font_family(self) -> str:
        return str(self._settings.value("editor/font_family", "") or "")

    @font_family.setter
    def font_family(self, value: str) -> None:
        self._settings.setValue("editor/font_family", value)

    # ---------------------------------------------------------- quebra de linha

    @property
    def word_wrap(self) -> bool:
        return self._settings.value("editor/word_wrap", False, type=bool)

    @word_wrap.setter
    def word_wrap(self, value: bool) -> None:
        self._settings.setValue("editor/word_wrap", bool(value))

    # ----------------------------------------------------------------- janela

    @property
    def window_geometry(self) -> QByteArray | None:
        value = self._settings.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    @window_geometry.setter
    def window_geometry(self, value: QByteArray) -> None:
        self._settings.setValue("window/geometry", value)

    @property
    def window_maximized(self) -> bool:
        return self._settings.value("window/maximized", False, type=bool)

    @window_maximized.setter
    def window_maximized(self, value: bool) -> None:
        self._settings.setValue("window/maximized", bool(value))

    # ------------------------------------------------------------- diretórios

    @property
    def last_open_dir(self) -> Path:
        return self._dir("dialogs/last_open_dir")

    @last_open_dir.setter
    def last_open_dir(self, value: Path) -> None:
        self._settings.setValue("dialogs/last_open_dir", str(value))

    @property
    def last_save_dir(self) -> Path:
        return self._dir("dialogs/last_save_dir")

    @last_save_dir.setter
    def last_save_dir(self, value: Path) -> None:
        self._settings.setValue("dialogs/last_save_dir", str(value))

    def _dir(self, key: str) -> Path:
        value = str(self._settings.value(key, "") or "")
        path = Path(value) if value else Path.home()
        return path if path.is_dir() else Path.home()
