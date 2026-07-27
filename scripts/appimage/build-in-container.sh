#!/usr/bin/env bash
# Monta a AppDir e gera o AppImage + o .tar.gz portátil.
#
# Roda dentro do container Debian 11 disparado por scripts/build-appimage.sh.
# Não chamar direto a menos que se saiba o que se está fazendo.
set -euo pipefail

PROJETO="${PROJETO:-/projeto}"
TRABALHO="/tmp/build-bloco-de-notas"
APPDIR="$TRABALHO/AppDir"
SAIDA="$PROJETO/dist"
RECURSOS="$PROJETO/src/bloco_de_notas/resources"
EXCLUDELIST_OFICIAL="$PROJETO/scripts/appimage/excludelist"
EXCLUDELIST_LOCAL="$PROJETO/scripts/appimage/excludelist-local"
EXCLUDELIST="/tmp/excludelist-efetiva"

# PySide6 6.9.3 é a última versão publicada como manylinux_2_28. A partir da
# 6.10 os wheels são manylinux_2_34, o que sozinho excluiria Ubuntu 22.04 e
# Fedora 35 — anulando o motivo de construir no Debian 11.
PYSIDE_VERSAO="6.9.3"

PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/cpython-3.12.13%2B20260718-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

PYTHON_MINOR="3.12"
SITE="$APPDIR/usr/lib/python$PYTHON_MINOR/site-packages"
QT_DIR="$SITE/PySide6/Qt"

# Módulos Qt mantidos. O código usa Core/Gui/Widgets/Network; DBus, XcbQpa,
# Wayland*, OpenGL e Svg entram porque os plugins de plataforma dependem deles.
QT_LIBS_MANTER=(
    Core Gui Widgets Network DBus OpenGL Svg
    XcbQpa WaylandClient WaylandEglClientHwIntegration
)

# Plugins mantidos: sem "platforms" não há como abrir janela; os de wayland
# são o que permite o mesmo arquivo rodar nativamente no KDE da Fedora.
QT_PLUGINS_MANTER=(
    platforms platformthemes platforminputcontexts
    imageformats iconengines generic xcbglintegrations
    wayland-decoration-client wayland-graphics-integration-client
    wayland-shell-integration
)

log() { printf '\n==> %s\n' "$*"; }

# ---------------------------------------------------------------- dependências

log "Instalando bibliotecas de runtime do Qt"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    ca-certificates wget xz-utils file binutils desktop-file-utils zsync \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-shm0 libxcb-sync1 libxcb-util1 \
    libxcb-xfixes0 libxcb-xkb1 libxcb-glx0 libxcb-xinerama0 libxcb1 \
    libxkbcommon0 libxkbcommon-x11-0 libx11-xcb1 libxau6 libxdmcp6 \
    libfontconfig1 libfreetype6 libdbus-1-3 libglib2.0-0 libpng16-16 \
    libwayland-client0 libwayland-cursor0 libwayland-egl1 \
    libegl1 libgl1 libglx0 libopengl0 >/dev/null

# ------------------------------------------------------------------- AppDir

log "Preparando AppDir"
rm -rf "$TRABALHO"
mkdir -p "$APPDIR/usr" "$TRABALHO/downloads" "$SAIDA"

log "Baixando CPython $PYTHON_MINOR relocável"
# O Debian 11 só traz Python 3.9. Este CPython é feito para ser embarcado e
# funciona a partir de qualquer diretório.
wget -q -O "$TRABALHO/downloads/python.tar.gz" "$PYTHON_URL"
tar -xzf "$TRABALHO/downloads/python.tar.gz" -C "$TRABALHO"
cp -a "$TRABALHO/python/." "$APPDIR/usr/"
rm -rf "$TRABALHO/python"

PYTHON_BIN="$APPDIR/usr/bin/python3"
"$PYTHON_BIN" --version

log "Instalando PySide6-Essentials $PYSIDE_VERSAO e o aplicativo"
# Copiar apenas as fontes: instalar direto de /projeto faria o pip copiar
# também o .venv do host (centenas de MB) para o diretório temporário.
FONTE="$TRABALHO/fonte"
mkdir -p "$FONTE"
cp -a "$PROJETO/pyproject.toml" "$PROJETO/README.md" "$PROJETO/src" "$FONTE/"

"$PYTHON_BIN" -m pip install --quiet --no-cache-dir --upgrade pip
"$PYTHON_BIN" -m pip install --quiet --no-cache-dir \
    "PySide6-Essentials==$PYSIDE_VERSAO" "$FONTE"

# ---------------------------------------------------------------------- poda

log "Podando módulos do Qt não utilizados"
tamanho_antes=$(du -sm "$APPDIR" | cut -f1)

manter_lib() {
    local arquivo nome
    nome="$(basename "$1")"
    for modulo in "${QT_LIBS_MANTER[@]}"; do
        [[ "$nome" == "libQt6$modulo.so"* ]] && return 0
    done
    return 1
}

# Bibliotecas Qt fora da lista de permissão (Qml, Quick, Multimedia com as
# libav* do ffmpeg, Sql, Test, Designer...).
if [[ -d "$QT_DIR/lib" ]]; then
    for arquivo in "$QT_DIR"/lib/*; do
        nome="$(basename "$arquivo")"
        case "$nome" in
            libQt6*) manter_lib "$arquivo" || rm -rf "$arquivo" ;;
            libav*|libsw*) rm -rf "$arquivo" ;;   # ffmpeg, só usado por Multimedia
        esac
    done
fi

# Bindings Python dos módulos removidos.
for arquivo in "$SITE"/PySide6/Qt*.abi3.so; do
    [[ -e "$arquivo" ]] || continue
    nome="$(basename "$arquivo")"
    modulo="${nome#Qt}"; modulo="${modulo%%.abi3.so}"
    manter=1
    for permitido in "${QT_LIBS_MANTER[@]}"; do
        [[ "$modulo" == "$permitido" ]] && manter=0 && break
    done
    [[ $manter -eq 1 ]] && rm -f "$arquivo"
done

# Diretórios de plugins fora da lista.
if [[ -d "$QT_DIR/plugins" ]]; then
    for pasta in "$QT_DIR"/plugins/*/; do
        nome="$(basename "$pasta")"
        manter=1
        for permitido in "${QT_PLUGINS_MANTER[@]}"; do
            [[ "$nome" == "$permitido" ]] && manter=0 && break
        done
        [[ $manter -eq 1 ]] && rm -rf "$pasta"
    done
fi

# Partes do CPython embarcado que este aplicativo nunca importa. O Tcl/Tk
# sozinho passa de 10 MB, e vem junto só porque o build padrão traz tkinter.
PY_LIB="$APPDIR/usr/lib/python$PYTHON_MINOR"
rm -rf "$PY_LIB/tkinter" "$PY_LIB/idlelib" "$PY_LIB/turtledemo" "$PY_LIB/turtle.py" \
       "$PY_LIB/test" "$PY_LIB/lib2to3" "$PY_LIB/ensurepip" \
       "$PY_LIB/config-$PYTHON_MINOR"* \
       "$APPDIR/usr/include" "$APPDIR/usr/share/man" \
       "$APPDIR/usr/lib"/libtcl*.so* "$APPDIR/usr/lib"/libtk*.so* \
       "$APPDIR/usr/lib"/tcl* "$APPDIR/usr/lib"/tk* "$APPDIR/usr/lib"/itcl* \
       "$APPDIR/usr/lib"/thread* "$APPDIR/usr/lib"/*.a
rm -f "$PY_LIB/lib-dynload"/_tkinter*.so

# pip e setuptools só serviam para montar esta AppDir.
rm -rf "$SITE/pip" "$SITE/pip-"* "$SITE/setuptools" "$SITE/setuptools-"* \
       "$SITE/pkg_resources" "$SITE/wheel" "$SITE/wheel-"*

# Plugins de plataforma: manter só os que fazem sentido num desktop. O eglfs
# e o linuxfb são para framebuffer/embarcado e dependem de módulos Qt que a
# poda acima removeu — deixá-los ali seria carregar plugins quebrados.
PLATFORMS_MANTER=(libqxcb.so libqwayland-generic.so libqwayland-egl.so
                  libqoffscreen.so libqminimal.so)
for arquivo in "$QT_DIR"/plugins/platforms/*.so; do
    [[ -e "$arquivo" ]] || continue
    nome="$(basename "$arquivo")"
    manter=1
    for permitido in "${PLATFORMS_MANTER[@]}"; do
        [[ "$nome" == "$permitido" ]] && manter=0 && break
    done
    [[ $manter -eq 1 ]] && rm -f "$arquivo"
done

# QML, traduções e exemplos não têm uso num aplicativo de widgets.
rm -rf "$QT_DIR/qml" "$QT_DIR/translations" "$SITE/PySide6/examples" \
       "$SITE/PySide6/scripts" "$SITE/PySide6/glue" "$SITE/PySide6/include" \
       "$SITE/PySide6/typesystems" "$SITE/PySide6/Qt/libexec" \
       "$SITE"/PySide6/*.pyi "$SITE"/shiboken6/*.pyi
find "$APPDIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR" -name '*.debug' -delete 2>/dev/null || true

tamanho_depois=$(du -sm "$APPDIR" | cut -f1)
echo "AppDir: ${tamanho_antes} MB -> ${tamanho_depois} MB"

# --------------------------------------------------- bibliotecas do sistema

log "Copiando bibliotecas do sistema exigidas pelo Qt"
mkdir -p "$APPDIR/usr/lib"
# Lista oficial + as exclusões próprias do projeto (ver excludelist-local).
grep -hE '^lib' "$EXCLUDELIST_OFICIAL" "$EXCLUDELIST_LOCAL" | sort -u > "$EXCLUDELIST"
# Faz o ldd resolver primeiro dentro da AppDir: o que já está embarcado não
# é copiado de novo.
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$QT_DIR/lib"

listar_dependencias() {
    find "$APPDIR" -type f \( -name '*.so' -o -name '*.so.*' \) -print0 \
        | xargs -0 -r -n8 ldd 2>/dev/null \
        | grep -F '=> /' \
        | awk '{print $1 "\t" $3}' \
        | sort -u
}

copiadas=0
for rodada in 1 2 3 4; do
    novas=0
    while IFS=$'\t' read -r soname caminho; do
        [[ -z "$soname" || -z "$caminho" || ! -e "$caminho" ]] && continue
        # Já vem embarcada (Qt ou rodada anterior).
        [[ "$caminho" == "$APPDIR"/* ]] && continue
        # Precisa vir do host: driver gráfico, glibc, libstdc++ (ver excludelist).
        grep -qxF "$soname" "$EXCLUDELIST" && continue
        [[ -e "$APPDIR/usr/lib/$soname" ]] && continue
        cp -L "$caminho" "$APPDIR/usr/lib/$soname"
        novas=$((novas + 1))
    done < <(listar_dependencias)
    copiadas=$((copiadas + novas))
    echo "  rodada $rodada: $novas bibliotecas"
    [[ $novas -eq 0 ]] && break
done
echo "Total embarcado: $copiadas bibliotecas do sistema"

log "Removendo plugins com dependências insatisfeitas"
# Regra que se mantém sozinha: neste ponto tudo o que será distribuído já está
# na AppDir, e as bibliotecas da excludelist existem no container de build. Se
# um plugin ainda tem "not found", ele é insatisfazível de verdade — seja um
# resto da poda (libqpdf sem Qt6Pdf), seja algo que exige uma pilha que não
# empacotamos (libqgtk3 exige GTK3 inteiro).
#
# Nada disso faz falta a um editor de texto: o tema é nosso, os diálogos são
# do Qt, e o teclado virtual e o wl-shell obsoleto não têm uso no desktop.
# Um plugin quebrado só produziria aviso no log do usuário.
removidos=0
while IFS= read -r plugin; do
    if ldd "$plugin" 2>/dev/null | grep -q 'not found'; then
        echo "  removendo $(basename "$(dirname "$plugin")")/$(basename "$plugin")"
        rm -f "$plugin"
        removidos=$((removidos + 1))
    fi
done < <(find "$QT_DIR/plugins" -name '*.so')
echo "  $removidos plugins removidos"

# ------------------------------------------------------ metadados da AppDir

log "Escrevendo AppRun, .desktop e ícone"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# Ponto de entrada do AppImage.
AQUI="$(dirname "$(readlink -f "$0")")"
SITE="$AQUI/usr/lib/python3.12/site-packages"

# Isola do Python do host: sem isto, um PYTHONPATH ou PYTHONHOME herdado do
# ambiente do usuário faria o interpretador embarcado carregar módulos alheios.
unset PYTHONPATH
export PYTHONHOME="$AQUI/usr"
export PYTHONDONTWRITEBYTECODE=1

export LD_LIBRARY_PATH="$AQUI/usr/lib:$SITE/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="$SITE/PySide6/Qt/plugins"

# QT_QPA_PLATFORM fica deliberadamente sem definição: é o que faz o mesmo
# arquivo usar Wayland numa sessão KDE da Fedora e xcb no X11.
exec "$AQUI/usr/bin/python3" -m bloco_de_notas "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# O .desktop sai do mesmo modelo usado pela instalação local, para não existirem
# duas descrições do aplicativo que possam divergir.
sed 's|__EXEC__|bloco-de-notas|' "$RECURSOS/bloco-de-notas.desktop" \
    > "$APPDIR/bloco-de-notas.desktop"
mkdir -p "$APPDIR/usr/share/applications"
cp "$APPDIR/bloco-de-notas.desktop" "$APPDIR/usr/share/applications/"

cp "$RECURSOS/bloco-de-notas.png" "$APPDIR/bloco-de-notas.png"
cp "$RECURSOS/bloco-de-notas.png" "$APPDIR/.DirIcon"
for tamanho in 256 128 64 48; do
    origem="$RECURSOS/bloco-de-notas.png"
    [[ $tamanho -ne 256 ]] && origem="$RECURSOS/bloco-de-notas-$tamanho.png"
    [[ -f "$origem" ]] || continue
    pasta="$APPDIR/usr/share/icons/hicolor/${tamanho}x${tamanho}/apps"
    mkdir -p "$pasta"
    cp "$origem" "$pasta/bloco-de-notas.png"
done

desktop-file-validate "$APPDIR/bloco-de-notas.desktop"

# ------------------------------------------------------------- empacotamento

VERSAO="$("$PYTHON_BIN" -c 'import bloco_de_notas; print(bloco_de_notas.__version__)')"

log "Gerando o .tar.gz portátil"
# Alternativa para máquinas sem libfuse2 (Fedora não a instala por padrão):
# basta extrair e executar, sem FUSE nenhum.
PACOTE="bloco-de-notas-$VERSAO-x86_64"
rm -rf "$TRABALHO/$PACOTE"
cp -a "$APPDIR" "$TRABALHO/$PACOTE"
ln -sf AppRun "$TRABALHO/$PACOTE/bloco-de-notas"
tar -czf "$SAIDA/$PACOTE.tar.gz" -C "$TRABALHO" "$PACOTE"

log "Gerando o AppImage"
wget -q -O "$TRABALHO/appimagetool" "$APPIMAGETOOL_URL"
chmod +x "$TRABALHO/appimagetool"
# Não há FUSE dentro do container; o runtime do próprio appimagetool se
# extrai sozinho com esta variável.
export APPIMAGE_EXTRACT_AND_RUN=1
export ARCH=x86_64
"$TRABALHO/appimagetool" "$APPDIR" "$SAIDA/Bloco_de_Notas-$VERSAO-x86_64.AppImage"

# O container roda como root; devolve os artefatos ao dono do projeto.
if [[ -n "${HOST_UID:-}" && -n "${HOST_GID:-}" ]]; then
    chown -R "$HOST_UID:$HOST_GID" "$SAIDA"
fi

log "Pronto"
ls -lh "$SAIDA"
