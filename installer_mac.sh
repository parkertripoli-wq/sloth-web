#!/bin/bash
# Sloth Web installer for macOS  (.sh — run from Terminal, do not double-click)
#   chmod +x installer_mac.sh && ./installer_mac.sh
# One-liner (no file, never opens TextEdit):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/installer_mac.sh)"
set -e
cd "$(dirname "$0")" 2>/dev/null || true

echo "========================================"
echo "  Sloth Web 3.0  —  macOS installer"
echo "========================================"
echo

# Homebrew PATH (Apple Silicon + Intel)
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

INSTALL_DIR="$HOME/SlothWeb"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew (you will be asked for your password)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

echo "Installing Python..."
brew install python@3.13 python@3.12 2>/dev/null || brew install python || true

PY=""
for c in python3.13 python3.12 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python was not found. Install it from https://www.python.org/downloads/macos/ and re-run."
  read -r -p "Press Return to close..."
  exit 1
fi
echo "Using $($PY --version)"

"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PY" -m pip install --upgrade pip --user
echo "Installing PyQt6 (this can take a minute)..."
"$PY" -m pip install --user "PyQt6" "PyQt6-WebEngine" "requests"

REPO="https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main"
echo "Downloading Sloth Web..."
if curl -fsSL "$REPO/SlothWeb-3.0.py" -o "SlothWeb.py"; then
  echo "Got SlothWeb-3.0.py"
elif curl -fsSL "$REPO/bwsr.py" -o "SlothWeb.py"; then
  echo "Got bwsr.py (fallback)"
else
  echo "Download failed. Check your internet and try again."
  read -r -p "Press Return to close..."
  exit 1
fi
curl -fsSL "$REPO/sloth_web.ico" -o "sloth_web.ico" || true

# Launcher in ~/bin (no sudo)
mkdir -p "$HOME/bin"
cat > "$HOME/bin/sloth-web" <<EOF
#!/bin/bash
# keep brew python on PATH
[ -x /opt/homebrew/bin/brew ] && eval "\$(/opt/homebrew/bin/brew shellenv)"
[ -x /usr/local/bin/brew ] && eval "\$(/usr/local/bin/brew shellenv)"
cd "$INSTALL_DIR"
exec $PY "$INSTALL_DIR/SlothWeb.py" "\$@"
EOF
chmod +x "$HOME/bin/sloth-web"

# PATH for future terminals
for rc in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc"; do
  if [ -f "$rc" ] || [ "$rc" = "$HOME/.zshrc" ]; then
    touch "$rc"
    grep -q 'export PATH="$HOME/bin:$PATH"' "$rc" 2>/dev/null || echo 'export PATH="$HOME/bin:$PATH"' >> "$rc"
  fi
done

# Double-click app wrapper (opens Terminal-less if pythonw, else python)
APP="$HOME/Applications/Sloth Web.app"
mkdir -p "$APP/Contents/MacOS" "$HOME/Applications"
cat > "$APP/Contents/MacOS/Sloth Web" <<EOF
#!/bin/bash
[ -x /opt/homebrew/bin/brew ] && eval "\$(/opt/homebrew/bin/brew shellenv)"
cd "$INSTALL_DIR"
exec $PY "$INSTALL_DIR/SlothWeb.py"
EOF
chmod +x "$APP/Contents/MacOS/Sloth Web"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Sloth Web</string>
  <key>CFBundleIdentifier</key><string>me.slothweb.browser</string>
  <key>CFBundleVersion</key><string>3.0</string>
  <key>CFBundleExecutable</key><string>Sloth Web</string>
  <key>CFBundlePackageType</key><string>APPL</string>
</dict>
</plist>
PLIST

echo
echo "========================================"
echo "  Installed to: $INSTALL_DIR"
echo "  Run:          sloth-web"
echo "  Or open:      $HOME/Applications/Sloth Web.app"
echo "  (Open a NEW Terminal window so PATH updates.)"
echo "========================================"
read -r -p "Press Return to close..."
