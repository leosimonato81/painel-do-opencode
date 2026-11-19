#!/usr/bin/env bash
# Gera o pacote .deb do Painel do OpenCode (Ubuntu, Debian e derivados) na pasta dist/.
#   ./gerar-deb.sh [versão]      ex.: ./gerar-deb.sh 1.0
set -euo pipefail
umask 022

VERSAO="${1:-1.0}"
cd "$(dirname "$0")"
RAIZ="$(mktemp -d)"
trap 'rm -rf "$RAIZ"' EXIT
chmod 755 "$RAIZ"

install -Dm755 opencode-painel "$RAIZ/usr/bin/opencode-painel"
# Ícone reserva: o painel desenha o ícone definitivo (logo do OpenCode + selo) na primeira vez que abre.
install -Dm644 ../windows/icone.png "$RAIZ/usr/share/icons/hicolor/128x128/apps/local.opencode.Painel.png"
install -d "$RAIZ/usr/share/applications" "$RAIZ/DEBIAN"

cat > "$RAIZ/usr/share/applications/local.opencode.Painel.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Painel do OpenCode
Comment=Liga/desliga o serviço do OpenCode, troca a senha e configura o início automático
Exec=/usr/bin/opencode-painel
Icon=local.opencode.Painel
Terminal=false
Categories=System;
StartupNotify=true
StartupWMClass=local.opencode.Painel
EOF

cat > "$RAIZ/DEBIAN/control" <<EOF
Package: opencode-painel
Version: $VERSAO
Architecture: all
Maintainer: leosimonato81 <https://github.com/leosimonato81/painel-do-opencode>
Depends: python3, python3-gi, python3-cairo, gir1.2-gtk-4.0, gir1.2-adw-1, procps
Section: utils
Priority: optional
Homepage: https://github.com/leosimonato81/painel-do-opencode
Description: Painel para controlar o serviço do OpenCode (GNOME)
 Liga, desliga e reinicia o serviço do OpenCode, mostra o endereço para
 o app OpenCode Mobile, troca a senha e escolhe o que acontece ao entrar
 no computador. Projeto não oficial.
EOF

mkdir -p dist
SAIDA="dist/opencode-painel_${VERSAO}_all.deb"
dpkg-deb --root-owner-group --build "$RAIZ" "$SAIDA" >/dev/null
echo "Pronto: linux/$SAIDA"
