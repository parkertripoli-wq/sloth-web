import sys
import os
import json
import requests
import re
import webbrowser
import subprocess
import urllib.parse
import time
from PyQt5.QtCore import QUrl, Qt, QTimer, pyqtSignal, QStringListModel, QBuffer
from PyQt5.QtWidgets import (QMainWindow, QToolBar, QAction, QLineEdit, 
                             QProgressBar, QTabWidget, QStatusBar, QWidget, 
                             QVBoxLayout, QPushButton, QTabBar, QFileDialog, 
                             QMenu, QInputDialog, QFormLayout, QGroupBox, 
                             QHBoxLayout, QSlider, QApplication, QCompleter,
                             QDialog, QListWidget, QDialogButtonBox, QMessageBox,
                             QListWidgetItem, QTextEdit, QColorDialog)
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
        url = f"http://suggestqueries.google.com/complete/search?client=firefox&q={query}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()[1]
    except Exception:
        pass
    return []

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
        val = self.passwords[site]
        if not isinstance(val, list): val = []; self.passwords[site] = val
        val.append({"user": username, "pass": password})
        self.save()

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
        try:
            with open("version.txt", "r") as f: self.local_version = f.read().strip()
        except: self.local_version = "0.0.0"
        self.version_url = "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/version.txt"
        self.exe_url = "https://github.com/parkertripoli-wq/sloth-web/releases/latest/download/SlothWebBrowser.exe"

    def check_for_updates(self):
        try:
            response = requests.get(self.version_url, timeout=5)
            response.raise_for_status()
            remote_version = response.text.strip()
            if remote_version > self.local_version:
                reply = QMessageBox.question(self.parent, "Update Available", f"A new version ({remote_version}) is available. Update now?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes: self.download_and_install(remote_version)
        except Exception:
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
            
            with open("version.txt", "w") as f:
                f.write(version)
                
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
        if not HAS_REGISTRY: return False
        try:
            exe_path = sys.executable if not getattr(sys, 'frozen', False) else sys.executable
            app_name = "SlothWebBrowser"
            
            # 1. Register the application
            key_path = rf"Software\Classes\{app_name}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Sloth Web Browser HTML Document")
                with winreg.CreateKey(key, "DefaultIcon") as icon_key:
                    winreg.SetValue(icon_key, "", winreg.REG_SZ, f"{exe_path},0")
                with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                    winreg.SetValue(cmd_key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')

            # 2. Register for protocols
            protocols = ["http", "https"]
            for proto in protocols:
                proto_path = rf"Software\Classes\{proto}\shell\open\command"
                # This part is more sensitive on modern Windows and might require user confirmation in Settings
                # But we register the capability
                pass

            # 3. Register as a browser capability
            cap_path = rf"Software\Clients\StartMenuInternet\{app_name}\Capabilities"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_path) as key:
                winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "Sloth Web")
                winreg.SetValueEx(key, "ApplicationDescription", 0, winreg.REG_SZ, "Simple, Fast, Secure Sloth Browser")
                with winreg.CreateKey(key, "URLAssociations") as url_key:
                    winreg.SetValueEx(url_key, "http", 0, winreg.REG_SZ, app_name)
                    winreg.SetValueEx(url_key, "https", 0, winreg.REG_SZ, app_name)
            
            return True
        except Exception as e:
            print(f"Registry error: {e}")
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

NEON_VOID_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>NEON VOID – DNS_PROBE_POSSIBLE</title>
  <style>
    :root {
      --bg: #060014;
      --glow-primary: #00ffee;
      --glow-accent: #ff0099;
      --text: #d0ffff;
    }
    body.light-mode {
      --bg: #f0e8ff;
      --glow-primary: #0066aa;
      --glow-accent: #cc0066;
      --text: #1a0033;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Courier New', Courier, monospace;
      -webkit-overflow-scrolling: touch;
    }
    #scanlines {
      position: fixed; inset:0; pointer-events:none; z-index:2;
      background: repeating-linear-gradient(transparent 0, transparent 4px, rgba(0,0,0,0.5) 4px, rgba(0,0,0,0.5) 8px);
      animation: scan 12s linear infinite;
      opacity: 0.5;
    }
    @keyframes scan { 0% { transform: translateY(-100%); } 100% { transform: translateY(100%); } }
    canvas#bg { position:fixed; inset:0; z-index:1; pointer-events:none; }
    .container {
      position: relative;
      z-index: 10;
      padding: 1.5rem;
      min-height: 100vh;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      max-width: 1500px;
      margin: 0 auto;
    }
    h1 {
      font-size: clamp(5rem, 12vw, 10rem);
      text-align: center;
      background: linear-gradient(90deg, var(--glow-accent), var(--glow-primary), var(--glow-accent));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      animation: hue 20s infinite, glitch 3s infinite;
      text-shadow: 0 0 40px var(--glow-accent), 0 0 80px var(--glow-primary);
    }
    @keyframes hue { 0%,100% { filter: hue-rotate(0deg); } 50% { filter: hue-rotate(180deg); } }
    @keyframes glitch { 0%,100%{transform:translate(0);} 20%{transform:translate(-3px,2px);} 40%{transform:translate(3px,-2px);} }
    h2 { text-align:center; font-size:2.5rem; color:var(--glow-primary); text-shadow:0 0 20px currentColor; }
    .code { font-size:2rem; color:var(--glow-accent); text-align:center; letter-spacing:8px; margin:1rem 0; }
    .msg { text-align:center; font-size:1.4rem; margin:1.5rem 0; opacity:0.9; }
    .games-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.5rem;
      margin: 2rem 0;
    }
    .game-card {
      background: rgba(20,0,40,0.6);
      border: 2px solid var(--glow-primary);
      border-radius: 12px;
      padding: 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: all 0.3s;
      backdrop-filter: blur(6px);
    }
    .game-card:hover {
      transform: translateY(-8px);
      box-shadow: 0 0 40px var(--glow-primary);
      border-color: var(--glow-accent);
    }
    .controls {
      text-align: center;
      margin: 1.5rem 0;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 1rem;
    }
    .neon-btn {
      background: transparent;
      border: 2px solid var(--glow-primary);
      color: var(--glow-primary);
      padding: 0.8rem 1.6rem;
      font-size: 1.1rem;
      border-radius: 50px;
      cursor: pointer;
      transition: all 0.3s;
    }
    .neon-btn:hover { background: rgba(0,255,238,0.15); box-shadow: 0 0 30px var(--glow-primary); }
    #gameArea { display: none; flex-direction: column; align-items: center; padding: 1rem; background: rgba(0,0,0,0.7); border-radius: 16px; margin: 2rem 0; }
    #gameCanvas { border: 3px solid var(--glow-primary); border-radius: 10px; background: #0004; max-width: 100%; touch-action: none; }
    #instructions { font-size: 1.3rem; margin: 1rem 0; color: #ffee00; text-shadow: 0 0 10px #ffee00; }
    #settingsModal {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.85);
      z-index: 100;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .settings-content {
      background: rgba(20,0,40,0.9);
      border: 3px solid var(--glow-accent);
      border-radius: 16px;
      padding: 2rem;
      max-width: 500px;
      width: 90%;
      color: var(--text);
    }
    label { display: block; margin: 1rem 0; font-size: 1.2rem; }
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

# --- Theming & UI Styles ---

class ThemeManager:
    @staticmethod
    def get_qss(dark=True, color="#4a9eff"):
        bg = "#1e1e1e" if dark else "#ffffff"
        fg = "#e0e0e0" if dark else "#333333"
        nav_bg = "rgba(45, 45, 45, 0.8)" if dark else "rgba(240, 240, 240, 0.8)"
        border = "#3f3f3f" if dark else "#cccccc"
        return f"""
            QMainWindow {{ background-color: {bg}; }}
            QToolBar {{ background-color: {nav_bg}; border: none; padding: 5px; }}
            QLineEdit {{ background-color: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 15px; padding: 5px 15px; }}
            QLineEdit:focus {{ border: 1px solid {color}; }}
            QTabBar::tab {{ background-color: {"#353535" if dark else "#e1e1e1"}; color: {fg}; padding: 8px 15px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background-color: {bg}; border-bottom: 2px solid {color}; }}
            QProgressBar {{ border: none; background-color: {bg}; height: 2px; }}
            QProgressBar::chunk {{ background-color: {color}; }}
            QPushButton {{ background-color: {"#3c3c3c" if dark else "#e1e1e1"}; color: {fg}; border: none; border-radius: 5px; padding: 5px 10px; }}
            QPushButton:hover {{ background-color: {color}; color: white; }}
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
        glass_bg = "rgba(255, 255, 255, 0.07)"
        accent = self.browser.accent_color
        
        style = f"""
            <style>
                :root {{ --accent: {accent}; --bg: #0d0d0d; --fg: #f0f0f0; --glass: {glass_bg}; }}
                body {{ background: var(--bg); color: var(--fg); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; overflow-x: hidden; }}
                .container {{ background: var(--glass); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 40px; width: 100%; max-width: 1000px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); animation: fade 0.5s ease-out; margin-bottom: 30px; }}
                @keyframes fade {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
                h1 {{ font-size: 3rem; font-weight: 800; margin: 0 0 20px; background: linear-gradient(135deg, #fff 0%, var(--accent) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; text-align: center; }}
                h2 {{ font-size: 1.4rem; margin: 25px 0 12px; border-bottom: 2px solid var(--accent); display: inline-block; padding-bottom: 5px; }}
                p {{ line-height: 1.6; color: #aaa; font-size: 1.05rem; text-align: center; }}
                .btn {{ display: inline-flex; align-items: center; justify-content: center; padding: 10px 20px; background: var(--accent); color: white; text-decoration: none; border-radius: 12px; font-weight: 600; transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1); border: none; cursor: pointer; margin: 5px; }}
                .btn:hover {{ filter: brightness(1.1); transform: translateY(-2px); box-shadow: 0 10px 20px -5px var(--accent); }}
                .btn-secondary {{ background: rgba(255,255,255,0.1); color: #fff; }}
                .btn-secondary:hover {{ background: rgba(255,255,255,0.15); }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; width: 100%; margin-top: 25px; }}
                .module-card {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 18px; display: flex; flex-direction: column; align-items: center; text-decoration: none; color: white; transition: 0.2s; }}
                .module-card:hover {{ background: rgba(255,255,255,0.08); border-color: var(--accent); transform: translateY(-5px); }}
                .module-icon {{ font-size: 2rem; margin-bottom: 8px; }}
                .module-title {{ font-weight: 600; font-size: 0.85rem; }}
                .arcade-card {{ background: linear-gradient(45deg, #1a1a1a, #000); border: 2px solid #333; grid-column: span 2; position: relative; overflow: hidden; }}
                .arcade-card:hover {{ border-color: #ff00ff; box-shadow: 0 0 20px rgba(255,0,255,0.3); }}
                .tag {{ position: absolute; top: 10px; right: 10px; background: #ff00ff; font-size: 0.7rem; padding: 2px 8px; border-radius: 20px; font-weight: 800; text-transform: uppercase; }}
                .dashboard-frame {{ width: 100%; height: 500px; border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; margin-top: 30px; background: #000; }}

                .card {{ background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255,255,255,0.05); transition: 0.2s; }}
                .card:hover {{ border-color: var(--accent); background: rgba(255,255,255,0.03); }}
                .shortcut-list {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; width: 100%; }}
                .shortcut-item {{ background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; display: flex; justify-content: space-between; border-left: 3px solid var(--accent); }}
                .kbd {{ background: #333; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-family: monospace; border-bottom: 2px solid #000; }}
            </style>
        """
        
        common_head = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>"
        
        html = None
        if url == "sloth://home" or host == "home":
            html = f"{common_head}<body><div class='container'>" \
                   f"<h1>🏠 Sloth Home</h1><p>Welcome to Sloth Web Browser! Select a module or explore the dashboard below:</p>" \
                   f"<div class='grid'>" \
                   f"<a href='sloth://settings' class='module-card'><span class='module-icon'>⚙️</span><span class='module-title'>Settings</span></a>" \
                   f"<a href='sloth://bookmarks' class='module-card'><span class='module-icon'>📑</span><span class='module-title'>Bookmarks</span></a>" \
                   f"<a href='sloth://downloads' class='module-card'><span class='module-icon'>⬇️</span><span class='module-title'>Downloads</span></a>" \
                   f"<a href='sloth://history' class='module-card'><span class='module-icon'>🕒</span><span class='module-title'>History</span></a>" \
                   f"<a href='sloth://help' class='module-card'><span class='module-icon'>❓</span><span class='module-title'>Help</span></a>" \
                   f"<a href='sloth://extensions' class='module-card'><span class='module-icon'>🧩</span><span class='module-title'>Extensions</span></a>" \
                   f"<a href='sloth://about' class='module-card'><span class='module-icon'>ℹ️</span><span class='module-title'>About</span></a>" \
                   f"<a href='sloth://arcade' class='module-card arcade-card'><span class='tag'>Live</span><span class='module-icon'>🎮</span><span class='module-title'>Arcade Lab</span></a>" \
                   f"</div>" \
                   f"<div style='margin-top:40px; text-align:center;'>" \
                   f"  <form action='https://cse.google.com/cse' method='GET' style='display:flex; width:100%; max-width:600px; margin:0 auto;'>" \
                   f"    <input type='hidden' name='cx' value='666b70a81f11c4eb9'>" \
                   f"    <input type='text' name='q' placeholder='Search the Grid...' style='padding:15px 25px; border-radius:50px 0 0 50px; border:1px solid rgba(255,255,255,0.1); background:rgba(255,255,255,0.05); color:white; width:100%; outline:none; font-size:1.1rem;'>" \
                   f"    <button type='submit' style='padding:15px 30px; border-radius:0 50px 50px 0; border:none; background:var(--accent); color:white; font-weight:bold; cursor:pointer;'>Search</button>" \
                   f"  </form>" \
                   f"</div>" \
                   f"<iframe src='https://parkertrip.github.io/newtab' class='dashboard-frame'></iframe>" \
                   f"</div></body></html>"
        elif url == "sloth://arcade" or host == "arcade":
            html = f"{common_head}<body><div class='container' style='max-width:600px;'><h1>🎮 Sloth Arcade</h1><p>Play a quick round of <b>Sloth-Snake</b> while your pages load.</p>" \
                   f"<canvas id='game' width='400' height='400' style='background:#000; display:block; margin:20px auto; border:4px solid var(--accent);'></canvas>" \
                   f"<div style='text-align:center;'><button class='btn' onclick='reset()'>Restart Game</button></div>" \
                   f"<script>const c=document.getElementById('game'),x=c.getContext('2d');let s=[{{x:10,y:10}}],f={{x:15,y:15}},dx=0,dy=0,sz=20;function draw(){{x.fillStyle='#000';x.fillRect(0,0,400,400);x.fillStyle='#0f0';s.forEach(p=>x.fillRect(p.x*sz,p.y*sz,sz-2,sz-2));x.fillStyle='#f00';x.fillRect(f.x*sz,f.y*sz,sz-2,sz-2);let nh={{x:s[0].x+dx,y:s[0].y+dy}};s.unshift(nh);if(nh.x==f.x&&nh.y==f.y){{f={{x:Math.floor(Math.random()*20),y:Math.floor(Math.random()*20)}}}}else{{s.pop()}}if(nh.x<0||nh.x>=20||nh.y<0||nh.y>=20){{reset()}}}}function reset(){{s=[{{x:10,y:10}}];dx=1;dy=0;}}document.onkeydown=e=>{{if(e.key=='ArrowUp'&&dy==0){{dx=0;dy=-1}}if(e.key=='ArrowDown'&&dy==0){{dx=0;dy=1}}if(e.key=='ArrowLeft'&&dx==0){{dx=-1;dy=0}}if(e.key=='ArrowRight'&&dx==0){{dx=1;dy=0}}}};setInterval(draw,100);reset();</script>" \
                   f"<div style='margin-top:40px; text-align:center;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"

        elif url == "sloth://settings" or host == "settings" or url == "sloth://about" or host == "about":
            content = f"""
                <h1>{"Settings" if "settings" in url or host == "settings" else "About Sloth"}</h1>
                <div style='background: rgba(255,255,255,0.03); padding: 30px; border-radius: 20px;'>
                    {"<h2>Appearance & Layout</h2>"
                     "<div style='display:flex; justify-content: space-between; align-items: center; margin-bottom: 20px;'><span>Project Accent Color</span><input type='color' value='"+self.browser.accent_color+"' onchange='window.location.href=\"sloth://set-color?c=\"+this.value.replace(\"#\", \"\")' style='width:50px; height:50px; border:none; background:none; cursor:pointer;'></div>"
                     "<div style='display:flex; justify-content: space-between; align-items: center; margin-bottom: 20px;'><span>Interface Theme</span><button class='btn btn-secondary' onclick='window.location.href=\"sloth://toggle-theme\"'>"+("Switch to Light" if self.browser.dark_theme else "Switch to Dark")+"</button></div>"
                     "<div style='display:flex; justify-content: space-between; align-items: center; margin-bottom: 20px;'><span>Navigation Bar Position</span><select onchange='window.location.href=\"sloth://set-nav?p=\"+this.value' style='padding:8px; border-radius:8px; background:rgba(0,0,0,0.5); color:white; border:1px solid var(--accent);'><option value='top' "+("selected" if self.browser.nav_pos=="top" else "")+">Top</option><option value='bottom' "+("selected" if self.browser.nav_pos=="bottom" else "")+">Bottom</option><option value='left' "+("selected" if self.browser.nav_pos=="left" else "")+">Left</option><option value='right' "+("selected" if self.browser.nav_pos=="right" else "")+">Right</option></select></div>"
                     "<div style='display:flex; justify-content: space-between; align-items: center; margin-bottom: 20px;'><span>Tabs Layout</span><button class='btn btn-secondary' onclick='window.location.href=\"sloth://toggle-layout\"'>Toggle Side/Top Tabs</button></div>"
                     "<div style='display:flex; justify-content: space-between; align-items: center;'><span>Default Browser Status</span><button class='btn' onclick='window.location.href=\"sloth://set-default\"'>Make Default</button></div>"
                     if ("settings" in url or host == "settings") else "<h2>Platinum Edition</h2><p><b>Version 2.0.2</b></p><p>Built for precision. Designed for speed, privacy, and minimalist aesthetics.</p><div style='margin-top:20px;'><a href='https://github.com/parkertripoli-wq/sloth-web' class='btn'>Inspect Source Code</a></div>"}
                </div>
            """
            html = f"{common_head}<body><div class='container'>{content}<div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://bookmarks" or host == "bookmarks":
            items = "".join([f"<div class='card'><div><div class='card-title'>{b.replace('https://','').replace('http://','')[:50]}</div></div><a href='{b}' class='btn' style='margin:0;'>Open Link</a></div>" for b in self.browser.bookmarks])
            html = f"{common_head}<body><div class='container'><h1>Your Bookmarks</h1><div style='margin-top:20px;'>{items or '<p style=\"text-align:center; padding:40px;\">No bookmarks saved yet. Click the 🔖 icon to add some!</p>'}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://history" or host == "history":
            items = "".join([f"<div class='card'><div><div class='card-meta'>{h['time']} • {h['url'][:60]}...</div><div class='card-title'>{h['title'][:50]}</div></div><a href='{h['url']}' class='btn' style='margin:0;'>Return</a></div>" for h in reversed(self.browser.history_manager.history)])
            html = f"{common_head}<body><div class='container'><h1>History</h1><div style='text-align:center; margin-bottom:20px;'><a href='sloth://clear-history' class='btn' style='background:#ff4444;'>Clear History</a></div><div style='margin-top:20px;'>{items or '<p style=\"text-align:center; padding:40px;\">Browsing history will appear here as you explore the grid.</p>'}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://downloads" or host == "downloads":
            # Filter for items that have a path (finished or started)
            items = "".join([f"<div class='card'><div><div class='card-title'>{os.path.basename(d.path()) if hasattr(d, 'path') else 'Unknown File'}</div><p style='margin:0; font-size:0.9rem;'>Status: Download</p></div><a href='file:///{os.path.dirname(d.path()) if hasattr(d, 'path') else ''}' class='btn' style='margin:0;'>Open Folder</a></div>" for d in self.browser.downloads])
            html = f"{common_head}<body><div class='container'><h1>Downloads</h1><div style='margin-top:20px;'>{items or '<p style=\"text-align:center; padding:40px;\">Downloaded files will appear here.</p>'}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://help" or host == "help":
            html = f"{common_head}<body><div class='container'><h1>Help & Shortcuts</h1><div class='shortcut-list'><div class='shortcut-item'><span>New Tab</span><span class='kbd'>Ctrl + T</span></div><div class='shortcut-item'><span>Close Tab</span><span class='kbd'>Ctrl + W</span></div><div class='shortcut-item'><span>Reload Page</span><span class='kbd'>Ctrl + R</span></div><div class='shortcut-item'><span>Dashboard</span><span class='kbd'>Alt + Home</span></div><div class='shortcut-item'><span>Settings</span><span class='kbd'>Ctrl + ,</span></div><div class='shortcut-item'><span>History</span><span class='kbd'>Ctrl + H</span></div></div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://extensions" or host == "extensions":
            ext_path = os.path.abspath("extensions")
            html = f"{common_head}<body><div class='container'><h1>🧩 Extension Engine</h1><p>Expand your grid with custom capabilities.</p>" \
                   f"<div style='background:rgba(255,255,255,0.03); border-radius:16px; padding:25px; margin:20px 0; border:1px solid rgba(255,255,255,0.05);'>" \
                   f"<p>Extensions are loaded from the <b>extensions</b> folder in the Sloth directory.</p>" \
                   f"<code style='background:#000; padding:10px; border-radius:8px; display:block; margin:10px 0; color:var(--accent); overflow-x:auto;'>{ext_path}</code>" \
                   f"<p style='font-size:0.9rem; opacity:0.8;'>Simply drop any <code>.js</code> file into this folder to inject it into every page you visit.</p>" \
                   f"</div>" \
                   f"<div style='display:flex; gap:15px; justify-content:center; margin-top:20px;'>" \
                   f"<a href='https://github.com/parkertripoli-wq/sloth-web/tree/main/extensions' class='btn' style='background:#ff00ff;'>Open Sloth Store</a>" \
                   f"<a href='https://chromewebstore.google.com/' class='btn' style='background:#4285f4;'>Open Chrome Store</a>" \
                   f"</div>" \
                   f"<p style='margin-top:15px; color:#aaa; font-style:italic;'>Both Sloth and standard Chrome-compatible scripts are supported.</p>" \
                   f"<div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://clear-history":
            self.browser.history_manager.history = []
            self.browser.history_manager.save()
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://history'></head></html>"
        elif url == "sloth://newtab" or host == "newtab" or path == "/":
             html = f"<html><head><meta http-equiv='refresh' content='0; url=https://parkertrip.github.io/newtab'></head></html>"
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
        elif url == "sloth://toggle-layout":
            self.browser.toggle_layout()
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-nav"):
            try:
                pos = url.split("?p=")[1]
                self.browser.set_nav_pos(pos)
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://set-default":
            if DefaultBrowserManager.set_as_default():
                self.browser.log("Registered Sloth Web. Please verify in Windows Settings.", notify=True)
            else:
                self.browser.log("Failed to update registry.")
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
        self.rules = []
        self.cache_file = get_storage_path("adblock_cache.txt")
        self.custom_list_urls = [
            "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/2.0%20resources/adblock%20list",
            "https://raw.githubusercontent.com/Turtlecute33/toolz/master/src/d3host.txt"
        ]
        self.load_defaults()
        self.load_cache()
        QTimer.singleShot(1000, self.fetch_remote_rules)

    def load_defaults(self):
        # Base aggressive rules - Host based for speed
        self.host_blacklist = {
            "googlesyndication.com", "doubleclick.net", "google-analytics.com",
            "adservice.google.com", "googleadservices.com", "securepubads",
            "amazon-adsystem", "adnxs", "taboola", "outbrain", "criteo",
            "popads", "popcash", "propellerads"
        }
        
        # Regex based for more complex patterns
        self.regex_blacklist = [
            re.compile(r"youtube\.com/api/stats/ads"), re.compile(r"youtube\.com/get_midroll_"),
            re.compile(r"youtube\.com/api/stats/qoe"), re.compile(r"youtube\.com/ptracking"),
            re.compile(r"ytimg\.com.*ads"), re.compile(r"ad\.doubleclick\.net")
        ]
        
        # Define UA strings
        # DEFAULT is now Sloth Web Browser as requested
        self.default_ua = "Sloth Web Browser/2.0.2 (Windows NT 10.0; Win64; x64)"
        # PURE CHROME for the store
        self.chrome_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"


    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
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
                    all_new_rules.extend(lines)
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith(("!", "#", " ")): continue
                        if "." in line and "*" not in line and "[" not in line:
                            self.host_blacklist.add(line)
                        else:
                            try: self.regex_blacklist.append(re.compile(re.escape(line)))
                            except: pass
            except Exception: pass
        
        # Save to cache for next startup
        if all_new_rules:
            try:
                with open(self.cache_file, "w") as f:
                    f.write("\n".join(all_new_rules))
            except: pass

    def interceptRequest(self, info):
        if not self.enabled: return
        url_obj = info.requestUrl()
        u = url_obj.toString()
        host = url_obj.host().lower()

        # Dynamic User-Agent switching for Chrome Store / Google compatibility
        if "chrome.google.com" in host or "chromewebstore" in host or "accounts.google.com" in host:
            info.setHttpHeader(b"User-Agent", self.chrome_ua.encode())
        else:
            info.setHttpHeader(b"User-Agent", self.default_ua.encode())

        # Efficient AdBlocking
        if host in self.host_blacklist:
            info.block(True)
            return

        for r in self.regex_blacklist:
            if r.search(u):
                info.block(True)
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
            .ytd-display-ad-renderer, .ytd-video-masthead-ad-renderer { display: none !important; }
        """
        # Script to auto-skip ads and handle overlays
        js = f"""
            (function(){{
                var style = document.createElement('style');
                style.textContent = `{css}`;
                if(document.head) document.head.appendChild(style);
                else document.documentElement.appendChild(style);
                
                // Aggressive Skip Logic
                setInterval(() => {{
                    const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-hover, .ytp-ad-skip-button-modern');
                    if(skipBtn) skipBtn.click();
                    
                    const overlayClose = document.querySelector('.ytp-ad-overlay-close-button');
                    if(overlayClose) overlayClose.click();
                    
                    const video = document.querySelector('video');
                    if(video && document.querySelector('.ad-showing')) {{
                        video.currentTime = video.duration || 9999;
                    }}
                }}, 500);
            }})();
        """
        self.setSourceCode(js)

class ChromeStoreCloak(QWebEngineScript):
    def __init__(self, ua):
        super().__init__()
        self.setName("ChromeStoreCloak")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        self.setRunsOnSubFrames(True)
        # Force JS to report Chrome for compatibility on specific sites
        js = f"""
            (function(){{
                if(location.hostname.includes("google.com") || location.hostname.includes("chromewebstore")){{
                    const newUA = "{ua}";
                    Object.defineProperty(navigator, 'userAgent', {{ get: function(){{ return newUA; }} }});
                    Object.defineProperty(navigator, 'appVersion', {{ get: function(){{ return newUA; }} }});
                    Object.defineProperty(navigator, 'vendor', {{ get: function(){{ return 'Google Inc.'; }} }});
                    // Advanced Cloaking: Mimic Chrome runtime object and deep detection points
                    if(!window.chrome) {{
                        window.chrome = {{ 
                            app: {{
                                isInstalled: false,
                                getDetails: function() {{}},
                                getIsInstalled: function() {{}}
                            }},
                            runtime: {{
                                connect: function() {{}},
                                sendMessage: function() {{}},
                                id: "cjpalhdlnbpafiamejdnhcphjbkeiib"
                            }},
                            webstore: {{
                                install: function(url, success, failure) {{
                                    console.log("Sloth: Store extraction triggered for " + url);
                                    if(failure) failure("Sloth Browser handles extensions via folder injection. Check Help for instructions.");
                                }},
                                onInstallStageChanged: {{}},
                                onDownloadProgress: {{}}
                            }},
                            loadTimes: function() {{ return {{}}; }},
                            csi: function() {{ return {{}}; }}
                        }};
                    }}
                }}
            }})();
        """
        self.setSourceCode(js)

# --- UI Components / Dialogs ---

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        l = QVBoxLayout(self)
        self.theme_btn = QPushButton(f"Theme: {'Dark' if parent.dark_theme else 'Light'}")
        self.theme_btn.clicked.connect(self.toggle_theme)
        l.addWidget(self.theme_btn)
        
        self.color_btn = QPushButton("Choose Accent Color")
        self.color_btn.clicked.connect(self.choose_color)
        l.addWidget(self.color_btn)
        
        self.clear_btn = QPushButton("Clear Grid Cache (Bypass Detection)")
        self.clear_btn.clicked.connect(self.clear_cache)
        l.addWidget(self.clear_btn)

        self.layout_btn = QPushButton("Toggle Vertical Tabs")
        self.layout_btn.clicked.connect(self.parent().toggle_layout)
        l.addWidget(self.layout_btn)

        close = QPushButton("Close", clicked=self.accept)
        l.addWidget(close)

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
        QMessageBox.information(self, "Cache Cleared", "The grid cache and cookies have been purged. YouTube detection should be reset.")

class DownloadManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setMinimumWidth(400)
        l = QVBoxLayout(self)
        self.list = QListWidget()
        l.addWidget(self.list)
        l.addWidget(QPushButton("Close", clicked=self.accept))

    def add_download(self, item):
        it = QListWidgetItem(f"{item.path()} (Starting...)")
        self.list.addItem(it)
        item.downloadProgress.connect(lambda r, t: it.setText(f"{item.path()} ({int(r/t*100) if t>0 else 0}%)"))
        item.finished.connect(lambda: it.setText(f"{item.path()} (Done)"))
        item.accept()

class CustomWebEngineView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser_parent = parent

    def contextMenuEvent(self, event):
        menu = self.page().createStandardContextMenu()
        menu.addSeparator()
        
        inspect_action = menu.addAction("Inspect Element")
        inspect_action.triggered.connect(self.inspect_element)
        
        view_source_action = menu.addAction("View Page Source")
        view_source_action.triggered.connect(self.view_source)
        
        menu.exec_(event.globalPos())

    def inspect_element(self):
        # Create a separate window for DevTools
        self.browser_parent.log("Opening DevTools...")
        dev_view = QWebEngineView()
        self.page().setDevToolsPage(dev_view.page())
        
        # We need a wrapper to keep the view alive
        self.dev_window = QMainWindow(self.browser_parent)
        self.dev_window.setWindowTitle("Sloth DevTools")
        self.dev_window.resize(900, 600)
        self.dev_window.setCentralWidget(dev_view)
        self.dev_window.show()

    def view_source(self):
        url = self.url().toString()
        if url:
            source_url = "view-source:" + url
            self.browser_parent.add_tab(QUrl(source_url))
            self.browser_parent.log(f"Viewing source of {url}")

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
        
        self.ad_block_enabled = self.config_manager.get("ad_block_enabled", True)
        self.dark_theme = self.config_manager.get("dark_theme", True)
        self.accent_color = self.config_manager.get("accent_color", "#4a9eff")
        self.nav_pos = self.config_manager.get("nav_pos", "top")
        self.tabs_pos = self.config_manager.get("tabs_pos", "north")
        
        self.downloads = []
        
        self.update_manager = UpdateManager(self)
        
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
        
        # Set exact modern User-Agent for perfect site compatibility
        # We use 'Sloth Web Browser' as the default identity now
        ua = "Sloth Web Browser/2.0.1 (Windows NT 10.0; Win64; x64)"
        QWebEngineProfile.defaultProfile().setHttpUserAgent(ua)
        QWebEngineProfile.defaultProfile().setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
        QWebEngineProfile.defaultProfile().setHttpCacheMaximumSize(52428800) # 50MB Memory Cache
        
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
        self.nav.setMovable(False)
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        
        # We will apply nav pos at the end, but let's at least add it to the window now
        # to ensure it's tracked by the layout system during widget addition.
        self.addToolBar(Qt.TopToolBarArea, self.nav)


        self.back_action = QAction("⬅️", self)
        self.back_action.triggered.connect(self.back)
        self.back_action.setToolTip("Back")
        self.nav.addAction(self.back_action)

        self.forward_action = QAction("➡️", self)
        self.forward_action.triggered.connect(self.forward)
        self.forward_action.setToolTip("Forward")
        self.nav.addAction(self.forward_action)

        self.reload_action = QAction("🔄", self)
        self.reload_action.triggered.connect(self.reload)
        self.reload_action.setToolTip("Reload")
        self.nav.addAction(self.reload_action)

        self.home_action = QAction("🏠", self)
        self.home_action.triggered.connect(self.home)
        self.home_action.setToolTip("Home")
        self.nav.addAction(self.home_action)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate)
        self.url_bar.textChanged.connect(self.update_suggestions)
        self.completer = QCompleter(self)
        self.url_bar.setCompleter(self.completer)
        
        self.ssl_action = QAction("🔓", self)
        self.url_bar.addAction(self.ssl_action, QLineEdit.LeadingPosition)
        
        self.nav.addWidget(self.url_bar)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.nav.addWidget(self.progress)

        for icon, slot, tip in [("➕", self.add_tab, "New Tab"), ("📖", self.toggle_reader, "Reader Mode"),
                                ("🔖", self.bookmark, "Add Bookmark"), ("📑", self.show_bookmarks, "Bookmarks"),
                                ("⚙️", self.show_settings, "Settings"), ("⬇️", self.show_downloads, "Downloads"),
                                ("🕶️", self.toggle_privacy, "Privacy Mode"), ("Incognito", lambda: self.add_tab(incognito=True), "Incognito")]:
            a = QAction(icon, self)
            a.triggered.connect(slot)
            a.setToolTip(tip)
            self.nav.addAction(a)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        
        # Apply configured tabs position
        self.apply_tabs_pos()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.setCentralWidget(self.tabs)
        
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        # Apply configured layout/nav positions after all UI elements are created
        self.apply_nav_pos()
        self.apply_tabs_pos()
        
        self.log("Browser initialized.")
        
        self.dl_manager = DownloadManager(self)
        self.add_tab()

    def log(self, message, notify=False):
        self.status.showMessage(message, 5000)
        print(f"[LOG] {message}")
        if notify and HAS_TOAST:
            try:
                ToastNotifier().show_toast("Sloth Web", message, duration=5, threaded=True)
            except: pass

    def add_tab(self, url=None, incognito=False):
        if isinstance(url, bool) or url is None: url = QUrl("sloth://home")
        browser = CustomWebEngineView(self)
        
        page = QWebEnginePage(self)
        page.profile().scripts().insert(CosmeticFilter())
        
        # Inject the Chrome Store Cloak to fool JS-based detection on Google sites
        cloak = ChromeStoreCloak("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")
        page.profile().scripts().insert(cloak)
        if incognito:
            page.profile().setHttpCacheType(QWebEngineProfile.NoCache)
            page.profile().setPersistentStoragePath("")
        
        interceptor = AdBlockInterceptor(self, self.ad_block_enabled)
        page.profile().setUrlRequestInterceptor(interceptor)
        page.profile().downloadRequested.connect(self.dl_manager.add_download)
        
        browser.setPage(page)
        idx = self.tabs.addTab(browser, "New Tab")
        
        browser.load(url)
        browser.urlChanged.connect(lambda q: self.update_ui(q, idx))
        browser.titleChanged.connect(lambda t: (self.tabs.setTabText(idx, t[:25]), self.history_manager.add_entry(t, browser.url().toString())))
        browser.iconChanged.connect(lambda icon: self.tabs.setTabIcon(idx, icon))
        browser.loadProgress.connect(lambda p: (self.progress.setValue(p), self.progress.setVisible(p < 100)))
        
        # Connect navigation signals for back/forward buttons
        browser.page().interactionChanged.connect(self.update_nav_actions)
        browser.urlChanged.connect(lambda _: self.update_nav_actions())
        
        # Error handling for custom error page
        page.loadFinished.connect(lambda ok: self.handle_load_finished(ok, browser))
        
        self.tabs.setCurrentIndex(idx)

    def handle_load_finished(self, ok, browser):
        if not ok:
            # Check if it was a real error or just a cancelled load
            # For simplicity, we show the Neon Void page on any failure
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
            self.url_bar.setText(q.toString())
            self.ssl_action.setText("🔒" if q.scheme() == "https" else "🔓")

    def tab_changed(self, idx):
        b = self.current_browser()
        if b:
            self.url_bar.setText(b.url().toString())
            self.ssl_action.setText("🔒" if b.url().scheme() == "https" else "🔓")

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
        if len(t) > 2: self.completer.setModel(QStringListModel(get_search_suggestions(t)))

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
        if b: b.setUrl(QUrl("sloth://home"))
    
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
            u = b.url().toString()
            if u not in self.bookmarks:
                self.bookmarks.append(u)
                save_bookmarks(self.bookmarks_file, self.bookmarks)

    def show_bookmarks(self):
        d = QDialog(self); d.setWindowTitle("Bookmarks"); l = QVBoxLayout(d)
        w = QListWidget(); l.addWidget(w)
        for b in self.bookmarks: w.addItem(b)
        def on_item_clicked(item):
            b = self.current_browser()
            if b: b.setUrl(QUrl(item.text()))
            d.accept()
        w.itemDoubleClicked.connect(on_item_clicked)
        d.exec_()

    def show_settings(self): SettingsDialog(self).exec_()
    def show_downloads(self): self.dl_manager.show()
    def toggle_privacy(self):
        self.ad_block_enabled = not self.ad_block_enabled
        self.status.showMessage(f"AdBlock {'Enabled' if self.ad_block_enabled else 'Disabled'}")

    def apply_theme(self):
        app = QApplication.instance()
        self.setStyleSheet(ThemeManager.get_qss(self.dark_theme, self.accent_color))
        ThemeManager.apply_palette(app, self.dark_theme)


if __name__ == "__main__":
    scheme = QWebEngineUrlScheme(b"sloth")
    scheme.setFlags(QWebEngineUrlScheme.LocalScheme | QWebEngineUrlScheme.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)
    
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec_())
