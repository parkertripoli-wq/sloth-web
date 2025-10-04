#!/bin/bash

# Set installation directory
INSTALL_DIR="$HOME/SlothWeb/bwsr"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR" || exit 1

echo "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ $? -ne 0 ]; then
        echo "Homebrew installation failed. Please install manually and retry."
        exit 1
    fi
fi

echo "Installing Python 3.13.7 via Homebrew..."
brew install python@3.13 || {
    echo "Failed to install Python. Ensure Homebrew is up to date with 'brew update'."
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

echo "Creating alias for Sloth Web Browser..."
echo '#!/bin/bash' > "sloth-web"
echo 'cd "$HOME/SlothWeb/bwsr" && python3 bwsr.py' >> "sloth-web"
chmod +x "sloth-web"
mv "sloth-web" "/usr/local/bin/sloth-web" || mv "sloth-web" "$HOME/.local/bin/sloth-web"

echo "Creating desktop alias..."
echo "alias sloth-web='python3 $HOME/SlothWeb/bwsr/bwsr.py'" >> "$HOME/.zshrc"
source "$HOME/.zshrc"

echo "Installation complete! Run Sloth Web Browser by typing 'sloth-web' in the terminal or using the alias."
echo "Visit https://parkertripoli-wq.github.io/ to browse and install extensions for Sloth Web. (working)"
echo "Bye, have a nice day!"
read -p "Press any key to exit..."
