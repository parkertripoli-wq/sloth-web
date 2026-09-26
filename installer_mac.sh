#!/bin/bash
# Sloth Web 3.0 — macOS installer (.sh)
# Do NOT double-click this file (Finder opens TextEdit).
# In Terminal:
#   chmod +x installer_mac.sh && ./installer_mac.sh
set -u

echo "========================================"
echo "  Sloth Web 3.0  —  macOS installer"
echo "========================================"
echo

if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

INSTALL_DIR="$HOME/SlothWeb"
mkdir -p "$INSTALL_DIR"

py_ok() {
  command -v "$1" >/dev/null 2>&1 || return 1
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)' >/dev/null 2>&1
}

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if py_ok "$c"; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo "Python 3.10+ is not installed. Installing it..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "Installing Homebrew first (it will ask for your Mac password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
      echo "Homebrew failed. Install Python from https://www.python.org/downloads/macos/ then run this again."
      read -r -p "Press Return to close..."
      exit 1
    }
    if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
  fi
  brew install python@3.13 || brew install python || true
  hash -r 2>/dev/null || true
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
  for c in python3.13 python3.12 python3; do
    if py_ok "$c"; then PY="$c"; break; fi
  done
fi

if [ -z "$PY" ]; then
  echo "Python still was not found. Install it from https://www.python.org/downloads/macos/ and run this again."
  read -r -p "Press Return to close..."
  exit 1
fi
echo "Using $($PY --version) ($PY)"

echo "Creating a private Python environment..."
if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  "$PY" -m venv "$INSTALL_DIR/venv" || "$PY" -m venv --without-pip "$INSTALL_DIR/venv"
fi
VPY="$INSTALL_DIR/venv/bin/python"
if [ ! -x "$VPY" ]; then
  echo "Could not create $INSTALL_DIR/venv"
  read -r -p "Press Return to close..."
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
    read -r -p "Press Return to close..."
    exit 1
  }
fi
"$VPY" -c "import PyQt6, PyQt6.QtWebEngineWidgets, requests; print('modules ok')" || {
  echo "Modules imported failed after install."
  read -r -p "Press Return to close..."
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
  read -r -p "Press Return to close..."
  exit 1
fi
curl -fsSL -o "$INSTALL_DIR/sloth_web.ico" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/sloth_web.ico" || true

# app bundle used on the Desktop and in Applications
write_app() {
  local APP="$1"
  mkdir -p "$APP/Contents/MacOS"
  cat > "$APP/Contents/MacOS/Sloth Web" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$VPY" "$INSTALL_DIR/SlothWeb.py"
EOF
  chmod +x "$APP/Contents/MacOS/Sloth Web"
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Sloth Web</string>
  <key>CFBundleDisplayName</key><string>Sloth Web</string>
  <key>CFBundleIdentifier</key><string>me.slothweb.browser</string>
  <key>CFBundleVersion</key><string>3.0</string>
  <key>CFBundleShortVersionString</key><string>3.0</string>
  <key>CFBundleExecutable</key><string>Sloth Web</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST
}

echo "Putting Sloth Web on the Desktop..."
mkdir -p "$HOME/Applications" "$HOME/Desktop"
rm -rf "$HOME/Applications/Sloth Web.app" "$HOME/Desktop/Sloth Web.app"
write_app "$HOME/Applications/Sloth Web.app"
cp -R "$HOME/Applications/Sloth Web.app" "$HOME/Desktop/Sloth Web.app"
chmod -R u+rwx "$HOME/Desktop/Sloth Web.app" "$HOME/Applications/Sloth Web.app"
xattr -dr com.apple.quarantine "$HOME/Desktop/Sloth Web.app" "$HOME/Applications/Sloth Web.app" 2>/dev/null || true

mkdir -p "$HOME/bin"
cat > "$HOME/bin/sloth-web" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$VPY" "$INSTALL_DIR/SlothWeb.py" "\$@"
EOF
chmod +x "$HOME/bin/sloth-web"
touch "$HOME/.zshrc"
grep -q 'export PATH="$HOME/bin:$PATH"' "$HOME/.zshrc" 2>/dev/null || echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.zshrc"

echo
echo "========================================"
echo "  Python:   $($PY --version)"
echo "  Modules:  installed in $INSTALL_DIR/venv"
echo "  Browser:  $INSTALL_DIR/SlothWeb.py"
echo "  Desktop:  $HOME/Desktop/Sloth Web.app"
echo "  Also in:  $HOME/Applications/Sloth Web.app"
echo "  If macOS blocks the Desktop app: right-click it → Open"
echo "========================================"
read -r -p "Press Return to close..."
