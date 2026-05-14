import sys
import os
import json
import struct
import zipfile
import io
import shutil
import requests
import re
import webbrowser
import subprocess
import urllib.parse
import time
import threading
import platform

__version__ = "2.5"

from PyQt5.QtCore import QUrl, Qt, QTimer, pyqtSignal, QStringListModel, QBuffer, QThread
from PyQt5.QtWidgets import (QMainWindow, QToolBar, QAction, QLineEdit, 
                             QProgressBar, QTabWidget, QStatusBar, QWidget, 
                             QVBoxLayout, QPushButton, QTabBar, QFileDialog, 
                             QMenu, QInputDialog, QFormLayout, QGroupBox, 
                             QHBoxLayout, QSlider, QApplication, QCompleter,
                             QDialog, QListWidget, QDialogButtonBox, QMessageBox,
                             QListWidgetItem, QTextEdit, QColorDialog, QComboBox,
                             QCheckBox, QLabel, QDockWidget)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineDownloadItem, QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlSchemeHandler, QWebEngineUrlScheme, QWebEngineUrlRequestJob
from PyQt5.QtGui import QIcon, QPalette, QColor, QCursor
try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False

try:
    import winreg
    HAS_REGISTRY = True
except ImportError:
    HAS_REGISTRY = False

import platform

class Platform:
    IS_WIN = platform.system() == "Windows"
    IS_MAC = platform.system() == "Darwin"
    IS_LINUX = platform.system() == "Linux"
    
    @staticmethod
    def get_user_agent():
        if Platform.IS_MAC:
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        elif Platform.IS_LINUX:
            return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    @staticmethod
    def get_platform_string():
        if Platform.IS_MAC: return "MacIntel"
        if Platform.IS_LINUX: return "Linux x86_64"
        return "Win32"

from PyQt5.QtWebEngineWidgets import QWebEngineSettings

# --- Utilities & Path Handling ---

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_storage_path(filename):
    """ Get path to user storage (bookmarks, passwords) in a writable location """
    app_data = os.path.join(os.path.expanduser("~"), ".sloth_web")
    os.makedirs(app_data, exist_ok=True)
    return os.path.join(app_data, filename)

def load_bookmarks(bookmarks_file):
    try:
        if os.path.exists(bookmarks_file):
            with open(bookmarks_file, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return ["https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort="]

def save_bookmarks(bookmarks_file, bookmarks):
    try:
        with open(bookmarks_file, "w") as f:
            json.dump(bookmarks, f, indent=2)
        return True
    except Exception:
        return False

def get_search_suggestions(query):
    try:
        url = f"http://suggestqueries.google.com/complete/search?client=firefox&q={urllib.parse.quote(query)}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()[1]
    except Exception:
        pass
    return []

class SuggestionWorker(QThread):
    suggestions_ready = pyqtSignal(list)
    def __init__(self, query):
        super().__init__()
        self.query = query
    def run(self):
        res = get_search_suggestions(self.query)
        self.suggestions_ready.emit(res)

class PasswordManager:
    def __init__(self, filename):
        self.filename = filename
        loaded = self.load()
        self.passwords = loaded if isinstance(loaded, dict) else {}

    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.passwords, f, indent=2)
        except Exception:
            pass

    def add_password(self, site, username, password):
        if not isinstance(self.passwords, dict): self.passwords = {}
        if site not in self.passwords: self.passwords[site] = []
        
        # Update if user exists, otherwise append
        val = self.passwords[site]
        for p in val:
            if p['user'] == username:
                p['pass'] = password
                self.save()
                return
        
        val.append({"user": username, "pass": password})
        self.save()

    def delete_password(self, site, index):
        if site in self.passwords and index < len(self.passwords[site]):
            self.passwords[site].pop(index)
            if not self.passwords[site]:
                del self.passwords[site]
            self.save()
            return True
        return False

class ConfigManager:
    def __init__(self, filename):
        self.filename = filename
        self.config = self.load()

    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

class UpdateManager:
    def __init__(self, parent):
        self.parent = parent
        self.local_version = __version__
        self.version_url = "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/version.txt"
        self.exe_url = "https://github.com/parkertripoli-wq/sloth-web/releases/latest/download/SlothWebBrowser.exe"

    def check_for_updates(self, force=False):
        try:
            response = requests.get(self.version_url, timeout=5)
            response.raise_for_status()
            remote_version = response.text.strip()
            if remote_version > self.local_version:
                reply = QMessageBox.question(self.parent, "Update Available", f"A new version ({remote_version}) is available. Your version is {self.local_version}. Update now?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes: self.download_and_install(remote_version)
            elif force:
                QMessageBox.information(self.parent, "Up to Date", f"Sloth Web Browser is up to date! (Version {self.local_version}).")
        except Exception as e:
            if force:
                QMessageBox.warning(self.parent, "Update Error", f"Failed to check for updates: {e}")
            self.parent.log(f"Update check failed.")

    def download_and_install(self, version):
        self.parent.log(f"Downloading update version {version}...")
        try:
            # We download the source code as requested
            src_url = "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/bwsr.py"
            response = requests.get(src_url, timeout=30)
            response.raise_for_status()
            
            with open(__file__, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            QMessageBox.information(self.parent, "Update Complete", "The browser has been updated and will now restart.")
            
            # Auto-restart
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            QMessageBox.critical(self.parent, "Update Error", f"Update failed: {e}")
            self.parent.log(f"Update error: {e}")

class DefaultBrowserManager:
    @staticmethod
    def set_as_default():
        if Platform.IS_WIN:
            if not HAS_REGISTRY: return False
            try:
                import winreg
                app_name = "SlothWeb"
                exe_path = sys.executable
                cap_path = rf"Software\Clients\StartMenuInternet\{app_name}\Capabilities"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cap_path, winreg.RESERVED, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "Sloth Web")
                    with winreg.CreateKey(key, "URLAssociations") as url_key:
                        winreg.SetValueEx(url_key, "http", 0, winreg.REG_SZ, app_name)
                        winreg.SetValueEx(url_key, "https", 0, winreg.REG_SZ, app_name)
                return True
            except: return False
        elif Platform.IS_LINUX:
            try:
                subprocess.run(["xdg-settings", "set", "default-web-browser", "sloth-web.desktop"], check=False)
                return True
            except: return False
        elif Platform.IS_MAC:
            try:
                subprocess.run(["open", "-a", "SlothWeb", "--args", "--set-default-browser"], check=False)
                return True
            except: return False
        return False

class HistoryManager:
    def __init__(self, filename):
        self.filename = filename
        self.history = self.load()

    def load(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.history[-100:], f, indent=2) 
        except Exception:
            pass

    def add_entry(self, title, url):
        if not url.startswith("sloth://"):
            self.history.append({"title": title, "url": url, "time": time.strftime("%H:%M")})
            self.save()

# --- Constants & HTML Templates ---
CHROMIUM_FLAGS = [
    "--ignore-gpu-blocklist",
    "--enable-zero-copy",
    "--num-raster-threads=4",
    "--enable-smooth-scrolling",
    "--force-color-profile=srgb",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--max-gum-fps=60",
    "--js-flags=--max-old-space-size=2048",
    "--remote-debugging-port=9222",
]

NEON_VOID_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>NEON VOID – DNS_PROBE_POSSIBLE</title>
  <style>
    :root {
      --bg: #050505;
      --glow-primary: #00ffee;
      --glow-accent: #ff0099;
      --text: #ffffff;
      --font-main: system-ui, -apple-system, sans-serif;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-main);
      overflow: hidden;
    }
    #scanlines {
      position: fixed; inset:0; pointer-events:none; z-index:2;
      background: repeating-linear-gradient(transparent 0, transparent 4px, rgba(0,0,0,0.1) 4px, rgba(0,0,0,0.1) 8px);
      opacity: 0.3;
    }
    canvas#bg { position:fixed; inset:0; z-index:1; pointer-events:none; }
    .container {
      position: relative;
      z-index: 10;
      padding: 2rem;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      max-width: 1000px;
      margin: 0 auto;
      text-align: center;
    }
    h1 {
      font-size: clamp(4rem, 15vw, 8rem);
      font-weight: 900;
      letter-spacing: -4px;
      background: linear-gradient(to bottom, #fff, #666);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: -1rem;
    }
    h2 { 
      font-size: clamp(1.5rem, 4vw, 2.5rem); 
      color: var(--glow-primary); 
      text-shadow: 0 0 20px var(--glow-primary);
      text-transform: uppercase;
      letter-spacing: 4px;
      margin-bottom: 1rem;
    }
    .code { 
      font-family: monospace;
      font-size: 1.2rem; 
      color: var(--glow-accent); 
      background: rgba(255, 0, 153, 0.1);
      padding: 8px 16px;
      border-radius: 8px;
      border: 1px solid var(--glow-accent);
      margin-bottom: 2rem;
    }
    .msg { 
      font-size: 1.2rem; 
      max-width: 600px;
      line-height: 1.6;
      opacity: 0.7;
      margin-bottom: 3rem; 
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 1.5rem;
    }
    .neon-btn {
      background: var(--glow-primary);
      color: #000;
      border: none;
      padding: 14px 32px;
      font-size: 1rem;
      font-weight: 700;
      border-radius: 12px;
      cursor: pointer;
      transition: 0.3s cubic-bezier(0.2, 0, 0, 1);
    }
    .neon-btn:hover { 
      transform: translateY(-5px);
      box-shadow: 0 20px 40px -10px var(--glow-primary); 
    }
    .neon-btn-alt {
      background: rgba(255,255,255,0.05);
      color: #fff;
      border: 1px solid rgba(255,255,255,0.1);
    }
    .neon-btn-alt:hover {
      background: rgba(255,255,255,0.1);
    }
    #gameArea { display: none; }
  </style>
</head>
<body>
<div id="scanlines"></div>
<canvas id="bg"></canvas>
<div class="container">
  <h1>VOID</h1>
  <h2>CONNECTION TERMINATED</h2>
  <div class="code">DNS_PROBE_POSSIBLE</div>
  <div class="msg">The domain vanished into the neon fog.<br>While the grid reroutes, play something.</div>
  <div class="controls">
    <button class="neon-btn" onclick="window.location.href='sloth://settings'">Settings (sloth://settings)</button>
    <button class="neon-btn" onclick="location.reload()">Retry Connection</button>
    <button class="neon-btn" onclick="history.back()">Go Back</button>
  </div>
  <div class="games-grid">
    <div class="game-card" data-game="snake"><h3>Neon Snake</h3><p>Eat orbs, don't crash (WIP)</p></div>
    <div class="game-card" data-game="clicker"><h3>Neon Surge</h3><p>Click frenzy for points (WIP)</p></div>
  </div>
</div>
<script>
const bg = document.getElementById('bg');
const bctx = bg.getContext('2d');
bg.width = window.innerWidth; bg.height = window.innerHeight;
let particles = [];
for (let i = 0; i < 120; i++) {
  particles.push({
    x: Math.random() * bg.width, y: Math.random() * bg.height,
    vx: (Math.random() - 0.5) * 0.8, vy: (Math.random() - 0.5) * 0.8,
    r: Math.random() * 3 + 1, hue: Math.random() * 60 + 180
  });
}
function animateBg() {
  bctx.fillStyle = 'rgba(6,0,20,0.07)';
  bctx.fillRect(0,0,bg.width,bg.height);
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0 || p.x > bg.width) p.vx *= -1;
    if (p.y < 0 || p.y > bg.height) p.vy *= -1;
    bctx.beginPath(); bctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    bctx.fillStyle = `hsl(${p.hue},100%,70%)`;
    bctx.fill();
  });
  requestAnimationFrame(animateBg);
}
animateBg();
</script>
</body>
</html>
"""

# --- Data Management (Customizations) ---

class CustomizationManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f, indent=4)
        except: pass

    def set_custom(self, site, selector, key, val):
        if site not in self.data: self.data[site] = {}
        if selector not in self.data[site]: self.data[site][selector] = {}
        self.data[site][selector][key] = val
        self.save()

    def clear_site(self, site):
        if site in self.data:
            del self.data[site]
            self.save()

    def get_for_site(self, site):
        # Handle subdomains by checking parent domains if needed, but exact hostname is safer for now
        return self.data.get(site, {})

# --- AdBlock & Utilities ---

class ThemeManager:
    @staticmethod
    def get_qss(dark=True, color="#4a9eff", texture="none"):
        bg = "#121212" if dark else "#f5f5f7"
        fg = "#e1e1e1" if dark else "#1d1d1f"
        nav_bg = "rgba(30, 30, 30, 0.95)" if dark else "rgba(255, 255, 255, 0.95)"
        border = "#2a2a2a" if dark else "#d2d2d7"
        hover_bg = "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.05)"
        font_family = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, Cantarell, sans-serif"
        
        texture_img = ""
        if texture == "noise":
            texture_img = "url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAMAAAA6fKPSAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAlQTFRF////zMzM////p8Y9fAAAAAN0Uk5T//8A18o9BAAAAD1JREFUeNpiYGBgYGJgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYAD8AAMAsAByP786AAAAAElFTkSuQmCC')"
        elif texture == "stripes":
            texture_img = "repeating-linear-gradient(45deg, rgba(255,255,255,0.03) 0, rgba(255,255,255,0.03) 1px, transparent 0, transparent 50%)"
        elif texture == "grid":
            texture_img = f"radial-gradient({color}33 1px, transparent 0)"
        
        texture_prop = ""
        if texture_img:
            bg_size = "10px 10px" if texture == "stripes" else ("20px 20px" if texture == "grid" else "auto")
            texture_prop = f"background-image: {texture_img}; background-repeat: repeat;"
        
        toolbar_bg_val = f"{texture_img}, qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {nav_bg}, stop:1 {bg})" if texture_img else f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {nav_bg}, stop:1 {bg})"
        toolbar_bg = f"background-image: {toolbar_bg_val};"

        return f"""
            QMainWindow {{ 
                background-color: {bg}; 
                font-family: {font_family}; 
            }}
            QToolBar {{ 
                background-color: {nav_bg};
                {toolbar_bg}
                border-bottom: 2px solid {color}; 
                padding: 10px; 
                spacing: 12px; 
            }}
            QToolBar::handle {{ background: {color}; width: 2px; }}
            QMainWindow, QDockWidget, QStatusBar, QTabWidget, QTabBar, QLineEdit, QPushButton, QMenu, QListWidget, QDialog, QMessageBox, QLabel, QGroupBox {{
                {texture_prop}
                color: {fg};
            }}
            QDialog, QMessageBox, QGroupBox {{
                background-color: {bg};
                border: 1px solid {border};
            }}
            QLineEdit {{ 
                background-color: {"#1a1a1a" if dark else "#ffffff"}; 
                color: {fg}; 
                border: 2px solid {border}; 
                border-radius: 14px; 
                padding: 8px 16px; 
                font-size: 14px; 
                selection-background-color: {color}; 
            }}
            QLineEdit:focus {{ 
                border: 2px solid {color}; 
                background-color: {"#222222" if dark else "#f9f9f9"};
            }}
            QTabWidget::pane {{ 
                border-top: 1px solid {border}; 
                background: {bg}; 
            }}
            QTabBar::tab {{ 
                background-color: transparent; 
                color: {fg}; 
                padding: 12px 24px; 
                border: none; 
                font-weight: 600; 
                font-size: 13px; 
                min-width: 120px; 
            }}
            QTabBar::tab:hover {{ 
                background-color: {color}11; 
                border-top-left-radius: 10px; 
                border-top-right-radius: 10px; 
            }}
            QTabBar::tab:selected {{ 
                background-color: {bg}; 
                color: {color}; 
                border-bottom: 4px solid {color}; 
                font-weight: 800;
            }}
            QTabBar::close-button {{ 
                background: transparent;
                border-radius: 6px;
                margin: 4px;
                padding: 2px;
            }}
            QTabBar::close-button:hover {{ 
                background-color: rgba(255, 60, 60, 0.7); 
            }}
            QProgressBar {{ 
                border: none; 
                background-color: transparent; 
                height: 4px; 
            }}
            QProgressBar::chunk {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 #ffffff); 
                border-radius: 2px;
            }}
            QPushButton {{ 
                background-color: {color}15; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: 10px; 
                padding: 8px 16px; 
                font-weight: bold; 
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background-color: {color}33; 
                border: 1px solid {color}; 
                color: {color};
            }}
            QStatusBar {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                font-size: 12px; 
                border-top: 1px solid {border}; 
                padding: 4px;
            }}
            QMenu {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                border: 1px solid {color}55; 
                border-radius: 12px; 
                padding: 8px; 
            }}
            QMenu::item {{ 
                padding: 8px 30px; 
                border-radius: 6px; 
            }}
            QMenu::item:selected {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 {color}aa); 
                color: white; 
            }}
            QDockWidget {{ 
                color: {color}; 
                font-weight: 800; 
                border: 1px solid {border}; 
                {texture_prop}
            }}
            QDockWidget::title {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {nav_bg}, stop:1 {bg}); 
                padding: 12px; 
                border-bottom: 2px solid {color}; 
                font-size: 14px;
            }}
            QListWidget {{ 
                background-color: transparent; 
                border: none; 
                color: {fg}; 
            }}
            QListWidget::item {{ 
                padding: 15px; 
                border-bottom: 1px solid {border}55; 
                margin: 4px 8px;
                border-radius: 10px;
            }}
            QListWidget::item:hover {{ 
                background-color: {color}0a; 
            }}
            QListWidget::item:selected {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}22, stop:1 {color}44); 
                color: {color}; 
                border-left: 4px solid {color};
            }}
            QScrollBar:vertical {{ 
                border: none; 
                background: transparent; 
                width: 12px; 
                margin: 0;
            }}
            QScrollBar::handle:vertical {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}44, stop:1 {color}88); 
                border-radius: 6px; 
                min-height: 30px; 
                margin: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
        """

    @staticmethod
    def apply_palette(app, dark=True, window_color=None):
        palette = QPalette()
        if window_color:
            w_color = QColor(window_color) if isinstance(window_color, str) else window_color
        else:
            w_color = QColor(43, 43, 43) if dark else QColor(245, 245, 245)
        
        palette.setColor(QPalette.Window, w_color)
        palette.setColor(QPalette.WindowText, Qt.white if dark else Qt.black)
        palette.setColor(QPalette.Base, QColor(30, 30, 30) if dark else QColor(255, 255, 255))
        palette.setColor(QPalette.Text, Qt.white if dark else Qt.black)
        palette.setColor(QPalette.Button, QColor(60, 60, 60) if dark else QColor(225, 225, 225))
        palette.setColor(QPalette.ButtonText, Qt.white if dark else Qt.black)
        palette.setColor(QPalette.Highlight, QColor(74, 158, 255))
        app.setPalette(palette)

class SlothSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, parent):
        super().__init__(parent)
        self.browser = parent
        self._active_jobs = {} # Persist buffers until job is destroyed

    def requestStarted(self, job):


        url_obj = job.requestUrl()
        url = url_obj.toString().rstrip('/')
        host = url_obj.host().lower()
        path = url_obj.path().lower()
        
        # Shared Styles for Internal Pages
        accent = self.browser.accent_color
        
        style = f"""
            <style>
                :root {{ 
                    --accent: {accent}; 
                    --bg: {("#0f0f0f" if self.browser.dark_theme else "#f5f5f7")}; 
                    --fg: {("#f0f0f0" if self.browser.dark_theme else "#1d1d1f")}; 
                    --glass: {("rgba(255, 255, 255, 0.05)" if self.browser.dark_theme else "rgba(0, 0, 0, 0.03)")}; 
                    --border: {("rgba(255, 255, 255, 0.1)" if self.browser.dark_theme else "rgba(0, 0, 0, 0.1)")};
                }}
                body {{ 
                    background: var(--bg); 
                    color: var(--fg); 
                    font-family: system-ui, -apple-system, sans-serif; 
                    margin: 0; 
                    padding: 40px 20px; 
                    display: flex; 
                    flex-direction: column; 
                    align-items: center; 
                    min-height: 100vh; 
                    overflow-x: hidden; 
                    transition: background 0.3s, color 0.3s;
                }}
                .container {{ 
                    background: var(--glass); 
                    backdrop-filter: blur(30px); 
                    -webkit-backdrop-filter: blur(30px);
                    border: 1px solid var(--border); 
                    border-radius: 28px; 
                    padding: 50px; 
                    width: 100%; 
                    max-width: 900px; 
                    box-shadow: 0 40px 100px -20px rgba(0,0,0,0.5); 
                    animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1); 
                }}
                @keyframes fadeUp {{ 
                    from {{ opacity: 0; transform: translateY(30px); }} 
                    to {{ opacity: 1; transform: translateY(0); }} 
                }}
                h1 {{ 
                    font-size: 3.5rem; 
                    font-weight: 800; 
                    margin: 0 0 15px; 
                    background: linear-gradient(135deg, var(--fg) 30%, var(--accent) 100%); 
                    -webkit-background-clip: text; 
                    -webkit-text-fill-color: transparent; 
                    letter-spacing: -2px; 
                    text-align: center; 
                }}
                p {{ 
                    line-height: 1.6; 
                    color: var(--fg); 
                    opacity: 0.7;
                    font-size: 1.1rem; 
                    text-align: center; 
                    max-width: 600px;
                    margin: 0 auto 30px;
                }}
                .grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); 
                    gap: 16px; 
                    width: 100%; 
                    margin-top: 30px; 
                }}
                .module-card {{ 
                    background: var(--glass); 
                    border: 1px solid var(--border); 
                    border-radius: 20px; 
                    padding: 24px; 
                    display: flex; 
                    flex-direction: column; 
                    align-items: center; 
                    text-decoration: none; 
                    color: var(--fg); 
                    transition: 0.3s cubic-bezier(0.25, 1, 0.5, 1); 
                }}
                .module-card:hover {{ 
                    background: var(--accent); 
                    color: white;
                    border-color: var(--accent); 
                    transform: translateY(-8px) scale(1.02); 
                    box-shadow: 0 20px 40px -10px var(--accent);
                }}
                .module-card:hover .module-icon {{ transform: scale(1.1); }}
                .module-icon {{ font-size: 2.5rem; margin-bottom: 12px; transition: 0.3s; }}
                .module-title {{ font-weight: 700; font-size: 0.95rem; }}
                
                .btn {{ 
                    display: inline-flex; 
                    align-items: center; 
                    justify-content: center; 
                    padding: 12px 28px; 
                    background: var(--accent); 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 14px; 
                    font-weight: 700; 
                    transition: 0.3s; 
                    border: none; 
                    cursor: pointer; 
                    margin: 5px; 
                }}
                .btn:hover {{ 
                    filter: brightness(1.1); 
                    transform: translateY(-3px); 
                    box-shadow: 0 12px 24px -6px var(--accent); 
                }}
                .btn-secondary {{ background: var(--glass); color: var(--fg); border: 1px solid var(--border); }}
                .btn-secondary:hover {{ background: var(--border); }}
                
                .card {{ 
                    background: var(--glass); 
                    border-radius: 18px; 
                    padding: 24px; 
                    margin-bottom: 16px; 
                    display: flex; 
                    justify-content: space-between; 
                    align-items: center; 
                    border: 1px solid var(--border); 
                    transition: 0.2s; 
                }}
                .card:hover {{ border-color: var(--accent); background: var(--border); }}
                .card-title {{ font-weight: 700; font-size: 1rem; margin-bottom: 4px; }}
                .card-meta {{ font-size: 0.85rem; opacity: 0.6; }}
                
                input, select {{
                    padding: 12px 20px;
                    border-radius: 14px;
                    background: var(--glass);
                    border: 1px solid var(--border);
                    color: var(--fg);
                    outline: none;
                    font-size: 1rem;
                    transition: 0.2s;
                }}
                input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 4px {accent}33; }}
            </style>
        """
        
        common_head = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>"
        
        html = None
        if url == "sloth://home" or host == "home":
            html = f"{common_head}<body><div class='container'>" \
                   f"<h1 style='font-size:4rem; margin-bottom:5px; background: linear-gradient(to right, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>SLOTH PLATINUM</h1>" \
                   f"<p style='font-size:1.2rem; opacity:0.6; margin-bottom:40px;'>Navigation Hub & System Dashboard</p>" \
                   f"<div class='grid'>" \
                   f"<a href='sloth://settings' class='module-card'><span class='module-icon'>⚙️</span><span class='module-title'>Settings</span></a>" \
                   f"<a href='sloth://bookmarks' class='module-card'><span class='module-icon'>📑</span><span class='module-title'>Bookmarks</span></a>" \
                   f"<a href='sloth://downloads' class='module-card'><span class='module-icon'>⬇️</span><span class='module-title'>Downloads</span></a>" \
                   f"<a href='sloth://history' class='module-card'><span class='module-icon'>🕒</span><span class='module-title'>History</span></a>" \
                   f"<a href='sloth://passwords' class='module-card'><span class='module-icon'>🔐</span><span class='module-title'>Passwords</span></a>" \
                   f"<a href='sloth://gpu' class='module-card'><span class='module-icon'>📟</span><span class='module-title'>GPU & System</span></a>" \
                   f"<a href='sloth://stats' class='module-card'><span class='module-icon'>📊</span><span class='module-title'>Statistics</span></a>" \
                   f"<a href='sloth://help' class='module-card'><span class='module-icon'>❓</span><span class='module-title'>Help</span></a>" \
                   f"<a href='sloth://extensions' class='module-card'><span class='module-icon'>🧩</span><span class='module-title'>Extensions</span></a>" \
                   f"<a href='sloth://about' class='module-card'><span class='module-icon'>ℹ️</span><span class='module-title'>About</span></a>" \
                   f"<a href='sloth://update' class='module-card'><span class='module-icon'>🔁</span><span class='module-title'>Update</span></a>" \
                   f"<a href='sloth://arcade' class='module-card arcade-card'><span class='tag'>Live</span><span class='module-icon'>🎮</span><span class='module-title'>Arcade Lab</span></a>" \
                   f"<a href='sloth://flags' class='module-card'><span class='module-icon'>🚩</span><span class='module-title'>Flags</span></a>" \
                   f"</div>" \
                   f"<div style='margin-top:50px;'>" \
                   f"  <h3 style='text-align:left; color:var(--accent); margin-bottom:15px; border-left:4px solid var(--accent); padding-left:15px;'>⚡ Quick Access</h3>" \
                   f"  <div class='grid' style='grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));'>" \
                   f"    <a href='https://www.google.com' class='module-card' style='padding:15px;'><span style='font-size:1.2rem;'>Google</span></a>" \
                   f"    <a href='https://www.youtube.com' class='module-card' style='padding:15px;'><span style='font-size:1.2rem;'>YouTube</span></a>" \
                   f"    <a href='https://github.com' class='module-card' style='padding:15px;'><span style='font-size:1.2rem;'>GitHub</span></a>" \
                   f"    <a href='https://discord.com' class='module-card' style='padding:15px;'><span style='font-size:1.2rem;'>Discord</span></a>" \
                   f"    <a href='https://chatgpt.com' class='module-card' style='padding:15px;'><span style='font-size:1.2rem;'>ChatGPT</span></a>" \
                   f"  </div>" \
                   f"</div>" \
                   f"<div style='margin-top:40px; text-align:center;'>" \
                   f"  <form action='https://cse.google.com/cse' method='GET' style='display:flex; width:100%; max-width:600px; margin:0 auto;'>" \
                   f"    <input type='hidden' name='cx' value='666b70a81f11c4eb9'>" \
                   f"    <input type='text' name='q' placeholder='Search the Grid...' style='padding:15px 25px; border-radius:50px 0 0 50px; border:1px solid rgba(255,255,255,0.1); background:rgba(255,255,255,0.05); color:white; width:100%; outline:none; font-size:1.1rem;'>" \
                   f"    <button type='submit' style='padding:15px 30px; border-radius:0 50px 50px 0; border:none; background:var(--accent); color:white; font-weight:bold; cursor:pointer;'>Search</button>" \
                   f"  </form>" \
                   f"</div>" \
                   f"<iframe src='https://parkertrip.github.io/newtab' sandbox='allow-scripts allow-same-origin allow-forms allow-popups' style='width:100%; height:800px; border:1px solid var(--border); border-radius:24px; margin-top:40px; background:var(--bg);'></iframe>" \
                   f"</div></body></html>"
        elif url == "sloth://arcade" or host == "arcade":
            html = f"""{common_head}
            <body style='background: var(--bg); color: var(--fg); font-family:sans-serif;'>
                <div class='container'>
                    <h1 style='text-align:center; font-size:3rem; margin-bottom:10px;'>🎮 Arcade Lab</h1>
                    <p style='text-align:center; opacity:0.7;'>High-performance grid gaming.</p>
                    
                    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:30px; margin-top:30px;'>
                        <!-- Neon Snake -->
                        <div class='card' style='display:block;'>
                            <h2 style='color:#00ff88; margin-top:0;'>🐍 Neon Snake</h2>
                            <canvas id='snakeGame' width='300' height='300' style='background:#000; display:block; margin:10px auto; border:2px solid #00ff88; image-rendering:pixelated;'></canvas>
                            <div style='text-align:center; margin-top:10px;'>
                                <div id='s-score' style='font-family:monospace; margin-bottom:10px;'>Score: 0</div>
                                <button class='btn' onclick='startSnake()' style='background:#00ff88; color:#000;'>Start Snake</button>
                            </div>
                        </div>

                        <!-- Neon Clicker -->
                        <div class='card' style='display:block;'>
                            <h2 style='color:#ff00ff; margin-top:0;'>⚡ Neon Surge</h2>
                            <div id='clickerArea' style='height:300px; background:rgba(255,0,255,0.05); border:2px solid #ff00ff; border-radius:12px; display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer;' onclick='surgeClick()'>
                                <div style='font-size:4rem;'>⚡</div>
                                <div id='surge-count' style='font-size:2.5rem; font-weight:bold; font-family:monospace;'>0</div>
                                <div style='opacity:0.6;'>CLICK TO SURGE</div>
                            </div>
                            <div style='text-align:center; margin-top:10px;'>
                                <div id='surge-pps' style='font-size:0.8rem; opacity:0.5;'>Energy / sec: 0</div>
                                <button class='btn' onclick='resetSurge()' style='background:#ff00ff;'>Reset Surge</button>
                            </div>
                        </div>
                    </div>

                    <script>
                        // --- Snake Engine ---
                        const sc=document.getElementById('snakeGame'),sx=sc.getContext('2d');
                        let s,f,dx,dy,sz=15,sScore=0,sInterval;
                        function startSnake() {{
                            clearInterval(sInterval);
                            s=[{{x:10,y:10}}]; f={{x:15,y:15}}; dx=1; dy=0; sScore=0;
                            sInterval=setInterval(drawSnake, 100);
                        }}
                        function drawSnake() {{
                            sx.fillStyle='#000'; sx.fillRect(0,0,300,300);
                            sx.fillStyle='#00ff88'; s.forEach(p=>sx.fillRect(p.x*sz,p.y*sz,sz-1,sz-1));
                            sx.fillStyle='#ff0000'; sx.fillRect(f.x*sz,f.y*sz,sz-1,sz-1);
                            let nh={{x:s[0].x+dx,y:s[0].y+dy}};
                            if(nh.x<0||nh.x>=20||nh.y<0||nh.y>=20||s.some(p=>p.x==nh.x&&p.y==nh.y)) {{
                                clearInterval(sInterval); alert("GAME OVER! Score: " + sScore); return;
                            }}
                            s.unshift(nh);
                            if(nh.x==f.x&&nh.y==f.y){{
                                sScore++; document.getElementById('s-score').innerText="Score: "+sScore;
                                f={{x:Math.floor(Math.random()*20),y:Math.floor(Math.random()*20)}};
                            }} else {{ s.pop(); }}
                        }}
                        document.addEventListener('keydown', e=>{{
                            if(e.key=='ArrowUp'&&dy==0){{dx=0;dy=-1}}
                            if(e.key=='ArrowDown'&&dy==0){{dx=0;dy=1}}
                            if(e.key=='ArrowLeft'&&dx==0){{dx=-1;dy=0}}
                            if(e.key=='ArrowRight'&&dx==0){{dx=1;dy=0}}
                        }});

                        // --- Surge Clicker ---
                        let energy=0;
                        function surgeClick() {{
                            energy++; 
                            document.getElementById('surge-count').innerText = energy;
                            const area = document.getElementById('clickerArea');
                            if(area) {{
                                area.style.transform = 'scale(0.95)';
                                setTimeout(() => area.style.transform = 'scale(1)', 50);
                            }}
                        }}
                        function resetSurge() {{ 
                            energy=0; 
                            document.getElementById('surge-count').innerText = '0'; 
                        }}
                        
                        // Ensure event listeners are attached
                        document.addEventListener('DOMContentLoaded', () => {{
                            const clickArea = document.getElementById('clickerArea');
                            if(clickArea) clickArea.addEventListener('click', surgeClick);
                        }});
                    </script>
                    
                    <div style='margin-top:40px; text-align:center;'><a href='sloth://home' class='btn btn-secondary'>← Back to Dashboard</a></div>
                </div>
            </body></html>"""
        elif url == "sloth://settings" or host == "settings":
            title = "Settings"
            is_settings = True
            
            if is_settings:
                # Toolbar order
                order = self.browser.config_manager.get("toolbar_order", ["back", "forward", "reload", "home", "url_bar", "new_tab", "sidebar", "settings", "downloads"])
                order_str = ",".join(order)
                
                # Home URL
                h_url = self.browser.config_manager.get("home_url", "sloth://home")
                
                content = f"""
                    <div class='card' style='display:block;'>
                        <h2 style='color:var(--accent); margin-top:0;'>🎨 Appearance & Layout</h2>
                        <div style='display:flex; flex-direction:column; gap:15px;'>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Home Page URL</span>
                                <div style='display:flex; gap:10px;'>
                                    <input type='text' id='h-url' value='{h_url}' style='width:250px; background:rgba(255,255,255,0.05); color:white; border:1px solid var(--border); padding:8px; border-radius:8px;'>
                                    <button class='btn' onclick='window.location.href="sloth://set-home?u="+encodeURIComponent(document.getElementById("h-url").value)'>Set</button>
                                </div>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>New Tab URL</span>
                                <div style='display:flex; gap:10px;'>
                                    <input type='text' id='nt-url' value='{self.browser.config_manager.get("new_tab_url", "sloth://home")}' style='width:250px; background:rgba(255,255,255,0.05); color:white; border:1px solid var(--border); padding:8px; border-radius:8px;'>
                                    <button class='btn' onclick='window.location.href="sloth://set-nt?u="+encodeURIComponent(document.getElementById("nt-url").value)'>Set as New Tab</button>
                                </div>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Set Active as Home</span>
                                <button class='btn' onclick='window.location.href="sloth://set-current-home"'>Current Page</button>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Set Active as New Tab</span>
                                <button class='btn' onclick='window.location.href="sloth://set-current-nt"'>Current Page</button>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Site Customizations</span>
                                <button class='btn' style='background:#ff4444; border-color:#ff4444;' onclick='if(confirm("Clear all element restyling?")) window.location.href="sloth://clear-customizations"'>Reset All</button>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Theme Mode</span>
                                <button class='btn' onclick='window.location.href="sloth://toggle-theme"'>{("Switch to Light" if self.browser.dark_theme else "Switch to Dark")}</button>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Accent Color</span>
                                <input type='color' value='{accent}' onchange='window.location.href="sloth://set-color?c="+this.value.replace("#", "")' style='width:50px; height:40px; border:none; background:none; cursor:pointer;'>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>UI Texture</span>
                                <select onchange='window.location.href="sloth://set-texture?t="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:8px;'>
                                    <option value='none' {"selected" if self.browser.config_manager.get("ui_texture")=="none" else ""}>Clean</option>
                                    <option value='noise' {"selected" if self.browser.config_manager.get("ui_texture")=="noise" else ""}>Noise</option>
                                    <option value='stripes' {"selected" if self.browser.config_manager.get("ui_texture")=="stripes" else ""}>Stripes</option>
                                    <option value='grid' {"selected" if self.browser.config_manager.get("ui_texture")=="grid" else ""}>Grid</option>
                                </select>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Default Font Size</span>
                                <select onchange='window.location.href="sloth://set-font-size?s="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:8px;'>
                                    <option value='12' {"selected" if self.browser.config_manager.get("font_size")==12 else ""}>Small</option>
                                    <option value='16' {"selected" if self.browser.config_manager.get("font_size")==16 or not self.browser.config_manager.get("font_size") else "selected"}>Medium</option>
                                    <option value='20' {"selected" if self.browser.config_manager.get("font_size")==20 else ""}>Large</option>
                                    <option value='24' {"selected" if self.browser.config_manager.get("font_size")==24 else ""}>Extra Large</option>
                                </select>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Default Zoom</span>
                                <select onchange='window.location.href="sloth://set-zoom?z="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:8px;'>
                                    <option value='0.8' {"selected" if self.browser.config_manager.get("zoom")==0.8 else ""}>80%</option>
                                    <option value='1.0' {"selected" if self.browser.config_manager.get("zoom")==1.0 or not self.browser.config_manager.get("zoom") else "selected"}>100%</option>
                                    <option value='1.2' {"selected" if self.browser.config_manager.get("zoom")==1.2 else ""}>120%</option>
                                    <option value='1.5' {"selected" if self.browser.config_manager.get("zoom")==1.5 else ""}>150%</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div class='card' style='display:block;'>
                        <h2 style='color:var(--accent); margin-top:0;'>🔧 Toolbar Engine</h2>
                        <p style='font-size:0.8rem; opacity:0.7;'>Reorder your grid buttons. Available IDs: back, forward, reload, home, url_bar, new_tab, sidebar, settings, downloads, privacy</p>
                        <input type='text' id='t-order' value='{order_str}' style='width:100%; margin:10px 0;'>
                        <button class='btn' style='width:100%; background:var(--accent);' onclick='window.location.href="sloth://set-toolbar?o="+document.getElementById("t-order").value'>Update Toolbar Grid</button>
                    </div>

                    <div class='card' style='display:block;'>
                        <h2 style='color:var(--accent); margin-top:0;'>🧭 Navigation</h2>
                        <div style='display:flex; flex-direction:column; gap:15px;'>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Nav Position</span>
                                <select onchange='window.location.href="sloth://set-nav?p=\"+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:8px;'>
                                    <option value='top' {"selected" if self.browser.nav_pos=="top" else ""}>Top</option>
                                    <option value='bottom' {"selected" if self.browser.nav_pos=="bottom" else ""}>Bottom</option>
                                </select>
                            </div>
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span>Tabs Position</span>
                                <button class='btn' onclick='window.location.href="sloth://toggle-layout"'>Toggle Top/Side Tabs</button>
                            </div>
                        </div>
                    </div>
                """
            else:
                content = f"""
                    <div class='card' style='display:block; text-align:center;'>
                        <div style='font-size:4rem;'>🦥</div>
                        <h1>Sloth Web Platinum</h1>
                        <p>Version {__version__}</p>
                        <p style='opacity:0.7;'>The ultimate minimalist browsing grid.</p>
                        <div style='margin-top:20px;'><a href='https://github.com/parkertripoli-wq/sloth-web' class='btn'>View Source</a></div>
                    </div>
                """
            
            html = f"{common_head}<body><div class='container'><h1>{title}</h1><div class='grid'>{content}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://bookmarks" or host == "bookmarks":
            bm_items = ""
            for b in self.browser.bookmarks:
                b_url = b.get('url', '#') if isinstance(b, dict) else str(b)
                short_url = b_url.replace('https://','').replace('http://','')[:50]
                bm_items += f"<div class='card bookmark-item'><div><div class='card-title'>{title}</div><div class='card-meta'>{short_url}</div></div><div style='display:flex; gap:10px;'><a href='{b_url}' class='btn' style='margin:0;'>Open</a><a href='sloth://delete-bookmark?u={urllib.parse.quote(b_url)}' class='btn' style='margin:0; background:#ff4444;'>Delete</a></div></div>"
            
            html = f"""{common_head}<body><div class='container'><h1>Your Bookmarks</h1>
                   <div style='margin-bottom:20px;'><input type='text' id='bookmarkSearch' placeholder='Filter bookmarks...' onkeyup='filterBookmarks()' style='width:100%; padding:12px 20px; border-radius:12px; background:rgba(255,255,255,0.05); color:white; border:1px solid var(--accent); outline:none;'></div>
                   <div id='bookmarkList'>{bm_items}</div>
                   <script>
                   function filterBookmarks() {{
                       let q = document.getElementById('bookmarkSearch').value.toLowerCase();
                       document.querySelectorAll('.bookmark-item').forEach(i => {{
                           i.style.display = i.innerText.toLowerCase().includes(q) ? 'flex' : 'none';
                       }});
                   }}
                   </script>
                   <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"""
        elif url == "sloth://history" or host == "history":
            items = "".join([f"<div class='card'><div><div class='card-meta'>{h['time']} • {h['url'][:60]}...</div><div class='card-title'>{h['title'][:50]}</div></div><a href='{h['url']}' class='btn' style='margin:0;'>Return</a></div>" for h in reversed(self.browser.history_manager.history)])
            html = f"{common_head}<body><div class='container'><h1>History</h1><div style='text-align:center; margin-bottom:20px;'><a href='sloth://clear-history' class='btn' style='background:#ff4444;'>Clear History</a></div><div style='margin-top:20px;'>{items or '<p style=\"text-align:center; padding:40px;\">Browsing history will appear here as you explore the grid.</p>'}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://downloads" or host == "downloads":
            items = "".join([f"<div class='card'><div><div class='card-title'>{os.path.basename(d['path'])}</div><p style='margin:0; font-size:0.9rem;'>Status: Downloaded</p></div><a href='file:///{os.path.dirname(d['path']).replace(os.sep, '/')}' class='btn' style='margin:0;'>Open Folder</a></div>" for d in reversed(self.browser.downloads)])
            html = f"{common_head}<body><div class='container'><h1>Downloads</h1><div style='margin-top:20px;'>{items or '<p style=\"text-align:center; padding:40px;\">Downloaded files will appear here.</p>'}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://help" or host == "help":
            html = f"{common_head}<body><div class='container'><h1>Help & Shortcuts</h1><div class='shortcut-list'><div class='card'><span>New Tab</span><span class='btn btn-secondary'>Ctrl + T</span></div><div class='card'><span>Close Tab</span><span class='btn btn-secondary'>Ctrl + W</span></div><div class='card'><span>Reload Page</span><span class='btn btn-secondary'>Ctrl + R</span></div><div class='card'><span>Dashboard</span><span class='btn btn-secondary'>Alt + Home</span></div><div class='card'><span>Settings</span><span class='btn btn-secondary'>Ctrl + ,</span></div><div class='card'><span>History</span><span class='btn btn-secondary'>Ctrl + H</span></div></div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://about" or host == "about":
            html = f"""{common_head}<body><div class='container' style='padding:0; max-width:100%;'>
                <div style='position:relative; width:100%; height:90vh;'>
                    <iframe src='https://parkertrip.github.io/slothweb' style='position:absolute; top:0; left:0; width:100%; height:100%; border:none; border-radius:12px;'></iframe>
                </div>
                <div style='padding:20px; text-align:center;'>
                    <a href='sloth://home' class='btn btn-secondary'>← Return to Grid</a>
                </div>
            </div></body></html>"""
        elif url == "sloth://update" or host == "update":
            html = f"{common_head}<body><div class='container' style='max-width:500px;'><h1>Update Sloth</h1><p>Current Version: <b>{__version__}</b></p><div style='text-align:center; margin-top:30px;'><a href='sloth://force-update' class='btn' style='background:#ffaa00; width:100%;'>Check for Updates</a></div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://stats" or host == "stats":
            tab_count = self.browser.tabs.count()
            history_count = len(self.browser.history_manager.history)
            bookmark_count = len(self.browser.bookmarks)
            html = f"""{common_head}<body><div class='container'>
                <h1>📊 Usage Statistics</h1>
                <p>Tracking your journey through the grid.</p>
                <div class='grid'>
                    <div class='card'><div><div class='card-title'>Active Tabs</div><div class='card-meta'>{tab_count} open tabs</div></div></div>
                    <div class='card'><div><div class='card-title'>History</div><div class='card-meta'>{history_count} items logged</div></div></div>
                    <div class='card'><div><div class='card-title'>Bookmarks</div><div class='card-meta'>{bookmark_count} sites saved</div></div></div>
                </div>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div>
            </div></body></html>"""
        elif url == "sloth://flags" or host == "flags":
            flags_text = "\n".join(self.browser.config_manager.get("chromium_flags", CHROMIUM_FLAGS))
            html = f"""{common_head}<body><div class='container'>
                <h1>🚩 Engine Flags</h1>
                <p>Modify Chromium launch flags. Enter one flag per line. <b>Requires restart to apply.</b></p>
                <form action='sloth://save-flags' method='GET' style='width:100%;'>
                    <textarea name='f' style='width:100%; height:300px; background:rgba(0,0,0,0.2); color:var(--fg); border:1px solid var(--accent); border-radius:14px; padding:15px; font-family:monospace; outline:none; resize:vertical;'>{flags_text}</textarea>
                    <div style='text-align:center; margin-top:20px;'>
                        <button type='submit' class='btn' style='width:100%; max-width:300px;'>Save & Restart Engine</button>
                    </div>
                </form>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div>
            </div></body></html>"""
        elif url.startswith("sloth://save-flags"):
            try:
                # Use urllib to properly decode the textarea content
                query = urllib.parse.parse_qs(url_obj.query())
                if 'f' in query:
                    new_flags = [f.strip() for f in query['f'][0].split('\n') if f.strip()]
                    self.browser.config_manager.set("chromium_flags", new_flags)
                    self.browser.log("Flags updated. Restarting...")
                    # Trigger restart
                    QTimer.singleShot(500, lambda: os.execl(sys.executable, sys.executable, *sys.argv))
            except Exception as e:
                print(f"Failed to save flags: {e}")
            html = f"<html><body><p>Restarting...</p><script>window.location.href='sloth://home'</script></body></html>"
        elif url == "sloth://passwords" or host == "passwords":
            pws = self.browser.password_manager.passwords
            items = ""
            for site, list_pws in pws.items():
                for i, p in enumerate(list_pws):
                    # Use unquote and quote to ensure site names with spaces or dots don't break the URL
                    safe_site = urllib.parse.quote(site)
                    items += f"<div class='card'><div style='flex:1;'><div class='card-title'>{site}</div><div class='card-meta'>User: {p['user']} | Pass: {'•'*len(p['pass'])}</div></div><a href='sloth://delete-password?s={safe_site}&i={i}' class='btn' style='background:#ff4444; margin:0;'>Delete</a></div>"
            html = f"""{common_head}<body><div class='container'>
                <h1>🔐 Saved Passwords</h1>
                
                <div class='card' style='background:rgba(255,255,255,0.02); display:block;'>
                    <h3>Add Password Manually</h3>
                    <div style='display:flex; gap:10px; margin-top:10px;'>
                        <input type='text' id='m_site' placeholder='Site (e.g. google.com)' style='flex:1;'>
                        <input type='text' id='m_user' placeholder='Username' style='flex:1;'>
                        <input type='password' id='m_pass' placeholder='Password' style='flex:1;'>
                        <button class='btn' onclick='window.location.href="sloth://add-password?s="+document.getElementById("m_site").value+"&u="+document.getElementById("m_user").value+"&p="+document.getElementById("m_pass").value'>Add Entry</button>
                    </div>
                </div>

                <div style='margin-top:20px;'>{items or '<p style="text-align:center; padding:40px;">No passwords saved in the vault yet.</p>'}</div>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div>
            </div></body></html>"""
        elif url.startswith("sloth://delete-password"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                site = urllib.parse.unquote(query.get('s', [''])[0])
                idx_str = query.get('i', ['-1'])[0]
                idx = int(idx_str)
                if site and idx >= 0:
                    self.browser.password_manager.delete_password(site, idx)
            except Exception as e:
                self.browser.log(f"Delete error: {e}")
            html = f"<html><body><script>window.location.href='sloth://passwords'</script></body></html>"
        elif url == "sloth://export":
            self.browser.export_data()
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url == "sloth://import":
            self.browser.import_data()
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url.startswith("sloth://set-nt"):
            try:
                query_str = url_obj.toString().split('?', 1)[1] if '?' in url_obj.toString() else ''
                q = urllib.parse.parse_qs(query_str)
                u = q.get('u', [''])[0]
                if u:
                    u = urllib.parse.unquote(u)
                    if not u.startswith(("http", "sloth:")): u = "https://" + u
                    self.browser.config_manager.set("new_tab_url", u)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://gpu" or host == "gpu":
            import platform as pf
            info = {
                "OS": f"{pf.system()} {pf.release()}",
                "Processor": pf.processor(),
                "Python": pf.python_version(),
                "Architecture": pf.machine(),
                "Browser Engine": "QtWebEngine (Chromium Based)",
                "Acceleration": "Hardware Accelerated (GPU)"
            }
            items = "".join([f"<div class='card'><div><div class='card-title'>{k}</div><div class='card-meta'>{v}</div></div></div>" for k, v in info.items()])
            html = f"{common_head}<body><div class='container'><h1>📟 System & GPU</h1><p>Active environment details and acceleration status.</p><div style='margin-top:20px;'>{items}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://force-update":
            self.browser.update_manager.check_for_updates(force=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://update'></head></html>"
        elif url == "sloth://extensions" or host == "extensions":
            ext_path = os.path.abspath("extensions")
            html = f"{common_head}<body><div class='container'><h1>🧩 Extension Engine</h1><p>Expand your grid with custom capabilities.</p>" \
                   f"<div style='background:rgba(255,255,255,0.03); border-radius:16px; padding:25px; margin:20px 0; border:1px solid rgba(255,255,255,0.05);'>" \
                   f"<p>Extensions are loaded from the <b>extensions</b> folder in the Sloth directory.</p>" \
                   f"<code style='background:#000; padding:10px; border-radius:8px; display:block; margin:10px 0; color:var(--accent); overflow-x:auto;'>{ext_path}</code>" \
                   f"<p style='font-size:0.9rem; opacity:0.8;'>Simply drop any <code>.js</code> file into this folder to inject it into every page you visit.</p>" \
                   f"</div>" \
                   f"<div style='display:flex; gap:15px; justify-content:center; margin-top:20px;'>" \
                   f"<a href='https://parkertripoli-wq.github.io/' class='btn' style='background:#ff00ff;'>Open Sloth Store</a>" \
                   f"<a href='https://chromewebstore.google.com/' class='btn' style='background:#4285f4;'>Open Chrome Store (WIP)</a>" \
                   f"</div>" \
                   f"<p style='margin-top:15px; color:#aaa; font-style:italic;'>Both Sloth and standard Chrome-compatible scripts are supported.</p>" \
                   f"<div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://clear-history":
            self.browser.history_manager.history = []
            self.browser.history_manager.save()
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://history'></head></html>"
        elif url == "sloth://newtab" or host == "newtab" or path == "/":
             nt_url = self.browser.config_manager.get("new_tab_url", "sloth://home")
             html = f"<html><head><meta http-equiv='refresh' content='0; url={nt_url}'></head></html>"
        elif url.startswith("sloth://set-color"):
            try:
                color = "#" + url.split("?c=")[1]
                self.browser.accent_color = color
                self.browser.config_manager.set("accent_color", color)
                self.browser.apply_theme()
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://toggle-theme":
            self.browser.dark_theme = not self.browser.dark_theme
            self.browser.config_manager.set("dark_theme", self.browser.dark_theme)
            self.browser.apply_theme()
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-texture"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                t = query.get('t', ['none'])[0]
                self.browser.config_manager.set("ui_texture", t)
                self.browser.apply_theme()
            except: pass
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url.startswith("sloth://set-toolbar"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                order = query.get('o', [''])[0].split(",")
                if order:
                    self.browser.config_manager.set("toolbar_order", order)
                    self.browser.log("Toolbar updated. Restart to apply changes.", notify=True)
            except: pass
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url == "sloth://toggle-layout":
            self.browser.toggle_layout()
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://bookmark-setup":
            self.browser.bookmarks.append({"title": "Sloth Setup", "url": "sloth://start"})
            save_bookmarks(self.browser.bookmarks_file, self.browser.bookmarks)
            self.browser.log("Setup page bookmarked!", notify=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://start'></head></html>"
        elif url == "sloth://start" or host == "start":
            html = f"""{common_head}
            <body style='padding:0; overflow-x:hidden; background: var(--bg); color: var(--fg);'>
                <div class='container' style='max-width:1000px; min-height:100vh; padding:60px 20px; box-sizing:border-box; background:transparent; border:none; box-shadow:none;'>
                    <h1 style='font-size:3.5rem; margin-bottom:10px; background: linear-gradient(to right, #00ffee, #ff0099); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Welcome to Sloth Platinum</h1>
                    <p style='font-size:1.3rem; opacity:0.8; margin-bottom:50px;'>Let's get you set up for the ultimate browsing experience.</p>
                    
                    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:30px; width:100%;'>
                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent);'>1. Data Backup (.sw)</h2>
                            <p>Export all your bookmarks, passwords, and history to a single <b>.sw</b> file. You can import it later to restore your grid.</p>
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <a href='sloth://export' class='btn' style='background:var(--accent); flex:1;'>📤 Export .sw File</a>
                                <a href='sloth://import' class='btn' style='background:#666; flex:1;'>📥 Import .sw File</a>
                            </div>
                        </div>
                        
                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent);'>2. UI Appearance</h2>
                            <p>Select your grid texture and base accent color.</p>
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <select onchange='window.location.href="sloth://set-texture?t="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:10px; flex:1;'>
                                    <option value='none'>Clean</option>
                                    <option value='noise'>Noise</option>
                                    <option value='stripes'>Stripes</option>
                                    <option value='grid'>Grid</option>
                                </select>
                                <input type='color' value='{accent}' onchange='window.location.href="sloth://set-color?c="+this.value.replace("#", "")' style='width:50px; height:45px; border:none; background:none; cursor:pointer;'>
                            </div>
                        </div>
                    </div>

                    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:30px; width:100%; margin-top:30px;'>
                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent);'>3. Privacy & AdBlock</h2>
                            <p>Sloth blocks ads by default. You can toggle strict mode or clear your grid footprint.</p>
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <a href='sloth://toggle-privacy' class='btn' style='background:#ff4444; flex:1;'>🛡️ Toggle Privacy</a>
                                <a href='sloth://clear-history' class='btn' style='background:#666; flex:1;'>🧹 Purge Grid</a>
                            </div>
                        </div>
                        
                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent);'>4. Search Engine</h2>
                            <p>Choose your primary entry point into the grid.</p>
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <select onchange='window.location.href="sloth://set-search?s="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:10px; flex:1;'>
                                    <option value='google'>Google (CSE)</option>
                                    <option value='bing'>Bing</option>
                                    <option value='duckduckgo'>DuckDuckGo</option>
                                    <option value='yahoo'>Yahoo</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div class='card' style='display:block; margin-top:30px;'>
                        <h2 style='color:var(--accent);'>5. Customise Anything (Tutorial)</h2>
                        <div style='display:flex; gap:20px; align-items:center;'>
                            <div style='flex:1;'>
                                <p>Sloth allows you to restyle <b>any</b> element on <b>any</b> website. Simply right-click an element and select <b>'Customize Element'</b>.</p>
                                <p>You can also use <b>Ctrl+U</b> to open the source or <b>Ctrl+Shift+I</b> for Sloth DevTools.</p>
                            </div>
                            <div style='width:200px; height:120px; background:rgba(255,255,255,0.05); border:1px dashed var(--accent); border-radius:12px; display:flex; align-items:center; justify-content:center; text-align:center; padding:10px;'>
                                💡 Tip: Try hiding annoying ads with the context menu!
                            </div>
                        </div>
                    </div>

                    <div style='display:grid; grid-template-columns: 1fr 1fr 1fr; gap:20px; width:100%; margin-top:30px;'>
                        <div class='card' style='display:block; text-align:center;'>
                            <span style='font-size:2rem;'>⚡</span>
                            <h3>Performance</h3>
                            <p>GPU Acceleration and multi-threaded rendering are active.</p>
                        </div>
                        <div class='card' style='display:block; text-align:center;'>
                            <span style='font-size:2rem;'>🧩</span>
                            <h3>Extensions</h3>
                            <p>Load custom JS scripts from the extensions folder.</p>
                        </div>
                        <div class='card' style='display:block; text-align:center;'>
                            <span style='font-size:2rem;'>🔐</span>
                            <h3>Security</h3>
                            <p>Encrypted local password vault and history storage.</p>
                        </div>
                    </div>

                    <div class='card' style='display:block; margin-top:30px;'>
                        <h2 style='color:var(--accent);'>⌨️ Essential Shortcuts</h2>
                        <div style='display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; font-family:monospace; font-size:0.9rem;'>
                            <div><b>Ctrl + T</b> New Tab</div>
                            <div><b>Ctrl + W</b> Close Tab</div>
                            <div><b>Ctrl + R</b> Reload</div>
                            <div><b>Alt + Home</b> Home Page</div>
                            <div><b>Ctrl + ,</b> Settings</div>
                            <div><b>Ctrl + H</b> History</div>
                            <div><b>Ctrl + J</b> Downloads</div>
                            <div><b>Ctrl + F</b> Find</div>
                            <div><b>Ctrl + Shift + I</b> DevTools</div>
                        </div>
                    </div>

                    <div style='margin-top:60px; text-align:center;'>
                        <a href='sloth://bookmark-setup' class='btn btn-secondary' style='margin-bottom:20px; display:inline-block;'>⭐ Bookmark This Page</a><br>
                        <a href='sloth://finish-setup' class='btn' style='background: linear-gradient(45deg, #00ffee, #ff0099, #7000ff); padding:25px 80px; font-size:1.8rem; border-radius:50px; box-shadow: 0 0 40px rgba(0,255,238,0.3); transition: 0.5s;'>Start your browsing experience</a>
                    </div>
                </div>
            </body></html>"""
        elif url == "sloth://finish-setup":
            self.browser.config_manager.set("setup_complete", True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://home'></head></html>"
        elif url.startswith("sloth://add-password"):
            try:
                # Format: sloth://add-password?s=site&u=user&p=pass
                params = url.split("?")[1].split("&")
                site = params[0].split("=")[1]
                user = params[1].split("=")[1]
                pw = params[2].split("=")[1]
                self.browser.password_manager.add_password(site, user, pw)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://passwords'></head></html>"
        elif url.startswith("sloth://delete-bookmark"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                b_url = query.get('u', [''])[0]
                self.browser.bookmarks = [b for b in self.browser.bookmarks if (b.get('url') if isinstance(b, dict) else b) != b_url]
                save_bookmarks(self.browser.bookmarks_file, self.browser.bookmarks)
                self.browser.log("Bookmark deleted.", notify=True)
                if self.browser.sidebar.isVisible(): self.browser.update_sidebar()
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://bookmarks'></head></html>"
        elif url.startswith("sloth://set-nav"):
            try:
                pos = url.split("?p=")[1]
                self.browser.set_nav_pos(pos)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-home"):
            try:
                query_str = url_obj.toString().split('?', 1)[1] if '?' in url_obj.toString() else ''
                q = urllib.parse.parse_qs(query_str)
                h_url = q.get('u', [''])[0]
                if h_url:
                    h_url = urllib.parse.unquote(h_url)
                    if not h_url.startswith(("http", "sloth:")): h_url = "https://" + h_url
                    self.browser.config_manager.set("home_url", h_url)
                    self.browser.log(f"Home URL updated to {h_url}", notify=True)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://clear-customizations":
            # We inject JS to clear localStorage on the current page, or we can just tell the user how to do it.
            # But the user wants a button. 
            # Since customized elements are stored in localStorage per-site, a global clear is tricky from Python.
            # We'll inject a script to the current page to clear it.
            b = self.browser.current_browser()
            if b:
                b.page().runJavaScript("localStorage.removeItem('__sloth_customizations'); location.reload();")
                self.browser.log("Cleared customizations for this site.", notify=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://set-current-home":
            b = self.browser.current_browser()
            if b:
                active_url = b.url().toString()
                self.browser.config_manager.set("home_url", active_url)
                self.browser.log(f"Current page set as Home: {active_url}", notify=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://set-current-nt":
            b = self.browser.current_browser()
            if b:
                active_url = b.url().toString()
                self.browser.config_manager.set("new_tab_url", active_url)
                self.browser.log(f"Current page set as New Tab: {active_url}", notify=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://set-default":
            if DefaultBrowserManager.set_as_default():
                if Platform.IS_WIN:
                    self.browser.log("Registered Sloth Web. Please verify in Windows Settings.", notify=True)
                else:
                    self.browser.log("Sloth Web successfully registered as default browser.", notify=True)
            else:
                if Platform.IS_MAC:
                    self.browser.log("Mac: Please set as default in System Settings.", notify=True)
                else:
                    self.browser.log("Failed to set as default browser.")
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-font-size"):
            try:
                size = int(url.split("?s=")[1])
                self.browser.config_manager.set("font_size", size)
                s = QWebEngineSettings.globalSettings()
                s.setFontSize(QWebEngineSettings.DefaultFontSize, size)
                self.browser.log(f"Default font size set to {size}", notify=True)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-zoom"):
            try:
                zoom = float(url.split("?z=")[1])
                self.browser.config_manager.set("zoom", zoom)
                # Apply to current tabs
                for i in range(self.browser.tabs.count()):
                    w = self.browser.tabs.widget(i)
                    if isinstance(w, QWebEngineView):
                        w.setZoomFactor(zoom)
                self.browser.log(f"Default zoom set to {int(zoom*100)}%", notify=True)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        
        if html:
            data = html.encode('utf-8')
            buf = QBuffer()
            buf.setData(data)
            buf.open(QBuffer.ReadOnly)
            
            job_id = id(job)
            self._active_jobs[job_id] = buf
            
            def cleanup():
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
                    
            job.destroyed.connect(cleanup)
            job.reply(b"text/html", buf)
        else:
            job.fail(QWebEngineUrlRequestJob.UrlInvalid)


# --- AdBlock & Request Blocking ---

class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None, enabled=True):
        super().__init__(parent)
        self.enabled = enabled
        self.lock = threading.Lock()
        self.host_blacklist = set()
        self.regex_blacklist = []
        self.cache_file = get_storage_path("adblock_cache.txt")
        self.custom_list_urls = [
            "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/2.0%20resources/adblock%20list",
            "https://raw.githubusercontent.com/Turtlecute33/toolz/master/src/d3host.txt"
        ]
        self.default_ua = Platform.get_user_agent()
        self.load_defaults()
        # Fetch rules in background to prevent startup hangs/crashes
        threading.Thread(target=self.fetch_remote_rules, daemon=True).start()
        self.load_cache()

    def load_defaults(self):
        with self.lock:
            # Base aggressive rules - Host based for speed
            self.host_blacklist = {
                "googlesyndication.com", "doubleclick.net", "google-analytics.com",
                "adservice.google.com", "googleadservices.com", "securepubads",
                "amazon-adsystem", "adnxs", "taboola", "outbrain", "criteo",
                "popads", "popcash", "propellerads"
            }
            
            # Regex based for more complex patterns - Optimized into a single combined regex
            self.ad_regex = re.compile(r"youtube\.com/api/stats/(ads|qoe)|youtube\.com/(get_midroll_|ptracking|ads/)|ytimg\.com.*ads|ad\.doubleclick\.net|googleads\.g\.doubleclick\.net")
            self.regex_blacklist = [self.ad_regex]
        
        # Define UA strings
        # DEFAULT is a pure standard UA to ensure site compatibility
        self.default_ua = Platform.get_user_agent()
        # PURE CHROME for the store
        self.chrome_ua = Platform.get_user_agent()


    def load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    with self.lock:
                        for line in f.read().splitlines():
                            line = line.strip()
                            if not line or line.startswith(("!", "#", " ")): continue
                            if "." in line and "*" not in line and "[" not in line:
                                self.host_blacklist.add(line)
                            else:
                                try: self.regex_blacklist.append(re.compile(re.escape(line)))
                                except: pass
        except: pass

    def fetch_remote_rules(self):
        all_new_rules = []
        for url in self.custom_list_urls:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    lines = r.text.splitlines()
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith(("!", "#", "[", " ")): continue
                        
                        domain = None
                        if line.startswith("||") and "^" in line:
                            domain = line[2:].split("^")[0].split("/")[0]
                        elif line.startswith(("0.0.0.0", "127.0.0.1")):
                            parts = line.split()
                            if len(parts) >= 2: domain = parts[1]
                        elif "." in line and "/" not in line and "*" not in line:
                            domain = line
                        
                        if domain:
                            with self.lock:
                                self.host_blacklist.add(domain.lower())
                            all_new_rules.append(domain.lower())
            except: pass
        
        if all_new_rules:
            try:
                with open(self.cache_file, "w") as f:
                    f.write("\n".join(set(all_new_rules)))
            except: pass

    def interceptRequest(self, info):
        if not self.enabled: return
        url_obj = info.requestUrl()
        u = url_obj.toString()
        host = url_obj.host().lower()

        # Dynamic User-Agent switching:
        # If site is google/chrome site -> use Chrome UA. Otherwise -> use Sloth UA.
        is_chrome_site = any(domain in (host or "") for domain in ["google.", "gstatic.com", "googleapis.com", "chromewebstore", "youtube.com"])
        
        if not is_chrome_site:
            info.setHttpHeader(b"User-Agent", self.default_ua.encode())
        else:
            # Perfect Client Hints set for Google properties
            info.setHttpHeader(b"Sec-CH-UA", b'"Not/A)Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"')
            info.setHttpHeader(b"Sec-CH-UA-Mobile", b"?0")
            info.setHttpHeader(b"Sec-CH-UA-Platform", f'"{platform.system()}"'.encode())
            info.setHttpHeader(b"Sec-CH-UA-Platform-Version", f'"{platform.release()}"'.encode())
            info.setHttpHeader(b"Sec-CH-UA-Full-Version-List", b'"Not/A)Brand";v="8.0.0.0", "Chromium";v="124.0.0.0", "Google Chrome";v="124.0.0.0"')
            info.setHttpHeader(b"Accept-Language", b"en-US,en;q=0.9")

        # Intelligent Blocking: Check blacklist even for first-party if they are known ad patterns
        # Essential for YouTube and other sites that serve ads from their own domain
        with self.lock:
            # Fast host check first
            if host in self.host_blacklist:
                info.block(True)
                return
            
            # Then check combined regex if necessary
            if self.ad_regex.search(u):
                info.block(True)
                return

        # Then do the first-party bypass for everything else (improves performance)
        first_party = info.firstPartyUrl().host().lower()
        if host == first_party or host.endswith("." + first_party):
            return

class CosmeticFilter(QWebEngineScript):
    def __init__(self):
        super().__init__()
        self.setName("CosmeticFilter")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        self.setRunsOnSubFrames(True)
        css = """
            .adbox, .banner_ads, .adsbox, .textads, .video-ads, #masthead-ad, 
            .ytd-ad-slot-renderer, .ytp-ad-overlay-container, .ytp-ad-message-container,
            #player-ads, #merch-shelf, .ytp-ad-progress-list, .ytp-ad-skip-button-slot,
            ytd-companion-slot-renderer, ytd-action-companion-ad-renderer,
            #ad-text-38, .ytp-ad-text-overlay, [class^="ytp-ad-"], [id^="ytp-ad-"],
            .ad-showing, .ad-interrupting, ytd-promoted-video-renderer,
            .ytd-display-ad-renderer, .ytd-video-masthead-ad-renderer,
            ytd-ad-slot-renderer, #player-ads, .ytd-in-feed-ad-layout-renderer,
            .ytd-video-masthead-ad-v2-renderer, #panels.ytd-watch-flexy { display: none !important; }
        """
        # Optimized Cosmetic Injection with Null Safety
        js = f"""
            (function(){{
                const addStyle = () => {{
                    const target = document.head || document.documentElement;
                    if (target) {{
                        const style = document.createElement('style');
                        style.textContent = `{css}`;
                        target.appendChild(style);
                        return true;
                    }}
                    return false;
                }};
                
                if (!addStyle()) {{
                    const obs = new MutationObserver(() => {{ if (addStyle()) obs.disconnect(); }});
                    obs.observe(document.documentElement || document, {{ childList: true, subtree: true }});
                }}
                
                // Optimized YouTube Ad Skip Logic (MutationObserver for performance)
                const nukeAds = () => {{
                    const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-hover, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-slot');
                    if(skipBtn) {{ skipBtn.click(); }}
                    
                    const video = document.querySelector('video');
                    if(video && (document.querySelector('.ad-showing') || document.querySelector('.ad-interrupting'))) {{
                        if (isFinite(video.duration)) video.currentTime = video.duration;
                    }}
                    
                    document.querySelectorAll('ytd-ad-slot-renderer, #player-ads, .ytd-companion-slot-renderer, .ytd-action-companion-ad-renderer, .ytp-ad-overlay-container').forEach(el => el.remove());
                }};
                
                let timer = setInterval(nukeAds, 500);
                setTimeout(() => clearInterval(timer), 10000);
                
                const observer = new MutationObserver(nukeAds);
                observer.observe(document, {{ childList: true, subtree: true }});
            }})();
        """
        self.setSourceCode(js)

class ChromeStoreCloak(QWebEngineScript):
    """Injects JS to fully masquerade as Google Chrome on every page load."""
    CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"

    def __init__(self):
        super().__init__()
        self.setName("ChromeStoreCloak")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        self.setRunsOnSubFrames(True)
        ua = self.CHROME_UA
        js = """
(function() {
    'use strict';
    var _ua = """ + repr(ua) + """;

    // --- Helper: safe defineProperty (configurable + writable) ---
    function def(obj, prop, val) {
        try {
            Object.defineProperty(obj, prop, {
                get: function() { return val; },
                set: function(v) { val = v; },
                configurable: true,
                enumerable: true
            });
        } catch(e) {}
    }

    // --- Navigator spoofing ---
    def(navigator, 'userAgent', _ua);
    def(navigator, 'appVersion', _ua.replace('Mozilla/', ''));
    def(navigator, 'vendor', 'Google Inc.');
    def(navigator, 'platform', '""" + Platform.get_platform_string() + """');
    def(navigator, 'language', 'en-US');
    def(navigator, 'languages', ['en-US', 'en']);
    def(navigator, 'webdriver', false);
    def(navigator, 'maxTouchPoints', 0);
    def(navigator, 'hardwareConcurrency', 8);
    def(navigator, 'deviceMemory', 8);
    def(navigator, 'appName', 'Netscape');
    def(navigator, 'product', 'Gecko');
    def(navigator, 'productSub', '20030107');

    // --- Plugins (Chrome-standard set) ---
    var fakeMimeType = { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: null };
    var fakePDF = { name: 'Chrome PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', 0: fakeMimeType, length: 1 };
    var fakePlugin2 = { name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer', 0: fakeMimeType, length: 1 };
    var pluginArr = [fakePDF, fakePlugin2];
    try { pluginArr.__proto__ = PluginArray.prototype; } catch(e) {}
    pluginArr.refresh = function() {};
    pluginArr.item = function(i) { return this[i]; };
    pluginArr.namedItem = function(n) { return this.find(function(p){ return p.name === n; }) || null; };
    def(navigator, 'plugins', pluginArr);

    // --- UserAgentData (Client Hints) ---
    var uaData = {
        brands: [
            { brand: 'Not/A)Brand', version: '8' },
            { brand: 'Chromium', version: '145' },
            { brand: 'Google Chrome', version: '145' }
        ],
        mobile: false,
        platform: '""" + platform.system() + """',
        getHighEntropyValues: function(hints) {
            return Promise.resolve({
                architecture: 'x86', bitness: '64', brands: this.brands,
                fullVersionList: [
                    { brand: 'Not/A)Brand', version: '8.0.0.0' },
                    { brand: 'Chromium', version: '145.0.0.0' },
                    { brand: 'Google Chrome', version: '145.0.0.0' }
                ],
                mobile: false, model: '', platform: '""" + platform.system() + """',
                platformVersion: '""" + platform.release() + """', uaFullVersion: '145.0.0.0', wow64: false
            });
        },
        toJSON: function() { return { brands: this.brands, mobile: this.mobile, platform: this.platform }; }
    };
    def(navigator, 'userAgentData', uaData);

    // --- window.chrome: ALWAYS overwrite (QWebEngine may have partial stub) ---
    window.chrome = {
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            getDetails: function() { return null; },
            getIsInstalled: function() { return false; },
            installState: function(cb) { if(cb) cb('not_installed'); }
        },
        runtime: {
            connect: function() { return { onMessage: { addListener: function() {}, removeListener: function() {} }, postMessage: function() {}, disconnect: function() {} }; },
            sendMessage: function() {},
            onMessage: { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
            onConnect: { addListener: function() {}, removeListener: function() {} },
            onStartup: { addListener: function() {} },
            onInstalled: { addListener: function() {} },
            id: undefined,
            getManifest: function() { return {}; },
            getURL: function(p) { return 'chrome-extension://' + p; },
            lastError: null,
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
            PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
            requestUpdateCheck: function(cb) { if(cb) cb('no_update', {}); }
        },
        webstore: {
            install: function(url, onSuccess, onFailure) {
                // Extract extension ID from page URL e.g. /detail/ext-name/{ID}
                var segments = (location.pathname + location.href).split('/');
                var extId = null;
                for (var i = 0; i < segments.length; i++) {
                    var s = segments[i].split('?')[0].split('#')[0];
                    if (s.length === 32 && /^[a-z]+$/.test(s)) {
                        extId = s;
                        break;
                    }
                }
                if (!extId) {
                    if (typeof onFailure === 'function') onFailure('Could not determine extension ID from URL.');
                    return;
                }
                // Build the CRX download URL (same one Chrome uses internally)
                var crxUrl = 'https://clients2.google.com/service/update2/crx'
                    + '?response=redirect'
                    + '&prodversion=145.0.0.0'
                    + '&acceptformat=crx3,crx2'
                    + '&x=id%3D' + extId + '%26installsource%3Dondemand%26uc';
                // Trigger download directly by navigating to the URL
                window.location.href = crxUrl;
                if (typeof onSuccess === 'function') onSuccess();
            },
            onInstallStageChanged: { addListener: function() {}, removeListener: function() {} },
            onDownloadProgress: { addListener: function() {}, removeListener: function() {} },
            ErrorCode: { ABORTED:'aborted', BLACKLISTED:'blacklisted', BLOCKED_BY_POLICY:'admin_policy', ICON_ERROR:'icon_error', INCORRECT_HASH:'incorrect_hash', INVALID_STORE_RESPONSE:'invalid_store_response', LAUNCH_FEATURE_DISABLED:'launch_feature_disabled', LAUNCH_IN_PROGRESS:'launch_in_progress', LAUNCH_UNSUPPORTED_EXTENSION_TYPE:'launch_unsupported_extension_type', MISSING_DEPENDENCIES:'missing_dependencies' },
            InstallStage: { DOWNLOADING: 'downloading', INSTALLING: 'installing' }
        },
        csi: function() { return { startE: Date.now(), onloadT: Date.now(), pageT: Date.now() - (performance.timing ? performance.timing.navigationStart : 0), tran: 15 }; },
        loadTimes: function() {
            var t = performance.timing || {};
            return { commitLoadTime: (t.domLoading||0)/1000, connectionInfo: 'h2', finishDocumentLoadTime: (t.domContentLoadedEventEnd||0)/1000, finishLoadTime: (t.loadEventEnd||0)/1000, firstPaintAfterLoadTime: 0, firstPaintTime: (t.domLoading||0)/1000, navigationType: 'Other', npnNegotiatedProtocol: 'h2', requestTime: (t.navigationStart||0)/1000, startLoadTime: (t.navigationStart||0)/1000, wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: true, wasNpnNegotiated: true };
        },
        cast: {},
        i18n: { getMessage: function() { return ''; }, getUILanguage: function() { return 'en'; } },
        storage: { local: { get: function(k,cb){if(cb)cb({});}, set: function(i,cb){if(cb)cb();}, remove: function(k,cb){if(cb)cb();}, clear: function(cb){if(cb)cb();} }, sync: { get: function(k,cb){if(cb)cb({});}, set: function(i,cb){if(cb)cb();} } }
    };

    // --- Permissions API shim ---
    if (navigator.permissions) {
        var origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function(params) {
            if (params && params.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission, onchange: null });
            }
            return origQuery(params).catch(function() {
                return { state: 'prompt', onchange: null };
            });
        };
    }

    // --- CWS: hide "Switch to Chrome" banner & re-enable "Add to Chrome" button ---
    function patchCWS() {
        // Inject CSS to hide all incompatibility warnings
        if (!document.__slothCSSInjected) {
            document.__slothCSSInjected = true;
            var style = document.createElement('style');
            style.id = 'sloth-cws-patch';
            style.textContent = [
                '[data-controller="IncompatibleBrowserStore"]', '.incompat-text',
                '.incompat-notice', '#cws-incompatible-notice',
                '.UywwFc-eCJI8e', 'ow-div.incompat'
            ].join(',') + ' { display: none !important; }';
            var head = document.head || document.documentElement;
            if (head) head.appendChild(style);
        }

        // Re-enable any disabled install buttons
        var btns = document.querySelectorAll(
            '[aria-label="Add to Chrome"], [aria-label*="Add to"], ' +
            '.webstore-test-button-label, button[jsaction*="install"], ' +
            'button[class*="UywwFc-"]'
        );
        btns.forEach(function(btn) {
            btn.removeAttribute('disabled');
            btn.removeAttribute('aria-disabled');
            btn.style.pointerEvents = 'auto';
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
        });

        // Remove any added-to-DOM incompat banners
        var banners = document.querySelectorAll(
            '[class*="incompat"], [id*="incompat"], [class*="IncompatibleBrowser"], ' +
            '[data-view*="Incompat"]'
        );
        banners.forEach(function(el) { el.style.display = 'none'; });
    }

    // Run immediately and watch for DOM changes
    if (document.readyState !== 'loading') patchCWS();
    document.addEventListener('DOMContentLoaded', patchCWS);
    window.addEventListener('load', patchCWS);
    var _obs = new MutationObserver(function() { patchCWS(); });
    if (document.body) {
        _obs.observe(document.body, { childList: true, subtree: true, attributes: true });
    } else {
        document.addEventListener('DOMContentLoaded', function() {
            _obs.observe(document.body, { childList: true, subtree: true, attributes: true });
        });
    }

})();
        """
        self.setSourceCode(js)

class PageCustomizerScript(QWebEngineScript):
    """Adds the ability to restyle any element (saved per-site in localStorage)."""
    def __init__(self):
        super().__init__()
        self.setName("PageCustomizerScript")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        self.setRunsOnSubFrames(True)
        js = """
        (function() {
            function applyStyles(styles) {
                if (!styles) return;
                for (let selector in styles) {
                    let elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        let s = styles[selector];
                        if (s.color) el.style.color = s.color;
                        if (s.bg) el.style.backgroundColor = s.bg;
                        if (s.size) el.style.fontSize = s.size;
                        if (s.opacity) el.style.opacity = s.opacity;
                    });
                }
            }

            function applySaved() {
                try {
                    let styles = JSON.parse(localStorage.getItem('__sloth_customizations') || '{}');
                    applyStyles(styles);
                } catch(e) {}
            }

            const observer = new MutationObserver((mutations) => {
                applySaved();
            });
            observer.observe(document, { childList: true, subtree: true });

            window.applySaved = applySaved;
            document.addEventListener('DOMContentLoaded', applySaved);
            window.addEventListener('load', applySaved);
            
            // Track right-click target to generate a selector
            document.addEventListener('contextmenu', function(e) {
                window.__slothContextTarget = e.target;
            }, true);
            
            window.__slothCustomizeElement = function() {
                let el = window.__slothContextTarget;
                if (!el) {
                    // Fallback to hover element if context target lost
                    el = document.querySelector(':hover');
                }
                if (!el) return;
                
                // Build a more robust unique selector
                function getSelector(element) {
                    if (element.id) return "#" + element.id;
                    let path = [];
                    while (element.nodeType === Node.ELEMENT_NODE) {
                        let selector = element.nodeName.toLowerCase();
                        if (element.id) {
                            selector += "#" + element.id;
                            path.unshift(selector);
                            break;
                        } else if (element.className && typeof element.className === 'string') {
                            selector += "." + element.className.trim().split(/\\s+/).join(".");
                        }
                        let sib = element, nth = 1;
                        while (sib = sib.previousElementSibling) {
                            if (sib.nodeName.toLowerCase() == selector.split(/[#.]/)[0]) nth++;
                        }
                        if (nth > 1) selector += ":nth-of-type(" + nth + ")";
                        path.unshift(selector);
                        element = element.parentNode;
                    }
                    return path.join(" > ");
                }

                let selector = getSelector(el);
                
                let action = prompt("Customize this element (" + selector + ")\\nOptions: color, bg, size, opacity, hide\\ne.g. 'bg: #ff0000' or 'hide'", "");
                if (!action) return;
                
                let key, val;
                if (action.toLowerCase() === 'hide') {
                    key = 'display';
                    val = 'none';
                } else {
                    let parts = action.split(':');
                    if (parts.length < 2) return;
                    key = parts[0].trim().toLowerCase();
                    val = parts.slice(1).join(':').trim();
                }
                
                let styles = JSON.parse(localStorage.getItem('__sloth_customizations') || '{}');
                if (!styles[selector]) styles[selector] = {};
                
                if (key === 'color') { el.style.color = val; styles[selector].color = val; }
                else if (key === 'bg' || key === 'background') { el.style.backgroundColor = val; styles[selector].bg = val; }
                else if (key === 'size' || key === 'font-size') { el.style.fontSize = val; styles[selector].size = val; }
                else if (key === 'opacity') { el.style.opacity = val; styles[selector].opacity = val; }
                else if (key === 'display') { el.style.display = val; styles[selector].display = val; }
                
                localStorage.setItem('__sloth_customizations', JSON.stringify(styles));
                
                // Signal to Python for global persistence
                console.log("SLOTH_CUSTOMIZE:" + window.location.hostname + "::" + selector + "::" + key + "::" + val);
            };

            // Password Detection
            document.addEventListener('submit', function(e) {
                try {
                    var form = e.target;
                    var passInput = form.querySelector('input[type="password"]');
                    if (passInput) {
                        var userInput = form.querySelector('input[type="text"], input[type="email"], input[type="tel"], [autocomplete="username"], [autocomplete="email"]');
                        var user = userInput ? userInput.value : (form.querySelector('input:not([type="password"])') ? form.querySelector('input:not([type="password"])').value : '');
                        var pass = passInput.value;
                        var site = window.location.hostname;
                        if (pass && pass.length > 2) {
                            console.log("SLOTH_PASS_SAVE:" + site + "::" + user + "::" + pass);
                        }
                    }
                } catch(err) {}
            }, true);
        })();
        """
        self.setSourceCode(js)

class CompatibilityPolyfill(QWebEngineScript):
    """Polyfills for modern JS features missing in older QtWebEngine versions."""
    def __init__(self):
        super().__init__()
        self.setName("CompatibilityPolyfill")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        self.setRunsOnSubFrames(True)
        js = """
        (function() {
            // Polyfill Promise.withResolvers (Chrome 119+)
            if (!Promise.withResolvers) {
                Promise.withResolvers = function() {
                    let resolve, reject;
                    const promise = new Promise((res, rej) => {
                        resolve = res;
                        reject = rej;
                    });
                    return { promise, resolve, reject };
                };
            }
            // Polyfill globalThis if missing
            if (typeof globalThis === 'undefined') {
                (function() {
                    if (typeof self !== 'undefined') { return self; }
                    if (typeof window !== 'undefined') { return window; }
                    if (typeof global !== 'undefined') { return global; }
                    throw new Error('unable to locate global object');
                })();
            }
            // Polyfill Object.hasOwn (Chrome 93+)
            if (!Object.hasOwn) {
                Object.hasOwn = (obj, prop) => Object.prototype.hasOwnProperty.call(obj, prop);
            }
        })();
        """
        self.setSourceCode(js)


# --- UI Components / Dialogs ---

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Sloth Browser Settings")
        self.setMinimumWidth(400)
        l = QVBoxLayout(self)
        
        g1 = QGroupBox("Appearance")
        l1 = QVBoxLayout(g1)
        self.theme_btn = QPushButton(f"Theme: {'Dark' if parent.dark_theme else 'Light'}")
        self.theme_btn.clicked.connect(self.toggle_theme)
        l1.addWidget(self.theme_btn)
        
        self.color_btn = QPushButton("Choose Accent Color")
        self.color_btn.clicked.connect(self.choose_color)
        l1.addWidget(self.color_btn)

        self.layout_btn = QPushButton("Toggle Tabs Orientation")
        self.layout_btn.clicked.connect(self.parent().toggle_layout)
        l1.addWidget(self.layout_btn)
        l.addWidget(g1)
        
        g2 = QGroupBox("Engine & Privacy")
        l2 = QVBoxLayout(g2)
        
        self.ad_check = QCheckBox("Enable Ad-Blocker")
        self.ad_check.setChecked(parent.ad_block_enabled)
        self.ad_check.stateChanged.connect(self.toggle_adblock)
        l2.addWidget(self.ad_check)

        self.ua_box = QComboBox()
        self.ua_box.addItems(["Sloth Platinum", "Chrome (Standard)", "Firefox", "Safari"])
        ua_curr = parent.config_manager.get("custom_ua", "Sloth Platinum")
        self.ua_box.setCurrentText(ua_curr)
        self.ua_box.currentTextChanged.connect(self.set_ua)
        l2.addWidget(QLabel("User Agent:"))
        l2.addWidget(self.ua_box)

        self.nt_edit = QLineEdit(parent.config_manager.get("new_tab_url", "sloth://home"))
        self.nt_edit.setPlaceholderText("New Tab URL (e.g. sloth://home)")
        self.nt_edit.textChanged.connect(self.set_nt)
        l2.addWidget(QLabel("New Tab URL:"))
        l2.addWidget(self.nt_edit)
        
        flags_btn = QPushButton("Manage Engine Flags")
        flags_btn.clicked.connect(self.open_flags)
        l2.addWidget(flags_btn)
        l.addWidget(g2)

        g3 = QGroupBox("Advanced")
        l3 = QVBoxLayout(g3)
        self.clear_btn = QPushButton("Clear Cache & Cookies")
        self.clear_btn.clicked.connect(self.clear_cache)
        l3.addWidget(self.clear_btn)
        l.addWidget(g3)

        close = QPushButton("Close", clicked=self.accept)
        l.addWidget(close)

    def open_flags(self):
        self.accept()
        self.parent().add_tab(QUrl("sloth://flags"))

    def set_ua(self, val):
        self.parent().config_manager.set("custom_ua", val)
    
    def set_nt(self, val):
        self.parent().config_manager.set("new_tab_url", val)

    def toggle_adblock(self, state):
        self.parent().ad_block_enabled = bool(state)
        self.parent().config_manager.set("ad_block_enabled", self.parent().ad_block_enabled)

    def toggle_theme(self):
        self.parent().dark_theme = not self.parent().dark_theme
        self.theme_btn.setText(f"Theme: {'Dark' if self.parent().dark_theme else 'Light'}")
        self.parent().apply_theme()

    def choose_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.parent().accent_color = c.name()
            self.parent().apply_theme()

    def clear_cache(self):
        profile = QWebEngineProfile.defaultProfile()
        profile.clearHttpCache()
        profile.cookieStore().deleteAllCookies()
        QMessageBox.information(self, "Cache Cleared", "The grid cache and cookies have been purged.")

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.browser_parent = parent
        self.featurePermissionRequested.connect(self.on_feature_permission_requested)

    def on_feature_permission_requested(self, url, feature):
        feature_name = {
            QWebEnginePage.Geolocation: "Location",
            QWebEnginePage.MediaAudioCapture: "Microphone",
            QWebEnginePage.MediaVideoCapture: "Camera",
            QWebEnginePage.MediaAudioVideoCapture: "Camera and Microphone",
            QWebEnginePage.Notifications: "Notifications",
            QWebEnginePage.DesktopVideoCapture: "Screen Sharing",
            QWebEnginePage.DesktopAudioVideoCapture: "Screen and Audio Sharing"
        }.get(feature, "Unknown Permission")
        
        reply = QMessageBox.question(self.browser_parent, "Permission Request",
            f"The website {url.host()} wants to access your {feature_name}. Allow?",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)
            self.browser_parent.update_permission_icon(url, feature_name, True)
        else:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionDeniedByUser)
            self.browser_parent.update_permission_icon(url, feature_name, False)

    def javaScriptPrompt(self, securityOrigin, msg, defaultValue):
        text, ok = QInputDialog.getText(self.browser_parent, "JavaScript Prompt", msg, QLineEdit.Normal, defaultValue)
        return ok, text

    def javaScriptConfirm(self, securityOrigin, msg):
        reply = QMessageBox.question(self.browser_parent, "JavaScript Confirm", msg, QMessageBox.Yes | QMessageBox.No)
        return reply == QMessageBox.Yes

    def javaScriptAlert(self, securityOrigin, msg):
        QMessageBox.information(self.browser_parent, "JavaScript Alert", msg)

    def createWindow(self, type_):
        # Called when the browser needs to open a new tab/window (e.g. target="_blank")
        return self.browser_parent.add_tab().page()

    def javaScriptConsoleMessage(self, level, message, line, source):
        if message.startswith("SLOTH_PASS_SAVE:"):
            try:
                parts = message.split("::")
                site = parts[1]
                user = parts[2]
                pw = parts[3]
                self.browser_parent.save_password_request(site, user, pw)
            except: pass
        elif message.startswith("SLOTH_CUSTOMIZE:"):
            try:
                parts = message.split("::")
                site = parts[1]
                selector = parts[2]
                key = parts[3]
                val = parts[4]
                self.browser_parent.custom_manager.set_custom(site, selector, key, val)
            except: pass
        super().javaScriptConsoleMessage(level, message, line, source)

class CRXInstaller:
    """Extracts content scripts from a Chrome Extension (.crx) file."""

    @staticmethod
    def get_zip_data(data):
        """Strip the CRX header and return raw ZIP bytes."""
        if data[:4] != b'Cr24':
            # Maybe it's already a plain ZIP (some older .crx files)
            if data[:2] == b'PK':
                return data
            raise ValueError("Not a valid CRX file (bad magic bytes)")
        version = struct.unpack_from('<I', data, 4)[0]
        if version == 3:
            header_size = struct.unpack_from('<I', data, 8)[0]
            return data[12 + header_size:]
        elif version == 2:
            pubkey_len = struct.unpack_from('<I', data, 8)[0]
            sig_len = struct.unpack_from('<I', data, 12)[0]
            return data[16 + pubkey_len + sig_len:]
        else:
            raise ValueError(f"Unknown CRX version: {version}")

    @staticmethod
    def install(crx_path, browser_ref):
        """Install a .crx file by extracting its content scripts."""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
            ext_dir = os.path.join(base_dir, "extensions")
            os.makedirs(ext_dir, exist_ok=True)

            with open(crx_path, 'rb') as f:
                data = f.read()

            zip_data = CRXInstaller.get_zip_data(data)
            ext_id = os.path.splitext(os.path.basename(crx_path))[0]
            ext_out_dir = os.path.join(ext_dir, "_crx_" + ext_id)
            os.makedirs(ext_out_dir, exist_ok=True)

            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                zf.extractall(ext_out_dir)

            manifest_path = os.path.join(ext_out_dir, 'manifest.json')
            ext_name = ext_id
            installed = []

            if os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                ext_name = manifest.get('name', ext_id)
                for cs in manifest.get('content_scripts', []):
                    for js_file in cs.get('js', []):
                        src = os.path.join(ext_out_dir, js_file.replace('/', os.sep))
                        if os.path.exists(src):
                            dest_name = f"{ext_id}_{os.path.basename(js_file)}"
                            dest = os.path.join(ext_dir, dest_name)
                            shutil.copy2(src, dest)
                            installed.append(dest_name)

            msg = f"Extension '{ext_name}' installed! {len(installed)} script(s) loaded.\nRestart the browser to activate, or reload tabs manually."
            if browser_ref:
                QMessageBox.information(browser_ref, "Extension Installed", msg)
                browser_ref.log(f"Extension installed: {ext_name}")
            return True
        except Exception as e:
            if browser_ref:
                QMessageBox.critical(browser_ref, "Extension Install Failed", f"Could not install extension:\n{e}")
            return False


class DownloadManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.browser_ref = parent
        self.setWindowTitle("Downloads")
        self.setMinimumWidth(400)
        l = QVBoxLayout(self)
        self.list = QListWidget()
        l.addWidget(self.list)
        l.addWidget(QPushButton("Close", clicked=self.accept))

    def add_download(self, item):
        path = item.path()
        # Auto-install Chrome extensions
        if path.lower().endswith('.crx'):
            # Save to a temp crx path then install
            crx_dir = get_storage_path("crx_downloads")
            os.makedirs(crx_dir, exist_ok=True)
            crx_path = os.path.join(crx_dir, os.path.basename(path))
            item.setPath(crx_path)
            item.accept()
            
            # Store for downloads page
            self.browser_ref.downloads.append({"path": crx_path, "status": "Finished"})
            
            it = QListWidgetItem(f"Installing extension: {os.path.basename(crx_path)}...")
            self.list.addItem(it)
            br = self.browser_ref
            def on_crx_done():
                it.setText(f"Extension: {os.path.basename(crx_path)} (Installing...)") 
                CRXInstaller.install(crx_path, br)
                it.setText(f"Extension: {os.path.basename(crx_path)} (Done ✅)")
            item.finished.connect(on_crx_done)
            return

        # OS Download Prompt
        suggested_name = os.path.basename(path)
        save_path, _ = QFileDialog.getSaveFileName(self.browser_ref, "Save File", suggested_name)
        
        if not save_path:
            item.cancel()
            return

        item.setPath(save_path)
        self.browser_ref.downloads.append({"path": save_path, "status": "Finished"})
        it = QListWidgetItem(f"{os.path.basename(save_path)} (Starting...)")
        self.list.addItem(it)
        item.downloadProgress.connect(lambda r, t: it.setText(f"{os.path.basename(save_path)} ({int(r/t*100) if t>0 else 0}%)"))
        item.finished.connect(lambda: it.setText(f"{os.path.basename(save_path)} (Done ✅)"))
        item.accept()
        
        # Open manager if not visible
        self.show()
        self.raise_()

class CustomWebEngineView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser_parent = parent

    def view_source(self):
        url = self.url().toString()
        if not url: return
        self.page().toHtml(lambda html: self.browser_parent.add_tab(QUrl(f"sloth://view-source?url={url}"), source_html=html))

    def inspect_element(self):
        # Integrated Sloth DevTools (Side Dock)
        self.browser_parent.toggle_devtools()

    def customize_element(self):
        # Trigger the injected customization script
        self.page().runJavaScript("if(window.__slothCustomizeElement) window.__slothCustomizeElement();")

    def contextMenuEvent(self, event):
        menu = self.page().createStandardContextMenu()
        
        # Check if we clicked on a link
        data = self.page().contextMenuData()
        if data.linkUrl().isValid():
            open_tab = menu.addAction("🔗 Open Link in New Tab")
            open_tab.triggered.connect(lambda: self.browser_parent.add_tab(data.linkUrl()))
            menu.insertAction(menu.actions()[0], open_tab)
            menu.insertSeparator(menu.actions()[1])

        menu.addSeparator()
        
        menu.addSeparator()

        customize_action = menu.addAction("🎨 Customize Element")
        customize_action.triggered.connect(self.customize_element)
        
        menu.addSeparator()
        
        inspect_action = menu.addAction("🔎 Inspect")
        inspect_action.triggered.connect(self.inspect_element)
        
        view_source_action = menu.addAction("🔎 View Page Source")
        view_source_action.triggered.connect(self.view_source)
        
        menu.exec_(event.globalPos())

# --- Main Browser ---

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sloth Web")
        self.setWindowIcon(QIcon(get_resource_path("sloth_web.ico")))
        self.showMaximized()

        self.bookmarks_file = get_storage_path("bookmarks.json")
        self.bookmarks = load_bookmarks(self.bookmarks_file)
        self.history_manager = HistoryManager(get_storage_path("history.json"))
        self.password_manager = PasswordManager(get_storage_path("passwords.json"))
        self.config_manager = ConfigManager(get_storage_path("config.json"))
        self.custom_manager = CustomizationManager(get_storage_path("customizations.json"))
        
        self.ad_block_enabled = self.config_manager.get("ad_block_enabled", True)
        self.dark_theme = self.config_manager.get("dark_theme", True)
        self.accent_color = self.config_manager.get("accent_color", "#4a9eff")
        self.nav_pos = self.config_manager.get("nav_pos", "top")
        self.tabs_pos = self.config_manager.get("tabs_pos", "north")
        
        self.downloads = []
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(3)
        self.status = QStatusBar()
        self.dl_manager = DownloadManager(self)
        self.completer = QCompleter()
        
        self.update_manager = UpdateManager(self)
        
        # Shared AdBlocker Interceptor to prevent crashes and multiple rule fetches
        self.ad_interceptor = AdBlockInterceptor(self, self.ad_block_enabled)
        QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(self.ad_interceptor)
        
        # Install the scheme handler BEFORE init_ui to ensure the first tab can load it
        self.sloth_handler = SlothSchemeHandler(self)
        QWebEngineProfile.defaultProfile().installUrlSchemeHandler(b"sloth", self.sloth_handler)
        
        self.init_ui()
        self.handle_extensions()
        
        # Optimize global settings for maximum Chromium compatibility and extreme speed
        s = QWebEngineSettings.globalSettings()
        attrs = {
            "AutoLoadImages": True,
            "Accelerated2dCanvasEnabled": True,
            "WebGLEnabled": True,
            "ScrollAnimatorEnabled": True,
            "LocalContentCanAccessRemoteUrls": True,
            "LocalContentCanAccessFileUrls": True,
            "FullScreenSupportEnabled": True,
            "PlaybackRequiresUserGesture": False,
            "JavascriptEnabled": True,
            "JavascriptCanAccessClipboard": True,
            "LocalStorageEnabled": True,
            "PluginsEnabled": True,
            "DnsPrefetchEnabled": True,
            "HyperlinkAuditingEnabled": False,
            "AllowRunningInsecureContent": True,
            "JavascriptCanOpenWindows": True,
            "FocusOnNavigationEnabled": True,
            "ErrorPageEnabled": True,
            "AllowWindowActivationFromJavaScript": True,
            "ServiceWorkerEnabled": True,
            "PdfViewerEnabled": True,
            "WebRTCPublicInterfacesOnly": False,
            "ScreenCaptureEnabled": True
        }
        for attr_name, val in attrs.items():
            if hasattr(QWebEngineSettings, attr_name):
                s.setAttribute(getattr(QWebEngineSettings, attr_name), val)
        
        # Set standard fonts for maximum readability and cross-site consistency
        s.setFontFamily(QWebEngineSettings.StandardFont, "Segoe UI")
        s.setFontFamily(QWebEngineSettings.SansSerifFont, "Segoe UI")
        s.setFontFamily(QWebEngineSettings.SerifFont, "Times New Roman")
        s.setFontFamily(QWebEngineSettings.FixedFont, "Consolas")
        s.setFontSize(QWebEngineSettings.DefaultFontSize, self.config_manager.get("font_size", 16))
        
        # The default UA must be a real Chrome UA at profile level.
        # The interceptor will override back to Sloth UA for non-Google sites.
        CHROME_UA = Platform.get_user_agent()
        profile = QWebEngineProfile.defaultProfile()
        
        # Ensure data persistence by setting explicit storage paths
        storage_path = os.path.join(os.path.expanduser("~"), ".sloth_web", "profile_data")
        os.makedirs(storage_path, exist_ok=True)
        profile.setPersistentStoragePath(storage_path)
        profile.setCachePath(os.path.join(storage_path, "cache"))
        
        profile.setHttpUserAgent(CHROME_UA)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
        profile.setHttpCacheMaximumSize(1024 * 1024 * 100)  # 100MB
        
        self.apply_theme()
        
        QTimer.singleShot(2000, self.update_manager.check_for_updates)

    def handle_extensions(self):
        # Use a local extensions folder in the same directory as the script/executable
        base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
        ext_path = os.path.join(base_dir, "extensions")
        
        if not os.path.exists(ext_path):
            try: os.makedirs(ext_path, exist_ok=True)
            except: pass
        
        if os.path.exists(ext_path):
            count = 0
            for f in os.listdir(ext_path):
                if f.endswith(".js"):
                    try:
                        with open(os.path.join(ext_path, f), "r", encoding="utf-8") as script_file:
                            code = script_file.read()
                            s = QWebEngineScript()
                            s.setSourceCode(code)
                            s.setInjectionPoint(QWebEngineScript.DocumentReady)
                            s.setWorldId(QWebEngineScript.MainWorld)
                            s.setRunsOnSubFrames(True)
                            QWebEngineProfile.defaultProfile().scripts().insert(s)
                            count += 1
                    except Exception as e:
                        print(f"Failed to load extension {f}: {e}")
            self.log(f"Injected {count} extensions from {ext_path}")

    def init_ui(self):
        self.nav = QToolBar("Nav")
        self.nav.setMovable(True) # Allow user to move it
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        
        order = self.config_manager.get("toolbar_order", ["back", "forward", "reload", "home", "url_bar", "bookmark", "new_tab", "sidebar", "settings", "downloads"])
        
        self.back_action = QAction("⬅️", self)
        self.back_action.setToolTip("Go Back to the previous page")
        self.back_action.triggered.connect(self.back)
        
        self.forward_action = QAction("➡️", self)
        self.forward_action.setToolTip("Go Forward to the next page")
        self.forward_action.triggered.connect(self.forward)
        
        self.reload_action = QAction("🔄", self)
        self.reload_action.setToolTip("Reload the current page (Ctrl+R)")
        self.reload_action.triggered.connect(self.reload)
        
        self.home_action = QAction("🏠", self)
        self.home_action.setToolTip("Return to your Home Page (Alt+Home)")
        self.home_action.triggered.connect(self.home)
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL or search the Grid...")
        self.url_bar.returnPressed.connect(self.navigate)
        self.url_bar.textChanged.connect(self.update_suggestions)
        self.url_bar.setMinimumWidth(300)
        self.url_bar.setCompleter(self.completer)
        self.ssl_action = QAction("🔓", self)
        self.url_bar.addAction(self.ssl_action, QLineEdit.LeadingPosition)

        from PyQt5.QtWidgets import QStyle
        self.site_info_action = QAction(self.style().standardIcon(QStyle.SP_MessageBoxInformation), "Site Info", self)
        self.site_info_action.triggered.connect(self.show_site_info)
        self.url_bar.addAction(self.site_info_action, QLineEdit.LeadingPosition)



        # Mapping for dynamic construction
        actions = {
            "back": lambda: self.nav.addAction(self.back_action),
            "forward": lambda: self.nav.addAction(self.forward_action),
            "reload": lambda: self.nav.addAction(self.reload_action),
            "home": lambda: self.nav.addAction(self.home_action),
            "url_bar": lambda: self.nav.addWidget(self.url_bar),
            "new_tab": lambda: self.nav.addAction(QAction("➕", self, toolTip="Open a New Tab (Ctrl+T)", triggered=self.add_tab)),
            "sidebar": lambda: self.nav.addAction(QAction("📂", self, toolTip="Toggle Sloth Hub (Sidebar)", triggered=self.toggle_sidebar)),
            "settings": lambda: self.nav.addAction(QAction("⚙️", self, toolTip="Open Sloth Settings (Ctrl+,)", triggered=self.show_settings)),
            "downloads": lambda: self.nav.addAction(QAction("⬇️", self, toolTip="Show Downloads Manager", triggered=self.show_downloads)),
            "privacy": lambda: self.nav.addAction(QAction("🕶️", self, toolTip="Toggle AdBlock Privacy Mode", triggered=self.toggle_privacy)),
            "progress": lambda: self.nav.addWidget(self.progress),
            "bookmark": lambda: self.nav.addAction(QAction("⭐", self, toolTip="Bookmark this page", triggered=self.bookmark)),
            "bookmarks": lambda: self.nav.addAction(QAction("🔖", self, toolTip="Show all Bookmarks", triggered=self.show_bookmarks)),
        }

        for item in order:
            if item in actions: actions[item]()

        self.addToolBar(Qt.TopToolBarArea, self.nav)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        
        # Apply configured tabs position
        self.apply_tabs_pos()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        
        # Add a "New Tab" button to the tab bar
        self.add_tab_btn = QPushButton("➕")
        self.add_tab_btn.setFlat(True)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        self.add_tab_btn.setFixedSize(30, 30)
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.TopRightCorner)
        
        self.setCentralWidget(self.tabs)
        
        # --- Integrated DevTools Dock ---
        self.devtools_dock = QDockWidget("Sloth DevTools", self)
        self.devtools_view = QWebEngineView()
        self.devtools_dock.setWidget(self.devtools_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.devtools_dock)
        self.devtools_dock.setVisible(False)

        # --- Sidebar (Customizable) ---
        self.sidebar = QDockWidget("Sloth Hub", self)
        self.sidebar.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.sidebar_content = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_content)
        
        self.sidebar_tabs = QTabWidget()
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.itemClicked.connect(lambda i: self.add_tab(QUrl(i.toolTip())))
        self.bookmarks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks_list.customContextMenuRequested.connect(self.show_bookmarks_context_menu)
        
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(lambda i: self.add_tab(QUrl(i.toolTip())))
        
        self.sidebar_tabs.addTab(self.bookmarks_list, "🔖")
        self.sidebar_tabs.addTab(self.history_list, "🕒")
        self.sidebar_layout.addWidget(self.sidebar_tabs)
        
        self.sidebar.setWidget(self.sidebar_content)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar)
        self.sidebar.setVisible(False) # Hidden by default
        
        self.update_sidebar()
        
        self.setStatusBar(self.status)
        
        # Apply configured layout/nav positions after all UI elements are created
        self.apply_nav_pos()
        self.apply_tabs_pos()
        
        self.log("Browser initialized.")
        
        self.add_tab()

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Sloth Data", "sloth_backup.sw", "Sloth Web Data (*.sw)")
        if path:
            data = {
                "bookmarks": self.bookmarks,
                "history": self.history_manager.history,
                "passwords": self.password_manager.passwords,
                "config": self.config_manager.config
            }
            try:
                with open(path, "w") as f:
                    json.dump(data, f)
                self.log(f"Data exported to {path}", notify=True)
            except Exception as e:
                self.log(f"Export failed: {e}", notify=True)

    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Sloth Data", "", "Sloth Web Data (*.sw)")
        if path:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self.bookmarks = data.get("bookmarks", [])
                save_bookmarks(self.bookmarks_file, self.bookmarks)
                self.history_manager.history = data.get("history", [])
                self.history_manager.save()
                self.password_manager.passwords = data.get("passwords", {})
                self.password_manager.save()
                self.config_manager.config = data.get("config", {})
                self.config_manager.save()
                self.log(f"Data imported from {path}. Restarting recommended.", notify=True)
                self.apply_theme()
            except Exception as e:
                self.log(f"Import failed: {e}", notify=True)

    def log(self, message, notify=False):
        self.status.showMessage(message, 5000)
        print(f"[LOG] {message}")
        if notify:
            if HAS_TOAST and Platform.IS_WIN:
                try:
                    ToastNotifier().show_toast("Sloth Web", message, duration=5, threaded=True)
                except: pass
            else:
                # Custom cross-platform notification using a temporary status message or QMessageBox
                # for now, we just rely on the status bar which is already updated.
                pass

    def save_password_request(self, site, user, pw):
        # Site might be hostname
        msg = f"Would you like Sloth to save the password for '{user}' on {site}?"
        ret = QMessageBox.question(self, "🔐 Save Password", msg, QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.password_manager.add_password(site, user, pw)
            self.log(f"Password saved for {site}", notify=True)

    def add_tab(self, url=None, incognito=False, source_html=None):
        if isinstance(url, bool) or url is None: 
            url = QUrl(self.config_manager.get("home_url", "sloth://home"))
        
        # Check if we need to show the start page first time
        if not self.config_manager.get("setup_complete", False) and url == QUrl("sloth://home"):
            url = QUrl("sloth://start")
        
        # Use dedicated profile for incognito
        if incognito:
            profile = QWebEngineProfile(self)
            # Use a fresh but lightweight interceptor for incognito if needed
            profile.setUrlRequestInterceptor(AdBlockInterceptor(self, self.ad_block_enabled))
        else:
            profile = QWebEngineProfile.defaultProfile()
            
        # Ensure scripts are injected once per profile
        if not hasattr(profile, "_sloth_injected"):
            profile.scripts().insert(CompatibilityPolyfill())
            profile.scripts().insert(ChromeStoreCloak())
            profile.scripts().insert(CosmeticFilter())
            profile.scripts().insert(PageCustomizerScript())
            profile._sloth_injected = True
            
        page = CustomWebEnginePage(profile, self)
        profile.downloadRequested.connect(self.dl_manager.add_download)

        browser = CustomWebEngineView(self)
        browser.setPage(page)
        idx = self.tabs.addTab(browser, "New Tab")
        
        # Custom Close Button to ensure ❌ shows correctly
        close_btn = QPushButton("❌")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { border:none; background:transparent; font-size:12px; } QPushButton:hover { background: rgba(255,0,0,0.2); border-radius:4px; }")
        close_btn.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(browser)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.RightSide, close_btn)
        
        # Apply custom UA if set
        ua_type = self.config_manager.get("custom_ua", "Sloth Platinum")
        if "Firefox" in ua_type: profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        elif "Safari" in ua_type: profile.setHttpUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15")
        elif "Sloth" in ua_type: profile.setHttpUserAgent(f"SlothWeb/Platinum ({__version__})")
        
        if source_html:
            # If we are viewing source, we set the HTML directly after a short delay
            browser.setHtml(f"<html><head><title>Source of {url.toString()}</title><style>body{{background:#0f0f0f;color:#0f0;font-family:monospace;white-space:pre-wrap;padding:20px;}}</style></head><body>{source_html.replace('<','&lt;').replace('>','&gt;')}</body></html>")
        else:
            browser.load(url if url else QUrl(self.config_manager.get("home_url", "sloth://home")))
        
        # Use weak references (by using indexOf(b)) to fix the tab-index-drift bug
        browser.urlChanged.connect(lambda q, b=browser: self.update_ui(q, self.tabs.indexOf(b)))
        browser.titleChanged.connect(lambda t, b=browser: (
            self.tabs.setTabText(self.tabs.indexOf(b), t[:25]), 
            self.history_manager.add_entry(t, b.url().toString())
        ))
        browser.iconChanged.connect(lambda icon, b=browser: self.tabs.setTabIcon(self.tabs.indexOf(b), icon))
        browser.loadProgress.connect(lambda p: (self.progress.setValue(p), self.progress.setVisible(p < 100)))
        
        # Connect navigation signals for back/forward buttons
        browser.urlChanged.connect(lambda _: self.update_nav_actions())
        browser.loadFinished.connect(lambda _: self.update_nav_actions())
        
        # Error handling for custom error page
        page.loadFinished.connect(lambda ok, b=browser: self.handle_load_finished(ok, b))
        
        self.tabs.setCurrentIndex(idx)
        
        # Apply default zoom
        zoom = self.config_manager.get("zoom", 1.0)
        if zoom != 1.0:
            browser.setZoomFactor(zoom)
            
        return browser

    def handle_load_finished(self, ok, browser):
        if ok:
            # Sync global customizations to the page's localStorage
            site = browser.url().host()
            if site:
                styles = self.custom_manager.get_for_site(site)
                if styles:
                    styles_json = json.dumps(styles).replace("'", "\\'")
                    js = f"localStorage.setItem('__sloth_customizations', '{styles_json}'); if(window.applySaved) applySaved();"
                    browser.page().runJavaScript(js)
        else:
            # Check if it was a real error or just a cancelled load
            browser.setHtml(NEON_VOID_HTML, browser.url())

    def toggle_layout(self):
        if self.tabs.tabPosition() == QTabWidget.North:
            self.tabs_pos = "west"
        else:
            self.tabs_pos = "north"
        self.config_manager.set("tabs_pos", self.tabs_pos)
        self.apply_tabs_pos()
        self.log(f"Switched tabs layout to {self.tabs_pos}.")

    def apply_tabs_pos(self):
        if self.tabs_pos == "west":
            self.tabs.setTabPosition(QTabWidget.West)
        else:
            self.tabs.setTabPosition(QTabWidget.North)

    def set_nav_pos(self, pos):
        self.nav_pos = pos
        self.config_manager.set("nav_pos", self.nav_pos)
        self.apply_nav_pos()
        self.log(f"Switched nav bar position to {self.nav_pos}.")

    def apply_nav_pos(self):
        # Remove and re-add nav toolbar
        self.removeToolBar(self.nav)
        if self.nav_pos == "bottom":
            self.addToolBar(Qt.BottomToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Horizontal)
            self.nav.setMinimumHeight(40)
        elif self.nav_pos == "left":
            self.addToolBar(Qt.LeftToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Vertical)
            self.nav.setMinimumWidth(100)
        elif self.nav_pos == "right":
            self.addToolBar(Qt.RightToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Vertical)
            self.nav.setMinimumWidth(100)
        else:
            self.addToolBar(Qt.TopToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Horizontal)
            self.nav.setMinimumHeight(40)
        self.nav.show()
        self.nav.setVisible(True)

    def update_nav_actions(self):
        b = self.current_browser()
        if b:
            self.back_action.setEnabled(b.history().canGoBack())
            self.forward_action.setEnabled(b.history().canGoForward())


    def update_ui(self, q, idx):
        if idx == self.tabs.currentIndex():
            if not self.url_bar.hasFocus():
                self.url_bar.setText(q.toString())
            self.ssl_action.setText("🔒" if q.scheme() == "https" else "🔓")
            if hasattr(self, "sidebar") and self.sidebar.isVisible():
                self.update_sidebar()

    def tab_changed(self, idx):
        b = self.current_browser()
        if b:
            self.url_bar.setText(b.url().toString())
            self.ssl_action.setText("🔒" if b.url().scheme() == "https" else "🔓")

    def show_tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx == -1: return
        menu = QMenu()
        close_action = menu.addAction("Close Tab")
        close_others = menu.addAction("Close Others")
        duplicate = menu.addAction("Duplicate Tab")
        
        action = menu.exec_(self.tabs.mapToGlobal(pos))
        if action == close_action: self.close_tab(idx)
        elif action == close_others:
            for i in range(self.tabs.count() - 1, -1, -1):
                if i != idx: self.close_tab(i)
        elif action == duplicate:
            url = self.tabs.widget(idx).url()
            self.add_tab(url)

    def current_browser(self):
        curr = self.tabs.currentWidget()
        return curr if isinstance(curr, QWebEngineView) else None

    def navigate(self):
        url = self.url_bar.text().strip()
        if not url: return
        if url.startswith("sloth://"):
            b = self.current_browser()
            if b: b.setUrl(QUrl(url))
            return
        if "." not in url and ":" not in url: 
            query = urllib.parse.quote(url)
            url = f"https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.q={query}&gsc.sort="
        elif not url.startswith("http") and not url.startswith("view-source:") and not url.startswith("sloth:"): 
            url = "https://" + url
        b = self.current_browser()
        if b: b.setUrl(QUrl(url))

    def update_suggestions(self, t):
        if len(t) > 2:
            if hasattr(self, "_suggest_thread") and self._suggest_thread.isRunning():
                self._suggest_thread.terminate()
                self._suggest_thread.wait()
            
            self._suggest_thread = SuggestionWorker(t)
            self._suggest_thread.suggestions_ready.connect(lambda s: self.completer.setModel(QStringListModel(s)))
            self._suggest_thread.start()

    def close_tab(self, i):
        if self.tabs.count() > 1: self.tabs.removeTab(i)

    def back(self): 
        b = self.current_browser()
        if b: b.back()
    def forward(self): 
        b = self.current_browser()
        if b: b.forward()
    def reload(self): 
        b = self.current_browser()
        if b: b.reload()
    def home(self): 
        b = self.current_browser()
        if b: b.setUrl(QUrl(self.config_manager.get("home_url", "sloth://home")))
    
    def toggle_reader(self):
        b = self.current_browser()
        if b: b.page().runJavaScript("""
            (function(){
                if(window.is_reader){ location.reload(); return; }
                window.is_reader=true;
                let c = document.querySelector('article') || document.querySelector('.post-content') || document.querySelector('main') || document.body;
                let title = document.title;
                document.body.innerHTML = `
                    <div style="max-width:850px; margin:40px auto; font-family:'Segoe UI', serif; font-size:20px; line-height:1.65; color:#2c3e50; background:#fff; padding:50px; border-radius:12px; box-shadow:0 15px 45px rgba(0,0,0,0.08);">
                        <h1 style="font-size:36px; margin-bottom:20px; color:#1a252f;">${title}</h1>
                        <hr style="border:0; border-top:1px solid #eee; margin:30px 0;">
                        ${c.innerHTML}
                    </div>`;
                document.body.style.background="#f8f9fa";
            })()
        """)
        
    def bookmark(self):
        b = self.current_browser()
        if b:
            url = b.url().toString()
            title = b.title() or url
            # Check if already bookmarked
            if not any(bm.get('url') == url for bm in self.bookmarks if isinstance(bm, dict)):
                self.bookmarks.append({"title": title, "url": url})
                save_bookmarks(self.bookmarks_file, self.bookmarks)
                self.log(f"Bookmarked: {title}", notify=True)
                if self.sidebar.isVisible(): self.update_sidebar()

    def show_bookmarks(self):
        d = QDialog(self); d.setWindowTitle("Bookmarks"); l = QVBoxLayout(d)
        w = QListWidget(); l.addWidget(w)
        for b in self.bookmarks:
            title = b.get('title', 'No Title') if isinstance(b, dict) else str(b)
            url = b.get('url', '#') if isinstance(b, dict) else str(b)
            item = QListWidgetItem(f"🔖 {title}")
            item.setToolTip(url)
            w.addItem(item)
        def on_item_clicked(item):
            b = self.current_browser()
            if b: b.setUrl(QUrl(item.text()))
            d.accept()
        w.itemDoubleClicked.connect(on_item_clicked)
        d.exec_()

    def update_permission_icon(self, url, feature_name, granted):
        b = self.current_browser()
        if b and b.url().host() == url.host():
            icon = "🎤" if "Microphone" in feature_name else "📸" if "Camera" in feature_name else "📍" if "Location" in feature_name else "🔔" if "Notifications" in feature_name else "🛡️"
            status = "Granted" if granted else "Denied"
            
            if not hasattr(b, 'active_perms'):
                b.active_perms = []
            b.active_perms.append(f"{icon} {feature_name}: {status}")

    def show_site_info(self):
        b = self.current_browser()
        if not b: return
        url = b.url()
        secure = "🔒 Secure Connection" if url.scheme() == "https" else "🔓 Insecure Connection"
        perms = getattr(b, 'active_perms', [])
        perm_text = "Active Permissions:\\n" + "\\n".join(perms) if perms else "No special permissions requested."
        QMessageBox.information(self, f"Site Info: {url.host()}", f"{secure}\\n\\n{perm_text}")

    def show_settings(self): SettingsDialog(self).exec_()
    def show_downloads(self): self.dl_manager.show()
    def toggle_privacy(self):
        self.ad_block_enabled = not self.ad_block_enabled
        self.status.showMessage(f"AdBlock {'Enabled' if self.ad_block_enabled else 'Disabled'}")

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())
        if self.sidebar.isVisible():
            self.update_sidebar()

    def toggle_devtools(self):
        visible = not self.devtools_dock.isVisible()
        self.devtools_dock.setVisible(visible)
        if visible:
            # Proper integrated DevTools: inspect the current tab
            b = self.current_browser()
            if b:
                self.devtools_view.page().setInspectedPage(b.page())

    def update_sidebar(self):
        self.bookmarks_list.clear()
        for b in self.bookmarks:
            if isinstance(b, dict):
                title = b.get('title', 'No Title')
                url = b.get('url', '#')
            else:
                title = str(b)
                url = str(b)
            item = QListWidgetItem(f"🔖 {title}")
            item.setToolTip(url)
            self.bookmarks_list.addItem(item)
            
        self.history_list.clear()
        for h in self.history_manager.history[-50:]:
            item = QListWidgetItem(f"🕒 {h['time']} - {h['title']}")
            item.setToolTip(h['url'])
            self.history_list.addItem(item)

    def show_bookmarks_context_menu(self, pos):
        item = self.bookmarks_list.itemAt(pos)
        if not item: return
        menu = QMenu()
        open_action = menu.addAction("Open in New Tab")
        delete_action = menu.addAction("Delete Bookmark")
        action = menu.exec_(self.bookmarks_list.mapToGlobal(pos))
        if action == open_action:
            self.add_tab(QUrl(item.toolTip()))
        elif action == delete_action:
            url = item.toolTip()
            self.bookmarks = [b for b in self.bookmarks if (b.get('url') if isinstance(b, dict) else b) != url]
            save_bookmarks(self.bookmarks_file, self.bookmarks)
            self.update_sidebar()
            self.log("Bookmark deleted.", notify=True)

    def apply_theme(self):
        app = QApplication.instance()
        texture = self.config_manager.get("ui_texture", "none")
        qss = ThemeManager.get_qss(self.dark_theme, self.accent_color, texture)
        app.setStyleSheet(qss) # Apply globally to all windows/dialogs to fix unreadable alerts
        ThemeManager.apply_palette(app, self.dark_theme)


if __name__ == "__main__":
    # --- Chromium GPU & Performance flags (must be set before QApplication) ---
    config_path = os.path.join(os.path.expanduser("~"), ".sloth_web", "config.json")
    active_flags = CHROMIUM_FLAGS
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                active_flags = cfg.get("chromium_flags", CHROMIUM_FLAGS)
        except: pass
    sys.argv += active_flags

    scheme = QWebEngineUrlScheme(b"sloth")
    scheme.setFlags(QWebEngineUrlScheme.LocalScheme | QWebEngineUrlScheme.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)

    app = QApplication(sys.argv)
    app.setApplicationName("Sloth Web")
    app.setOrganizationName("SlothWeb")
    window = Browser()
    window.show()
    sys.exit(app.exec_())


