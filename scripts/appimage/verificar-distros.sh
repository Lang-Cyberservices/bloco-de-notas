#!/usr/bin/env bash
# Verifica o AppImage em containers das distribuições alvo.
#
# Responde à pergunta que importa: "isto vai abrir numa máquina que não é a
# minha?". Para cada distro, confere que nenhuma biblioteca ficou faltando e
# roda o ciclo digitar → autosave → fechar → reabrir → salvar.
#
# Uso: scripts/appimage/verificar-distros.sh [imagem ...]
set -euo pipefail

PROJETO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DISTROS=("$@")
if [[ ${#DISTROS[@]} -eq 0 ]]; then
    # fedora:41 é o alvo declarado; as demais confirmam a promessa de glibc 2.31+.
    DISTROS=("fedora:41" "debian:11" "ubuntu:22.04" "debian:12")
fi

if ! ls "$PROJETO"/dist/*.AppImage >/dev/null 2>&1; then
    echo "Nenhum AppImage em dist/. Rode scripts/build-appimage.sh antes." >&2
    exit 1
fi

falhas=()
for distro in "${DISTROS[@]}"; do
    echo
    echo "=============================================================="
    echo "  $distro"
    echo "=============================================================="
    if docker run --rm \
        -v "$PROJETO/dist":/dist:ro \
        -v "$PROJETO/scripts/appimage":/verif:ro \
        -e ARTEFATO=appimage \
        "$distro" bash /verif/verificar-dentro.sh
    then
        echo "  >> $distro: OK"
    else
        echo "  >> $distro: FALHOU"
        falhas+=("$distro")
    fi
done

# O .tar.gz é o caminho para máquinas sem libfuse2; precisa ser testado sem
# nenhuma extração de AppImage envolvida.
echo
echo "=============================================================="
echo "  fedora:41 — pacote .tar.gz (sem FUSE)"
echo "=============================================================="
if docker run --rm \
    -v "$PROJETO/dist":/dist:ro \
    -v "$PROJETO/scripts/appimage":/verif:ro \
    -e ARTEFATO=tarball \
    fedora:41 bash /verif/verificar-dentro.sh
then
    echo "  >> tar.gz: OK"
else
    echo "  >> tar.gz: FALHOU"
    falhas+=("tar.gz")
fi

echo
if [[ ${#falhas[@]} -eq 0 ]]; then
    echo "TUDO OK em: ${DISTROS[*]} + tar.gz"
else
    echo "FALHARAM: ${falhas[*]}"
    exit 1
fi
