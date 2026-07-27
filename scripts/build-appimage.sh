#!/usr/bin/env bash
# Constrói o AppImage do Bloco de Notas dentro de um container Debian 11.
#
# POR QUE UM CONTAINER: a glibc da máquina de construção vira o piso de
# compatibilidade do binário. Esta máquina tem glibc 2.39; construir aqui
# geraria um AppImage que só roda em distribuições de 2024 em diante. O
# Debian 11 (glibc 2.31) faz o artefato rodar em Fedora 33+, Ubuntu 20.04+,
# Debian 11+, Mint 20+ e RHEL 9.
#
# Uso:
#   scripts/build-appimage.sh              constrói no container (recomendado)
#   scripts/build-appimage.sh --sem-docker constrói direto no host (depuração;
#                                          o resultado NÃO é portátil)
set -euo pipefail

PROJETO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGEM="debian:11"

if [[ "${1:-}" == "--sem-docker" ]]; then
    echo "AVISO: construindo com a glibc do host — artefato não portátil." >&2
    PROJETO="$PROJETO" exec bash "$PROJETO/scripts/appimage/build-in-container.sh"
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "docker não encontrado. Use --sem-docker para uma build local não portátil." >&2
    exit 1
fi

mkdir -p "$PROJETO/dist"

echo "==> Construindo em $IMAGEM (glibc 2.31)"
docker run --rm \
    -v "$PROJETO":/projeto \
    -e PROJETO=/projeto \
    -e HOST_UID="$(id -u)" \
    -e HOST_GID="$(id -g)" \
    "$IMAGEM" \
    bash /projeto/scripts/appimage/build-in-container.sh

echo
echo "==> Artefatos em $PROJETO/dist:"
ls -lh "$PROJETO/dist"
