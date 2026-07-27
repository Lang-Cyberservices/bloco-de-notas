#!/usr/bin/env python3
"""Gera o ícone do aplicativo.

Desenhado com QPainter em vez de ser um arquivo binário opaco: assim o ícone
fica versionado como código legível e é fácil de ajustar. O motivo repete a
identidade do editor — coluna de números à esquerda, linhas de texto e o ponto
`●` que o título da janela usa para "ainda não salvo".

Uso:
    .venv/bin/python scripts/gerar-icone.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)

from bloco_de_notas.ui import theme  # noqa: E402

TAMANHOS = (256, 128, 64, 48)
DESTINO = RAIZ / "src" / "bloco_de_notas" / "resources"

# Proporções em fração do lado, para o desenho escalar em qualquer tamanho.
MARGEM = 0.06
RAIO = 0.18
LARGURA_GUTTER = 0.17

#: (topo, largura) de cada linha de texto, em fração do lado.
LINHAS = (
    (0.26, 0.52),
    (0.39, 0.66),
    (0.52, 0.42),
    (0.65, 0.60),
)


def desenhar(lado: int) -> QPixmap:
    pixmap = QPixmap(lado, lado)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    margem = lado * MARGEM
    corpo = QRectF(margem, margem, lado - 2 * margem, lado - 2 * margem)
    raio = lado * RAIO

    # Corpo: o mesmo degradê discreto do tema escuro.
    fundo = QLinearGradient(corpo.topLeft(), corpo.bottomRight())
    fundo.setColorAt(0.0, QColor(theme.SURFACE))
    fundo.setColorAt(1.0, QColor(theme.SURFACE_ALT))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(fundo))
    painter.drawRoundedRect(corpo, raio, raio)

    # Coluna de números: uma faixa mais escura à esquerda, recortada pelo
    # contorno arredondado do corpo.
    recorte = QPainterPath()
    recorte.addRoundedRect(corpo, raio, raio)
    painter.save()
    painter.setClipPath(recorte)
    painter.setBrush(QColor(theme.GUTTER_BG))
    painter.drawRect(
        QRectF(corpo.left(), corpo.top(), corpo.width() * LARGURA_GUTTER, corpo.height())
    )
    painter.restore()

    # Marcas dos números de linha.
    esquerda_gutter = corpo.left() + corpo.width() * 0.05
    largura_marca = corpo.width() * 0.07
    altura_linha = corpo.height() * 0.055
    painter.setBrush(QColor(theme.GUTTER_FG))
    for topo, _ in LINHAS:
        painter.drawRoundedRect(
            QRectF(
                esquerda_gutter,
                corpo.top() + corpo.height() * topo,
                largura_marca,
                altura_linha,
            ),
            altura_linha / 2,
            altura_linha / 2,
        )

    # Linhas de texto; a segunda é a "linha atual", em destaque.
    esquerda_texto = corpo.left() + corpo.width() * (LARGURA_GUTTER + 0.08)
    for indice, (topo, largura) in enumerate(LINHAS):
        painter.setBrush(
            QColor(theme.TEXT) if indice == 1 else QColor(theme.TEXT_DIM)
        )
        painter.drawRoundedRect(
            QRectF(
                esquerda_texto,
                corpo.top() + corpo.height() * topo,
                corpo.width() * largura,
                altura_linha,
            ),
            altura_linha / 2,
            altura_linha / 2,
        )

    # O ponto ● de "não salvo", a marca do aplicativo.
    diametro = corpo.width() * 0.17
    painter.setBrush(QColor(theme.ACCENT))
    painter.drawEllipse(
        QRectF(
            corpo.right() - diametro * 1.35,
            corpo.bottom() - diametro * 1.35,
            diametro,
            diametro,
        )
    )

    painter.end()
    return pixmap


def main() -> int:
    # QGuiApplication basta para desenhar; não abre janela nenhuma.
    QGuiApplication(["gerar-icone", "-platform", "offscreen"])
    DESTINO.mkdir(parents=True, exist_ok=True)

    for lado in TAMANHOS:
        pixmap = desenhar(lado)
        nome = (
            "bloco-de-notas.png" if lado == 256 else f"bloco-de-notas-{lado}.png"
        )
        caminho = DESTINO / nome
        if not pixmap.save(str(caminho), "PNG"):
            print(f"Falha ao gravar {caminho}", file=sys.stderr)
            return 1
        print(f"{caminho.relative_to(RAIZ)} ({lado}x{lado})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
