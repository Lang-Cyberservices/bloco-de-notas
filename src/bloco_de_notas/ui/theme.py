"""Paleta do tema escuro.

As cores vivem aqui em vez de só no `.qss` porque a coluna de números e o
destaque da linha atual são desenhados à mão em `paintEvent`, onde folhas de
estilo não chegam. O `.qss` é gerado a partir destas mesmas constantes, então
a interface inteira compartilha uma paleta só.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette

# Fundo e texto
BACKGROUND = "#1e2127"
SURFACE = "#22262e"
SURFACE_ALT = "#1b1d23"
BORDER = "#33383f"
TEXT = "#d7dae0"
TEXT_DIM = "#8b919c"

# Editor
EDITOR_BG = "#1e2127"
EDITOR_FG = "#d7dae0"
CURRENT_LINE = "#282c34"
SELECTION_BG = "#3a4a63"
SELECTION_FG = "#ffffff"
CURSOR = "#e6e9ef"

# Coluna de números
GUTTER_BG = "#1b1d23"
GUTTER_FG = "#5a616d"
GUTTER_FG_CURRENT = "#d7dae0"

# Destaques
ACCENT = "#4c8bf5"
ERROR = "#e06c75"

# Ocorrências da busca
MATCH_BG = "#4a5a2a"
MATCH_CURRENT_BG = "#7a6420"


def color(value: str) -> QColor:
    return QColor(value)


def load_stylesheet() -> str:
    """Lê `resources/dark.qss` e substitui os marcadores `@nome` pelas cores."""
    qss_path = Path(__file__).resolve().parent.parent / "resources" / "dark.qss"
    text = qss_path.read_text(encoding="utf-8")
    replacements = {
        "@background": BACKGROUND,
        "@surface": SURFACE,
        "@surface_alt": SURFACE_ALT,
        "@border": BORDER,
        "@text": TEXT,
        "@text_dim": TEXT_DIM,
        "@editor_bg": EDITOR_BG,
        "@editor_fg": EDITOR_FG,
        "@selection_bg": SELECTION_BG,
        "@selection_fg": SELECTION_FG,
        "@accent": ACCENT,
        "@error": ERROR,
    }
    # Do marcador mais longo para o mais curto: senão `@text` seria
    # substituído dentro de `@text_dim`, gerando cores inválidas.
    for marker in sorted(replacements, key=len, reverse=True):
        text = text.replace(marker, replacements[marker])
    return text


def dark_palette() -> QPalette:
    """Paleta aplicada à QApplication.

    Necessária além do `.qss`: diálogos de arquivo e caixas de mensagem
    montam parte de seus elementos a partir da QPalette, e sem isto
    apareceriam com fundo claro no meio da interface escura (§7).
    """
    palette = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    palette.setColor(role.Window, color(BACKGROUND))
    palette.setColor(role.WindowText, color(TEXT))
    palette.setColor(role.Base, color(EDITOR_BG))
    palette.setColor(role.AlternateBase, color(SURFACE))
    palette.setColor(role.ToolTipBase, color(SURFACE))
    palette.setColor(role.ToolTipText, color(TEXT))
    palette.setColor(role.Text, color(TEXT))
    palette.setColor(role.Button, color(SURFACE))
    palette.setColor(role.ButtonText, color(TEXT))
    palette.setColor(role.BrightText, color(ERROR))
    palette.setColor(role.Link, color(ACCENT))
    palette.setColor(role.Highlight, color(SELECTION_BG))
    palette.setColor(role.HighlightedText, color(SELECTION_FG))
    palette.setColor(role.PlaceholderText, color(TEXT_DIM))

    palette.setColor(group.Disabled, role.Text, color(TEXT_DIM))
    palette.setColor(group.Disabled, role.ButtonText, color(TEXT_DIM))
    palette.setColor(group.Disabled, role.WindowText, color(TEXT_DIM))

    return palette
