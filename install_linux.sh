#!/bin/bash

# Set installation directory
INSTALL_DIR="$HOME/SlothWeb/bwsr"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR" || exit 1

# Detect package manager
if [ -f /etc/debian_version ]; then
    PM="apt"
    PKG_MANAGER="sudo apt update && sudo apt install -y"
elif [ -f /etc/redhat-release ]; then
    PM="dnf"
    PKG_MANAGER="sudo dnf install -y"
else
    echo "Unsupported Linux distribution. Please install Python 3.13.7 manually."
    exit 1
fi

echo "Installing Python 3.13.7 via $PM..."
$PKG_MANAGER python3 python3-pip || {
    echo "Failed to install Python. Ensure you have internet access and run with sudo if needed."
    exit 1
}

echo "Ensuring pip is up to date..."
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip

echo "Downloading the icon (sloth_web.ico)..."
curl -L -o "sloth_web.ico" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/sloth_web.ico"

echo "Downloading the browser (bwsr.py)..."
curl -L -o "bwsr.py" "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/bwsr.py"

echo "Installing dependencies..."
python3 -m pip install PyQt5 PyQtWebEngine requests || {
    echo "Failed to install dependencies. Ensure pip is installed and you have internet access."
    echo "Run 'python3 -m ensurepip --upgrade' and 'python3 -m pip install --upgrade pip' if needed."
    exit 1
}

echo "Creating desktop entry..."
cat > "$HOME/Desktop/Sloth Web Browser.desktop" <<EOL
[Desktop Entry]
Name=Sloth Web Browser
Exec=sh -c "cd $INSTALL_DIR && python3 bwsr.py"
Type=Application
Icon=$INSTALL_DIR/sloth_web.ico
Terminal=false
Categories=Network;WebBrowser;
EOL
chmod +x "$HOME/Desktop/Sloth Web Browser.desktop"

echo "Copying desktop entry to applications menu..."
mkdir -p "$HOME/.local/share/applications"
cp "$HOME/Desktop/Sloth Web Browser.desktop" "$HOME/.local/share/applications/"

echo "Installation complete! Run Sloth Web Browser by double-clicking the desktop icon or typing 'python3 bwsr.py' in $INSTALL_DIR."
echo "Visit https://parkertripoli-wq.github.io/ to browse and install extensions for Sloth Web. (work in progress)"
echo "Bye, have a nice day!"
read -p "Press any key to exit..."