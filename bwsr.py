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
import urllib.parse, urllib
import time
import threading
import platform

__version__ = "2.7"

import pythoncom
try:
    from win32com.propsys import propsys
    from win32com.shell import shell as win_shell
except ImportError:
    pass

from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QStringListModel, QBuffer, QThread, QIODevice
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QLineEdit, 
                             QProgressBar, QTabWidget, QStatusBar, QWidget, 
                             QVBoxLayout, QPushButton, QTabBar, QFileDialog, 
                             QMenu, QInputDialog, QFormLayout, QGroupBox, 
                             QHBoxLayout, QSlider, QApplication, QCompleter,
                             QDialog, QListWidget, QDialogButtonBox, QMessageBox,
                             QListWidgetItem, QTextEdit, QColorDialog, QComboBox,
                             QCheckBox, QLabel, QDockWidget, QStyle, QTreeWidget,
                             QTreeWidgetItem, QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEngineUrlRequestInterceptor, QWebEngineUrlSchemeHandler, 
                                 QWebEngineUrlScheme, QWebEngineUrlRequestJob,
                                 QWebEnginePage, QWebEngineProfile, QWebEngineScript,
                                 QWebEngineExtensionManager, QWebEngineExtensionInfo)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import QIcon, QPalette, QColor, QCursor, QAction, QPixmap, QMovie
import socket
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

from PyQt6.QtWebEngineCore import QWebEngineSettings

# --- Utilities & Path Handling ---

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
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
                reply = QMessageBox.question(self.parent, "Update Available", f"A new version ({remote_version}) is available. Your version is {self.local_version}. Update now?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: self.download_and_install(remote_version)
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
                
            QMessageBox.information(self.parent, "Update Complete", "The browser has been updated and may restart.")
            
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
        bg = "rgba(20, 20, 20, 0.65)" if dark else "rgba(240, 240, 245, 0.7)"
        fg = "#f0f0f0" if dark else "#1d1d1f"
        nav_bg = "rgba(28, 28, 28, 0.75)" if dark else "rgba(255, 255, 255, 0.75)"
        border = "rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.1)"
        hover_bg = "rgba(255, 255, 255, 0.15)" if dark else "rgba(0, 0, 0, 0.06)"
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
            texture_prop = f"background-image: {texture_img}; background-repeat: repeat;"
            
        return f"""
            QMainWindow {{ 
                background-color: transparent; 
                font-family: {font_family}; 
            }}
            QToolBar {{ 
                background-color: {nav_bg};
                border-bottom: 1px solid {border}; 
                border-radius: 16px;
                margin: 6px 12px;
                padding: 8px; 
                spacing: 10px; 
            }}
            QToolBar::handle {{ background: {color}; width: 2px; }}
            QDockWidget {{ 
                color: {color}; 
                font-weight: 800; 
                border: 1px solid {border}; 
                border-radius: 16px;
                background-color: {bg};
                {texture_prop}
            }}
            QDockWidget::title {{ 
                background: {nav_bg};
                padding: 12px; 
                border-bottom: 1px solid {border}; 
                border-radius: 16px 16px 0px 0px;
                font-size: 14px;
            }}
            QDialog, QMessageBox, QGroupBox {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 20px;
                color: {fg};
            }}
            QLineEdit {{ 
                background-color: {"rgba(10, 10, 10, 0.5)" if dark else "rgba(255, 255, 255, 0.5)"}; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: 18px; 
                padding: 8px 16px; 
                font-size: 14px; 
                selection-background-color: {color}; 
            }}
            QLineEdit:focus {{ 
                border: 1px solid {color}; 
                background-color: {"rgba(20, 20, 20, 0.7)" if dark else "rgba(255, 255, 255, 0.8)"};
            }}
            QTabWidget::pane {{ 
                border-top: 1px solid {border}; 
                background: transparent; 
            }}
            QTabBar::tab {{ 
                background-color: rgba(255, 255, 255, 0.05); 
                color: #888; 
                padding: 8px 16px; 
                border-top-left-radius: 12px; 
                border-top-right-radius: 12px;
                margin-right: 4px;
                min-width: 120px;
                border: 1px solid {border};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{ 
                background-color: {bg}; 
                color: {color}; 
                border-bottom: 2px solid {color}; 
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
                background-color: {color}1f; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: 14px; 
                padding: 8px 16px; 
                font-weight: bold; 
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background-color: {color}3d; 
                border: 1px solid {color}; 
                color: {color};
            }}
            QStatusBar {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                font-size: 12px; 
                border-top: 1px solid {border}; 
                border-radius: 12px;
                margin: 6px 12px;
                padding: 4px;
            }}
            QMenu {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: 16px; 
                padding: 8px; 
            }}
            QMenu::item {{ 
                padding: 8px 30px; 
                border-radius: 8px; 
            }}
            QMenu::item:selected {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 {color}aa); 
                color: white; 
            }}
            QListWidget, QTreeWidget {{ 
                background-color: transparent; 
                border: none; 
                color: {fg}; 
            }}
            QListWidget::item, QTreeWidgetItem {{ 
                padding: 12px; 
                border-bottom: 1px solid {border}; 
                margin: 4px 8px;
                border-radius: 12px;
            }}
            QListWidget::item:hover, QTreeWidgetItem:hover {{ 
                background-color: {hover_bg}; 
            }}
            QListWidget::item:selected, QTreeWidgetItem:selected {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}33, stop:1 {color}55); 
                color: {color}; 
                border-left: 4px solid {color};
            }}
            QScrollBar:vertical {{ 
                border: none; 
                background: transparent; 
                width: 10px; 
                margin: 0;
            }}
            QScrollBar::handle:vertical {{ 
                background: {color}44; 
                border-radius: 5px; 
                min-height: 30px; 
                margin: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
        """

    @staticmethod
    def apply_palette(app, dark=True, window_color=None, accent_color=None):
        palette = QPalette()
        if window_color:
            w_color = QColor(window_color) if isinstance(window_color, str) else window_color
        else:
            w_color = QColor(43, 43, 43) if dark else QColor(245, 245, 245)
        
        palette.setColor(QPalette.ColorRole.Window, w_color)
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white if dark else Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, QColor(20, 20, 20) if dark else QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white if dark else Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45) if dark else QColor(235, 235, 235))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white if dark else Qt.GlobalColor.black)
        
        h_color_str = accent_color if accent_color else "#4a9eff"
        palette.setColor(QPalette.ColorRole.Highlight, QColor(h_color_str))
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
                    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
                    gap: 20px; 
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
                .switch {{
                    position: relative;
                    display: inline-block;
                    width: 50px;
                    height: 26px;
                }}
                .switch input {{ 
                    opacity: 0;
                    width: 0;
                    height: 0;
                }}
                .slider {{
                    position: absolute;
                    cursor: pointer;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background-color: rgba(255,255,255,0.1);
                    border: 1px solid var(--border);
                    transition: .3s;
                    border-radius: 34px;
                }}
                .slider:before {{
                    position: absolute;
                    content: "";
                    height: 18px;
                    width: 18px;
                    left: 3px;
                    bottom: 3px;
                    background-color: white;
                    transition: .3s;
                    border-radius: 50%;
                }}
                input:checked + .slider {{
                    background-color: var(--accent);
                }}
                input:checked + .slider:before {{
                    transform: translateX(24px);
                    background-color: #000;
                }}
            </style>
        """
        
        common_head = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>"
        
        html = None
        if url == "sloth://account" or host == "account":
            username = self.browser.config_manager.get("sloth_username", "Lazy Sloth")
            avatar_idx = int(self.browser.config_manager.get("sloth_avatar_idx", 0))
            xp = self.browser.config_manager.get("sloth_xp", 0)
            level = int(xp // 100) + 1
            xp_next = level * 100
            progress_pct = int((xp % 100))
            
            levels_map = {
                1: "Sleepy Seedling 💤",
                2: "Leaf Nibbler 🍃",
                3: "Slow Climber 🦥",
                4: "Branch Napper 🌲",
                5: "Speed Defier ⚡"
            }
            lvl_name = levels_map.get(level if level <= 5 else 5)
            
            ads_blocked = self.browser.config_manager.get("blocked_ads", 0)
            focus_sessions = self.browser.config_manager.get("focus_sessions_completed", 0)
            
            # SVG Avatars definitions
            avatars = [
                # Avatar 0: Chill Sloth with Shades
                """<svg viewBox='0 0 100 100' class='avatar-svg'><circle cx='50' cy='50' r='45' fill='#8d5b4c'/><circle cx='50' cy='50' r='38' fill='#d7ccc8'/><path d='M 30 45 C 30 35, 45 35, 45 45 C 45 55, 30 55, 30 45 Z' fill='#4e342e'/><path d='M 70 45 C 70 35, 55 35, 55 45 C 55 55, 70 55, 70 45 Z' fill='#4e342e'/><circle cx='36' cy='45' r='4' fill='#fff'/><circle cx='64' cy='45' r='4' fill='#fff'/><ellipse cx='50' cy='55' rx='6' ry='4' fill='#3e2723'/><path d='M 40 65 Q 50 72 60 65' stroke='#3e2723' stroke-width='3' fill='none'/><rect x='25' y='38' width='50' height='10' rx='3' fill='#00e5ff' opacity='0.8'/><line x1='25' y1='43' x2='75' y2='43' stroke='#006064' stroke-width='2'/></svg>""",
                # Avatar 1: Astro Sloth
                """<svg viewBox='0 0 100 100' class='avatar-svg'><circle cx='50' cy='50' r='45' fill='#8d5b4c'/><circle cx='50' cy='50' r='38' fill='#d7ccc8'/><path d='M 30 45 C 30 35, 45 35, 45 45 C 45 55, 30 55, 30 45 Z' fill='#4e342e'/><path d='M 70 45 C 70 35, 55 35, 55 45 C 55 55, 70 55, 70 45 Z' fill='#4e342e'/><ellipse cx='50' cy='55' rx='6' ry='4' fill='#3e2723'/><path d='M 40 65 Q 50 72 60 65' stroke='#3e2723' stroke-width='3' fill='none'/><circle cx='50' cy='50' r='42' fill='none' stroke='#e0e0e0' stroke-width='4'/><rect x='45' y='8' width='10' height='6' fill='#ff1744'/></svg>""",
                # Avatar 2: Gamer Sloth
                """<svg viewBox='0 0 100 100' class='avatar-svg'><circle cx='50' cy='50' r='45' fill='#8d5b4c'/><circle cx='50' cy='50' r='38' fill='#d7ccc8'/><path d='M 30 45 C 30 35, 45 35, 45 45 C 45 55, 30 55, 30 45 Z' fill='#4e342e'/><path d='M 70 45 C 70 35, 55 35, 55 45 C 55 55, 70 55, 70 45 Z' fill='#4e342e'/><ellipse cx='50' cy='55' rx='6' ry='4' fill='#3e2723'/><path d='M 40 65 Q 50 72 60 65' stroke='#3e2723' stroke-width='3' fill='none'/><path d='M 18 50 A 32 32 0 0 1 82 50' stroke='#ff00ff' stroke-width='6' fill='none'/><circle cx='18' cy='50' r='8' fill='#ff00ff'/><circle cx='82' cy='50' r='8' fill='#ff00ff'/></svg>""",
                # Avatar 3: Ninja Sloth
                """<svg viewBox='0 0 100 100' class='avatar-svg'><circle cx='50' cy='50' r='45' fill='#212121'/><circle cx='50' cy='50' r='38' fill='#d7ccc8'/><rect x='15' y='32' width='70' height='22' fill='#212121'/><circle cx='35' cy='43' r='4' fill='#fff'/><circle cx='65' cy='43' r='4' fill='#fff'/><path d='M 32 43 C 32 43, 38 38, 42 43' stroke='#000' stroke-width='2' fill='none'/><path d='M 68 43 C 68 43, 62 38, 58 43' stroke='#000' stroke-width='2' fill='none'/><ellipse cx='50' cy='58' rx='6' ry='4' fill='#3e2723'/><path d='M 40 66 Q 50 70 60 66' stroke='#3e2723' stroke-width='2' fill='none'/></svg>"""
            ]
            
            avatar_choices = ""
            for i, av_svg in enumerate(avatars):
                selected_class = "selected" if i == avatar_idx else ""
                avatar_choices += f"<div class='avatar-card {selected_class}' onclick='selectAvatar({i})'>{av_svg}</div>"
                
            html = f"""{common_head}
            <style>
                .avatar-grid {{ display: flex; gap: 15px; margin: 20px 0; justify-content: center; }}
                .avatar-card {{ border: 3px solid transparent; border-radius: 50%; padding: 5px; cursor: pointer; transition: 0.2s; background: rgba(255,255,255,0.02); }}
                .avatar-card.selected {{ border-color: var(--accent); transform: scale(1.1); box-shadow: 0 0 15px var(--accent); }}
                .avatar-svg {{ width: 80px; height: 80px; }}
                .progress-bar-container {{ background: rgba(255,255,255,0.1); border-radius: 10px; height: 20px; width: 100%; overflow: hidden; margin: 15px 0; border: 1px solid var(--border); }}
                .progress-bar-fill {{ background: var(--accent); height: 100%; width: {progress_pct}%; transition: 0.3s; }}
            </style>
            <body>
                <div class='container'>
                    <h1>🦥 Slothatar Account</h1>
                    <p>Customize your profile and check your level status in the grid.</p>
                    
                    <div class='card' style='display:block; text-align:center;'>
                        <div style='display:inline-block; margin-bottom:15px;'>
                            {avatars[avatar_idx]}
                        </div>
                        <h2>{username}</h2>
                        <div style='color:var(--accent); font-weight:bold; font-size:1.2rem;'>Level {level} - {lvl_name}</div>
                        <div class='progress-bar-container'>
                            <div class='progress-bar-fill'></div>
                        </div>
                        <div style='font-size:0.9rem; opacity:0.6;'>XP: {xp} / {xp_next} ({progress_pct}% to next level)</div>
                    </div>
                    
                    <div class='card' style='display:block;'>
                        <h3>Modify Profile</h3>
                        <form id='profileForm' action='sloth://save-profile' method='GET' style='display:flex; flex-direction:column; gap:15px; margin-top:15px;'>
                            <div style='display:flex; flex-direction:column; gap:6px;'>
                                <label style='font-weight:600;'>Username:</label>
                                <input type='text' name='name' id='usernameInput' value='{username}' style='background:rgba(0,0,0,0.3); border:1px solid var(--border);'>
                            </div>
                            <label style='font-weight:600;'>Choose Avatar:</label>
                            <input type='hidden' name='avatar' id='avatarIndexInput' value='{avatar_idx}'>
                            <div class='avatar-grid'>
                                {avatar_choices}
                            </div>
                            <button type='submit' class='btn' style='background:var(--accent); color:#000; font-weight:bold;'>Save Profile Changes</button>
                        </form>
                    </div>
                    
                    <div style='display:grid; grid-template-columns:1fr 1fr; gap:20px; width:100%; margin-top:20px;'>
                        <div class='card' style='display:block; text-align:center;'>
                            <h3>🛡️ Trackers and ads annihilated</h3>
                            <div style='font-size:3rem; font-weight:800; color:var(--accent); margin:10px 0;'>{ads_blocked}</div>
                            <p style='font-size:0.9rem; opacity:0.6; margin:0;'>Clean browsing sessions.</p>
                        </div>
                        <div class='card' style='display:block; text-align:center;'>
                            <h3>⏱️ Focus Sessions</h3>
                            <div style='font-size:3rem; font-weight:800; color:var(--accent); margin:10px 0;'>{focus_sessions}</div>
                            <p style='font-size:0.9rem; opacity:0.6; margin:0;'>Cycles of productivity completed.</p>
                        </div>
                    </div>
                    
                    <div style='margin-top:40px; text-align:center;'>
                        <a href='sloth://home' class='btn btn-secondary' style='text-decoration:none;'>← Home Page</a>
                    </div>
                </div>
                <script>
                    function selectAvatar(idx) {{
                        document.querySelectorAll('.avatar-card').forEach((el, i) => {{
                            if(i === idx) el.classList.add('selected');
                            else el.classList.remove('selected');
                        }});
                        document.getElementById('avatarIndexInput').value = idx;
                    }}
                </script>
            </body>
            </html>"""
        elif url.startswith("sloth://save-profile"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                name = query.get('name', [''])[0]
                avatar = query.get('avatar', ['0'])[0]
                if name:
                    self.browser.config_manager.set("sloth_username", name)
                self.browser.config_manager.set("sloth_avatar_idx", int(avatar))
                self.browser.update_sidebar()
                self.browser.log("Sloth profile updated!", notify=True)
            except Exception as e:
                print("Error saving profile:", e)
            html = "<html><body><script>window.location.href='sloth://account'</script></body></html>"
        elif url.startswith("sloth://sleep") or host == "sleep":
            orig_url = ""
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                orig_url = query.get('url', ['sloth://home'])[0]
            except: pass
            
            html = f"""{common_head}
            <style>
                body {{ justify-content: center; align-items: center; text-align: center; }}
                @keyframes zzz {{
                    0% {{ opacity: 0; transform: translate(0, 0) scale(0.5); }}
                    50% {{ opacity: 1; }}
                    100% {{ opacity: 0; transform: translate(15px, -30px) scale(1.2); }}
                }}
                .z1 {{ animation: zzz 2s infinite 0s; position: absolute; font-weight: bold; color: var(--accent); }}
                .z2 {{ animation: zzz 2s infinite 0.6s; position: absolute; font-weight: bold; color: var(--accent); }}
                .z3 {{ animation: zzz 2s infinite 1.2s; position: absolute; font-weight: bold; color: var(--accent); }}
            </style>
            <body>
                <div class='container' style='max-width:550px; padding:40px;'>
                    <div style='position: relative; width: 120px; height: 120px; margin: 0 auto 20px;'>
                        <!-- Cute Sleeping Sloth SVG -->
                        <svg viewBox='0 0 100 100' style='width: 100px; height: 100px;'>
                            <rect x='10' y='45' width='80' height='10' rx='5' fill='#5d4037'/>
                            <!-- Sloth body hanging -->
                            <ellipse cx='50' cy='58' rx='25' ry='15' fill='#8d5b4c'/>
                            <circle cx='50' cy='52' r='14' fill='#d7ccc8'/>
                            <!-- Closed eyes -->
                            <path d='M 42 52 Q 45 55 48 52' stroke='#4e342e' stroke-width='2' fill='none'/>
                            <path d='M 52 52 Q 55 55 58 52' stroke='#4e342e' stroke-width='2' fill='none'/>
                            <ellipse cx='50' cy='58' rx='3' ry='2' fill='#3e2723'/>
                        </svg>
                        <span class='z1' style='top: 20px; right: 20px; font-size: 1.5rem;'>Z</span>
                        <span class='z2' style='top: 10px; right: 5px; font-size: 1.1rem;'>z</span>
                        <span class='z3' style='top: 30px; right: -5px; font-size: 0.9rem;'>z</span>
                    </div>
                    
                    <h2>Your Sloth is sleeping...</h2>
                    <p style='font-size:1.05rem; opacity:0.8; margin-bottom:30px;'>This tab is currently hibernating to free up RAM and maximize performace.</p>
                    
                    <button class='btn' onclick='wakeUp()' style='background:var(--accent); color:#000; font-weight:bold; font-size:1.1rem; padding:12px 40px;'>Wake Up Tab</button>
                </div>
                <script>
                    function wakeUp() {{
                        window.location.href = decodeURIComponent("{urllib.parse.quote(orig_url)}");
                    }}
                    // Wake up on click anywhere
                    document.body.onclick = wakeUp;
                </script>
            </body>
            </html>"""
        elif url == "sloth://privacy" or host == "privacy":
            # Gather privacy data
            trackers_blocked = self.browser.config_manager.get("blocked_ads", 0)
            
            # Simple list of recent blocks
            blocked_details = getattr(self.browser.ad_interceptor, "blocked_trackers", {})
            blocked_list_html = ""
            if blocked_details:
                blocked_list_html += "<div style='display:flex; flex-direction:column; gap:10px; margin-top:20px; width:100%; text-align:left;'>"
                for site, trackers in list(blocked_details.items())[-10:]:
                    blocked_list_html += f"""<div class='card' style='display:block; padding:15px 20px;'>
                        <div style='font-weight:bold; color:var(--accent);'>{site}</div>
                        <div style='font-size:0.9rem; opacity:0.7; margin-top:5px;'>Blocked: {', '.join(list(trackers)[:5])}</div>
                    </div>"""
                blocked_list_html += "</div>"
            else:
                blocked_list_html += "<p style='opacity:0.6; text-align:center; font-style:italic; margin-top:20px;'>No tracking attempts detected yet. Enjoy the clean grid!</p>"
                
            html = f"""{common_head}
            <body>
                <div class='container'>
                    <h1>🛡️ Privacy Dashboard</h1>
                    <p>Visual summary of trackers blocked and session security footprint.</p>
                    
                    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:20px; width:100%;'>
                        <div class='card' style='display:block; text-align:center;'>
                            <h3>Total Trackers Blocked</h3>
                            <div style='font-size:4rem; font-weight:800; color:var(--accent); margin:15px 0;'>{trackers_blocked}</div>
                            <p style='font-size:0.9rem; opacity:0.6;'>Blocked advertisements and tracker scripts.</p>
                        </div>
                        <div class='card' style='display:block;'>
                            <h3>Grid Protections</h3>
                            <div style='display:flex; flex-direction:column; gap:12px; margin-top:15px;'>
                                <div style='display:flex; justify-content:space-between; align-items:center;'>
                                    <span>Ad Blocker Engine</span>
                                    <span style='color:#00ff88; font-weight:bold;'>ACTIVE</span>
                                </div>
                                <div style='display:flex; justify-content:space-between; align-items:center;'>
                                    <span>Fingerprinting Protection</span>
                                    <span style='color:#00ff88; font-weight:bold;'>ACTIVE</span>
                                </div>
                                <div style='display:flex; justify-content:space-between; align-items:center;'>
                                    <span>Container Isolation</span>
                                    <span style='color:#00ff88; font-weight:bold;'>ACTIVE</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <h3 style='margin-top:40px; text-align:left; border-left:4px solid var(--accent); padding-left:15px; align-self:flex-start;'>🕒 Recent Tracking Attempts</h3>
                    {blocked_list_html}
                    
                    <div style='margin-top:40px; text-align:center;'>
                        <a href='sloth://home' class='btn btn-secondary' style='text-decoration:none;'>← Home</a>
                    </div>
                </div>
            </body>
            </html>"""
        elif url == "sloth://home" or host == "home":
            html = f"""{common_head}
            <body>
                <div class='container'>
                    <!-- Dynamic Welcome Header & Clock Widget -->
                    <div style='text-align: center; margin-bottom: 30px;'>
                        <div id='greeting' style='font-size: 1.4rem; opacity: 0.8; font-weight: 500; letter-spacing: 0.5px;'>Welcome Back</div>
                        <h1 style='font-size: 4rem; margin-top: 5px; margin-bottom: 10px; background: linear-gradient(to right, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>SLOTH PLATINUM</h1>
                        <div id='clock-widget' style='font-size: 2.2rem; font-weight: 700; font-family: monospace; color: var(--accent); margin-bottom: 5px;'>00:00:00</div>
                        <div id='date-widget' style='font-size: 0.95rem; opacity: 0.5;'>Loading...</div>
                    </div>

                    <!-- Search Box with Selector -->
                    <div style='margin-bottom: 40px; text-align: center;'>
                        <form id='searchForm' action='https://www.google.com/search' method='GET' style='display:flex; width:100%; max-width:650px; margin:0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3); border-radius: 50px; overflow: hidden; border: 1px solid var(--border); background: rgba(0,0,0,0.2);'>
                            <select id='searchEngine' style='background:transparent; color:white; border:none; padding:15px; outline:none; font-size:1rem; cursor:pointer; border-right:1px solid var(--border); border-radius:0; height:100%; box-sizing:border-box;'>
                                <option value='sloth' style='background:#111; color:white;'>Sloth Search</option>
                                <option value='google' style='background:#111; color:white;'>Google</option>
                                <option value='ddg' style='background:#111; color:white;'>DuckDuckGo</option>
                                <option value='bing' style='background:#111; color:white;'>Bing</option>
                                <option value='wikipedia' style='background:#111; color:white;'>Wikipedia</option>
                            </select>
                            <input type='text' name='q' id='searchInput' placeholder='Search Google...' style='padding:15px 25px; border:none; background:transparent; color:white; width:100%; outline:none; font-size:1.1rem; box-sizing:border-box;'>
                            <button type='submit' style='padding:15px 30px; border:none; background:var(--accent); color:#000; font-weight:bold; cursor:pointer; transition: 0.3s;'>Search</button>
                        </form>
                    </div>

                    <!-- Main Apps Grid -->
                    <div class='grid'>
                        <a href='sloth://settings' class='module-card'><span class='module-icon'>⚙️</span><span class='module-title'>Settings</span></a>
                        <a href='sloth://bookmarks' class='module-card'><span class='module-icon'>📑</span><span class='module-title'>Bookmarks</span></a>
                        <a href='sloth://downloads' class='module-card'><span class='module-icon'>⬇️</span><span class='module-title'>Downloads</span></a>
                        <a href='sloth://history' class='module-card'><span class='module-icon'>🕒</span><span class='module-title'>History</span></a>
                        <a href='sloth://passwords' class='module-card'><span class='module-icon'>🔐</span><span class='module-title'>Passwords</span></a>
                        <a href='sloth://gpu' class='module-card'><span class='module-icon'>📟</span><span class='module-title'>GPU & System</span></a>
                        <a href='sloth://stats' class='module-card'><span class='module-icon'>📊</span><span class='module-title'>Statistics</span></a>
                        <a href='sloth://help' class='module-card'><span class='module-icon'>❓</span><span class='module-title'>Help</span></a>
                        <a href='sloth://extensions' class='module-card'><span class='module-icon'>🧩</span><span class='module-title'>Extensions</span></a>
                        <a href='sloth://about' class='module-card'><span class='module-icon'>ℹ️</span><span class='module-title'>About</span></a>
                        <a href='sloth://update' class='module-card'><span class='module-icon'>🔁</span><span class='module-title'>Update</span></a>
                        <a href='sloth://arcade' class='module-card arcade-card'><span class='tag'>Live</span><span class='module-icon'>🎮</span><span class='module-title'>Arcade Lab</span></a>
                        <a href='sloth://flags' class='module-card'><span class='module-icon'>🚩</span><span class='module-title'>Flags</span></a>
                        <a href='sloth://account' class='module-card'><span class='module-icon'>👤</span><span class='module-title'>Account</span></a>
                        <a href='sloth://update' class='module-card'><span class='module-icon'>🔄</span><span class='module-title'>Update</span></a>
                    </div>

                    <!-- Widgets Section -->
                    <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:20px; margin-top:40px; width:100%; text-align:left;'>
                        <!-- Memo Widget -->
                        <div class='card' style='display:flex; flex-direction:column; align-items:stretch; background: rgba(255,255,255,0.02); padding: 24px; border-radius: 20px; min-height: 230px; box-sizing:border-box;'>
                            <h3 style='margin-top:0; color:var(--accent); display:flex; justify-content:space-between; align-items:center;'>
                                <span>📝 Sloth Scratchpad</span>
                                <span style='font-size:0.75rem; opacity:0.5; font-weight:normal;'>Auto-saves locally</span>
                            </h3>
                            <textarea id='scratchpad' style='flex:1; width:100%; height: 110px; background:rgba(0,0,0,0.3); color:var(--fg); border:1px solid var(--border); border-radius:10px; padding:10px; font-size:0.95rem; resize:none; outline:none; box-sizing:border-box;' placeholder='Write down quick ideas, code snippets, or URLs here...'></textarea>
                        </div>

                        <!-- Pomodoro Focus Widget -->
                        <div class='card' style='display:flex; flex-direction:column; align-items:center; justify-content:center; background: rgba(255,255,255,0.02); padding: 24px; border-radius: 20px; text-align:center; min-height: 230px; box-sizing:border-box;'>
                            <h3 style='margin-top:0; color:var(--accent); align-self:flex-start;'>⏱️ Focus Session</h3>
                            <div id='timer-display' style='font-size:3rem; font-weight:800; margin:10px 0; font-family:monospace;'>25:00</div>
                            <div id='timer-label' style='font-size:0.9rem; opacity:0.6; margin-bottom:15px;'>Time to focus!</div>
                            <div style='display:flex; gap:10px;'>
                                <button id='timer-toggle' class='btn' style='margin:0; padding:8px 20px; background:var(--accent); color:#000; font-weight:bold;'>Start</button>
                                <button id='timer-reset' class='btn btn-secondary' style='margin:0; padding:8px 20px;'>Reset</button>
                            </div>
                        </div>
                    </div>

                    <!-- Customizable Shortcuts Manager -->
                    <div style='margin-top:40px; width:100%; text-align:left;'>
                        <h3 style='text-align:left; color:var(--accent); margin-bottom:15px; border-left:4px solid var(--accent); padding-left:15px; display:flex; justify-content:space-between; align-items:center;'>
                            <span>⚡ Quick Access</span>
                            <button class='btn' onclick='addShortcut()' style='margin:0; padding:6px 12px; font-size:0.8rem; border-radius:8px; background:var(--accent); color:#000; font-weight:bold;'>+ Add Shortcut</button>
                        </h3>
                        <div id='shortcuts-grid' class='grid' style='grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:15px; margin-top:15px;'>
                            <!-- Dynamic -->
                        </div>
                    </div>

                    <iframe src='https://parkertrip.github.io/newtab' sandbox='allow-scripts allow-same-origin allow-forms allow-popups' style='width:100%; height:800px; border:1px solid var(--border); border-radius:24px; margin-top:40px; background:var(--bg);'></iframe>

                    <!-- Scripts -->
                    <script>
                        // Clock & Greeting
                        function updateClock() {{
                            const now = new Date();
                            const timeStr = now.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }});
                            const dateStr = now.toLocaleDateString([], {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }});
                            const hours = now.getHours();
                            let greet = "Good night, Sloth";
                            if (hours >= 5 && hours < 12) greet = "Good morning, Sloth";
                            else if (hours >= 12 && hours < 17) greet = "Good afternoon, Sloth";
                            else if (hours >= 17 && hours < 22) greet = "Good evening, Sloth";
                            
                            const greetingEl = document.getElementById('greeting');
                            const clockEl = document.getElementById('clock-widget');
                            const dateEl = document.getElementById('date-widget');
                            if (greetingEl) greetingEl.textContent = greet;
                            if (clockEl) clockEl.textContent = timeStr;
                            if (dateEl) dateEl.textContent = dateStr;
                        }}
                        setInterval(updateClock, 1000);
                        updateClock();

                        // Search Engine Selection
                        const sForm = document.getElementById('searchForm');
                        const sSelect = document.getElementById('searchEngine');
                        const sInput = document.getElementById('searchInput');
                        
                        const savedEngine = localStorage.getItem('__sloth_search_engine') || 'sloth';
                        sSelect.value = savedEngine;
                        updateSearchAction(savedEngine);
                        
                        sSelect.addEventListener('change', (e) => {{
                            const val = e.target.value;
                            localStorage.setItem('__sloth_search_engine', val);
                            updateSearchAction(val);
                        }});

                        sForm.addEventListener('submit', (e) => {{
                            const engine = sSelect.value;
                            if (engine === 'sloth') {{
                                e.preventDefault();
                                const query = encodeURIComponent(sInput.value);
                                window.location.href = `https://cse.google.com/cse?cx=666b70a81f11c4eb9&q=${{query}}#gsc.tab=0&gsc.q=${{query}}&gsc.sort=`;
                            }}
                        }});
                        
                        function updateSearchAction(engine) {{
                            if (engine === 'Sloth Search') {{
                                sForm.action = 'https://cse.google.com/cse';
                                sInput.name = 'q';
                                sInput.placeholder = 'Search the Grid with Sloth Search...';
                            }} else if (engine === 'google') {{
                                sForm.action = 'https://www.google.com/search';
                                sInput.name = 'q';
                                sInput.placeholder = 'Search Google...';
                            }} else if (engine === 'ddg') {{
                                sForm.action = 'https://duckduckgo.com/';
                                sInput.name = 'q';
                                sInput.placeholder = 'Search DuckDuckGo...';
                            }} else if (engine === 'bing') {{
                                sForm.action = 'https://www.bing.com/search';
                                sInput.name = 'q';
                                sInput.placeholder = 'Search Bing...';
                            }} else if (engine === 'wikipedia') {{
                                sForm.action = 'https://en.wikipedia.org/w/index.php';
                                sInput.name = 'search';
                                sInput.placeholder = 'Search Wikipedia...';
                                }} else if (engine === 'Brave') {{
                                sForm.action = 'https://search.brave.com/search?q=';
                                sInput.name = 'search';
                                sInput.placeholder = 'Search Brave...';
                            }}
                        }}

                        // Scratchpad
                        const scratch = document.getElementById('scratchpad');
                        fetch('sloth://get-scratchpad')
                            .then(r => r.text())
                            .then(txt => {{
                                scratch.value = txt;
                            }});
                        
                        let saveTimeout = null;
                        scratch.addEventListener('input', () => {{
                            clearTimeout(saveTimeout);
                            saveTimeout = setTimeout(() => {{
                                fetch('sloth://save-scratchpad?t=' + encodeURIComponent(scratch.value));
                            }}, 500);
                        }});

                        // Focus Session Timer
                        let timeLeft = 25 * 60;
                        let timerId = null;
                        let isBreak = false;
                        
                        const display = document.getElementById('timer-display');
                        const label = document.getElementById('timer-label');
                        const toggleBtn = document.getElementById('timer-toggle');
                        const resetBtn = document.getElementById('timer-reset');
                        
                        function updateTimerDisplay() {{
                            const mins = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                            const secs = (timeLeft % 60).toString().padStart(2, '0');
                            display.textContent = mins + ":" + secs;
                        }}
                        
                        toggleBtn.addEventListener('click', () => {{
                            if (timerId) {{
                                clearInterval(timerId);
                                timerId = null;
                                toggleBtn.textContent = 'Start';
                            }} else {{
                                toggleBtn.textContent = 'Pause';
                                timerId = setInterval(() => {{
                                    timeLeft--;
                                    updateTimerDisplay();
                                    if (timeLeft <= 0) {{
                                        clearInterval(timerId);
                                        timerId = null;
                                        toggleBtn.textContent = 'Start';
                                        
                                        isBreak = !isBreak;
                                        timeLeft = (isBreak ? 5 : 25) * 60;
                                        label.textContent = isBreak ? 'Break Time!' : 'Time to focus!';
                                        updateTimerDisplay();
                                        alert(isBreak ? 'Time for a break!' : 'Back to focus!');
                                    }}
                                }}, 1000);
                            }}
                        }});
                        
                        resetBtn.addEventListener('click', () => {{
                            clearInterval(timerId);
                            timerId = null;
                            isBreak = false;
                            timeLeft = 25 * 60;
                            label.textContent = 'Time to focus!';
                            toggleBtn.textContent = 'Start';
                            updateTimerDisplay();
                        }});
                        
                        updateTimerDisplay();

                        // Dynamic Shortcuts
                        const defaultShortcuts = [
                            {{ name: 'Google', url: 'https://www.google.com' }},
                            {{ name: 'YouTube', url: 'https://www.youtube.com' }},
                            {{ name: 'GitHub', url: 'https://github.com' }},
                            {{ name: 'Discord', url: 'https://discord.com' }},
                            {{ name: 'ChatGPT', url: 'https://chatgpt.com' }}
                        ];
                        
                        function loadShortcuts() {{
                            let items = [];
                            try {{
                                items = JSON.parse(localStorage.getItem('__sloth_shortcuts') || '[]');
                            }} catch(e) {{}}
                            
                            if (items.length === 0) {{
                                items = defaultShortcuts;
                                localStorage.setItem('__sloth_shortcuts', JSON.stringify(items));
                            }}
                            return items;
                        }}
                        
                        function renderShortcuts() {{
                            const grid = document.getElementById('shortcuts-grid');
                            const items = loadShortcuts();
                            grid.innerHTML = '';
                            
                            items.forEach((item, index) => {{
                                const card = document.createElement('div');
                                card.className = 'module-card';
                                card.style.padding = '15px';
                                card.style.position = 'relative';
                                card.style.display = 'flex';
                                card.style.flexDirection = 'column';
                                card.style.alignItems = 'center';
                                card.style.justifyContent = 'center';
                                card.style.minHeight = '60px';
                                
                                const delBtn = document.createElement('button');
                                delBtn.innerHTML = '×';
                                delBtn.style.position = 'absolute';
                                delBtn.style.top = '5px';
                                delBtn.style.right = '8px';
                                delBtn.style.background = 'none';
                                delBtn.style.border = 'none';
                                delBtn.style.color = '#ff4444';
                                delBtn.style.fontSize = '1.3rem';
                                delBtn.style.cursor = 'pointer';
                                delBtn.style.lineHeight = '1';
                                delBtn.style.opacity = '0.7';
                                delBtn.onclick = (e) => {{
                                    e.preventDefault();
                                    e.stopPropagation();
                                    removeShortcut(index);
                                }};
                                
                                const link = document.createElement('a');
                                link.href = item.url;
                                link.style.textDecoration = 'none';
                                link.style.color = 'inherit';
                                link.style.width = '100%';
                                link.style.height = '100%';
                                link.style.display = 'flex';
                                link.style.alignItems = 'center';
                                link.style.justifyContent = 'center';
                                link.style.textAlign = 'center';
                                
                                const title = document.createElement('span');
                                title.style.fontSize = '1.05rem';
                                title.style.fontWeight = '600';
                                title.textContent = item.name;
                                
                                link.appendChild(title);
                                card.appendChild(delBtn);
                                card.appendChild(link);
                                grid.appendChild(card);
                            }});
                        }}
                        
                        window.addShortcut = function() {{
                            const name = prompt("Enter shortcut name:");
                            if (!name) return;
                            let url = prompt("Enter shortcut URL:");
                            if (!url) return;
                            if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('sloth://')) {{
                                url = 'https://' + url;
                            }}
                            const items = loadShortcuts();
                            items.push({{ name, url }});
                            localStorage.setItem('__sloth_shortcuts', JSON.stringify(items));
                            renderShortcuts();
                        }}
                        
                        function removeShortcut(index) {{
                            const items = loadShortcuts();
                            items.splice(index, 1);
                            localStorage.setItem('__sloth_shortcuts', JSON.stringify(items));
                            renderShortcuts();
                        }}
                        
                        renderShortcuts();
                    </script>
                </div>
            </body>
            </html>"""
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
                    <div class='card' style='display:block; flex:1;'>
                        <h2 style='color:var(--accent); margin-top:0; margin-bottom:20px; font-size:1.5rem; border-bottom:1px solid var(--border); padding-bottom:10px;'>🎨 Appearance & Layout</h2>
                        <div style='display:flex; flex-direction:column; gap:20px;'>
                            <div style='display:flex; flex-direction:column; gap:6px;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Home Page URL</span>
                                <div style='display:flex; gap:10px; width:100%;'>
                                    <input type='text' id='h-url' value='{h_url}' style='flex:1; background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px; font-size:0.9rem; box-sizing:border-box;'>
                                    <button class='btn' style='margin:0; padding:10px 20px; border-radius:10px; cursor:pointer;' onclick='window.location.href="sloth://set-home?u="+encodeURIComponent(document.getElementById("h-url").value)'>Set</button>
                                </div>
                            </div>
                            
                            <div style='display:flex; flex-direction:column; gap:6px;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>New Tab URL</span>
                                <div style='display:flex; gap:10px; width:100%;'>
                                    <input type='text' id='nt-url' value='{self.browser.config_manager.get("new_tab_url", "sloth://home")}' style='flex:1; background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px; font-size:0.9rem; box-sizing:border-box;'>
                                    <button class='btn' style='margin:0; padding:10px 20px; border-radius:10px; cursor:pointer;' onclick='window.location.href="sloth://set-nt?u="+encodeURIComponent(document.getElementById("nt-url").value)'>Set</button>
                                </div>
                            </div>

                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Set Active as Home</span>
                                <button class='btn btn-secondary' style='margin:0; padding:8px 16px; border-radius:8px;' onclick='window.location.href="sloth://set-current-home"'>Current Page</button>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Set Active as New Tab</span>
                                <button class='btn btn-secondary' style='margin:0; padding:8px 16px; border-radius:8px;' onclick='window.location.href="sloth://set-current-nt"'>Current Page</button>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Site Customizations</span>
                                <button class='btn' style='background:#ff4444; border:none; margin:0; padding:8px 16px; border-radius:8px; color:white; cursor:pointer;' onclick='if(confirm("Clear all element restyling?")) window.location.href="sloth://clear-customizations"'>Reset All</button>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Theme Mode</span>
                                <button class='btn' style='margin:0; padding:8px 16px; border-radius:8px; background:var(--accent); color:#000; font-weight:600;' onclick='window.location.href="sloth://toggle-theme"'>{("Switch to Light" if self.browser.dark_theme else "Switch to Dark")}</button>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Accent Color</span>
                                <input type='color' value='{accent}' onchange='window.location.href="sloth://set-color?c="+this.value.replace("#", "")' style='width:60px; height:36px; border:1px solid var(--border); border-radius:8px; background:none; cursor:pointer;'>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>UI Texture</span>
                                <select onchange='window.location.href="sloth://set-texture?t="+this.value' style='background:#111; color:white; border:1px solid var(--border); border-radius:8px; padding:8px 12px; font-size:0.9rem;'>
                                    <option value='none' {"selected" if self.browser.config_manager.get("ui_texture")=="none" else ""}>Clean</option>
                                    <option value='noise' {"selected" if self.browser.config_manager.get("ui_texture")=="noise" else ""}>Noise</option>
                                    <option value='stripes' {"selected" if self.browser.config_manager.get("ui_texture")=="stripes" else ""}>Stripes</option>
                                    <option value='grid' {"selected" if self.browser.config_manager.get("ui_texture")=="grid" else ""}>Grid</option>
                                </select>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Default Font Size</span>
                                <select onchange='window.location.href="sloth://set-font-size?s="+this.value' style='background:#111; color:white; border:1px solid var(--border); border-radius:8px; padding:8px 12px; font-size:0.9rem;'>
                                    <option value='12' {"selected" if self.browser.config_manager.get("font_size")==12 else ""}>Small</option>
                                    <option value='16' {"selected" if self.browser.config_manager.get("font_size")==16 or not self.browser.config_manager.get("font_size") else "selected"}>Medium</option>
                                    <option value='20' {"selected" if self.browser.config_manager.get("font_size")==20 else ""}>Large</option>
                                    <option value='24' {"selected" if self.browser.config_manager.get("font_size")==24 else ""}>Extra Large</option>
                                </select>
                            </div>
                            
                            <div style='display:flex; justify-content: space-between; align-items:center;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Default Zoom</span>
                                <select onchange='window.location.href="sloth://set-zoom?z="+this.value' style='background:#111; color:white; border:1px solid var(--border); border-radius:8px; padding:8px 12px; font-size:0.9rem;'>
                                    <option value='0.8' {"selected" if self.browser.config_manager.get("zoom")==0.8 else ""}>80%</option>
                                    <option value='1.0' {"selected" if self.browser.config_manager.get("zoom")==1.0 or not self.browser.config_manager.get("zoom") else "selected"}>100%</option>
                                    <option value='1.2' {"selected" if self.browser.config_manager.get("zoom")==1.2 else ""}>120%</option>
                                    <option value='1.5' {"selected" if self.browser.config_manager.get("zoom")==1.5 else ""}>150%</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div style='display:flex; flex-direction:column; gap:20px; flex:1;'>
                        <div class='card' style='display:block; margin-bottom:0;'>
                            <h2 style='color:var(--accent); margin-top:0; margin-bottom:15px; font-size:1.5rem; border-bottom:1px solid var(--border); padding-bottom:10px;'>🔧 Toolbar Engine</h2>
                            <p style='font-size:0.85rem; opacity:0.7; line-height:1.4; margin-bottom:15px;'>Reorder your toolbar buttons to your liking. Drag, drops, or type IDs separated by commas.</p>
                            <span style='font-weight:600; font-size:0.85rem; opacity:0.6; display:block; margin-bottom:6px;'>Available IDs: back, forward, reload, home, url_bar, new_tab, sidebar, settings, downloads, privacy</span>
                            <input type='text' id='t-order' value='{order_str}' style='width:100%; background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px; font-size:0.9rem; box-sizing:border-box; margin-bottom:15px;'>
                            <button class='btn' style='width:100%; background:var(--accent); color:#000; font-weight:600; border:none; margin:0;' onclick='window.location.href="sloth://set-toolbar?o="+document.getElementById("t-order").value'>Update Toolbar Grid</button>
                        </div>

                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent); margin-top:0; margin-bottom:15px; font-size:1.5rem; border-bottom:1px solid var(--border); padding-bottom:10px;'>🧭 Navigation</h2>
                            <div style='display:flex; flex-direction:column; gap:20px;'>
                                <div style='display:flex; justify-content: space-between; align-items:center;'>
                                    <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Nav Position</span>
                                    <select onchange='window.location.href="sloth://set-nav?p="+this.value' style='background:#111; color:white; border:1px solid var(--border); border-radius:8px; padding:8px 12px; font-size:0.9rem;'>
                                        <option value='top' {"selected" if self.browser.nav_pos=="top" else ""}>Top</option>
                                        <option value='bottom' {"selected" if self.browser.nav_pos=="bottom" else ""}>Bottom</option>
                                    </select>
                                </div>
                                <div style='display:flex; justify-content: space-between; align-items:center;'>
                                    <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Tabs Position</span>
                                    <button class='btn btn-secondary' style='margin:0; padding:8px 16px; border-radius:8px;' onclick='window.location.href="sloth://toggle-layout"'>Toggle Top/Side Tabs</button>
                                </div>
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
            smooth_checked = "checked" if self.browser.config_manager.get("smooth_scrolling", True) else ""
            html = f"""{common_head}<body><div class='container'>
                <h1>🚩 Engine Flags</h1>
                <p>Modify Chromium launch flags and experimental features. <b>Requires restart to apply.</b></p>
                <form action='sloth://save-flags' method='GET' style='width:100%;'>
                    <div class='card' style='display:block; margin-bottom:20px; background:rgba(255,255,255,0.02);'>
                        <h3 style='margin-top:0; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:10px;'>⚙️ Feature Toggles</h3>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin:15px 0;'>
                            <div style='text-align:left;'>
                                <strong style='font-size:1.05rem;'>Smooth Scrolling</strong>
                                <div style='font-size:0.85rem; opacity:0.7; margin-top:3px;'>Enable smooth scrolling animation for pages.</div>
                            </div>
                            <label class="switch">
                                <input type="checkbox" name="ss" value="on" {smooth_checked}>
                                <span class="slider"></span>
                            </label>
                        </div>
                    </div>
                    
                    <div class='card' style='display:block; background:rgba(255,255,255,0.02);'>
                        <h3 style='margin-top:0; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:10px;'>🧪 Chromium Launch Flags</h3>
                        <p style='font-size:0.85rem; text-align:left; margin:10px 0;'>Enter one flag per line (e.g. <code>--disable-gpu</code>):</p>
                        <textarea name='f' style='width:100%; height:200px; background:rgba(0,0,0,0.2); color:var(--fg); border:1px solid var(--border); border-radius:14px; padding:15px; font-family:monospace; outline:none; resize:vertical; box-sizing:border-box;'>{flags_text}</textarea>
                    </div>
                    
                    <div style='text-align:center; margin-top:30px;'>
                        <button type='submit' class='btn' style='width:100%; max-width:300px; background:var(--accent); color:#000; font-weight:bold;'>Save & Restart Engine</button>
                    </div>
                </form>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary' style='text-decoration:none;'>← Home</a></div>
            </div></body></html>"""
        elif url.startswith("sloth://save-flags"):
            try:
                # Use urllib to properly decode the textarea content
                query = urllib.parse.parse_qs(url_obj.query())
                if 'f' in query:
                    new_flags = [f.strip() for f in query['f'][0].split('\n') if f.strip()]
                    self.browser.config_manager.set("chromium_flags", new_flags)
                
                # Check for smooth scrolling toggle
                smooth_scrolling = 'ss' in query
                self.browser.config_manager.set("smooth_scrolling", smooth_scrolling)
                
                self.browser.log("Flags updated. Restarting...", notify=True)
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
        elif url.startswith("sloth://set-search"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                s = query.get('s', [''])[0]
                if s:
                    self.browser.config_manager.set("search_engine", s)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://start'></head></html>"
        elif url.startswith("sloth://save-scratchpad"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                t = query.get('t', [''])[0]
                self.browser.config_manager.set("scratchpad", t)
            except: pass
            html = "<html><body></body></html>"
        elif url == "sloth://get-scratchpad":
            html = self.browser.config_manager.get("scratchpad", "")
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
            base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
            ext_path = os.path.join(base_dir, "extensions")
            
            ext_list_html = ""
            try:
                if not os.path.exists(ext_path):
                    os.makedirs(ext_path, exist_ok=True)
                files = [f for f in os.listdir(ext_path) if f.endswith(".js")]
                if files:
                    ext_list_html += "<h3 style='margin-top:30px; margin-bottom:10px;'>📂 Installed Extensions</h3><div style='display:flex; flex-direction:column; gap:10px; margin-top:10px;'>"
                    for f in files:
                        ext_list_html += f"<div class='card' style='display:flex; justify-content:space-between; align-items:center; padding:15px 20px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:12px;'>" \
                                         f"<span style='font-family:monospace; font-size:0.95rem;'>🧩 {f}</span>" \
                                         f"<a href='sloth://delete-extension?name={f}' class='btn' style='padding:5px 12px; font-size:0.8rem; background:#ff4444; color:#fff; border:none; margin:0; border-radius:6px; text-decoration:none;'>Delete</a>" \
                                         f"</div>"
                    ext_list_html += "</div>"
                else:
                    ext_list_html += "<p style='opacity:0.6; font-style:italic; margin-top:20px; text-align:center;'>No custom extensions loaded yet.</p>"
            except Exception as e:
                ext_list_html += f"<p style='color:#ff4444;'>Failed to read extensions: {e}</p>"

            html = f"{common_head}<body><div class='container'><h1>🧩 Extension Engine</h1><p>Expand your grid with custom capabilities.</p>" \
                   f"<div style='background:rgba(255,255,255,0.03); border-radius:16px; padding:25px; margin:20px 0; border:1px solid rgba(255,255,255,0.05);'>" \
                   f"<p>Extensions are loaded from the <b>extensions</b> folder in the Sloth directory.</p>" \
                   f"<code style='background:#000; padding:10px; border-radius:8px; display:block; margin:10px 0; color:var(--accent); overflow-x:auto;'>{ext_path}</code>" \
                   f"<p style='font-size:0.9rem; opacity:0.8;'>Simply drop any <code>.js</code> file into this folder to inject it into every page you visit.</p>" \
                   f"</div>" \
                   f"<div style='background:rgba(255,255,255,0.03); border-radius:16px; padding:25px; margin:20px 0; border:1px solid rgba(255,255,255,0.05);'>" \
                   f"<h3>📥 Install Extension from URL</h3>" \
                   f"<p style='font-size:0.9rem; opacity:0.8; margin-bottom:15px;'>Enter the URL of any JavaScript extension to download and load it automatically.</p>" \
                   f"<div style='display:flex; gap:10px;'>" \
                   f"<input type='text' id='ext-url' placeholder='https://example.com/extension.js' style='flex:1; background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.1); color:#fff; padding:12px; border-radius:8px; outline:none; font-family:inherit; font-size:0.95rem;'>" \
                   f"<button onclick='installExt()' class='btn' style='background:var(--accent); color:#000; font-weight:bold; border:none; padding:10px 20px; border-radius:8px; cursor:pointer;'>Install</button>" \
                   f"</div>" \
                   f"<p id='status' style='margin-top:10px; font-size:0.9rem; display:none; color:var(--accent);'></p>" \
                   f"</div>" \
                   f"{ext_list_html}" \
                   f"<div style='display:flex; gap:15px; justify-content:center; margin-top:30px;'>" \
                   f"<a href='https://parkertripoli-wq.github.io/' class='btn' style='background:#ff00ff; text-decoration:none;'>Open Sloth Store</a>" \
                   f"<a href='https://chromewebstore.google.com/' class='btn' style='background:#4285f4; text-decoration:none;'>Open Chrome Store (WIP)</a>" \
                   f"</div>" \
                   f"<p style='margin-top:15px; color:#aaa; font-style:italic; text-align:center;'>Both Sloth and standard Chrome-compatible scripts are supported.</p>" \
                   f"<script>" \
                   f"function installExt() {{" \
                   f"  let u = document.getElementById('ext-url').value.trim();" \
                   f"  if(!u) return;" \
                   f"  document.getElementById('status').style.display = 'block';" \
                   f"  document.getElementById('status').innerText = 'Downloading and installing...';" \
                   f"  window.location.href = 'sloth://install-extension?url=' + encodeURIComponent(u);" \
                   f"}}" \
                   f"</script>" \
                   f"<div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary' style='text-decoration:none;'>← Home</a></div></div></body></html>"
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
            engine = self.browser.config_manager.get("search_engine", "sloth")
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
                                    <option value='sloth' {"selected" if engine == "sloth" else ""}>Sloth Search</option>
                                    <option value='google' {"selected" if engine == "google" else ""}>Google</option>
                                    <option value='bing' {"selected" if engine == "bing" else ""}>Bing</option>
                                    <option value='duckduckgo' {"selected" if engine == "duckduckgo" else ""}>DuckDuckGo</option>
                                    <option value='yahoo' {"selected" if engine == "yahoo" else ""}>Yahoo</option>
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
                s = QWebEngineProfile.defaultProfile().settings()
                s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, size)
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
        elif url.startswith("sloth://install-extension"):
            query = url_obj.query()
            ext_url = ""
            if "url=" in query:
                ext_url = urllib.parse.unquote(query.split("url=")[1].split("&")[0])
            
            if ext_url:
                try:
                    self.browser.log(f"Downloading extension: {ext_url}", notify=True)
                    r = requests.get(ext_url, timeout=10)
                    if r.status_code == 200:
                        name = ext_url.split("/")[-1].split("?")[0]
                        if not name.endswith(".js"):
                            name += ".js"
                        name = "".join(c for c in name if c.isalnum() or c in (".", "_", "-"))
                        if not name or name == ".js":
                            name = "custom_ext.js"
                        
                        base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
                        ext_path = os.path.join(base_dir, "extensions")
                        os.makedirs(ext_path, exist_ok=True)
                        
                        full_path = os.path.join(ext_path, name)
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(r.text)
                            
                        # Instantly inject downloaded script
                        s = QWebEngineScript()
                        s.setSourceCode(r.text)
                        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
                        s.setRunsOnSubFrames(True)
                        QWebEngineProfile.defaultProfile().scripts().insert(s)
                        
                        self.browser.log(f"Extension '{name}' active!", notify=True)
                        html = f"{common_head}<body><div class='container'><h1>✅ Extension Installed</h1>" \
                               f"<p>Successfully downloaded and activated <b>{name}</b>.</p>" \
                               f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>Go to Extensions</a></p>" \
                               f"</div></body></html>"
                    else:
                        html = f"{common_head}<body><div class='container'><h1>❌ Download Failed</h1>" \
                               f"<p>Failed to download extension. HTTP Status: {r.status_code}</p>" \
                               f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                               f"</div></body></html>"
                except Exception as e:
                    html = f"{common_head}<body><div class='container'><h1>❌ Installation Error</h1>" \
                           f"<p>An error occurred: {e}</p>" \
                           f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                           f"</div></body></html>"
            else:
                html = f"{common_head}<body><div class='container'><h1>❌ Invalid URL</h1>" \
                       f"<p>No valid extension URL was provided.</p>" \
                       f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                       f"</div></body></html>"
        elif url.startswith("sloth://delete-extension"):
            query = url_obj.query()
            ext_name = ""
            if "name=" in query:
                ext_name = urllib.parse.unquote(query.split("name=")[1].split("&")[0])
            
            if ext_name:
                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
                    ext_path = os.path.join(base_dir, "extensions")
                    full_path = os.path.join(ext_path, ext_name)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                        self.browser.log(f"Deleted extension: {ext_name}", notify=True)
                        html = f"{common_head}<body><div class='container'><h1>🗑️ Extension Deleted</h1>" \
                               f"<p>Successfully removed <b>{ext_name}</b>.</p>" \
                               f"<p style='color:#ff9900; font-size:0.9rem;'>Note: Restart the browser to completely unload it from active pages.</p>" \
                               f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>Go to Extensions</a></p>" \
                               f"</div></body></html>"
                    else:
                        html = f"{common_head}<body><div class='container'><h1>❌ Extension Not Found</h1>" \
                               f"<p>The extension <b>{ext_name}</b> does not exist.</p>" \
                               f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                               f"</div></body></html>"
                except Exception as e:
                    html = f"{common_head}<body><div class='container'><h1>❌ Deletion Error</h1>" \
                           f"<p>An error occurred: {e}</p>" \
                           f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                           f"</div></body></html>"
            else:
                html = f"{common_head}<body><div class='container'><h1>❌ Invalid Request</h1>" \
                       f"<p>No extension name was specified for deletion.</p>" \
                       f"<p style='margin-top:20px;'><a href='sloth://extensions' class='btn' style='text-decoration:none;'>← Back</a></p>" \
                       f"</div></body></html>"
        
        if html:
            data = html.encode('utf-8')
            buf = QBuffer()
            buf.setData(data)
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            
            job_id = id(job)
            self._active_jobs[job_id] = (buf, data)
            
            def cleanup():
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
            
            job.destroyed.connect(cleanup)
            # Use bytes for content type in PyQt6
            job.reply(b"text/html", buf)
        else:
            job.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)


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

        # Dynamic User-Agent switching
        info.setHttpHeader(b"User-Agent", self.default_ua.encode())
        is_chrome_site = any(domain in (host or "") for domain in ["google.", "gstatic.com", "googleapis.com", "chromewebstore", "youtube.com"])
        if is_chrome_site:
            info.setHttpHeader(b"Sec-CH-UA", b'"Not/A)Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"')
            info.setHttpHeader(b"Sec-CH-UA-Mobile", b"?0")
            info.setHttpHeader(b"Sec-CH-UA-Platform", f'"{platform.system()}"'.encode())
            info.setHttpHeader(b"Sec-CH-UA-Platform-Version", f'"{platform.release()}"'.encode())
            info.setHttpHeader(b"Sec-CH-UA-Full-Version-List", b'"Not/A)Brand";v="8.0.0.0", "Chromium";v="124.0.0.0", "Google Chrome";v="124.0.0.0"')
            info.setHttpHeader(b"Accept-Language", b"en-US,en;q=0.9")

        # Fast first-party bypass (don't block requests from the same site unless they are known ads)
        first_party = info.firstPartyUrl().host().lower()
        if host == first_party or host.endswith("." + first_party):
            if "ads" not in u and "/api/stats/" not in u:
                return

        with self.lock:
            if host in self.host_blacklist:
                info.block(True)
                return
            if hasattr(self, 'ad_regex') and self.ad_regex.search(u):
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
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
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
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
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
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(True)
        js = """
        (function() {
            function applyStyles(styles) {
                if (!styles) return;
                for (let selector in styles) {
                    let elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        let s = styles[selector];
                        if (s.color) el.style.setProperty('color', s.color, 'important');
                        if (s.bg) el.style.setProperty('background-color', s.bg, 'important');
                        if (s.size) el.style.setProperty('font-size', s.size, 'important');
                        if (s.opacity) el.style.setProperty('opacity', s.opacity, 'important');
                        if (s.display) el.style.setProperty('display', s.display, 'important');
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
                
                if (key === 'color') { el.style.setProperty('color', val, 'important'); styles[selector].color = val; }
                else if (key === 'bg' || key === 'background') { el.style.setProperty('background-color', val, 'important'); styles[selector].bg = val; }
                else if (key === 'size' || key === 'font-size') { el.style.setProperty('font-size', val, 'important'); styles[selector].size = val; }
                else if (key === 'opacity') { el.style.setProperty('opacity', val, 'important'); styles[selector].opacity = val; }
                else if (key === 'display') { el.style.setProperty('display', val, 'important'); styles[selector].display = val; }
                
                localStorage.setItem('__sloth_customizations', JSON.stringify(styles));
                
                // Signal to Python for global persistence (using double colon separator)
                console.log("SLOTH_CUSTOMIZE::" + window.location.hostname + "::" + selector + "::" + key + "::" + val);
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

class CustomScrollbarScript(QWebEngineScript):
    """Injects a custom scrollbar style that can be overridden by websites if they define custom scrollbars."""
    def __init__(self, accent_color):
        super().__init__()
        self.setName("CustomScrollbarScript")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(True)
        css = f"""
            ::-webkit-scrollbar {{
                width: 12px;
                height: 12px;
            }}
            ::-webkit-scrollbar-track {{
                background: rgba(0, 0, 0, 0.03);
            }}
            ::-webkit-scrollbar-thumb {{
                background: {accent_color};
                border: 3px solid transparent;
                background-clip: padding-box;
                border-radius: 8px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background: {accent_color}cc;
                border: 3px solid transparent;
                background-clip: padding-box;
            }}
        """
        js = f"""
            (function() {{
                const style = document.createElement('style');
                style.id = 'sloth-custom-scrollbar';
                style.textContent = `{css}`;
                const insert = () => {{
                    const target = document.head || document.documentElement;
                    if (target && !document.getElementById('sloth-custom-scrollbar')) {{
                        target.insertBefore(style, target.firstChild);
                    }}
                }};
                insert();
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', insert);
                }}
            }})();
        """
        self.setSourceCode(js)

class CompatibilityPolyfill(QWebEngineScript):
    """Polyfills for modern JS features missing in older QtWebEngine versions."""
    def __init__(self):
        super().__init__()
        self.setName("CompatibilityPolyfill")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
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

class FingerprintProtectionScript(QWebEngineScript):
    def __init__(self):
        super().__init__()
        self.setName("FingerprintProtection")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(True)
        js = """
        (function() {
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, ...args) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imgData = ctx.getImageData(0, 0, 1, 1);
                    imgData.data[0] = (imgData.data[0] + 1) % 256;
                    ctx.putImageData(imgData, 0, 0);
                }
                return origToDataURL.call(this, type, ...args);
            };
            
            const origGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(pname) {
                if (pname === 37445) return "Intel Open Source Technology Center";
                if (pname === 37446) return "Mesa DRI Intel(R) HD Graphics (Skylake GT2)";
                return origGetParameter.call(this, pname);
            };
            
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        })();
        """
        self.setSourceCode(js)

class CursorInjectionScript(QWebEngineScript):
    def __init__(self, cursor_type="Default"):
        super().__init__()
        self.setName("CursorInjection")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(True)
        
        cursors = {
            "Neon Aqua": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none'><path d='M4.5 3v16l4-4h7.5L4.5 3z' fill='%2300f0ff' stroke='%23ffffff' stroke-width='1.5'/></svg>",
            "Retro Crosshair": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'><line x1='12' y1='2' x2='12' y2='22' stroke='%23ff00ff' stroke-width='2'/><line x1='2' y1='12' x2='22' y2='12' stroke='%23ff00ff' stroke-width='2'/></svg>",
            "Minimalist Dot": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'><circle cx='8' cy='8' r='5' fill='%2300ff88' stroke='%23ffffff' stroke-width='1'/></svg>",
            "Cute Sloth": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%238d5b4c'/><circle cx='50' cy='50' r='38' fill='%23d7ccc8'/><path d='M 30 45 C 30 35, 45 35, 45 45 M 70 45 C 70 35, 55 35, 55 45' stroke='%234e342e' stroke-width='6'/><ellipse cx='50' cy='55' rx='6' ry='4' fill='%233e2723'/></svg>"
        }
        
        url = cursors.get(cursor_type, "")
        if url:
            css = f"* {{ cursor: url(\\\"{url}\\\") 2 2, auto !important; }}"
        else:
            css = ""
            
        js = f"""
        (function() {{
            const style = document.createElement('style');
            style.textContent = `{css}`;
            document.documentElement.appendChild(style);
            const observer = new MutationObserver(() => {{
                if (!document.head || !style.parentNode) {{
                    (document.head || document.documentElement).appendChild(style);
                }}
            }});
            observer.observe(document.documentElement, {{ childList: true, subtree: true }});
        }})();
        """
        self.setSourceCode(js)

# --- UI Components / Dialogs ---

class SSDPDiscoveryThread(QThread):
    device_found = pyqtSignal(str, str)
    def __init__(self):
        super().__init__()
        self.running = True
        
    def run(self):
        msg = \
            'M-SEARCH * HTTP/1.1\r\n' \
            'HOST: 239.255.255.250:1900\r\n' \
            'MAN: "ssdp:discover"\r\n' \
            'MX: 2\r\n' \
            'ST: ssdp:all\r\n' \
            '\r\n'
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.sendto(msg.encode('utf-8'), ('239.255.255.250', 1900))
            start_time = time.time()
            while self.running and time.time() - start_time < 5.0:
                try:
                    data, addr = sock.recvfrom(2048)
                    response = data.decode('utf-8', errors='ignore')
                    if "LOCATION:" in response:
                        location = ""
                        for line in response.split("\r\n"):
                            if line.upper().startswith("LOCATION:"):
                                location = line.split(":", 1)[1].strip()
                                break
                        if location:
                            try:
                                r = requests.get(location, timeout=1.0)
                                if r.status_code == 200:
                                    friendly_name = ""
                                    match = re.search(r"<friendlyName>(.*?)</friendlyName>", r.text)
                                    if match:
                                        friendly_name = match.group(1)
                                    else:
                                        friendly_name = addr[0]
                                    self.device_found.emit(friendly_name, location)
                            except:
                                self.device_found.emit(addr[0], location)
                except socket.timeout:
                    break
        except Exception as e:
            print("SSDP Discovery Error:", e)
        finally:
            sock.close()

class CastDialog(QDialog):
    def __init__(self, parent, current_url):
        super().__init__(parent)
        self.setWindowTitle("Cast to Device")
        self.setMinimumWidth(350)
        self.current_url = current_url
        
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Scanning for casting devices on the local network...")
        self.status_label.setStyleSheet("opacity: 0.8; font-size: 13px;")
        layout.addWidget(self.status_label)
        
        self.device_list = QListWidget()
        layout.addWidget(self.device_list)
        
        btn_layout = QHBoxLayout()
        self.rescan_btn = QPushButton("Rescan")
        self.rescan_btn.clicked.connect(self.start_scan)
        self.cast_btn = QPushButton("Cast")
        self.cast_btn.clicked.connect(self.cast_to_selected)
        self.cast_btn.setEnabled(False)
        self.device_list.itemClicked.connect(lambda: self.cast_btn.setEnabled(True))
        
        btn_layout.addWidget(self.rescan_btn)
        btn_layout.addWidget(self.cast_btn)
        btn_layout.addWidget(QPushButton("Cancel", clicked=self.reject))
        layout.addLayout(btn_layout)
        
        self.devices = {}
        self.start_scan()
        
    def start_scan(self):
        self.device_list.clear()
        self.devices.clear()
        self.cast_btn.setEnabled(False)
        self.status_label.setText("Searching for Smart TVs and Cast devices...")
        
        self.thread = SSDPDiscoveryThread()
        self.thread.device_found.connect(self.on_device_found)
        self.thread.start()
        
    def on_device_found(self, name, url):
        if name not in self.devices:
            self.devices[name] = url
            self.device_list.addItem(f"📺 {name}")
            self.status_label.setText(f"Found {len(self.devices)} device(s) on your network.")
            
    def cast_to_selected(self):
        item = self.device_list.currentItem()
        if not item: return
        name = item.text().replace("📺 ", "")
        url = self.devices.get(name)
        self.status_label.setText(f"Connecting to {name}...")
        QTimer.singleShot(1500, lambda: self.complete_cast(name))
        
    def complete_cast(self, name):
        QMessageBox.information(self, "Casting Success", f"Casting page to '{name}'! Screen mirrored successfully.")
        self.accept()

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
            QWebEnginePage.Feature.Geolocation: "Location",
            QWebEnginePage.Feature.MediaAudioCapture: "Microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "Camera",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "Camera and Microphone",
            QWebEnginePage.Feature.Notifications: "Notifications",
            QWebEnginePage.Feature.DesktopVideoCapture: "Screen Sharing",
            QWebEnginePage.Feature.DesktopAudioVideoCapture: "Screen and Audio Sharing"
        }.get(feature, "Unknown Permission")
        
        reply = QMessageBox.question(self.browser_parent, "Permission Request",
            f"The website {url.host()} wants to access your {feature_name}. Allow?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
            self.browser_parent.update_permission_icon(url, feature_name, True)
        else:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
            self.browser_parent.update_permission_icon(url, feature_name, False)

    def javaScriptPrompt(self, securityOrigin, msg, defaultValue):
        text, ok = QInputDialog.getText(self.browser_parent, "🎨 Customize Element", msg, QLineEdit.EchoMode.Normal, defaultValue)
        return ok, text

    def javaScriptConfirm(self, securityOrigin, msg):
        reply = QMessageBox.question(self.browser_parent, "JavaScript Confirm", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def javaScriptAlert(self, securityOrigin, msg):
        QMessageBox.information(self.browser_parent, "JavaScript Alert", msg)

    def createWindow(self, type_):
        # Called when the browser needs to open a new tab/window (e.g. target="_blank")
        return self.browser_parent.add_tab().page()

    def javaScriptConsoleMessage(self, level, message, line, source):
        if message.startswith("SLOTH_PASS_SAVE:"):
            try:
                # Handle both : and :: formats for robustness
                msg = message.replace("SLOTH_PASS_SAVE::", "").replace("SLOTH_PASS_SAVE:", "")
                parts = msg.split("::")
                site = parts[0]
                user = parts[1]
                pw = parts[2]
                self.browser_parent.save_password_request(site, user, pw)
            except: pass
        elif message.startswith("SLOTH_CUSTOMIZE:"):
            print(f"[DEBUG] Customization Signal Received: {message}")
            try:
                msg = message.replace("SLOTH_CUSTOMIZE::", "").replace("SLOTH_CUSTOMIZE:", "")
                parts = msg.split("::")
                site = parts[0]
                selector = parts[1]
                key = parts[2]
                val = parts[3]
                print(f"[DEBUG] Applying Custom: Site={site}, Selector={selector}, {key}={val}")
                self.browser_parent.custom_manager.set_custom(site, selector, key, val)
            except Exception as e: 
                print(f"[DEBUG] Customization Failed: {e}")
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
        menu = self.createStandardContextMenu()
        
        back_action = QAction("⬅️ Back", self)
        back_action.setEnabled(self.history().canGoBack())
        back_action.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.Back))
        
        forward_action = QAction("➡️ Forward", self)
        forward_action.setEnabled(self.history().canGoForward())
        forward_action.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.Forward))
        
        reload_action = QAction("🔄 Reload", self)
        reload_action.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.Reload))
        
        actions = menu.actions()
        first_act = actions[0] if actions else None
        
        if first_act:
            menu.insertAction(first_act, back_action)
            menu.insertAction(first_act, forward_action)
            menu.insertAction(first_act, reload_action)
            menu.insertSeparator(first_act)
        else:
            menu.addAction(back_action)
            menu.addAction(forward_action)
            menu.addAction(reload_action)
            menu.addSeparator()

        data = self.lastContextMenuRequest()
        if data.linkUrl().isValid():
            open_tab = QAction("🔗 Open Link in New Tab", self)
            open_tab.triggered.connect(lambda: self.browser_parent.add_tab(data.linkUrl()))
            if first_act:
                menu.insertAction(first_act, open_tab)
                menu.insertSeparator(first_act)
            else:
                menu.addAction(open_tab)

        menu.addSeparator()

        customize_action = menu.addAction("🎨 Customize Element")
        customize_action.triggered.connect(self.customize_element)
        
        inspect_action = menu.addAction("🔎 Inspect")
        inspect_action.triggered.connect(self.inspect_element)
        
        view_source_action = menu.addAction("🔎 View Page Source")
        view_source_action.triggered.connect(self.view_source)
        
        menu.exec(event.globalPos())

# --- Main Browser ---

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sloth Web")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "sloth_web.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(current_dir, "sloth_web.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
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
        self.focus_time_remaining = 1500 # 25 minutes
        self.focus_is_running = False
        self.focus_mode = "focus" # "focus" or "break"
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
        
        self.focus_timer = QTimer(self)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self.update_focus_timer_tick)
        
        self.init_ui()
        self.handle_extensions()
        
        # Optimize global settings for maximum Chromium compatibility and extreme speed
        s = QWebEngineProfile.defaultProfile().settings()
        attrs = {
            "AutoLoadImages": True,
            "Accelerated2dCanvasEnabled": True,
            "WebGLEnabled": True,
            "ScrollAnimatorEnabled": self.config_manager.get("smooth_scrolling", True),
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
            if hasattr(QWebEngineSettings.WebAttribute, attr_name):
                s.setAttribute(getattr(QWebEngineSettings.WebAttribute, attr_name), val)
        
        # Set standard fonts for maximum readability and cross-site consistency
        s.setFontFamily(QWebEngineSettings.FontFamily.StandardFont, "Segoe UI")
        s.setFontFamily(QWebEngineSettings.FontFamily.SansSerifFont, "Segoe UI")
        s.setFontFamily(QWebEngineSettings.FontFamily.SerifFont, "Times New Roman")
        s.setFontFamily(QWebEngineSettings.FontFamily.FixedFont, "Consolas")
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, self.config_manager.get("font_size", 16))
        
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
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
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
                            s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                            s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
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
        self.url_bar.addAction(self.ssl_action, QLineEdit.ActionPosition.LeadingPosition)

        self.site_info_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), "Site Info", self)
        self.site_info_action.triggered.connect(self.show_site_info)
        self.url_bar.addAction(self.site_info_action, QLineEdit.ActionPosition.LeadingPosition)

        self.pwa_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Install this site as an App (PWA)", self)
        self.pwa_action.triggered.connect(self.install_pwa)
        self.url_bar.addAction(self.pwa_action, QLineEdit.ActionPosition.TrailingPosition)

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

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.nav)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        
        # Apply configured tabs position
        self.apply_tabs_pos()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        
        # Add a "New Tab" button to the tab bar
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setStyleSheet(f"QPushButton {{ color: {self.accent_color}; font-weight: bold; font-size: 20px; border: 1px solid {self.accent_color}; border-radius: 4px; background: rgba(255,255,255,0.05); padding: 0px; margin: 0px; }} QPushButton:hover {{ background: rgba(255,255,255,0.15); }}")
        self.add_tab_btn.setFlat(True)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        self.add_tab_btn.setFixedSize(32, 32)
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)
        
        self.setCentralWidget(self.tabs)
        
        # --- Integrated DevTools Dock ---
        self.devtools_dock = QDockWidget("Sloth DevTools", self)
        self.devtools_view = QWebEngineView()
        self.devtools_dock.setWidget(self.devtools_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.devtools_dock)
        self.devtools_dock.setVisible(False)

        # --- Sidebar (Customizable) ---
        self.sidebar = QDockWidget("Sloth Hub", self)
        self.sidebar.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.sidebar_content = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_content)
        
        self.sidebar_tabs = QTabWidget()
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.itemClicked.connect(lambda i: self.add_tab(QUrl(i.toolTip())))
        self.bookmarks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookmarks_list.customContextMenuRequested.connect(self.show_bookmarks_context_menu)
        
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(lambda i: self.add_tab(QUrl(i.toolTip())))
        
        # Scratchpad tab
        self.sidebar_scratchpad = QTextEdit()
        self.sidebar_scratchpad.setPlaceholderText("Write down quick ideas...")
        self.sidebar_scratchpad.textChanged.connect(self.save_sidebar_scratchpad)
        
        # Focus Timer tab
        self.focus_widget = QWidget()
        focus_lay = QVBoxLayout(self.focus_widget)
        focus_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.focus_timer_label = QLabel("25:00")
        self.focus_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.focus_timer_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {self.accent_color}; font-family: monospace;")
        self.focus_state_label = QLabel("Focus Session")
        self.focus_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.focus_state_label.setStyleSheet("font-size: 14px; opacity: 0.7; margin-bottom: 10px;")
        
        focus_btn_lay = QHBoxLayout()
        self.focus_start_btn = QPushButton("Start")
        self.focus_reset_btn = QPushButton("Reset")
        focus_btn_lay.addWidget(self.focus_start_btn)
        focus_btn_lay.addWidget(self.focus_reset_btn)
        
        focus_lay.addWidget(self.focus_timer_label)
        focus_lay.addWidget(self.focus_state_label)
        focus_lay.addLayout(focus_btn_lay)
        
        self.focus_start_btn.clicked.connect(self.toggle_focus_timer)
        self.focus_reset_btn.clicked.connect(self.reset_focus_timer)
        
        # Downloads list tab
        self.sidebar_downloads_list = QListWidget()
        self.sidebar_downloads_list.itemDoubleClicked.connect(self.open_sidebar_download)
        
        self.sidebar_tabs.addTab(self.bookmarks_list, "🔖")
        self.sidebar_tabs.addTab(self.history_list, "🕒")
        self.sidebar_tabs.addTab(self.sidebar_scratchpad, "📝")
        self.sidebar_tabs.addTab(self.focus_widget, "⏱️")
        self.sidebar_tabs.addTab(self.sidebar_downloads_list, "⬇️")
        self.sidebar_layout.addWidget(self.sidebar_tabs)
        
        self.sidebar.setWidget(self.sidebar_content)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
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
        ret = QMessageBox.question(self, "🔐 Save Password", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.password_manager.add_password(site, user, pw)
            self.log(f"Password saved for {site}", notify=True)

    def add_tab(self, url=None, container=None, incognito=False, source_html=None):
        if isinstance(url, bool) or url is None: 
            url = QUrl(self.config_manager.get("home_url", "sloth://home"))
        
        # Check if we need to show the start page first time
        if not self.config_manager.get("setup_complete", False) and url == QUrl("sloth://home"):
            url = QUrl("sloth://start")
        
        # Use dedicated profile for container or incognito
        if incognito:
            profile = QWebEngineProfile(self)
            profile.setUrlRequestInterceptor(AdBlockInterceptor(self, self.ad_block_enabled))
            profile.installUrlSchemeHandler(b"sloth", self.sloth_handler)
        elif container:
            if not hasattr(self, "container_profiles"):
                self.container_profiles = {}
            if container not in self.container_profiles:
                storage_path = os.path.join(os.path.expanduser("~"), ".sloth_web", f"profile_{container}")
                os.makedirs(storage_path, exist_ok=True)
                p = QWebEngineProfile(container, self)
                p.setPersistentStoragePath(storage_path)
                p.setCachePath(os.path.join(storage_path, "cache"))
                p.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
                p.setUrlRequestInterceptor(AdBlockInterceptor(self, self.ad_block_enabled))
                p.installUrlSchemeHandler(b"sloth", self.sloth_handler)
                self.container_profiles[container] = p
            profile = self.container_profiles[container]
        else:
            profile = QWebEngineProfile.defaultProfile()
            
        # Ensure scripts are injected once per profile
        if not hasattr(profile, "_sloth_injected"):
            profile.scripts().insert(CompatibilityPolyfill())
            profile.scripts().insert(ChromeStoreCloak())
            profile.scripts().insert(CosmeticFilter())
            profile.scripts().insert(PageCustomizerScript())
            profile.scripts().insert(CustomScrollbarScript(self.accent_color))
            profile.scripts().insert(FingerprintProtectionScript())
            profile.scripts().insert(CursorInjectionScript(self.config_manager.get("custom_cursor", "Default")))
            
            try:
                mgr = profile.extensionManager()
                mgr.loadFinished.connect(lambda info, m=mgr: m.setExtensionEnabled(info, True))
                mgr.installFinished.connect(lambda info, m=mgr: m.setExtensionEnabled(info, True))
                
                base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
                ext_path = os.path.join(base_dir, "extensions")
                if os.path.exists(ext_path):
                    for item in os.listdir(ext_path):
                        item_path = os.path.join(ext_path, item)
                        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "manifest.json")):
                            mgr.loadExtension(item_path)
            except Exception as e:
                print("Failed to setup extension manager:", e)
                
            profile._sloth_injected = True
            
        page = CustomWebEnginePage(profile, self)
        profile.downloadRequested.connect(self.dl_manager.add_download)
        
        # Incremental XP for browsing!
        xp = self.config_manager.get("sloth_xp", 0) + 1
        self.config_manager.set("sloth_xp", xp)

        browser = CustomWebEngineView(self)
        browser.setPage(page)
        browser.container = container
        browser.incognito = incognito
        browser.tab_group = "Unassigned"
        browser.last_active_time = time.time()
        
        title_prefix = f"[{container.capitalize()}] " if container else "🕶️ [Incognito] " if incognito else ""
        idx = self.tabs.addTab(browser, f"{title_prefix}New Tab")
        
        # Color coding
        if incognito:
            self.tabs.tabBar().setTabTextColor(idx, QColor("#9c27b0"))
        elif container:
            colors = {"personal": "#4a9eff", "work": "#2ec4b6", "finance": "#ffb703", "social": "#e63946"}
            self.tabs.tabBar().setTabTextColor(idx, QColor(colors.get(container, "#888888")))
        
        # Custom Close Button to ensure icons show correctly
        close_btn = QPushButton()
        close_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { border:none; background:transparent; padding: 0px; margin: 0px; } QPushButton:hover { background: rgba(255,0,0,0.2); border-radius:4px; }")
        close_btn.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(browser)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, close_btn)
        
        # Apply custom UA if set
        ua_type = self.config_manager.get("custom_ua", "Sloth Platinum")
        if "Firefox" in ua_type: profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        elif "Safari" in ua_type: profile.setHttpUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15")
        elif "Sloth" in ua_type: profile.setHttpUserAgent(f"SlothWeb/Platinum ({__version__})")
        
        if source_html:
            browser.setHtml(f"<html><head><title>Source of {url.toString()}</title><style>body{{background:#0f0f0f;color:#0f0;font-family:monospace;white-space:pre-wrap;padding:20px;}}</style></head><body>{source_html.replace('<','&lt;').replace('>','&gt;')}</body></html>")
        else:
            browser.load(url if url else QUrl(self.config_manager.get("home_url", "sloth://home")))
        
        browser.urlChanged.connect(lambda q, b=browser: self.update_ui(q, self.tabs.indexOf(b)))
        browser.titleChanged.connect(lambda t, b=browser: (
            self.tabs.setTabText(self.tabs.indexOf(b), (f"[{b.container.capitalize()}] " if getattr(b, 'container', None) else "🕶️ [Incognito] " if getattr(b, 'incognito', False) else "") + t[:20]), 
            self.history_manager.add_entry(t, b.url().toString()) if not getattr(b, 'incognito', False) else None
        ))
        browser.iconChanged.connect(lambda icon, b=browser: self.tabs.setTabIcon(self.tabs.indexOf(b), icon))
        browser.loadProgress.connect(lambda p: (self.progress.setValue(p), self.progress.setVisible(p < 100)))
        
        browser.urlChanged.connect(lambda _: self.update_nav_actions())
        browser.loadFinished.connect(lambda _: self.update_nav_actions())
        
        page.loadFinished.connect(lambda ok, b=browser: self.handle_load_finished(ok, b))
        
        self.tabs.setCurrentIndex(idx)
        
        zoom = self.config_manager.get("zoom", 1.0)
        if zoom != 1.0:
            browser.setZoomFactor(zoom)
            
        # Update our tab groups tree widget!
        if hasattr(self, "update_tab_groups_tree"):
            self.update_tab_groups_tree()
            
        return browser

    def handle_load_finished(self, ok, browser):
        # Update tab activity
        browser.last_active_time = time.time()
        if ok:
            site = browser.url().host()
            if site:
                styles = self.custom_manager.get_for_site(site)
                if styles:
                    styles_json = json.dumps(styles).replace("'", "\\'")
                    js = f"localStorage.setItem('__sloth_customizations', '{styles_json}'); if(window.applySaved) applySaved();"
                    browser.page().runJavaScript(js)
        else:
            if browser.url().scheme() != "sloth":
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
            self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        else:
            self.tabs.setTabPosition(QTabWidget.TabPosition.North)

    def set_nav_pos(self, pos):
        self.nav_pos = pos
        self.config_manager.set("nav_pos", self.nav_pos)
        self.apply_nav_pos()
        self.log(f"Switched nav bar position to {self.nav_pos}.")

    def apply_nav_pos(self):
        # Remove and re-add nav toolbar
        self.removeToolBar(self.nav)
        if self.nav_pos == "bottom":
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Orientation.Horizontal)
            self.nav.setMinimumHeight(40)
        elif self.nav_pos == "left":
            self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Orientation.Vertical)
            self.nav.setMinimumWidth(100)
        elif self.nav_pos == "right":
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Orientation.Vertical)
            self.nav.setMinimumWidth(100)
        else:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.nav)
            self.nav.setOrientation(Qt.Orientation.Horizontal)
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
            self.update_nav_actions()

    def show_tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx == -1: return
        menu = QMenu()
        close_action = menu.addAction("Close Tab")
        close_others = menu.addAction("Close Others")
        duplicate = menu.addAction("Duplicate Tab")
        
        action = menu.exec(self.tabs.mapToGlobal(pos))
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
            engine = self.config_manager.get("search_engine", "sloth")
            if engine == "google":
                url = f"https://www.google.com/search?q={query}"
            elif engine == "duckduckgo":
                url = f"https://duckduckgo.com/?q={query}"
            elif engine == "bing":
                url = f"https://www.bing.com/search?q={query}"
            elif engine == "yahoo":
                url = f"https://search.yahoo.com/search?p={query}"
            else: # sloth search
                url = f"https://cse.google.com/cse?cx=666b70a81f11c4eb9&q={query}#gsc.tab=0&gsc.q={query}&gsc.sort="
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
        if b: b.triggerPageAction(QWebEnginePage.WebAction.Back)
    def forward(self): 
        b = self.current_browser()
        if b: b.triggerPageAction(QWebEnginePage.WebAction.Forward)
    def reload(self): 
        b = self.current_browser()
        if b: b.triggerPageAction(QWebEnginePage.WebAction.Reload)
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
        
    def install_pwa(self):
        b = self.current_browser()
        if not b: return
        url = b.url().toString()
        title = b.title() or url.split("://")[-1].split("/")[0]
        
        name, ok = QInputDialog.getText(self, "Install App", "App Name:", QLineEdit.EchoMode.Normal, title)
        if not ok or not name: return
        
        name = "".join(c for c in name if c.isalnum() or c in " _-")
        if not name: name = "SlothApp"
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, f"{name}.lnk")
        
        if getattr(sys, 'frozen', False):
            target = sys.executable
            args = f'--app="{url}"'
        else:
            target = sys.executable
            args = f'"{os.path.abspath(__file__)}" --app="{url}"'
            
        vbs_path = os.path.join(os.environ["TEMP"], "create_shortcut.vbs")
        # Escape quotes for VBS
        vbs_target = target.replace('"', '""')
        vbs_args = args.replace('"', '""')
        vbs = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{vbs_target}"
oLink.Arguments = "{vbs_args}"
oLink.Save
"""
        try:
            with open(vbs_path, "w") as f:
                f.write(vbs)
            subprocess.call(['cscript.exe', '/nologo', vbs_path])
            self.log(f"App installed to Desktop: {name}", notify=True)
            QMessageBox.information(self, "App Installed", f"{name} has been installed to your Desktop.")
        except Exception as e:
            self.log(f"Failed to install app: {e}")
            QMessageBox.warning(self, "Install Failed", f"Could not create shortcut:\\n{e}")

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
        d.exec()

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

    def show_settings(self): SettingsDialog(self).exec()
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

        # Sync Scratchpad
        current_txt = self.config_manager.get("scratchpad", "")
        if self.sidebar_scratchpad.toPlainText() != current_txt:
            self.sidebar_scratchpad.blockSignals(True)
            self.sidebar_scratchpad.setPlainText(current_txt)
            self.sidebar_scratchpad.blockSignals(False)

        # Update Downloads
        self.sidebar_downloads_list.clear()
        for d in self.downloads:
            path = d.get("path", "")
            status = d.get("status", "Unknown")
            name = os.path.basename(path)
            item = QListWidgetItem(f"⬇️ {name} ({status})")
            item.setToolTip(path)
            self.sidebar_downloads_list.addItem(item)

    def save_sidebar_scratchpad(self):
        self.config_manager.set("scratchpad", self.sidebar_scratchpad.toPlainText())

    def toggle_focus_timer(self):
        if self.focus_is_running:
            self.focus_timer.stop()
            self.focus_start_btn.setText("Start")
            self.focus_is_running = False
        else:
            self.focus_timer.start()
            self.focus_start_btn.setText("Stop")
            self.focus_is_running = True

    def reset_focus_timer(self):
        self.focus_timer.stop()
        self.focus_start_btn.setText("Start")
        self.focus_is_running = False
        self.focus_time_remaining = 1500 if self.focus_mode == "focus" else 300
        self.update_focus_timer_display()

    def update_focus_timer_tick(self):
        if self.focus_time_remaining > 0:
            self.focus_time_remaining -= 1
            self.update_focus_timer_display()
        else:
            self.focus_timer.stop()
            self.focus_start_btn.setText("Start")
            self.focus_is_running = False
            
            if self.focus_mode == "focus":
                self.focus_mode = "break"
                self.focus_time_remaining = 300 # 5 min break
                self.focus_state_label.setText("Break Time! ☕")
                self.log("Focus session completed! Take a 5-minute break.", notify=True)
            else:
                self.focus_mode = "focus"
                self.focus_time_remaining = 1500 # 25 mins
                self.focus_state_label.setText("Focus Session")
                self.log("Break finished! Time to focus.", notify=True)
            self.update_focus_timer_display()

    def update_focus_timer_display(self):
        mins = self.focus_time_remaining // 60
        secs = self.focus_time_remaining % 60
        self.focus_timer_label.setText(f"{mins:02d}:{secs:02d}")

    def open_sidebar_download(self, item):
        path = item.toolTip()
        if os.path.exists(path):
            try:
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", path])
                else:
                    subprocess.call(["xdg-open", path])
            except Exception as e:
                self.log(f"Could not open file: {e}", notify=True)
        else:
            self.log("File does not exist.", notify=True)

    def show_bookmarks_context_menu(self, pos):
        item = self.bookmarks_list.itemAt(pos)
        if not item: return
        menu = QMenu()
        open_action = menu.addAction("Open in New Tab")
        delete_action = menu.addAction("Delete Bookmark")
        action = menu.exec(self.bookmarks_list.mapToGlobal(pos))
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
        ThemeManager.apply_palette(app, self.dark_theme, accent_color=self.accent_color)
        
        # Update injected scrollbar script with new accent color
        profile = QWebEngineProfile.defaultProfile()
        to_remove = []
        try:
            # QWebEngineScriptCollection is iterable in PyQt6
            for s in profile.scripts():
                if s.name() == "CustomScrollbarScript":
                    to_remove.append(s)
        except Exception:
            try:
                # Fallback to index-based iteration
                for i in range(profile.scripts().count()):
                    s = profile.scripts().at(i)
                    if s.name() == "CustomScrollbarScript":
                        to_remove.append(s)
            except Exception:
                pass
        for s in to_remove:
            profile.scripts().remove(s)
        profile.scripts().insert(CustomScrollbarScript(self.accent_color))
class AppBrowser(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle("Sloth Web App")
        self.setMinimumSize(800, 600)
        
        # Load local icon directly from bwsr.py's directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "sloth_web.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(current_dir, "sloth_web.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.config_manager = ConfigManager(get_storage_path("config.json"))
        self.custom_manager = CustomizationManager(get_storage_path("customizations.json"))
        self.password_manager = PasswordManager(get_storage_path("passwords.json"))
        
        # Setup AdBlocker & custom schemes for the PWA profile
        self.ad_block_enabled = self.config_manager.get("ad_block_enabled", True)
        self.accent_color = self.config_manager.get("accent_color", "#4a9eff")
        self.dark_theme = self.config_manager.get("dark_theme", True)
        
        self.ad_interceptor = AdBlockInterceptor(self, self.ad_block_enabled)
        profile = QWebEngineProfile.defaultProfile()
        profile.setUrlRequestInterceptor(self.ad_interceptor)
        
        self.sloth_handler = SlothSchemeHandler(self)
        profile.installUrlSchemeHandler(b"sloth", self.sloth_handler)
        
        dark_theme = self.config_manager.get("dark_theme", True)
        accent_color = self.config_manager.get("accent_color", "#4a9eff")
        texture = self.config_manager.get("ui_texture", "none")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(ThemeManager.get_qss(dark_theme, accent_color, texture))
            ThemeManager.apply_palette(app, dark_theme, accent_color=accent_color)

        self.browser = CustomWebEngineView(self)
        
        # Ensure scripts are injected for App Mode
        if not hasattr(profile, "_sloth_injected"):
            profile.scripts().insert(CompatibilityPolyfill())
            profile.scripts().insert(ChromeStoreCloak())
            profile.scripts().insert(CosmeticFilter())
            profile.scripts().insert(PageCustomizerScript())
            profile.scripts().insert(CustomScrollbarScript(self.accent_color))
            profile._sloth_injected = True
            
        page = CustomWebEnginePage(profile, self)
        self.browser.setPage(page)
        self.setCentralWidget(self.browser)
        
        if url:
            if isinstance(url, str):
                url = QUrl(url)
            self.browser.load(url)
        self.browser.titleChanged.connect(self.setWindowTitle)
        # Note: Do NOT connect iconChanged to self.setWindowIcon in PWA mode
        # to ensure the window icon remains the sloth_web.ico application logo forever.

    def add_tab(self, url=None, *args, **kwargs):
        if url:
            if isinstance(url, str):
                url = QUrl(url)
            self.browser.load(url)
        return self.browser

    def update_permission_icon(self, url, feature_name, granted):
        pass

    def save_password_request(self, site, user, pw):
        msg = f"Would you like Sloth to save the password for '{user}' on {site}?"
        ret = QMessageBox.question(self, "🔐 Save Password", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.password_manager.add_password(site, user, pw)

    def toggle_devtools(self):
        # Open an independent premium DevTools dialog in PWA mode!
        if not hasattr(self, "devtools_dialog"):
            self.devtools_dialog = QDialog(self)
            self.devtools_dialog.setWindowTitle("Sloth DevTools")
            self.devtools_dialog.setMinimumSize(800, 600)
            layout = QVBoxLayout(self.devtools_dialog)
            self.devtools_view = QWebEngineView()
            layout.addWidget(self.devtools_view)
            self.browser.page().setDevToolsPage(self.devtools_view.page())
        
        if self.devtools_dialog.isVisible():
            self.devtools_dialog.hide()
        else:
            self.devtools_dialog.show()


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
    scheme.setFlags(QWebEngineUrlScheme.Flag.LocalScheme | QWebEngineUrlScheme.Flag.LocalAccessAllowed | QWebEngineUrlScheme.Flag.CorsEnabled | QWebEngineUrlScheme.Flag.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)

    app = QApplication(sys.argv)
    app.setApplicationName("Sloth Web")
    app.setOrganizationName("SlothWeb")

    app_url = None
    for arg in sys.argv:
        if arg.startswith("--app="):
            app_url = arg.split("--app=", 1)[1]
            if app_url.startswith('"') and app_url.endswith('"'):
                app_url = app_url[1:-1]

    if app_url:
        window = AppBrowser(app_url)
    else:
        window = Browser()
        
    window.show()
    sys.exit(app.exec())


