#!/bin/bash
# Sloth Web 3.0 installer for Linux
# Run in a terminal:
#   chmod +x installer_linux.sh && ./installer_linux.sh
# One-liner:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/installer_linux.sh)"
set -e

echo "========================================"
echo "  Sloth Web 3.0  —  Linux installer"
echo "========================================"
echo

INSTALL_DIR="$HOME/SlothWeb"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

install_pkgs() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv curl \
      libgl1 libegl1 libxkbcommon0 libnss3 libasound2 libxcomposite1 \
      libxdamage1 libxrandr2 libxtst6 libxshmfence1 fonts-liberation \
      libdbus-1-3 libxcb-cursor0 libxcb-xinerama0 || true
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip curl mesa-libGL nss alsa-lib \
      libXcomposite libXdamage libXrandr libXtst libxkbcommon || true
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip curl || true
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y python3 python3-pip curl || true
  else
    echo "Install python3 and pip yourself, then re-run."
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "Installing Python..."
  install_pkgs
else
  echo "Python: $(python3 --version)"
  echo "Installing Qt runtime libraries (needed by the browser engine)..."
  install_pkgs
fi

python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
python3 -m pip install --upgrade pip --user
echo "Installing PyQt6..."
python3 -m pip install --user "PyQt6" "PyQt6-WebEngine" "requests"

REPO="https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main"
echo "Downloading Sloth Web..."
if curl -fsSL "$REPO/SlothWeb-3.0.py" -o "SlothWeb.py"; then
  echo "Got SlothWeb-3.0.py"
elif curl -fsSL "$REPO/bwsr.py" -o "SlothWeb.py"; then
  echo "Got bwsr.py (fallback)"
else
  echo "Download failed."
  exit 1
fi
curl -fsSL "$REPO/sloth_web.ico" -o "sloth_web.ico" || true

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/sloth-web" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec python3 "$INSTALL_DIR/SlothWeb.py" "\$@"
EOF
chmod +x "$HOME/.local/bin/sloth-web"

DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
mkdir -p "$HOME/.local/share/applications" "$DESKTOP_DIR"
cat > "$HOME/.local/share/applications/sloth-web.desktop" <<EOF
[Desktop Entry]
Name=Sloth Web
Comment=Sloth Web Browser 3.0
Exec=python3 $INSTALL_DIR/SlothWeb.py
Path=$INSTALL_DIR
Icon=$INSTALL_DIR/sloth_web.ico
Type=Application
Terminal=false
Categories=Network;WebBrowser;
StartupNotify=true
EOF
chmod +x "$HOME/.local/share/applications/sloth-web.desktop"
cp "$HOME/.local/share/applications/sloth-web.desktop" "$DESKTOP_DIR/Sloth Web.desktop" 2>/dev/null || true
chmod +x "$DESKTOP_DIR/Sloth Web.desktop" 2>/dev/null || true

echo
echo "========================================"
echo "  Installed to: $INSTALL_DIR"
echo "  Run:          sloth-web"
echo "  Or:           python3 $INSTALL_DIR/SlothWeb.py"
echo "  Add ~/.local/bin to PATH if the command is not found."
echo "========================================"
read -r -p "Press Enter to close..." || true
