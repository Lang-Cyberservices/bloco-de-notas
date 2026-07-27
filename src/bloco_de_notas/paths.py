"""Resolução centralizada dos caminhos usados pelo aplicativo.

Nenhum outro módulo consulta `QStandardPaths` ou variáveis XDG: todos recebem
um `AppPaths`. Isso mantém a decisão de "onde os dados moram" em um único
lugar e permite que os testes apontem o aplicativo inteiro para um diretório
descartável, sem tocar no `~/.local/share` real.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from . import APP_SLUG


def _xdg_dir(env_var: str, fallback: str) -> Path:
    """Diretório XDG a partir do ambiente, com o fallback da especificação."""
    value = os.environ.get(env_var, "").strip()
    if value:
        return Path(value)
    return Path.home() / fallback


def _default_data_root() -> Path:
    # QStandardPaths respeita XDG_DATA_HOME e resolve para ~/.local/share.
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    )
    return Path(location) if location else _xdg_dir("XDG_DATA_HOME", ".local/share")


def _default_config_root() -> Path:
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericConfigLocation
    )
    return Path(location) if location else _xdg_dir("XDG_CONFIG_HOME", ".config")


@dataclass(frozen=True)
class AppPaths:
    """Onde ficam os dados do aplicativo.

    `AppPaths()` usa os diretórios reais do usuário. `AppPaths.for_base(tmp)`
    cria uma árvore isolada — é a forma usada pelos testes.
    """

    data_dir: Path
    config_dir: Path
    state_dir: Path

    @classmethod
    def default(cls) -> AppPaths:
        return cls(
            data_dir=_default_data_root() / APP_SLUG,
            config_dir=_default_config_root() / APP_SLUG,
            state_dir=_xdg_dir("XDG_STATE_HOME", ".local/state") / APP_SLUG,
        )

    @classmethod
    def for_base(cls, base: Path) -> AppPaths:
        """Árvore completa dentro de `base`, para testes e execuções isoladas."""
        base = Path(base)
        return cls(
            data_dir=base / "data",
            config_dir=base / "config",
            state_dir=base / "state",
        )

    @property
    def recovery_dir(self) -> Path:
        return self.data_dir / "recovery"

    @property
    def session_file(self) -> Path:
        return self.data_dir / "session.json"

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.ini"

    @property
    def log_file(self) -> Path:
        return self.state_dir / "app.log"

    def ensure_dirs(self) -> None:
        for directory in (self.recovery_dir, self.config_dir, self.state_dir):
            directory.mkdir(parents=True, exist_ok=True)
