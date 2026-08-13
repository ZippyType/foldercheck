#!/usr/bin/env bash
# Build a standalone FolderCheck binary on Linux.
#
# Requirements:
#   - Python 3.10+ with Tk support
#       Debian/Ubuntu:  sudo apt install python3 python3-tk python3-pip python3-venv
#       Fedora:         sudo dnf install python3 python3-tkinter python3-pip
#       Arch:           sudo pacman -S python tk
#
# Produces:
#   dist/FolderCheck        - single-file executable
#   dist/FolderCheck.desktop - optional launcher for menus

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "== Creating build venv =="
"$PY" -m venv .buildvenv
# shellcheck disable=SC1091
source .buildvenv/bin/activate

echo "== Installing build deps =="
pip install --upgrade pip pyinstaller pillow

echo "== Regenerating icon =="
python build_icon.py

echo "== Cleaning previous build =="
rm -rf build dist FolderCheck.spec

echo "== Building executable =="
pyinstaller \
    --noconfirm \
    --windowed \
    --onefile \
    --name FolderCheck \
    foldercheck.py

# Ship the icon next to the binary and create a .desktop entry template.
cp icon/FolderCheck.png dist/FolderCheck.png

INSTALL_PATH="$(pwd)/dist/FolderCheck"
ICON_PATH="$(pwd)/dist/FolderCheck.png"
cat > dist/FolderCheck.desktop <<EOF
[Desktop Entry]
Type=Application
Name=FolderCheck
Comment=Compare two sets of files or folders
Exec=${INSTALL_PATH}
Icon=${ICON_PATH}
Terminal=false
Categories=Utility;FileTools;
EOF

deactivate
rm -rf .buildvenv

echo
echo "Done."
echo "  Binary:  dist/FolderCheck"
echo "  Icon:    dist/FolderCheck.png"
echo "  Launcher: dist/FolderCheck.desktop"
echo
echo "To install for your user:"
echo "  mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons"
echo "  cp dist/FolderCheck        ~/.local/bin/"
echo "  cp dist/FolderCheck.png    ~/.local/share/icons/"
echo "  cp dist/FolderCheck.desktop ~/.local/share/applications/"
