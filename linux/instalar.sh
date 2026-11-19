#!/usr/bin/env bash
# Instala o Painel do OpenCode (GNOME) para o usuário atual. Não precisa de sudo.
#   ./instalar.sh            instala ou atualiza
#   ./instalar.sh --remover  desinstala
set -euo pipefail

BIN="$HOME/.local/bin/opencode-painel"
DESKTOP="$HOME/.local/share/applications/local.opencode.Painel.desktop"

if [ "${1:-}" = "--remover" ]; then
    rm -f "$BIN" "$DESKTOP" "$HOME"/.local/share/icons/hicolor/*/apps/local.opencode.Painel.png
    rm -rf "$HOME/.cache/opencode-painel" "$HOME/.config/opencode-painel"
    echo "Painel removido. (O início automático, se ativado, fica em ~/.config/autostart/opencode-inicio.desktop)"
    exit 0
fi

install -Dm755 "$(dirname "$0")/opencode-painel" "$BIN"
mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Painel do OpenCode
Comment=Liga/desliga o serviço do OpenCode, troca a senha e configura o início automático
Exec=$BIN
Icon=local.opencode.Painel
Terminal=false
Categories=System;
StartupNotify=true
StartupWMClass=local.opencode.Painel
EOF
update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
echo "Instalado. Procure \"Painel do OpenCode\" no menu de aplicativos."
echo "(O ícone aparece depois de abrir o painel uma vez; se não aparecer, saia e entre na sessão.)"
