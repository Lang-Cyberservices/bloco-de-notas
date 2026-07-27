#!/usr/bin/env bash
# Verifica o artefato dentro do container de uma distribuição alvo.
# Chamado por verificar-distros.sh — não usar direto.
set -euo pipefail

ARTEFATO="${ARTEFATO:-appimage}"
TRABALHO=/tmp/verificacao

# Instala SOMENTE a pilha que a excludelist assume existir em qualquer desktop
# gráfico: driver (mesa), X11/Wayland de base, fontes e libstdc++. Nada de
# instalar Qt ou xcb-util-cursor — se o AppImage precisar de algo além disto,
# é falha nossa e o teste tem que acusar.
instalar_base() {
    if command -v dnf >/dev/null 2>&1; then
        dnf install -y -q --setopt=install_weak_deps=False \
            mesa-libGL mesa-libEGL libX11 libX11-xcb libxcb libxkbcommon \
            libwayland-client libwayland-egl fontconfig freetype libstdc++ \
            dbus-libs findutils >/dev/null
    elif command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends \
            libgl1 libegl1 libx11-6 libx11-xcb1 libxcb1 libxkbcommon0 \
            libwayland-client0 libwayland-egl1 libfontconfig1 libfreetype6 \
            libstdc++6 libdbus-1-3 file >/dev/null
    else
        echo "gerenciador de pacotes desconhecido" >&2
        exit 1
    fi
}

echo "--- $(. /etc/os-release; echo "$PRETTY_NAME") | glibc $(ldd --version | head -1 | grep -oE '[0-9]+\.[0-9]+$')"
instalar_base

rm -rf "$TRABALHO"
mkdir -p "$TRABALHO"
cd "$TRABALHO"

if [[ "$ARTEFATO" == "tarball" ]]; then
    tar -xzf /dist/*.tar.gz
    RAIZ="$(echo "$TRABALHO"/bloco-de-notas-*-x86_64)"
else
    cp /dist/*.AppImage ./app.AppImage
    chmod +x ./app.AppImage
    # --appimage-extract dispensa FUSE, que não existe dentro do container.
    ./app.AppImage --appimage-extract >/dev/null
    RAIZ="$TRABALHO/squashfs-root"
fi

SITE="$RAIZ/usr/lib/python3.12/site-packages"
export PYTHONHOME="$RAIZ/usr"
export LD_LIBRARY_PATH="$RAIZ/usr/lib:$SITE/PySide6/Qt/lib"
export QT_PLUGIN_PATH="$SITE/PySide6/Qt/plugins"
unset PYTHONPATH

# ------------------------------------------- 1. toda biblioteca foi resolvida

falhou=0
verificar_ldd() {
    local alvo="$1" faltando
    [[ -e "$alvo" ]] || { echo "  AUSENTE: $alvo"; falhou=1; return; }
    faltando="$(ldd "$alvo" 2>/dev/null | grep 'not found' || true)"
    if [[ -n "$faltando" ]]; then
        echo "  FALTANDO em $(basename "$alvo"):"
        echo "$faltando" | sed 's/^/    /'
        falhou=1
    fi
}

echo "  Conferindo dependências dinâmicas..."
verificar_ldd "$RAIZ/usr/bin/python3"
# Todos os plugins, não só os de plataforma: um plugin que não carrega é uma
# funcionalidade que some silenciosamente na máquina do usuário.
while IFS= read -r plugin; do
    verificar_ldd "$plugin"
done < <(find "$QT_PLUGIN_PATH" -name '*.so')
for modulo in Core Gui Widgets Network XcbQpa WaylandClient; do
    verificar_ldd "$SITE/PySide6/Qt/lib/libQt6$modulo.so.6"
done

if [[ $falhou -ne 0 ]]; then
    echo "  RESULTADO: FALHOU (bibliotecas ausentes)"
    exit 1
fi
echo "  Todas as dependências resolvidas."

# --------------------------------------------------- 2. o aplicativo funciona

"$RAIZ/usr/bin/python3" /verif/smoke-test.py
