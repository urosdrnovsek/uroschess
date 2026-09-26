#!/usr/bin/env bash
# Install a desktop launcher for this checkout (works on any freedesktop.org
# Linux — GNOME, KDE, Hyprland/Omarchy, XFCE, …). Re-run after moving the repo.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DEST="$APPS/uroschess.desktop"

mkdir -p "$APPS"
cat > "$DEST" <<EOF
[Desktop Entry]
Type=Application
Name=Chess
GenericName=Chess
Comment=Play chess against a from-scratch search engine
Exec=$REPO/run.sh
Path=$REPO
Icon=$REPO/assets/chess.svg
Terminal=false
Categories=Game;BoardGame;
StartupWMClass=uroschess
Keywords=chess;board;game;
EOF

command -v desktop-file-validate >/dev/null && desktop-file-validate "$DEST"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "installed $DEST  ->  $REPO/run.sh"
