#!/bin/bash
# Sloth Web 3.0 — Linux installer
#   chmod +x installer_linux.sh && ./installer_linux.sh
set -u

echo "========================================"
echo "  Sloth Web 3.0  —  Linux installer"
echo "========================================"
echo

INSTALL_DIR="$HOME/SlothWeb"
mkdir -p "$INSTALL_DIR"

install_pkgs() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv python3-full curl \
      libgl1 libegl1 libxkbcommon0 libnss3 libxcomposite1 \
      libxdamage1 libxrandr2 libxtst6 fonts-liberation \
      libdbus-1-3 libxcb-cursor0 libxcb-xinerama0 desktop-file-utils || true
    sudo apt-get install -y libasound2t64 2>/dev/null || sudo apt-get install -y libasound2 || true
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip python3-virtualenv curl mesa-libGL nss alsa-lib \
      libXcomposite libXdamage libXrandr libXtst libxkbcommon || true
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip python-virtualenv curl || true
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y python3 python3-pip python3-virtualenv curl || true
  else
    echo "Could not detect a package manager. Install python3 and python3-venv, then run this again."
    exit 1
  fi
}

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)' >/dev/null 2>&1; then
  echo "Installing Python..."
  install_pkgs
else
  echo "Python: $(python3 --version 2>/dev/null || true)"
  echo "Installing browser libraries (Qt needs these)..."
  install_pkgs
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python did not install."
  exit 1
fi

echo "Creating a private Python environment..."
if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  python3 -m venv "$INSTALL_DIR/venv" || python3 -m venv --without-pip "$INSTALL_DIR/venv"
fi
VPY="$INSTALL_DIR/venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "Could not create $INSTALL_DIR/venv"
  echo "On Ubuntu, install python3-venv and run this again."
  exit 1
fi
"$VPY" -m ensurepip --upgrade >/dev/null 2>&1 || true
echo "Installing PyQt6, WebEngine, and requests..."
"$VPY" -m pip install --upgrade pip || true
if ! "$VPY" -m pip install PyQt6 PyQt6-WebEngine requests; then
  echo "Module install failed. Retrying..."
  "$VPY" -m pip install --upgrade pip
  "$VPY" -m pip install PyQt6 PyQt6-WebEngine requests || {
    echo "Python modules did not install. Scroll up for the pip error."
    exit 1
  }
fi
"$VPY" -c "import PyQt6, PyQt6.QtWebEngineWidgets, requests; print('modules ok')" || {
  echo "Modules imported failed after install."
  exit 1
}

echo "Looking for Sloth Web..."
SRC=""
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
for f in \
  "$SCRIPT_DIR/SlothWeb-3.0.py" \
  "$SCRIPT_DIR/SlothWeb.py" \
  "$HOME/Downloads/SlothWeb-3.0.py" \
  "$HOME/Downloads/SlothWeb.py"
do
  if [ -n "$f" ] && [ -f "$f" ]; then SRC="$f"; break; fi
done
if [ -n "$SRC" ]; then
  cp "$SRC" "$INSTALL_DIR/SlothWeb.py"
  echo "Copied $SRC"
else
  echo "Downloading from GitHub..."
  if ! curl -fL --retry 2 -o "$INSTALL_DIR/SlothWeb.py" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/SlothWeb-3.0.py"; then
    curl -fL --retry 2 -o "$INSTALL_DIR/SlothWeb.py" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/bwsr.py" || true
  fi
fi
if [ ! -s "$INSTALL_DIR/SlothWeb.py" ]; then
  echo "Could not find SlothWeb-3.0.py."
  echo "Put SlothWeb-3.0.py in the same folder as this installer and run it again."
  exit 1
fi
curl -fsSL -o "$INSTALL_DIR/sloth_web.ico" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/sloth_web.ico" || true

mkdir -p "$HOME/.local/bin"
cat > "$INSTALL_DIR/sloth-web" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$VPY" "$INSTALL_DIR/SlothWeb.py" "\$@"
EOF
chmod +x "$INSTALL_DIR/sloth-web"
cp "$INSTALL_DIR/sloth-web" "$HOME/.local/bin/sloth-web"
chmod +x "$HOME/.local/bin/sloth-web"

DESKTOP_DIR="$HOME/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
fi
mkdir -p "$HOME/.local/share/applications" "$DESKTOP_DIR"

cat > "$HOME/.local/share/applications/sloth-web.desktop" <<EOF
[Desktop Entry]
Version=1.0
Name=Sloth Web
Comment=Sloth Web Browser 3.0
Exec=$INSTALL_DIR/sloth-web
Path=$INSTALL_DIR
Icon=$INSTALL_DIR/sloth_web.ico
Type=Application
Terminal=false
Categories=Network;WebBrowser;
StartupNotify=true
EOF
cp "$HOME/.local/share/applications/sloth-web.desktop" "$DESKTOP_DIR/Sloth Web.desktop"
chmod +x "$HOME/.local/share/applications/sloth-web.desktop" "$DESKTOP_DIR/Sloth Web.desktop"
# GNOME/KDE will not launch an untrusted desktop file until this is set
gio set "$DESKTOP_DIR/Sloth Web.desktop" metadata::trusted true 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo
echo "========================================"
echo "  Python:   $(python3 --version 2>/dev/null)"
echo "  Modules:  installed in $INSTALL_DIR/venv"
echo "  Browser:  $INSTALL_DIR/SlothWeb.py"
echo "  Desktop:  $DESKTOP_DIR/Sloth Web.desktop"
echo "  If the icon says Untrusted: right-click it → Allow Launching"
echo "  Or run:   $INSTALL_DIR/sloth-web"
echo "========================================"
read -r -p "Press Enter to close..." || true
