#!/usr/bin/env bash
# Instala a entrada de menu do Bloco de Notas para o usuário atual.
#
# Depois de rodar, o aplicativo aparece no menu do sistema e passa a ser
# oferecido em "Abrir com" para arquivos .txt (§33).
set -euo pipefail

PROJETO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELO="$PROJETO/src/bloco_de_notas/resources/bloco-de-notas.desktop"
RECURSOS="$PROJETO/src/bloco_de_notas/resources"
DADOS="${XDG_DATA_HOME:-$HOME/.local/share}"
DESTINO="$DADOS/applications"
ARQUIVO="$DESTINO/bloco-de-notas.desktop"

PYTHON="$PROJETO/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "Ambiente virtual não encontrado em $PROJETO/.venv" >&2
    echo "Crie-o com: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
    exit 1
fi

# O Exec precisa ser um comando absoluto: o menu do sistema não herda o
# diretório do projeto nem o PATH do terminal.
EXEC="env PYTHONPATH=$PROJETO/src $PYTHON -m bloco_de_notas"

mkdir -p "$DESTINO"
sed "s|__EXEC__|$EXEC|" "$MODELO" > "$ARQUIVO"
chmod 644 "$ARQUIVO"

# O .desktop referencia Icon=bloco-de-notas; sem instalar os PNGs no tema
# hicolor o menu mostraria um ícone genérico.
for tamanho in 256 128 64 48; do
    origem="$RECURSOS/bloco-de-notas.png"
    [[ $tamanho -ne 256 ]] && origem="$RECURSOS/bloco-de-notas-$tamanho.png"
    [[ -f "$origem" ]] || continue
    pasta="$DADOS/icons/hicolor/${tamanho}x${tamanho}/apps"
    mkdir -p "$pasta"
    cp "$origem" "$pasta/bloco-de-notas.png"
done

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DADOS/icons/hicolor" >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESTINO" || true
fi

echo "Instalado em $ARQUIVO"
echo "Para abrir .txt com o Bloco de Notas por padrão:"
echo "  xdg-mime default bloco-de-notas.desktop text/plain"
