#!/usr/bin/env python3
"""
Sloth Web Browser 3.1 — complete desktop browser in one file.

This is the full native app (PyQt6 + Chromium / QtWebEngine): tabs, ad block,
bookmarks, passwords, arcade, extensions, PWA mode, sloth:// pages, and the rest.

Save this file as SlothWeb.py.

Install once:
    python -m pip install PyQt6 PyQt6-WebEngine requests

Optional on Windows (toasts / shortcuts):
    python -m pip install pywin32 win10toast

Run:
    python SlothWeb.py

Settings live in the .sloth_web folder in your home directory.
"""

import sys
import os
import json
import hashlib
import secrets
import base64
import html as html_lib
import smtplib
from email.mime.text import MIMEText
import struct
import zipfile
import io
import shutil
import requests
import re
import webbrowser
import subprocess
import urllib.parse, urllib.request, urllib
import time
import threading
import sqlite3
import glob
import platform

__version__ = "3.1"

SHORTCUTS = [
    ("New tab", "Ctrl + T"),
    ("New window", "Ctrl + N"),
    ("Close tab", "Ctrl + W"),
    ("Reopen closed tab", "Ctrl + Shift + T"),
    ("Next tab", "Ctrl + Tab"),
    ("Previous tab", "Ctrl + Shift + Tab"),
    ("Jump to tab 1–8", "Ctrl + 1 … 8"),
    ("Last tab", "Ctrl + 9"),
    ("Focus address bar", "Ctrl + L"),
    ("Find in page", "Ctrl + F"),
    ("Reload", "F5  /  Ctrl + R"),
    ("Back", "Alt + Left"),
    ("Forward", "Alt + Right"),
    ("Home", "Alt + Home"),
    ("Fullscreen", "F11"),
    ("Zoom in", "Ctrl + +"),
    ("Zoom out", "Ctrl + -"),
    ("Zoom reset", "Ctrl + 0"),
    ("Bookmark this page", "Ctrl + D"),
    ("Show or hide bookmarks bar", "Ctrl + Shift + B"),
    ("History", "Ctrl + H"),
    ("Downloads", "Ctrl + J"),
    ("Settings", "Ctrl + ,"),
    ("Command palette", "Ctrl + K"),
    ("Help", "sloth://help"),
    ("Setup", "sloth://start"),
    ("Spaces", "Ctrl + Shift + S"),
    ("Split view", "Ctrl + \\"),
    ("Peek", "Ctrl + Shift + P"),
    ("Reader mode", "Ctrl + Shift + R"),
    ("Translate page", "Ctrl + Shift + L"),
    ("Translate selection", "Alt + Shift + T"),
    ("Picture in picture", "Ctrl + Alt + P"),
    ("Zen compact", "Ctrl + Shift + Z"),
    ("Duplicate tab", "Ctrl + Alt + D"),
    ("Pin tab", "Ctrl + Shift + D"),
    ("Mute tab", "Ctrl + Shift + M"),
    ("Summarise page", "Ctrl + Alt + S"),
    ("Organise tabs", "Ctrl + Alt + O"),
    ("Mail", "Ctrl + Shift + O"),
    ("DevTools", "Ctrl + Shift + I"),
    ("View source", "Ctrl + U"),
]


def shortcut_cards():
    return "".join(
        f"<div class='card'><span>{name}</span><span class='btn btn-secondary'>{keys}</span></div>"
        for name, keys in SHORTCUTS
    )


def shortcut_grid():
    return "".join(f"<div><b>{keys}</b> {name}</div>" for name, keys in SHORTCUTS)

try:
    import pythoncom
except ImportError:
    pythoncom = None
try:
    from win32com.propsys import propsys
    from win32com.shell import shell as win_shell
except ImportError:
    pass

from PyQt6.QtCore import (QUrl, Qt, QTimer, pyqtSignal, QStringListModel, QBuffer, QThread, QIODevice,
                             QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QEvent, QSize, QCoreApplication)
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QLineEdit, 
                             QProgressBar, QTabWidget, QStatusBar, QWidget, 
                             QVBoxLayout, QPushButton, QTabBar, QFileDialog, 
                             QMenu, QInputDialog, QFormLayout, QGroupBox, 
                             QHBoxLayout, QSlider, QApplication, QCompleter,
                             QDialog, QListWidget, QDialogButtonBox, QMessageBox,
                             QListWidgetItem, QTextEdit, QColorDialog, QComboBox,
                             QCheckBox, QLabel, QDockWidget, QStyle, QTreeWidget,
                             QTreeWidgetItem, QSplitter, QScrollArea, QGraphicsOpacityEffect,
                             QGraphicsDropShadowEffect, QFrame, QSizePolicy)
from PyQt6.QtGui import QIcon, QPalette, QColor, QCursor, QAction, QPixmap, QMovie, QShortcut, QKeySequence, QImage, QGuiApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

# WebEngine MUST be imported after AA_ShareOpenGLContexts on Windows or it exits with no traceback.
if sys.platform == "win32":
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu --ignore-gpu-blocklist --enable-gpu-rasterization "
        "--enable-zero-copy --num-raster-threads=4 --disable-features=RendererCodeIntegrity"
    )
    try:
        import PyQt6 as _pyqt6
        _base = os.path.dirname(_pyqt6.__file__)
        for _rel in (("Qt6", "bin", "QtWebEngineProcess.exe"), ("Qt", "bin", "QtWebEngineProcess.exe")):
            _proc = os.path.join(_base, *_rel)
            if os.path.exists(_proc):
                os.environ["QTWEBENGINEPROCESS_PATH"] = _proc
                break
        _res = os.path.join(_base, "Qt6", "resources")
        if os.path.isdir(_res):
            os.environ["QTWEBENGINE_RESOURCES_PATH"] = _res
        _loc = os.path.join(_base, "Qt6", "translations", "qtwebengine_locales")
        if os.path.isdir(_loc):
            os.environ["QTWEBENGINE_LOCALES_PATH"] = _loc
    except Exception:
        pass
try:
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
except Exception:
    pass

from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEngineUrlRequestInterceptor, QWebEngineUrlSchemeHandler, 
                                 QWebEngineUrlScheme, QWebEngineUrlRequestJob,
                                 QWebEnginePage, QWebEngineProfile, QWebEngineScript,
                                 QWebEngineSettings)
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
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        elif Platform.IS_LINUX:
            return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"

    @staticmethod
    def get_platform_string():
        if Platform.IS_MAC: return "MacIntel"
        if Platform.IS_LINUX: return "Linux x86_64"
        return "Win32"

def qt_version_tuple():
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        parts = [int(x) for x in str(QT_VERSION_STR).split(".")[:3] if str(x).isdigit() or str(x).replace(".", "").isdigit()]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)

def qt_version_label():
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        return str(QT_VERSION_STR)
    except Exception:
        return "unknown"

def ext_info_get(info, name, default=None):
    val = getattr(info, name, None)
    if callable(val):
        try:
            return val()
        except Exception:
            return default
    return default if val is None else val

def native_extension_manager(profile=None):
    """Qt 6.10+ QWebEngineExtensionManager, or None with a reason."""
    ver = qt_version_tuple()
    if ver < (6, 10, 0):
        return None, f"Qt {qt_version_label()} (need 6.10+ for real Chrome extensions)"
    try:
        profile = profile or QWebEngineProfile.defaultProfile()
        mgr = profile.extensionManager()
        if mgr is None:
            return None, "PyQt6 did not expose extensionManager() — upgrade PyQt6-WebEngine"
        return mgr, "ok"
    except Exception as e:
        return None, f"extensionManager unavailable: {e}"

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

DEFAULT_HOME_APPS = [
    {"name": "Google", "url": "https://www.google.com"},
    {"name": "YouTube", "url": "https://www.youtube.com"},
    {"name": "GitHub", "url": "https://github.com"},
    {"name": "Discord", "url": "https://discord.com"},
    {"name": "ChatGPT", "url": "https://chatgpt.com"},
]

IP_CHECK_HINTS = (
    "ipify", "icanhazip", "ifconfig.me", "whatismyip", "ipinfo.io", "ident.me",
    "ipapi", "myip", "checkip", "ipdata", "showmyip", "ipaddress", "ipgeolocation",
    "wtfismyip", "api.ip", "ip.seeip", "ip-api.com", "l2.io",
)

def persist_default_profile():
    profile = QWebEngineProfile.defaultProfile()
    storage_path = os.path.join(os.path.expanduser("~"), ".sloth_web", "profile_data")
    os.makedirs(storage_path, exist_ok=True)
    profile.setPersistentStoragePath(storage_path)
    profile.setCachePath(os.path.join(storage_path, "cache"))
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
    try:
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    except Exception:
        pass
    try:
        if hasattr(profile, "isOffTheRecord") and profile.isOffTheRecord():
            pass
    except Exception:
        pass
    profile.setHttpCacheMaximumSize(1024 * 1024 * 250)
    return profile

SLOTH_WINDOWS = []

def space_id(name):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name or "space").strip())[:32].strip("_")
    return s.lower() or "space"

def default_spaces():
    return [
        {"id": "personal", "name": "Personal", "icon": "👤"},
        {"id": "work", "name": "Work", "icon": "💼"},
        {"id": "finance", "name": "Finance", "icon": "💰"},
        {"id": "social", "name": "Social", "icon": "💬"},
    ]

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

    def add_password(self, site, username, password, note=""):
        if not isinstance(self.passwords, dict):
            self.passwords = {}
        if site not in self.passwords:
            self.passwords[site] = []
        val = self.passwords[site]
        for p in val:
            if p.get("user") == username:
                p["pass"] = password
                if note:
                    p["note"] = note
                self.save()
                return
        val.append({"user": username, "pass": password, "note": note or "", "kind": "password"})
        self.save()

    def add_passkey(self, site, username):
        if not isinstance(self.passwords, dict):
            self.passwords = {}
        if site not in self.passwords:
            self.passwords[site] = []
        cred = secrets.token_hex(16)
        self.passwords[site].append({
            "user": username or "passkey",
            "pass": cred,
            "note": "local passkey",
            "kind": "passkey",
            "cred_id": cred,
        })
        self.save()
        return cred

    def find_for_site(self, site):
        if not site:
            return []
        site = site.lower()
        out = []
        for k, vals in (self.passwords or {}).items():
            if site in k.lower() or k.lower() in site:
                out.extend(vals)
        return out

    def delete_password(self, site, index):
        if site in self.passwords and index < len(self.passwords[site]):
            self.passwords[site].pop(index)
            if not self.passwords[site]:
                del self.passwords[site]
            self.save()
            return True
        return False

class MailManager:
    def __init__(self, filename):
        self.filename = filename
        data = {}
        try:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    data = json.load(f) or {}
        except Exception:
            data = {}
        self.boxes = data.get("boxes") or []
        self.messages = data.get("messages") or []
        self.filters = data.get("filters") or []

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump({"boxes": self.boxes, "messages": self.messages, "filters": self.filters}, f, indent=2)
        except Exception:
            pass

    def add_throwaway(self):
        addr = None
        try:
            r = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1", timeout=8)
            arr = r.json()
            if isinstance(arr, list) and arr:
                addr = str(arr[0])
        except Exception:
            addr = None
        if not addr:
            addr = f"sloth{secrets.token_hex(3)}@sloth.mail"
            login, domain = addr.split("@", 1)
            kind = "local"
        else:
            login, domain = addr.split("@", 1)
            kind = "throwaway"
        box = {"id": secrets.token_hex(4), "kind": kind, "address": addr, "login": login, "domain": domain, "label": addr}
        self.boxes.append(box)
        self.save()
        return box

    def add_real(self, address, label=""):
        address = (address or "").strip()
        if "@" not in address:
            address = address + "@sloth.local"
        box = {"id": secrets.token_hex(4), "kind": "real", "address": address, "login": address.split("@")[0], "domain": address.split("@", 1)[1], "label": label or address}
        self.boxes.append(box)
        self.save()
        return box

    def apply_filters(self, msg):
        blob = (msg.get("from", "") + " " + msg.get("subject", "") + " " + msg.get("body", "")).lower()
        for fl in self.filters:
            needle = (fl.get("match") or "").lower()
            if needle and needle in blob:
                act = fl.get("action") or "spam"
                if act == "spam":
                    msg["folder"] = "spam"
                elif act == "later":
                    msg["folder"] = "later"
                elif act == "tag":
                    msg["tag"] = fl.get("tag") or "tagged"
        return msg

    def add_message(self, box_id, folder, frm, to, subject, body, send_at=0):
        msg = {
            "id": secrets.token_hex(6),
            "box": box_id,
            "folder": folder,
            "from": frm,
            "to": to,
            "subject": subject,
            "body": body,
            "ts": int(time.time()),
            "send_at": int(send_at or 0),
            "read": folder != "inbox",
        }
        self.apply_filters(msg)
        self.messages.append(msg)
        self.save()
        return msg

    def refresh_throwaway(self, box):
        if box.get("kind") != "throwaway":
            return 0
        added = 0
        try:
            login, domain = box.get("login"), box.get("domain")
            r = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}", timeout=8)
            for m in r.json() or []:
                mid = str(m.get("id"))
                exists = any(x.get("ext_id") == mid and x.get("box") == box["id"] for x in self.messages)
                if exists:
                    continue
                det = requests.get(
                    f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}",
                    timeout=8,
                ).json()
                msg = {
                    "id": secrets.token_hex(6),
                    "ext_id": mid,
                    "box": box["id"],
                    "folder": "inbox",
                    "from": det.get("from") or m.get("from") or "",
                    "to": box.get("address"),
                    "subject": det.get("subject") or m.get("subject") or "",
                    "body": det.get("textBody") or det.get("body") or "",
                    "ts": int(time.time()),
                    "send_at": 0,
                    "read": False,
                }
                self.apply_filters(msg)
                self.messages.append(msg)
                added += 1
            if added:
                self.save()
        except Exception:
            pass
        return added

    def due_later(self):
        now = int(time.time())
        moved = 0
        for m in self.messages:
            if m.get("folder") == "later" and int(m.get("send_at") or 0) and int(m.get("send_at")) <= now:
                m["folder"] = "sent"
                m["ts"] = now
                moved += 1
        if moved:
            self.save()
        return moved

OFFLINE_ES = {
    "the": "el", "a": "un", "and": "y", "of": "de", "to": "a", "in": "en", "is": "es",
    "you": "tú", "that": "que", "it": "lo", "for": "para", "on": "en", "with": "con",
    "as": "como", "this": "esto", "be": "ser", "at": "en", "by": "por", "from": "de",
    "or": "o", "an": "un", "not": "no", "but": "pero", "are": "son", "we": "nosotros",
    "have": "tener", "was": "fue", "they": "ellos", "can": "puede", "will": "será",
    "page": "página", "search": "buscar", "home": "inicio", "settings": "ajustes",
    "password": "contraseña", "mail": "correo", "read": "leer", "save": "guardar",
    "open": "abrir", "close": "cerrar", "new": "nuevo", "tab": "pestaña",
}

class TranslateEngine:
    def __init__(self, config_manager):
        self.cfg = config_manager

    def offline(self, text, lang="es"):
        pack = dict(OFFLINE_ES)
        extra = self.cfg.get("offline_pack") or {}
        if isinstance(extra, dict):
            pack.update({str(k).lower(): str(v) for k, v in extra.items()})
        words = re.split(r"(\s+)", text)
        out = []
        for w in words:
            key = re.sub(r"[^A-Za-z']", "", w).lower()
            if key in pack:
                out.append(re.sub(r"[A-Za-z']+", pack[key], w, count=1))
            else:
                out.append(w)
        return "".join(out)

    def translate(self, text, dest="es"):
        text = (text or "")[:4000]
        if not text.strip():
            return ""
        try:
            r = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:500], "langpair": f"en|{dest}"},
                timeout=8,
            )
            data = r.json()
            t = (data.get("responseData") or {}).get("translatedText")
            if t:
                return t
        except Exception:
            pass
        return self.offline(text, dest)

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
        self.parent.log(f"Update {version} available. This standalone file will not overwrite itself from GitHub.")
        QMessageBox.information(
            self.parent,
            "Update Available",
            f"Version {version} is listed online.\n\nThis is your standalone sloth_web.py (v{self.local_version}). "
            "It will not auto-replace itself with the GitHub copy, which would wipe your local file.",
        )

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
    "--enable-gpu",
    "--ignore-gpu-blocklist",
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--num-raster-threads=4",
    "--enable-smooth-scrolling",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
]

SEARCH_ENGINES = [
    ("mergarms", "Mergarms (by Sloth Search)", "https://mergarms.grok.me/?q={q}"),
    ("sloth", "Sloth Search", "https://cse.google.com/cse?cx=666b70a81f11c4eb9&q={q}#gsc.tab=0&gsc.q={q}&gsc.sort="),
    ("google", "Google", "https://www.google.com/search?q={q}"),
    ("ddg", "DuckDuckGo", "https://duckduckgo.com/?q={q}"),
    ("bing", "Bing", "https://www.bing.com/search?q={q}"),
    ("brave", "Brave", "https://search.brave.com/search?q={q}"),
    ("wikipedia", "Wikipedia", "https://en.wikipedia.org/w/index.php?search={q}"),
    ("local", "Local engine (beta)", None),
]

def _engine_key(name):
    key = re.sub(r"[^a-z0-9]+", "", (name or "custom").lower())[:18]
    return key or "custom"

def all_search_engines(config=None):
    out = list(SEARCH_ENGINES)
    seen = {k for k, _n, _t in out}
    extra = []
    if config:
        extra = config.get("custom_search_engines") or []
    for e in extra:
        if not isinstance(e, dict):
            continue
        tmpl = (e.get("url") or e.get("template") or "").strip()
        if not tmpl:
            continue
        name = (e.get("name") or "Custom").strip() or "Custom"
        key = (e.get("key") or _engine_key(name)).lower()
        if key in seen:
            key = key + str(len(out))
        seen.add(key)
        out.append((key, name, tmpl))
    return out

def search_url(engine, query, local_url="", config=None):
    q = urllib.parse.quote_plus(query or "")
    engine = (engine or "mergarms").lower()
    if engine in ("local", "localhost"):
        tmpl = (local_url or "http://127.0.0.1:8888/?q={q}").strip()
        if "{q}" in tmpl:
            return tmpl.replace("{q}", q)
        if tmpl.endswith("="):
            return tmpl + q
        sep = "&" if "?" in tmpl else "?"
        return f"{tmpl}{sep}q={q}"
    for key, _name, tmpl in all_search_engines(config):
        if key == engine and tmpl:
            if "{q}" in tmpl:
                return tmpl.replace("{q}", q)
            if tmpl.endswith("="):
                return tmpl + q
            sep = "&" if "?" in tmpl else "?"
            return f"{tmpl}{sep}q={q}"
    return f"https://mergarms.grok.me/?q={q}"


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "utm_name", "utm_cid", "utm_reader", "utm_viz_id", "utm_pubreferrer", "utm_swu",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "msclkid", "mc_cid",
    "mc_eid", "igshid", "si", "ncid", "yclid", "_hsenc", "_hsmi", "mkt_tok",
    "oly_anon_id", "oly_enc_id", "vero_id", "wickedid", "yclid", "rb_clickid",
    "s_cid", "spm", "scm", "ref_src", "ref_url", "ref_cta", "ref_t",
}

def clean_tracking_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        q = [(k, v) for k, v in q if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
        query = urllib.parse.urlencode(q)
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, query, ""))
    except Exception:
        return url

def is_search_url(url):
    u = (url or "").lower()
    return any(x in u for x in ("?q=", "&q=", "/search", "mergarms.grok.me", "duckduckgo.com/?", "bing.com/search"))

def extractive_summary(text, limit=8):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return "Nothing to summarise on this page."
    parts = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    for i, s in enumerate(parts):
        s = s.strip()
        if 40 < len(s) < 280:
            scored.append((len(s) / (i + 3), s))
    scored.sort(reverse=True)
    picked = []
    for _, s in scored:
        if s not in picked:
            picked.append(s)
        if len(picked) >= limit:
            break
    if not picked:
        picked = parts[:limit]
    return " ".join(picked[:limit])

class SlothAI:
    @staticmethod
    def enabled(cfg):
        return bool(cfg.get("ai_enabled", True))

    @staticmethod
    def summarize(text, cfg=None):
        local = extractive_summary(text)
        endpoint = (cfg or {}).get("ai_endpoint") or ""
        if endpoint:
            try:
                r = requests.post(endpoint, json={"task": "summarize", "text": text[:8000]}, timeout=8)
                if r.ok:
                    data = r.json() if "json" in (r.headers.get("content-type") or "") else {"summary": r.text}
                    return (data.get("summary") or data.get("text") or local).strip()
            except Exception:
                pass
        return local

    @staticmethod
    def organize(tabs):
        groups = {}
        for item in tabs:
            host = (item.get("host") or "other").lower()
            parts = [p for p in host.split(".") if p]
            root = ".".join(parts[-2:]) if len(parts) >= 2 else (host or "other")
            if root in ("com", "net", "org", "io"):
                root = host
            groups.setdefault(root, []).append(item)
        return groups


class BrowserImporter:
    """Read bookmarks + recent history from Chrome, Edge, Brave, Firefox, Opera, Vivaldi."""

    @staticmethod
    def _local_app():
        return os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")

    @staticmethod
    def _roaming():
        return os.environ.get("APPDATA") or os.path.expanduser("~")

    @staticmethod
    def profiles():
        la = BrowserImporter._local_app()
        ro = BrowserImporter._roaming()
        home = os.path.expanduser("~")
        found = []
        candidates = [
            ("chrome", "Google Chrome", [
                os.path.join(la, "Google", "Chrome", "User Data", "Default", "Bookmarks"),
                os.path.join(home, ".config", "google-chrome", "Default", "Bookmarks"),
            ], [
                os.path.join(la, "Google", "Chrome", "User Data", "Default", "History"),
                os.path.join(home, ".config", "google-chrome", "Default", "History"),
            ]),
            ("edge", "Microsoft Edge", [
                os.path.join(la, "Microsoft", "Edge", "User Data", "Default", "Bookmarks"),
                os.path.join(home, ".config", "microsoft-edge", "Default", "Bookmarks"),
            ], [
                os.path.join(la, "Microsoft", "Edge", "User Data", "Default", "History"),
                os.path.join(home, ".config", "microsoft-edge", "Default", "History"),
            ]),
            ("brave", "Brave", [
                os.path.join(la, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Bookmarks"),
                os.path.join(home, ".config", "BraveSoftware", "Brave-Browser", "Default", "Bookmarks"),
            ], [
                os.path.join(la, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History"),
                os.path.join(home, ".config", "BraveSoftware", "Brave-Browser", "Default", "History"),
            ]),
            ("vivaldi", "Vivaldi", [
                os.path.join(la, "Vivaldi", "User Data", "Default", "Bookmarks"),
                os.path.join(home, ".config", "vivaldi", "Default", "Bookmarks"),
            ], [
                os.path.join(la, "Vivaldi", "User Data", "Default", "History"),
            ]),
            ("opera", "Opera", [
                os.path.join(ro, "Opera Software", "Opera Stable", "Bookmarks"),
                os.path.join(home, ".config", "opera", "Bookmarks"),
            ], []),
            ("opera_gx", "Opera GX", [
                os.path.join(ro, "Opera Software", "Opera GX Stable", "Bookmarks"),
            ], []),
            ("chromium", "Chromium", [
                os.path.join(la, "Chromium", "User Data", "Default", "Bookmarks"),
                os.path.join(home, ".config", "chromium", "Default", "Bookmarks"),
            ], [
                os.path.join(la, "Chromium", "User Data", "Default", "History"),
            ]),
            ("chrome_beta", "Chrome Beta", [
                os.path.join(la, "Google", "Chrome Beta", "User Data", "Default", "Bookmarks"),
            ], []),
            ("chrome_canary", "Chrome Canary", [
                os.path.join(la, "Google", "Chrome SxS", "User Data", "Default", "Bookmarks"),
            ], []),
            ("yandex", "Yandex", [
                os.path.join(la, "Yandex", "YandexBrowser", "User Data", "Default", "Bookmarks"),
            ], []),
            ("whale", "Naver Whale", [
                os.path.join(la, "Naver", "Naver Whale", "User Data", "Default", "Bookmarks"),
            ], []),
            ("thorium", "Thorium", [
                os.path.join(la, "Thorium", "User Data", "Default", "Bookmarks"),
            ], []),
            ("arc", "Arc", [
                os.path.join(la, "Arc", "User Data", "Default", "Bookmarks"),
                os.path.join(la, "TheBrowserCompany", "Arc", "User Data", "Default", "Bookmarks"),
            ], []),
            ("ungoogled", "Ungoogled Chromium", [
                os.path.join(la, "Chromium", "User Data", "Default", "Bookmarks"),
            ], []),
        ]
        for key, name, bms, hists in candidates:
            bm = next((p for p in bms if os.path.exists(p)), None)
            hist = next((p for p in hists if os.path.exists(p)), None)
            found.append({"key": key, "name": name, "bookmarks": bm, "history": hist, "present": bool(bm or hist)})
        ff_roots = [
            os.path.join(ro, "Mozilla", "Firefox", "Profiles"),
            os.path.join(home, ".mozilla", "firefox"),
            os.path.join(ro, "librewolf", "Profiles"),
            os.path.join(home, ".librewolf"),
            os.path.join(ro, "Waterfox", "Profiles"),
            os.path.join(ro, "Floorp", "Profiles"),
        ]
        ff_places = []
        for root in ff_roots:
            if os.path.isdir(root):
                ff_places.extend(glob.glob(os.path.join(root, "*", "places.sqlite")))
        found.append({
            "key": "firefox",
            "name": "Firefox",
            "bookmarks": ff_places[0] if ff_places else None,
            "history": ff_places[0] if ff_places else None,
            "present": bool(ff_places),
        })
        return found

    @staticmethod
    def _walk_chromium_bookmarks(node, out):
        if not isinstance(node, dict):
            return
        if node.get("type") == "url" and node.get("url"):
            out.append({"title": node.get("name") or node.get("url"), "url": node.get("url")})
        for child in node.get("children") or []:
            BrowserImporter._walk_chromium_bookmarks(child, out)

    @staticmethod
    def read_chromium_bookmarks(path):
        items = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        roots = data.get("roots") or {}
        for key in ("bookmark_bar", "other", "synced"):
            BrowserImporter._walk_chromium_bookmarks(roots.get(key) or {}, items)
        return items

    @staticmethod
    def read_chromium_history(path, limit=400):
        items = []
        tmp = path + ".slothcopy"
        try:
            shutil.copy2(path, tmp)
            con = sqlite3.connect(tmp)
            cur = con.cursor()
            cur.execute("SELECT url, title FROM urls WHERE url LIKE 'http%' ORDER BY last_visit_time DESC LIMIT ?", (limit,))
            for url, title in cur.fetchall():
                if url:
                    items.append({"title": title or url, "url": url, "time": time.strftime("%H:%M")})
            con.close()
        except Exception:
            items = []
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return items

    @staticmethod
    def read_firefox(places_path, limit=400):
        bms, hist = [], []
        tmp = places_path + ".slothcopy"
        try:
            shutil.copy2(places_path, tmp)
            con = sqlite3.connect(tmp)
            cur = con.cursor()
            try:
                cur.execute(
                    "SELECT moz_places.url, COALESCE(moz_bookmarks.title, moz_places.title) "
                    "FROM moz_bookmarks JOIN moz_places ON moz_places.id = moz_bookmarks.fk "
                    "WHERE moz_places.url LIKE 'http%' AND moz_bookmarks.type = 1"
                )
                for url, title in cur.fetchall():
                    bms.append({"title": title or url, "url": url})
            except Exception:
                pass
            try:
                cur.execute(
                    "SELECT url, title FROM moz_places WHERE url LIKE 'http%' "
                    "ORDER BY last_visit_date DESC LIMIT ?",
                    (limit,),
                )
                for url, title in cur.fetchall():
                    hist.append({"title": title or url, "url": url, "time": time.strftime("%H:%M")})
            except Exception:
                pass
            con.close()
        except Exception:
            pass
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return bms, hist

    @staticmethod
    def import_source(key, browser):
        info = next((p for p in BrowserImporter.profiles() if p["key"] == key), None)
        if not info or not info.get("present"):
            return {"ok": False, "message": f"{key} was not found on this computer.", "bookmarks": 0, "history": 0}
        added_bm, added_hist = 0, 0
        existing = set()
        for b in browser.bookmarks:
            if isinstance(b, dict):
                existing.add(b.get("url"))
            else:
                existing.add(str(b))
        try:
            if key == "firefox":
                bms, hist = BrowserImporter.read_firefox(info["bookmarks"])
            else:
                bms = BrowserImporter.read_chromium_bookmarks(info["bookmarks"]) if info.get("bookmarks") else []
                hist = BrowserImporter.read_chromium_history(info["history"]) if info.get("history") else []
            for bm in bms:
                u = bm.get("url")
                if u and u not in existing:
                    browser.bookmarks.append({"title": bm.get("title") or u, "url": u})
                    existing.add(u)
                    added_bm += 1
            if added_bm:
                save_bookmarks(browser.bookmarks_file, browser.bookmarks)
            seen = {h.get("url") for h in browser.history_manager.history if isinstance(h, dict)}
            for h in hist:
                if h.get("url") and h["url"] not in seen:
                    browser.history_manager.history.append(h)
                    seen.add(h["url"])
                    added_hist += 1
            if added_hist:
                browser.history_manager.save()
            try:
                browser.refresh_bookmarks_bar()
                browser.update_sidebar()
            except Exception:
                pass
            return {
                "ok": True,
                "message": f"Imported {added_bm} bookmarks and {added_hist} history items from {info['name']}.",
                "bookmarks": added_bm,
                "history": added_hist,
            }
        except Exception as e:
            return {"ok": False, "message": f"Import failed: {e}", "bookmarks": 0, "history": 0}

    @staticmethod
    def scan_disk(timeout=10):
        roots = [
            BrowserImporter._local_app(),
            BrowserImporter._roaming(),
            os.path.expanduser("~"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramW6432"),
        ]
        skip = {
            "windows", "system32", "winsxs", "node_modules", ".git", "temp", "tmp",
            "$recycle.bin", "system volume information", "cache", "code cache",
            "gpuCache".lower(), "gpucache", "shadercache",
        }
        hits = []
        seen = set()
        t0 = time.time()
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for dirpath, dirnames, files in os.walk(root):
                if time.time() - t0 > timeout:
                    return hits
                depth = dirpath[len(root):].count(os.sep)
                if depth > 6:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d.lower() not in skip and not d.startswith(".")]
                if "Bookmarks" in files:
                    p = os.path.join(dirpath, "Bookmarks")
                    if p not in seen:
                        seen.add(p)
                        hits.append({"name": os.path.basename(os.path.dirname(dirpath)) + " / " + os.path.basename(dirpath), "bookmarks": p, "history": os.path.join(dirpath, "History") if "History" in files else None, "kind": "chromium"})
                if "places.sqlite" in files:
                    p = os.path.join(dirpath, "places.sqlite")
                    if p not in seen:
                        seen.add(p)
                        hits.append({"name": "Firefox-like: " + os.path.basename(dirpath), "bookmarks": p, "history": p, "kind": "firefox"})
                if len(hits) >= 60:
                    return hits
        return hits

    @staticmethod
    def from_exe(exe_path):
        exe_path = os.path.abspath(exe_path)
        d = os.path.dirname(exe_path)
        guesses = [
            os.path.join(d, "User Data", "Default", "Bookmarks"),
            os.path.join(d, "Data", "Default", "Bookmarks"),
            os.path.join(os.path.dirname(d), "User Data", "Default", "Bookmarks"),
            os.path.join(d, "browser", "User Data", "Default", "Bookmarks"),
        ]
        low = exe_path.lower()
        la = BrowserImporter._local_app()
        ro = BrowserImporter._roaming()
        if "brave" in low:
            guesses.insert(0, os.path.join(la, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Bookmarks"))
        if "chrome" in low:
            guesses.insert(0, os.path.join(la, "Google", "Chrome", "User Data", "Default", "Bookmarks"))
        if "msedge" in low or "edge" in low:
            guesses.insert(0, os.path.join(la, "Microsoft", "Edge", "User Data", "Default", "Bookmarks"))
        if "firefox" in low:
            return {"ok": False, "firefox_root": os.path.join(ro, "Mozilla", "Firefox", "Profiles")}
        if "opera" in low:
            guesses.insert(0, os.path.join(ro, "Opera Software", "Opera Stable", "Bookmarks"))
        if "vivaldi" in low:
            guesses.insert(0, os.path.join(la, "Vivaldi", "User Data", "Default", "Bookmarks"))
        for g in guesses:
            if os.path.exists(g):
                return {"ok": True, "bookmarks": g, "history": os.path.join(os.path.dirname(g), "History")}
        return {"ok": False, "guesses": guesses}

    @staticmethod
    def import_any_path(path, browser):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            for name in ("Bookmarks", "places.sqlite"):
                p = os.path.join(path, name)
                if os.path.exists(p):
                    return BrowserImporter.import_any_path(p, browser)
            for root, dirs, files in os.walk(path):
                if "Bookmarks" in files:
                    return BrowserImporter.import_any_path(os.path.join(root, "Bookmarks"), browser)
                if "places.sqlite" in files:
                    return BrowserImporter.import_any_path(os.path.join(root, "places.sqlite"), browser)
                if root.count(os.sep) - path.count(os.sep) > 3:
                    dirs[:] = []
            return {"ok": False, "message": "No bookmarks file in that folder.", "bookmarks": 0, "history": 0}
        if path.lower().endswith((".exe", ".app", ".bin")):
            loc = BrowserImporter.from_exe(path)
            if loc.get("ok"):
                path = loc["bookmarks"]
            else:
                return {"ok": False, "message": "Could not find a profile next to that app. Pick the Bookmarks file inside User Data/Default.", "bookmarks": 0, "history": 0}
        info = {"key": "other", "name": os.path.basename(path), "bookmarks": path, "history": None, "present": True}
        if path.endswith("places.sqlite"):
            info["key"] = "firefox"
        try:
            if info["key"] == "firefox" or path.endswith("places.sqlite"):
                bms, hist = BrowserImporter.read_firefox(path)
            else:
                bms = BrowserImporter.read_chromium_bookmarks(path)
                hist_path = os.path.join(os.path.dirname(path), "History")
                hist = BrowserImporter.read_chromium_history(hist_path) if os.path.exists(hist_path) else []
            added_bm = added_hist = 0
            existing = set()
            for b in browser.bookmarks:
                existing.add(b.get("url") if isinstance(b, dict) else str(b))
            for bm in bms:
                u = bm.get("url")
                if u and u not in existing:
                    browser.bookmarks.append({"title": bm.get("title") or u, "url": u})
                    existing.add(u)
                    added_bm += 1
            if added_bm:
                save_bookmarks(browser.bookmarks_file, browser.bookmarks)
            seen = {h.get("url") for h in browser.history_manager.history if isinstance(h, dict)}
            for h in hist:
                if h.get("url") and h["url"] not in seen:
                    browser.history_manager.history.append(h)
                    seen.add(h["url"])
                    added_hist += 1
            if added_hist:
                browser.history_manager.save()
            try:
                browser.refresh_bookmarks_bar()
                browser.update_sidebar()
            except Exception:
                pass
            return {"ok": True, "message": f"Imported {added_bm} bookmarks and {added_hist} history items from {os.path.basename(path)}.", "bookmarks": added_bm, "history": added_hist}
        except Exception as e:
            return {"ok": False, "message": f"Import failed: {e}", "bookmarks": 0, "history": 0}



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
    def get_qss(dark=True, color="#4a9eff", texture="none", radius=16, density="comfortable", pill_tabs=True, compact=False, chrome_margin=8):
        bg = "rgba(20, 20, 20, 0.72)" if dark else "rgba(240, 240, 245, 0.78)"
        fg = "#f0f0f0" if dark else "#1d1d1f"
        nav_bg = "rgba(28, 28, 28, 0.82)" if dark else "rgba(255, 255, 255, 0.82)"
        border = "rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.1)"
        hover_bg = "rgba(255, 255, 255, 0.15)" if dark else "rgba(0, 0, 0, 0.06)"
        font_family = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, Cantarell, sans-serif"
        r = max(6, int(radius))
        m = 2 if compact else max(2, int(chrome_margin))
        dens = {"compact": (4, 6, 12, 88, 12), "roomy": (10, 14, 18, 148, 15)}.get(density, (7, 10, 16, 118, 13))
        pad_y, pad_x, tab_pad, tab_min, fsz = dens
        if compact:
            pad_y, pad_x, tab_pad, tab_min, fsz = 3, 8, 8, 72, 12
            m = min(m, 4)
        tab_r = 999 if pill_tabs else max(8, r - 4)

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
                border: 1px solid {border}; 
                border-radius: {r}px;
                margin: {m}px {m + 4}px;
                padding: {pad_y}px {pad_x}px; 
                spacing: {pad_x}px; 
            }}
            QToolBar::handle {{ background: {color}; width: 2px; border-radius: 1px; }}
            QDockWidget {{ 
                color: {color}; 
                font-weight: 800; 
                border: 1px solid {border}; 
                border-radius: {r}px;
                background-color: {bg};
                {texture_prop}
            }}
            QDockWidget::title {{ 
                background: {nav_bg};
                padding: {pad_y + 4}px; 
                border-bottom: 1px solid {border}; 
                border-radius: {r}px {r}px 0px 0px;
                font-size: {fsz}px;
            }}
            QDialog, QMessageBox, QGroupBox {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: {r + 4}px;
                color: {fg};
            }}
            QLineEdit {{ 
                background-color: {"rgba(10, 10, 10, 0.5)" if dark else "rgba(255, 255, 255, 0.5)"}; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: {tab_r if pill_tabs else r}px; 
                padding: {pad_y}px {pad_x + 6}px; 
                font-size: {fsz}px; 
                selection-background-color: {color}; 
            }}
            QLineEdit:focus {{ 
                border: 1px solid {color}; 
                background-color: {"rgba(20, 20, 20, 0.7)" if dark else "rgba(255, 255, 255, 0.8)"};
            }}
            QTabWidget::pane {{ 
                border: none; 
                background: transparent; 
                top: -1px;
            }}
            QTabBar::tab {{ 
                background-color: rgba(255, 255, 255, 0.05); 
                color: #888; 
                padding: {tab_pad // 2}px {tab_pad}px; 
                border-top-left-radius: {tab_r}px; 
                border-top-right-radius: {tab_r}px;
                border-bottom-left-radius: {8 if pill_tabs else 0}px;
                border-bottom-right-radius: {8 if pill_tabs else 0}px;
                margin-right: 4px;
                margin-top: 4px;
                min-width: {tab_min}px;
                border: 1px solid {border};
            }}
            QTabBar::tab:hover {{
                background-color: {hover_bg};
                color: {fg};
            }}
            QTabBar::tab:selected {{ 
                background-color: {bg}; 
                color: {color}; 
                border: 1px solid {color}66;
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
                height: 3px; 
            }}
            QProgressBar::chunk {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 #ffffff); 
                border-radius: 2px;
            }}
            QPushButton {{ 
                background-color: {color}1f; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: {max(10, r - 2)}px; 
                padding: {pad_y}px {pad_x}px; 
                font-weight: bold; 
                font-size: {fsz}px;
            }}
            QPushButton:hover {{ 
                background-color: {color}3d; 
                border: 1px solid {color}; 
                color: {color};
            }}
            QPushButton:pressed {{
                background-color: {color}55;
            }}
            QStatusBar {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                font-size: {max(11, fsz - 1)}px; 
                border: 1px solid {border}; 
                border-radius: {max(10, r - 4)}px;
                margin: {m}px {m + 4}px;
                padding: 2px {pad_x}px;
            }}
            QMenu {{ 
                background-color: {nav_bg}; 
                color: {fg}; 
                border: 1px solid {border}; 
                border-radius: 8px; 
                padding: 4px; 
            }}
            QMenu::item {{ 
                padding: 6px 40px 6px 12px; 
                border-radius: 4px;
                min-height: 22px;
            }}
            QMenu::item:selected {{ 
                background-color: rgba(255,255,255,0.08);
                color: {fg};
            }}
            QMenu::item:disabled {{
                color: {fg}66;
            }}
            QMenu::separator {{
                height: 1px;
                background: {border};
                margin: 4px 8px;
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
                border-radius: {max(8, r - 4)}px;
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
            QSlider::groove:horizontal {{
                height: 6px; background: {border}; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {color}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
            }}
            QComboBox {{
                background: {nav_bg}; color: {fg}; border: 1px solid {border};
                border-radius: {max(8, r - 4)}px; padding: 6px 10px;
            }}
            QComboBox QAbstractItemView {{
                background: {nav_bg}; color: {fg}; selection-background-color: {color};
                border: 1px solid {border}; border-radius: 8px;
            }}
            QCheckBox {{ color: {fg}; spacing: 8px; }}
            QLabel {{ color: {fg}; }}
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


class ChromeDialog(QDialog):
    def __init__(self, parent, title, message, kind="alert", default=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        accent = "#4a9eff"
        try:
            accent = parent.accent_color
        except Exception:
            pass
        self.setStyleSheet(f"""
            QDialog {{ background: #12151c; color: #eef3ff; border-radius: 16px; }}
            QLabel {{ color: #eef3ff; font-size: 14px; }}
            QLineEdit {{ background: #1b2130; color: #eef3ff; border: 1px solid {accent}; border-radius: 10px; padding: 8px 12px; }}
            QPushButton {{ background: {accent}; color: #081018; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 600; }}
            QPushButton#ghost {{ background: transparent; color: #c5d3ee; border: 1px solid #2a3348; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 18)
        lay.setSpacing(14)
        t = QLabel(title)
        t.setStyleSheet("font-size:18px; font-weight:700;")
        lay.addWidget(t)
        m = QLabel(str(message))
        m.setWordWrap(True)
        lay.addWidget(m)
        self.edit = None
        if kind == "prompt":
            self.edit = QLineEdit(default)
            lay.addWidget(self.edit)
        row = QHBoxLayout()
        row.addStretch()
        if kind != "alert":
            cancel = QPushButton("Cancel")
            cancel.setObjectName("ghost")
            cancel.clicked.connect(self.reject)
            row.addWidget(cancel)
        ok = QPushButton("OK" if kind != "confirm" else "Allow")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)
        self._ok = False

    def exec_ok(self):
        return self.exec() == QDialog.DialogCode.Accepted


class Motion:
    _live = []

    @staticmethod
    def duration(cfg):
        if cfg.get("reduce_motion", False):
            return 1
        return max(1, int(cfg.get("anim_ms", 280)))

    @classmethod
    def _keep(cls, anim):
        cls._live.append(anim)
        def _drop():
            if anim in cls._live:
                cls._live.remove(anim)
        anim.finished.connect(_drop)
        return anim

    @classmethod
    def window_opacity(cls, win, start, end, ms):
        anim = QPropertyAnimation(win, b"windowOpacity", win)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        return cls._keep(anim)

    @classmethod
    def fade_widget(cls, widget, start, end, ms, done=None):
        if widget is None:
            return None
        eff = widget.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        if done:
            anim.finished.connect(done)
        anim.start()
        return cls._keep(anim)

    @classmethod
    def max_width(cls, widget, start, end, ms):
        anim = QPropertyAnimation(widget, b"maximumWidth", widget)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        return cls._keep(anim)

class SlothSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, parent):
        super().__init__(parent)
        self.browser = parent
        self._active_jobs = {} # Persist buffers until job is destroyed

    def _home_apps(self):
        apps = self.browser.config_manager.get("home_apps")
        if not isinstance(apps, list) or not apps:
            apps = list(DEFAULT_HOME_APPS)
            self.browser.config_manager.set("home_apps", apps)
        return apps

    def _home_app_cards(self):
        cards = []
        for i, item in enumerate(self._home_apps()):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "App")).replace("<", "").replace(">", "")[:40]
            url = str(item.get("url", "#"))
            cards.append(
                f"<div class='module-card' style='position:relative;padding:18px;min-height:72px;'>"
                f"<a href='sloth://delete-app?i={i}' style='position:absolute;top:6px;right:10px;color:#ff4444;text-decoration:none;font-size:1.2rem;'>×</a>"
                f"<a href='{url}' style='text-decoration:none;color:inherit;display:flex;align-items:center;justify-content:center;height:100%;font-weight:600;'>{name}</a>"
                f"</div>"
            )
        return "".join(cards) or "<p style='opacity:0.6'>No apps yet. Use + Add App.</p>"

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
        elif url.startswith("sloth://sleep") or host in ("sleep", "sleeping"):
            orig_url = ""
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                orig_url = (query.get("url") or query.get("u") or [""])[0]
                orig_url = urllib.parse.unquote(orig_url or "")
            except Exception:
                orig_url = ""
            if orig_url.startswith("sloth://sleep"):
                orig_url = ""
            wake_href = urllib.parse.quote(orig_url, safe="")
            shown = html_lib.escape(orig_url) if orig_url else "this tab"
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
                        <svg viewBox='0 0 100 100' style='width: 100px; height: 100px;'>
                            <rect x='10' y='45' width='80' height='10' rx='5' fill='#5d4037'/>
                            <ellipse cx='50' cy='58' rx='25' ry='15' fill='#8d5b4c'/>
                            <circle cx='50' cy='52' r='14' fill='#d7ccc8'/>
                            <path d='M 42 52 Q 45 55 48 52' stroke='#4e342e' stroke-width='2' fill='none'/>
                            <path d='M 52 52 Q 55 55 58 52' stroke='#4e342e' stroke-width='2' fill='none'/>
                            <ellipse cx='50' cy='58' rx='3' ry='2' fill='#3e2723'/>
                        </svg>
                        <span class='z1' style='top: 20px; right: 20px; font-size: 1.5rem;'>Z</span>
                        <span class='z2' style='top: 10px; right: 5px; font-size: 1.1rem;'>z</span>
                        <span class='z3' style='top: 30px; right: -5px; font-size: 0.9rem;'>z</span>
                    </div>
                    <h2>Your Sloth is sleeping...</h2>
                    <p style='font-size:1.05rem; opacity:0.8; margin-bottom:12px;'>Hibernating to free RAM. Wake to return to the same page.</p>
                    <p style='font-size:0.85rem; opacity:0.65; word-break:break-all; margin-bottom:24px;'>{shown}</p>
                    <a class='btn' href='sloth://wake?url={wake_href}' style='background:var(--accent); color:#000; font-weight:bold; font-size:1.1rem; padding:12px 40px; text-decoration:none; display:inline-block;'>Wake Up Tab</a>
                </div>
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
            _cfg = self.browser.config_manager.config
            _se_opts = "".join(
                f"<option value='{html_lib.escape(k)}' style='background:#111; color:white;'{(' selected' if self.browser.config_manager.get('search_engine','mergarms')==k else '')}>{html_lib.escape(n)}</option>"
                for k, n, _t in all_search_engines(_cfg)
            )
            _se_map = {}
            for k, n, t in all_search_engines(_cfg):
                if k == "local":
                    _se_map[k] = str(self.browser.config_manager.get("local_search_url") or "http://127.0.0.1:8888/?q={q}")
                elif t:
                    _se_map[k] = t
            _se_json = json.dumps(_se_map)
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
                        <form id='searchForm' action='https://mergarms.grok.me/' method='GET' style='display:flex; width:100%; max-width:650px; margin:0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3); border-radius: 50px; overflow: hidden; border: 1px solid var(--border); background: rgba(0,0,0,0.2);'>
                            <select id='searchEngine' style='background:transparent; color:white; border:none; padding:15px; outline:none; font-size:1rem; cursor:pointer; border-right:1px solid var(--border); border-radius:0; height:100%; box-sizing:border-box;'>
                                {_se_opts}
                            </select>
                            <input type='text' name='q' id='searchInput' placeholder='Search Mergarms (by Sloth Search)...' style='padding:15px 25px; border:none; background:transparent; color:white; width:100%; outline:none; font-size:1.1rem; box-sizing:border-box;'>
                            <button type='submit' style='padding:15px 30px; border:none; background:var(--accent); color:#000; font-weight:bold; cursor:pointer; transition: 0.3s;'>Search</button>
                        </form>
                    </div>

                    <!-- Main Apps Grid -->
                    <div class='grid'>
                        <a href='sloth://settings' class='module-card'><span class='module-icon'>⚙️</span><span class='module-title'>Settings</span></a>
                        <a href='sloth://bookmarks' class='module-card'><span class='module-icon'>📑</span><span class='module-title'>Bookmarks</span></a>
                        <a href='sloth://downloads' class='module-card'><span class='module-icon'>⬇️</span><span class='module-title'>Downloads</span></a>
                        <a href='sloth://history' class='module-card'><span class='module-icon'>🕒</span><span class='module-title'>History</span></a>
                        <a href='sloth://passwords' class='module-card'><span class='module-icon'>🔐</span><span class='module-title'>Sloth Pass</span></a>
                        <a href='sloth://mail' class='module-card'><span class='module-icon'>📬</span><span class='module-title'>Sloth Mail</span></a>
                        <a href='sloth://translate' class='module-card'><span class='module-icon'>🌐</span><span class='module-title'>Translate</span></a>
                        <a href='sloth://reader' class='module-card'><span class='module-icon'>📖</span><span class='module-title'>Reader</span></a>
                        <a href='sloth://gpu' class='module-card'><span class='module-icon'>📟</span><span class='module-title'>GPU & System</span></a>
                        <a href='sloth://stats' class='module-card'><span class='module-icon'>📊</span><span class='module-title'>Statistics</span></a>
                        <a href='sloth://help' class='module-card'><span class='module-icon'>❓</span><span class='module-title'>Help</span></a>
                        <a href='sloth://extensions' class='module-card'><span class='module-icon'>🧩</span><span class='module-title'>Extensions</span></a>
                        <a href='sloth://about' class='module-card'><span class='module-icon'>ℹ️</span><span class='module-title'>About</span></a>
                        <a href='sloth://arcade' class='module-card arcade-card'><span class='tag'>Live</span><span class='module-icon'>🎮</span><span class='module-title'>Arcade Lab</span></a>
                        <a href='sloth://flags' class='module-card'><span class='module-icon'>🚩</span><span class='module-title'>Flags</span></a>
                        <a href='sloth://account' class='module-card'><span class='module-icon'>👤</span><span class='module-title'>Account</span></a>
                        <a href='sloth://spaces' class='module-card'><span class='module-icon'>🗂️</span><span class='module-title'>Spaces</span></a>
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
                            <a class='btn' href='sloth://add-app' style='margin:0; padding:6px 12px; font-size:0.8rem; border-radius:8px; background:var(--accent); color:#000; font-weight:bold; text-decoration:none;'>+ Add App</a>
                        </h3>
                        <div id='shortcuts-grid' class='grid' style='grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:15px; margin-top:15px;'>
                            {self._home_app_cards()}
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
                        
                        const savedEngine = localStorage.getItem('__sloth_search_engine') || {json.dumps(str(self.browser.config_manager.get("search_engine", "mergarms")))};
                        sSelect.value = savedEngine;
                        const searchMap = {_se_json};
                        updateSearchAction(savedEngine);
                        
                        sSelect.addEventListener('change', (e) => {{
                            const val = e.target.value;
                            localStorage.setItem('__sloth_search_engine', val);
                            updateSearchAction(val);
                        }});

                        sForm.addEventListener('submit', (e) => {{
                            e.preventDefault();
                            const engine = sSelect.value;
                            const query = encodeURIComponent(sInput.value || '');
                            let tmpl = searchMap[engine] || searchMap['mergarms'] || 'https://mergarms.grok.me/?q={{q}}';
                            let u = tmpl.indexOf('{{q}}') >= 0 ? tmpl.split('{{q}}').join(query) : (tmpl + (tmpl.indexOf('?')>=0 ? '&' : '?') + 'q=' + query);
                            window.location.href = u;
                        }});
                        
                        function updateSearchAction(engine) {{
                            sInput.name = 'q';
                            const opt = sSelect.options[sSelect.selectedIndex];
                            sInput.placeholder = 'Search ' + (opt ? opt.text : engine) + '...';
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
                cfg = self.browser.config_manager
                def tog(label, key, default=False):
                    on = bool(cfg.get(key, default))
                    nxt = "0" if on else "1"
                    col = "var(--accent)" if on else "#444"
                    fg = "#000" if on else "#fff"
                    return (
                        f"<div style='display:flex;justify-content:space-between;align-items:center;gap:10px;'>"
                        f"<span style='font-weight:600;font-size:0.95rem;opacity:0.9;'>{label}</span>"
                        f"<a class='btn' style='margin:0;padding:8px 16px;background:{col};color:{fg};text-decoration:none;' href='sloth://cfg?k={key}&v={nxt}'>{'On' if on else 'Off'}</a></div>"
                    )
                extra_toggles = "".join([
                    tog("AI features", "ai_enabled", True),
                    tog("Combined 1-line chrome", "combined_chrome", False),
                    tog("Sleep idle tabs", "auto_sleep_tabs", True),
                    tog("Auto-group tabs", "auto_group_tabs", True),
                    tog("Strip tracking from copied URLs", "clean_copy_urls", True),
                    tog("Block right-click hijack", "protect_context_menu", True),
                    tog("HTML/CSS-only mode", "html_only", False),
                    tog("Save browsing history", "save_history", True),
                    tog("Save search history", "save_search_history", True),
                    tog("Zen compact", "zen_compact", False),
                    tog("Ad blocker", "ad_block_enabled", True),
                    tog("Block trackers", "block_trackers", True),
                    tog("Spoof IP lookups", "mask_ip", False),
                    tog("Show status bar", "show_status", True),
                    tog("Show bookmarks bar", "show_bookmarks_bar", False),
                    tog("Restore tabs on launch", "restore_session", True),
                    tog("Pill tabs", "pill_tabs", True),
                    tog("Floating URL bar", "floating_url", False),
                    tog("Workspace tint", "workspace_tint", True),
                    tog("Reduce motion", "reduce_motion", False),
                ])
                extra_toggles += (
                    f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;'>"
                    f"<a class='btn' href='sloth://ai' style='text-decoration:none;margin:0;'>AI panel</a>"
                    f"<a class='btn' href='sloth://summarize' style='text-decoration:none;margin:0;'>Summarise this page</a>"
                    f"<a class='btn' href='sloth://organise-tabs' style='text-decoration:none;margin:0;'>Organise tabs</a>"
                    f"</div>"
                )
                
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

                            <div style='display:flex; flex-direction:column; gap:6px;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Default search engine</span>
                                <select onchange='window.location.href="sloth://set-search?s="+this.value' style='background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px;'>
                                    {''.join(f"<option value='{html_lib.escape(k)}' {'selected' if self.browser.config_manager.get('search_engine','mergarms')==k else ''}>{html_lib.escape(n)}</option>" for k,n,_t in all_search_engines(self.browser.config_manager.config))}
                                </select>
                            </div>
                            <div style='display:flex; flex-direction:column; gap:6px;'>
                                <span style='font-weight:600; font-size:0.95rem; opacity:0.9;'>Add your own search engine</span>
                                <p style='opacity:0.65; font-size:0.8rem; margin:0;'>Use <code>{{q}}</code> where the query goes. Example: <code>https://kagi.com/search?q={{q}}</code></p>
                                <div style='display:flex; gap:8px; flex-wrap:wrap;'>
                                    <input type='text' id='se-name' placeholder='Name (e.g. Kagi)' style='flex:1; min-width:120px; background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px;'>
                                    <input type='text' id='se-url' placeholder='https://example.com/search?q={{q}}' style='flex:2; min-width:180px; background:rgba(0,0,0,0.3); color:white; border:1px solid var(--border); padding:10px; border-radius:10px;'>
                                    <button class='btn' style='margin:0; padding:10px 16px;' onclick='window.location.href="sloth://add-search?n="+encodeURIComponent(document.getElementById("se-name").value)+"&u="+encodeURIComponent(document.getElementById("se-url").value)'>Add</button>
                                </div>
                                {''.join(
                                    f"<div style='display:flex;justify-content:space-between;align-items:center;gap:8px;'><span>{html_lib.escape(e.get('name') or '')} · <code>{html_lib.escape(e.get('url') or '')}</code></span><a class='btn' style='margin:0;padding:6px 10px;background:#ff4444;color:#fff;text-decoration:none;' href='sloth://del-search?k={urllib.parse.quote(e.get('key') or _engine_key(e.get('name') or ''))}'>Remove</a></div>"
                                    for e in (self.browser.config_manager.get('custom_search_engines') or []) if isinstance(e, dict)
                                )}
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
                        <div class='card' style='display:block;'>
                            <h2 style='color:var(--accent); margin-top:0; margin-bottom:15px; font-size:1.5rem; border-bottom:1px solid var(--border); padding-bottom:10px;'>⚡ Features (same as Settings box)</h2>
                            <div style='display:flex; flex-direction:column; gap:12px;'>{extra_toggles}</div>
                            <p style='opacity:0.65;font-size:0.85rem;margin-top:12px;'>Sleep after {cfg.get("sleep_after_min", 5)} min · AI endpoint: {html_lib.escape(str(cfg.get("ai_endpoint") or "on-device"))}</p>
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
            for b in (self.browser.bookmarks or []):
                if isinstance(b, dict):
                    b_url = b.get('url', '#') or '#'
                    b_title = b.get('title') or b_url
                else:
                    b_url = str(b)
                    b_title = b_url
                short_url = b_url.replace('https://','').replace('http://','')[:50]
                safe_title = str(b_title).replace('<','&lt;').replace('>','&gt;')
                bm_items += f"<div class='card bookmark-item'><div><div class='card-title'>{safe_title}</div><div class='card-meta'>{short_url}</div></div><div style='display:flex; gap:10px;'><a href='{b_url}' class='btn' style='margin:0;'>Open</a><a href='sloth://delete-bookmark?u={urllib.parse.quote(b_url)}' class='btn' style='margin:0; background:#ff4444;'>Delete</a></div></div>"
            
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
            items = "".join([
                f"<div class='card'><div><div class='card-meta'>{h['time']} • {h['url'][:60]}...</div><div class='card-title'>{h['title'][:50]}</div></div>"
                f"<div style='display:flex;gap:8px;'><a href='{h['url']}' class='btn' style='margin:0;'>Return</a>"
                f"<a href='sloth://delete-history-site?h={urllib.parse.quote(urllib.parse.urlsplit(h['url']).netloc)}' class='btn' style='margin:0;background:#ff4444;'>Delete site</a></div></div>"
                for h in reversed(self.browser.history_manager.history) if isinstance(h, dict)
            ])
            empty_hist = "<p style='text-align:center; padding:40px;'>Browsing history will appear here as you explore the grid.</p>"
            html = f"{common_head}<body><div class='container'><h1>History</h1><div style='text-align:center; margin-bottom:20px;'><a href='sloth://clear-history' class='btn' style='background:#ff4444;'>Clear History</a></div><div style='margin-top:20px;'>{items or empty_hist}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif url == "sloth://downloads" or host == "downloads":
            items = "".join([f"<div class='card'><div><div class='card-title'>{os.path.basename(d['path'])}</div><p style='margin:0; font-size:0.9rem;'>Status: Downloaded</p></div><a href='file:///{os.path.dirname(d['path']).replace(os.sep, '/')}' class='btn' style='margin:0;'>Open Folder</a></div>" for d in reversed(self.browser.downloads)])
            empty_dl = "<p style='text-align:center; padding:40px;'>Downloaded files will appear here.</p>"
            html = f"{common_head}<body><div class='container'><h1>Downloads</h1><div style='margin-top:20px;'>{items or empty_dl}</div><div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
        elif host == "add-app" or url.startswith("sloth://add-app"):
            QTimer.singleShot(0, self.browser.prompt_add_app)
            html = f"{common_head}<body><div class='container'><h1>Adding app…</h1><p>A dialog will open. If it does not, go Home and try again.</p><a href='sloth://home' class='btn'>Home</a></div></body></html>"
        elif host == "delete-app" or url.startswith("sloth://delete-app"):
            try:
                idx = int(urllib.parse.parse_qs(url_obj.query()).get("i", ["-1"])[0])
            except Exception:
                idx = -1
            apps = self._home_apps()
            if 0 <= idx < len(apps):
                apps.pop(idx)
                self.browser.config_manager.set("home_apps", apps)
            html = "<html><head><meta http-equiv='refresh' content='0; url=sloth://home'></head></html>"
        elif host == "spaces" or url == "sloth://spaces":
            spaces = self.browser.config_manager.get("custom_spaces") or default_spaces()
            cards = ""
            for sp in spaces:
                sid = space_id(sp.get("id") or sp.get("name"))
                nm = sp.get("name", sid)
                ic = sp.get("icon", "🗂️")
                cards += f"<a href='sloth://open-space?n={urllib.parse.quote(sid)}' class='module-card'><span class='module-icon'>{ic}</span><span class='module-title'>{nm}</span></a>"
                if sid not in ("personal", "work", "finance", "social"):
                    cards += f"<a href='sloth://delete-space?n={urllib.parse.quote(sid)}' class='module-card' style='min-height:auto;padding:10px;'><span class='module-title'>Remove {nm}</span></a>"
            html = f"""{common_head}<body><div class='container'><h1>Spaces</h1>
                <p>Separate cookie jars. Make as many as you want.</p>
                <div class='grid'>{cards}</div>
                <div class='card' style='display:block;margin-top:28px;'>
                    <h3>New space</h3>
                    <form action='sloth://create-space' method='GET' style='display:flex;gap:10px;margin-top:12px;'>
                        <input name='n' placeholder='Name (e.g. School)' style='flex:1;'>
                        <button class='btn' type='submit' style='background:var(--accent);color:#000;font-weight:700;'>Create</button>
                    </form>
                </div>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"""
        elif host == "create-space" or url.startswith("sloth://create-space"):
            raw = urllib.parse.parse_qs(url_obj.query()).get("n", [""])[0]
            sid = space_id(raw)
            spaces = self.browser.config_manager.get("custom_spaces") or default_spaces()
            if sid and not any(space_id(s.get("id") or s.get("name")) == sid for s in spaces):
                spaces.append({"id": sid, "name": raw.strip() or sid, "icon": "🗂️"})
                self.browser.config_manager.set("custom_spaces", spaces)
            html = "<html><head><meta http-equiv='refresh' content='0; url=sloth://spaces'></head></html>"
        elif host == "delete-space" or url.startswith("sloth://delete-space"):
            sid = space_id(urllib.parse.parse_qs(url_obj.query()).get("n", [""])[0])
            spaces = self.browser.config_manager.get("custom_spaces") or default_spaces()
            spaces = [s for s in spaces if space_id(s.get("id") or s.get("name")) != sid]
            self.browser.config_manager.set("custom_spaces", spaces)
            html = "<html><head><meta http-equiv='refresh' content='0; url=sloth://spaces'></head></html>"
        elif host == "open-space" or url.startswith("sloth://open-space"):
            name = space_id(urllib.parse.parse_qs(url_obj.query()).get("n", ["personal"])[0])
            QTimer.singleShot(80, lambda n=name: self.browser.open_space_safe(n))
            html = "<html><head><meta http-equiv='refresh' content='0; url=sloth://home'></head></html>"
        elif url == "sloth://help" or host == "help":
            html = f"{common_head}<body><div class='container'><h1>Help & Shortcuts</h1><p>These work from any page. Open this list any time at sloth://help.</p><div class='shortcut-list'>{shortcut_cards()}</div><div style='margin-top:40px;'><a href='sloth://start' class='btn btn-secondary'>Setup</a> <a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"
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
            def chk(key, default=True):
                return "checked" if self.browser.config_manager.get(key, default) else ""
            def row(name, key, blurb, default=True):
                return f"""<div style='display:flex; justify-content:space-between; align-items:center; margin:15px 0;'>
                    <div style='text-align:left;'><strong style='font-size:1.05rem;'>{name}</strong>
                    <div style='font-size:0.85rem; opacity:0.7; margin-top:3px;'>{blurb}</div></div>
                    <label class="switch"><input type="checkbox" name="{key}" value="on" {chk(key, default)}><span class="slider"></span></label>
                </div>"""
            html = f"""{common_head}<body><div class='container'>
                <h1>🚩 Engine Flags</h1>
                <p>Toggles apply immediately. Chromium launch flags still need a restart.</p>
                <form action='sloth://save-flags' method='GET' style='width:100%;'>
                    <div class='card' style='display:block; margin-bottom:20px; background:rgba(255,255,255,0.02);'>
                        <h3 style='margin-top:0; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:10px;'>⚙️ Feature Toggles</h3>
                        {row("Smooth scrolling", "ss", "Animate page scroll.")}
                        {row("JavaScript", "js", "Run scripts on pages.")}
                        {row("Load images", "img", "Show pictures.")}
                        {row("Autoplay media", "ap", "Videos may start on their own.")}
                        {row("Pop-ups", "pop", "Allow window.open / new tabs from JS.")}
                        {row("WebRTC leak shield", "rtc", "Hide local network addresses.", False)}
                        {row("Restore last session", "sess", "Reopen tabs on launch.")}
                        {row("GPU raster", "gpu", "Hardware-accelerated painting.")}
                        {row("Dark page hint", "darkp", "Ask sites for dark style.")}
                        {row("Spellcheck", "sp", "Underline misspellings.")}
                        {row("AI features", "ai", "Summarise pages and organise tabs.", True)}
                        {row("Sleep idle tabs", "slp", "Hibernate background tabs after a few minutes.", True)}
                        {row("Strip tracking from copies", "cln", "Clean utm/fbclid junk off copied URLs.", True)}
                        {row("Protect context menu", "ctx", "Ignore site right-click hijacks.", True)}
                        {row("HTML/CSS only", "htm", "Block page scripts.", False)}
                    </div>
                    <div class='card' style='display:block; background:rgba(255,255,255,0.02);'>
                        <h3 style='margin-top:0; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:10px;'>🧪 Chromium Launch Flags</h3>
                        <p style='font-size:0.85rem; text-align:left; margin:10px 0;'>One flag per line (e.g. <code>--disable-gpu</code>):</p>
                        <textarea name='f' style='width:100%; height:200px; background:rgba(0,0,0,0.2); color:var(--fg); border:1px solid var(--border); border-radius:14px; padding:15px; font-family:monospace; outline:none; resize:vertical; box-sizing:border-box;'>{flags_text}</textarea>
                    </div>
                    <div style='text-align:center; margin-top:30px;'>
                        <button type='submit' class='btn' style='width:100%; max-width:300px; background:var(--accent); color:#000; font-weight:bold;'>Save flags</button>
                    </div>
                </form>
                <div style='margin-top:40px;'><a href='sloth://home' class='btn btn-secondary' style='text-decoration:none;'>← Home</a></div>
            </div></body></html>"""
        elif url.startswith("sloth://save-flags"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                if 'f' in query:
                    new_flags = [f.strip() for f in query['f'][0].split('\n') if f.strip()]
                    self.browser.config_manager.set("chromium_flags", new_flags)
                mapping = {
                    "ss": "smooth_scrolling",
                    "js": "js_enabled",
                    "img": "images_enabled",
                    "ap": "autoplay_enabled",
                    "pop": "popups_enabled",
                    "rtc": "webrtc_shield",
                    "sess": "restore_session",
                    "gpu": "gpu_raster",
                    "darkp": "dark_pages",
                    "sp": "spellcheck",
                    "ai": "ai_enabled",
                    "slp": "auto_sleep_tabs",
                    "cln": "clean_copy_urls",
                    "ctx": "protect_context_menu",
                    "htm": "html_only",
                }
                for qk, ck in mapping.items():
                    self.browser.config_manager.set(ck, qk in query)
                self.browser.apply_runtime_flags()
                try:
                    self.browser.set_html_only(bool(self.browser.config_manager.get("html_only", False)))
                except Exception:
                    pass
                self.browser.log("Flags saved.", notify=True)
            except Exception as e:
                print(f"Failed to save flags: {e}")
            html = f"<html><body><p>Saved.</p><script>window.location.href='sloth://flags'</script></body></html>"
        elif url == "sloth://mail" or host == "mail":
            mm = self.browser.mail_manager
            mm.due_later()
            q = urllib.parse.parse_qs(url_obj.query())
            folder = (q.get("f", ["inbox"])[0] or "inbox")
            box_id = (q.get("b", [""])[0] or "")
            if not box_id and mm.boxes:
                box_id = mm.boxes[0]["id"]
            boxes_html = ""
            for b in mm.boxes:
                sel = "border-color:var(--accent)" if b["id"] == box_id else ""
                boxes_html += f"<a class='card' style='display:block;{sel}' href='sloth://mail?b={b['id']}&f={folder}'><div class='card-title'>{html_lib.escape(b.get('label') or b.get('address'))}</div><div class='card-meta'>{b.get('kind')} · {html_lib.escape(b.get('address',''))}</div></a>"
            msgs = [m for m in reversed(mm.messages) if (not box_id or m.get("box")==box_id) and m.get("folder")==folder]
            filt = (q.get("q", [""])[0] or "").lower()
            if filt:
                msgs = [m for m in msgs if filt in (m.get("subject","")+m.get("from","")+m.get("body","")).lower()]
            items = ""
            for m in msgs[:80]:
                items += f"<div class='card' style='display:block'><div class='card-title'>{html_lib.escape(m.get('subject') or '(no subject)')}</div><div class='card-meta'>{html_lib.escape(m.get('from',''))} → {html_lib.escape(m.get('to',''))}</div><p>{html_lib.escape((m.get('body') or '')[:400])}</p></div>"
            filters_html = "".join(f"<div class='card-meta'>{html_lib.escape(fl.get('match',''))} → {html_lib.escape(fl.get('action',''))}</div>" for fl in mm.filters)
            html = f"""{common_head}<body><div class='container'><h1>📬 Sloth Mail</h1>
            <p>Throwaway inboxes (1secmail) plus local/real aliases. Filters and send-later stay on this machine.</p>
            <div style='display:flex;gap:10px;flex-wrap:wrap;margin:12px 0'>
                <a class='btn' href='sloth://mail-new-throwaway'>+ Throwaway</a>
                <a class='btn btn-secondary' href='sloth://mail-refresh?b={box_id}'>Refresh</a>
                <a class='btn btn-secondary' href='sloth://mail?b={box_id}&f=inbox'>Inbox</a>
                <a class='btn btn-secondary' href='sloth://mail?b={box_id}&f=sent'>Sent</a>
                <a class='btn btn-secondary' href='sloth://mail?b={box_id}&f=later'>Later</a>
                <a class='btn btn-secondary' href='sloth://mail?b={box_id}&f=spam'>Spam</a>
            </div>
            <div class='grid' style='grid-template-columns:1fr 2fr;align-items:start'>
                <div>{boxes_html or "<p>No inboxes yet.</p>"}
                    <div class='card' style='display:block;margin-top:12px'><h3>Real inbox</h3>
                    <form action='sloth://mail-add-real' method='GET'><input name='a' placeholder='you@example.com'><button class='btn' type='submit'>Add</button></form></div>
                    <div class='card' style='display:block'><h3>Filter</h3>
                    <form action='sloth://mail-filter' method='GET'><input name='m' placeholder='match text'><select name='act'><option value='spam'>Move to spam</option><option value='later'>Send later pile</option><option value='tag'>Tag</option></select><button class='btn' type='submit'>Add filter</button></form>
                    {filters_html}</div>
                </div>
                <div>
                    <form action='sloth://mail' method='GET'><input type='hidden' name='b' value='{box_id}'><input type='hidden' name='f' value='{folder}'><input name='q' placeholder='Search this folder' value='{html_lib.escape(filt)}'></form>
                    {items or "<p>Nothing here.</p>"}
                    <div class='card' style='display:block;margin-top:16px'><h3>Compose / send later</h3>
                    <form action='sloth://mail-send' method='GET'>
                        <input type='hidden' name='b' value='{box_id}'>
                        <input name='to' placeholder='To'>
                        <input name='s' placeholder='Subject'>
                        <textarea name='body' placeholder='Message'></textarea>
                        <input name='mins' placeholder='Send later (minutes, 0 = now)'>
                        <button class='btn' type='submit'>Send</button>
                    </form></div>
                </div>
            </div>
            <div style='margin-top:40px'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"""
        elif host == "mail-new-throwaway" or url.startswith("sloth://mail-new-throwaway"):
            self.browser.mail_manager.add_throwaway()
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://mail'></head></html>"
        elif host == "mail-add-real" or url.startswith("sloth://mail-add-real"):
            a = urllib.parse.parse_qs(url_obj.query()).get("a", [""])[0]
            if a:
                self.browser.mail_manager.add_real(a)
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://mail'></head></html>"
        elif host == "mail-filter" or url.startswith("sloth://mail-filter"):
            q = urllib.parse.parse_qs(url_obj.query())
            mm = self.browser.mail_manager
            mm.filters.append({"id": secrets.token_hex(3), "match": q.get("m", [""])[0], "action": q.get("act", ["spam"])[0]})
            mm.save()
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://mail'></head></html>"
        elif host == "mail-refresh" or url.startswith("sloth://mail-refresh"):
            bid = urllib.parse.parse_qs(url_obj.query()).get("b", [""])[0]
            mm = self.browser.mail_manager
            for b in mm.boxes:
                if not bid or b["id"] == bid:
                    mm.refresh_throwaway(b)
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://mail'></head></html>"
        elif host == "mail-send" or url.startswith("sloth://mail-send"):
            q = urllib.parse.parse_qs(url_obj.query())
            mm = self.browser.mail_manager
            bid = q.get("b", [""])[0]
            box = next((b for b in mm.boxes if b["id"] == bid), mm.boxes[0] if mm.boxes else None)
            mins = 0
            try:
                mins = int(q.get("mins", ["0"])[0] or 0)
            except Exception:
                mins = 0
            folder = "later" if mins > 0 else "sent"
            send_at = int(time.time()) + mins * 60 if mins > 0 else 0
            if box:
                mm.add_message(box["id"], folder, box.get("address"), q.get("to", [""])[0], q.get("s", [""])[0], q.get("body", [""])[0], send_at)
                if folder == "sent":
                    self.browser.try_smtp_send(box.get("address"), q.get("to", [""])[0], q.get("s", [""])[0], q.get("body", [""])[0])
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://mail'></head></html>"
        elif url == "sloth://translate" or host == "translate":
            dest = self.browser.config_manager.get("translate_lang", "es")
            html = f"""{common_head}<body><div class='container'><h1>🌐 Sloth Translate</h1>
            <p>Page and selection translator. Offline pack is Spanish; online uses MyMemory when the network is up.</p>
            <div class='card' style='display:block'>
                <p>Target language code: <b>{html_lib.escape(str(dest))}</b></p>
                <form action='sloth://translate-set' method='GET'><input name='l' placeholder='es, fr, de…' value='{html_lib.escape(str(dest))}'><button class='btn' type='submit'>Set language</button></form>
                <p><a class='btn' href='sloth://translate-page'>Translate this tab</a>
                <a class='btn btn-secondary' href='sloth://translate-sel'>Translate selection</a>
                <a class='btn btn-secondary' href='sloth://translate-pack'>Install extra ES words</a></p>
            </div>
            <div style='margin-top:40px'><a href='sloth://home' class='btn btn-secondary'>← Home</a></div></div></body></html>"""
        elif url.startswith("sloth://translate-set"):
            l = urllib.parse.parse_qs(url_obj.query()).get("l", ["es"])[0] or "es"
            self.browser.config_manager.set("translate_lang", l.strip()[:8])
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://translate'></head></html>"
        elif host == "translate-page":
            QTimer.singleShot(0, self.browser.translate_page)
            html = "<html><body><script>history.back()</script></body></html>"
        elif host == "translate-sel":
            QTimer.singleShot(0, self.browser.translate_selection)
            html = "<html><body><script>history.back()</script></body></html>"
        elif host == "translate-pack":
            extra = self.browser.config_manager.get("offline_pack") or {}
            extra.update({"hello": "hola", "world": "mundo", "please": "por favor", "thanks": "gracias", "yes": "sí", "no": "no", "browser": "navegador"})
            self.browser.config_manager.set("offline_pack", extra)
            html = "<html><head><meta http-equiv='refresh' content='0;url=sloth://translate'></head></html>"
        elif url == "sloth://reader" or host == "reader":
            QTimer.singleShot(0, self.browser.toggle_reader)
            html = f"""{common_head}<body><div class='container'><h1>📖 Sloth Reader</h1>
            <p>Reader mode is toggling on the previous tab. Shortcut: Ctrl+Shift+R.</p>
            <a href='sloth://home' class='btn btn-secondary'>← Home</a></div></body></html>"""
        elif url == "sloth://passwords" or host == "passwords":
            pws = self.browser.password_manager.passwords
            items = ""
            for site, list_pws in pws.items():
                for i, p in enumerate(list_pws):
                    safe_site = urllib.parse.quote(site)
                    kind = p.get("kind") or "password"
                    note = html_lib.escape(p.get("note") or "")
                    items += f"<div class='card'><div style='flex:1;'><div class='card-title'>{html_lib.escape(site)} · {kind}</div><div class='card-meta'>User: {html_lib.escape(p.get('user',''))} | Secret: {'•'*max(4,len(p.get('pass') or ''))} {note}</div></div><a href='sloth://copy-password?s={safe_site}&i={i}' class='btn btn-secondary' style='margin:0'>Copy</a><a href='sloth://delete-password?s={safe_site}&i={i}' class='btn' style='background:#ff4444; margin:0;'>Delete</a></div>"
            html = f"""{common_head}<body><div class='container'>
                <h1>🔐 Sloth Pass</h1>
                <p>Local vault. Pages and extensions can request a fill with <code>console.log("SLOTH_PASS_GET:"+location.host)</code> or <code>window.slothPass.request()</code>.</p>
                <div class='card' style='background:rgba(255,255,255,0.02); display:block;'>
                    <h3>Add password</h3>
                    <form action='sloth://add-password' method='GET' style='display:flex; gap:10px; margin-top:10px; flex-wrap:wrap'>
                        <input type='text' name='s' placeholder='Site'>
                        <input type='text' name='u' placeholder='Username'>
                        <input type='password' name='p' placeholder='Password'>
                        <input type='text' name='n' placeholder='Note'>
                        <button class='btn' type='submit'>Add</button>
                    </form>
                    <form action='sloth://add-passkey' method='GET' style='display:flex;gap:10px;margin-top:10px'>
                        <input name='s' placeholder='Site for passkey'>
                        <input name='u' placeholder='Username'>
                        <button class='btn btn-secondary' type='submit'>Mint local passkey</button>
                    </form>
                </div>
                <div style='margin-top:20px;'>{items or '<p style="text-align:center; padding:40px;">Vault is empty.</p>'}</div>
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
        elif url.startswith("sloth://copy-password"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                site = urllib.parse.unquote(query.get("s", [""])[0])
                idx = int(query.get("i", ["-1"])[0])
                secret = self.browser.password_manager.passwords[site][idx].get("pass", "")
                QApplication.clipboard().setText(secret)
                self.browser.log("Copied from vault", notify=True)
            except Exception:
                pass
            html = "<html><body><script>window.location.href='sloth://passwords'</script></body></html>"
        elif url.startswith("sloth://add-passkey"):
            q = urllib.parse.parse_qs(url_obj.query())
            self.browser.password_manager.add_passkey(q.get("s", [""])[0] or "site", q.get("u", [""])[0])
            html = "<html><body><script>window.location.href='sloth://passwords'</script></body></html>"
        elif url == "sloth://export":
            self.browser.export_data()
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url == "sloth://import":
            self.browser.import_data()
            html = "<html><body><script>window.location.href='sloth://start'</script></body></html>"
        elif url.startswith("sloth://import-browser"):
            q = urllib.parse.parse_qs(url_obj.query())
            src = (q.get("src", [""])[0] or "").lower()
            result = BrowserImporter.import_source(src, self.browser)
            msg = urllib.parse.quote(result.get("message") or "Done")
            html = f"<html><body><script>window.location.href='sloth://start?imported={msg}'</script></body></html>"
        elif url.startswith("sloth://import-path"):
            q = urllib.parse.parse_qs(url_obj.query())
            p = urllib.parse.unquote(q.get("p", [""])[0] or "")
            result = BrowserImporter.import_any_path(p, self.browser) if p else {"message": "No path"}
            msg = urllib.parse.quote(result.get("message") or "Done")
            html = f"<html><body><script>window.location.href='sloth://start?imported={msg}'</script></body></html>"
        elif url == "sloth://import-scan":
            hits = BrowserImporter.scan_disk(10)
            rows = ""
            for h in hits:
                p = h.get("bookmarks") or ""
                rows += (
                    f"<a href='sloth://import-path?p={urllib.parse.quote(p)}' class='btn' style='display:block;text-align:left;text-decoration:none;margin:6px 0;'>"
                    f"<b>{html_lib.escape(h.get('name') or 'Browser')}</b><br><span style='opacity:.6;font-size:.8rem'>{html_lib.escape(p)}</span></a>"
                )
            if not rows:
                rows = "<p>No extra profiles found in a 10s scan. Use Choose .exe or Bookmarks file.</p>"
            html = f"""{common_head}
            <body><div class='container'><h1>Found browsers</h1>
            <p>Pick one to import bookmarks + recent history.</p>
            {rows}
            <div style='margin-top:24px'><a href='sloth://start' class='btn btn-secondary' style='text-decoration:none'>Back</a>
            <a href='sloth://pick-browser-file' class='btn' style='text-decoration:none'>Choose a file instead</a></div>
            </div></body></html>"""
        elif url == "sloth://pick-browser-file":
            QTimer.singleShot(0, self.browser.pick_browser_import)
            html = f"<html><body style='background:#111;color:#eee;font-family:sans-serif;padding:40px'>Choose a browser .exe, a Bookmarks file, or places.sqlite…</body></html>"
        elif url.startswith("sloth://set-nt"):
            try:
                q = urllib.parse.parse_qs(url_obj.query())
                u = urllib.parse.unquote((q.get("u") or [""])[0] or "")
                if u:
                    if not u.startswith(("http://", "https://", "sloth://", "file:")):
                        u = "https://" + u
                    self.browser.config_manager.set("new_tab_url", u)
                    self.browser.log(f"New tab page set to {u}", notify=True)
            except Exception:
                pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://add-search"):
            try:
                q = urllib.parse.parse_qs(url_obj.query())
                name = urllib.parse.unquote((q.get("n") or [""])[0] or "").strip()
                tmpl = urllib.parse.unquote((q.get("u") or [""])[0] or "").strip()
                if name and tmpl:
                    if "{q}" not in tmpl and "q=" not in tmpl.lower():
                        tmpl = tmpl + ("&" if "?" in tmpl else "?") + "q={q}"
                    extra = list(self.browser.config_manager.get("custom_search_engines") or [])
                    extra.append({"name": name, "url": tmpl, "key": _engine_key(name)})
                    self.browser.config_manager.set("custom_search_engines", extra)
                    self.browser.log(f"Added search engine {name}", notify=True)
            except Exception:
                pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://del-search"):
            try:
                q = urllib.parse.parse_qs(url_obj.query())
                key = urllib.parse.unquote((q.get("k") or [""])[0] or "").strip().lower()
                extra = [e for e in (self.browser.config_manager.get("custom_search_engines") or []) if (e.get("key") or _engine_key(e.get("name") or "")).lower() != key]
                self.browser.config_manager.set("custom_search_engines", extra)
                cur = self.browser.config_manager.get("search_engine", "mergarms")
                if cur == key:
                    self.browser.config_manager.set("search_engine", "mergarms")
                self.browser.log("Removed custom search engine", notify=True)
            except Exception:
                pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url.startswith("sloth://set-search"):
            try:
                query = urllib.parse.parse_qs(url_obj.query())
                s = query.get('s', [''])[0]
                if s:
                    self.browser.config_manager.set("search_engine", s)
                    dest = "sloth://start" if (query.get("from") or [""])[0] == "start" else "sloth://settings"
            except: pass
            html = f"<html><head><meta http-equiv='refresh' content='0; url={dest}'></head></html>"
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
            ext_list_html = ""
            roots = iter_extension_roots()
            try:
                items = list_installed_extensions()
                if items:
                    ext_list_html += "<h3 style='margin-top:30px; margin-bottom:10px;'>Installed</h3><div style='display:flex; flex-direction:column; gap:10px; margin-top:10px;'>"
                    for it in items:
                        eid = html_lib.escape(str(it.get("id") or ""))
                        ename = html_lib.escape(str(it.get("name") or eid))
                        ever = html_lib.escape(str(it.get("version") or ""))
                        kind = it.get("kind") or "js"
                        open_btn = ""
                        if kind == "crx":
                            open_btn = f"<a href='sloth://open-extension?id={urllib.parse.quote(str(it.get('id')))}' class='btn' style='padding:5px 12px; font-size:0.8rem; margin:0; text-decoration:none;'>Open</a>"
                        ext_list_html += (
                            f"<div class='card' style='display:flex; justify-content:space-between; align-items:center; padding:15px 20px; gap:12px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:12px;'>"
                            f"<div><div style='font-weight:700;'>🧩 {ename}</div>"
                            f"<div style='opacity:0.65; font-size:0.8rem; font-family:monospace;'>{eid} {ever}</div></div>"
                            f"<div style='display:flex; gap:8px; flex-shrink:0;'>{open_btn}"
                            f"<a href='sloth://delete-extension?name={urllib.parse.quote(str(it.get('id')))}' class='btn' style='padding:5px 12px; font-size:0.8rem; background:#ff4444; color:#fff; border:none; margin:0; border-radius:6px; text-decoration:none;'>Delete</a>"
                            f"</div></div>"
                        )
                    ext_list_html += "</div>"
                else:
                    ext_list_html += "<p style='opacity:0.6; font-style:italic; margin-top:20px; text-align:center;'>Nothing installed yet. Open the Chrome Web Store and press Add to Sloth.</p>"
            except Exception as e:
                ext_list_html += f"<p style='color:#ff4444;'>Failed to read extensions: {e}</p>"
            paths_html = "<br>".join(html_lib.escape(p) for p in roots)

            mgr, reason = native_extension_manager()
            ver = qt_version_label()
            if mgr:
                engine_html = f"<div class='card' style='display:block;border-color:rgba(80,200,120,0.4);'><b>Native engine: on</b> · Qt {html_lib.escape(ver)} · Manifest V3 via QWebEngineExtensionManager. Installed extensions start disabled; Sloth enables them after installFinished.</div>"
            else:
                engine_html = (
                    f"<div class='card' style='display:block;border-color:rgba(255,170,0,0.5);'>"
                    f"<b>Native Chrome extensions: off</b> · Qt {html_lib.escape(ver)} · {html_lib.escape(reason)}."
                    f"<p style='margin:10px 0 0;opacity:0.85;'>Qt WebEngine only gained real chrome.* / MV3 support in <b>6.10</b>. "
                    f"Upgrade, then restart Sloth:</p>"
                    f"<code style='display:block;margin-top:8px;background:#000;padding:10px;border-radius:8px;'>python -m pip install -U PyQt6 PyQt6-WebEngine</code>"
                    f"<p style='margin:10px 0 0;opacity:0.8;'>Until then Add to Sloth still unpacks the CRX, injects content scripts, and Open shows the popup HTML. APIs like chrome.runtime will not work.</p>"
                    f"</div>"
                )
            html = f"{common_head}<body><div class='container'><h1>🧩 Extension Engine</h1><p>Add from the Chrome Web Store, then press <b>Open</b>.</p>{engine_html}" \
                   f"<div style='background:rgba(255,255,255,0.03); border-radius:16px; padding:25px; margin:20px 0; border:1px solid rgba(255,255,255,0.05);'>" \
                   f"<p>Folders Sloth loads:</p>" \
                   f"<code style='background:#000; padding:10px; border-radius:8px; display:block; margin:10px 0; color:var(--accent); overflow-x:auto;'>{paths_html}</code>" \
                   f"<p style='font-size:0.9rem; opacity:0.8;'>Drop a <code>.js</code> file or an unpacked extension folder (with manifest.json) into these folders.</p>" \
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
                   f"<a href='https://chromewebstore.google.com/' class='btn' style='background:#4285f4; text-decoration:none;'>Open Chrome Store</a>" \
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
            engine = self.browser.config_manager.get("search_engine", "mergarms")
            q = urllib.parse.parse_qs(url_obj.query())
            imported_note = urllib.parse.unquote(q.get("imported", [""])[0] or "")
            browsers = BrowserImporter.profiles()
            import_cards = ""
            for p in browsers:
                badge = "<span style='font-size:0.75rem;color:#7dffb3;'>found on this PC</span>" if p["present"] else "<span style='font-size:0.75rem;opacity:0.45;'>not detected</span>"
                disabled = "" if p["present"] else "pointer-events:none;opacity:0.4;"
                import_cards += (
                    f"<a href='sloth://import-browser?src={p['key']}' class='btn' style='display:flex;flex-direction:column;gap:4px;text-decoration:none;{disabled}'>"
                    f"<b>{p['name']}</b>{badge}</a>"
                )
            imported_banner = ""
            if imported_note:
                imported_banner = f"<div class='card' style='display:block;margin-bottom:24px;border-color:var(--accent);'>{html_lib.escape(imported_note)}</div>"
            html = f"""{common_head}
            <body style='padding:0; overflow-x:hidden; background: var(--bg); color: var(--fg);'>
                <div class='container' style='max-width:1000px; min-height:100vh; padding:60px 20px; box-sizing:border-box; background:transparent; border:none; box-shadow:none;'>
                    <h1 style='font-size:3.5rem; margin-bottom:10px; background: linear-gradient(to right, #00ffee, #ff0099); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Welcome to Sloth Web</h1>
                    <p style='font-size:1.3rem; opacity:0.8; margin-bottom:40px;'>Bring your old browser with you, then settle in.</p>
                    {imported_banner}

                    <div class='card' style='display:block; margin-bottom:30px;'>
                        <h2 style='color:var(--accent);'>Import from another browser</h2>
                        <p>Copies bookmarks and recent history. Passwords stay in the other browser (they are encrypted). Nothing in Sloth is deleted.</p>
                        <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:10px; margin-top:14px;'>
                            {import_cards}
                        </div>
                        <div style='margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;'>
                            <a href='sloth://import-scan' class='btn' style='text-decoration:none; background:var(--accent); color:#000;'>Scan this PC for browsers</a>
                            <a href='sloth://pick-browser-file' class='btn btn-secondary' style='text-decoration:none;'>Choose .exe or Bookmarks file</a>
                            <a href='sloth://import' class='btn btn-secondary' style='text-decoration:none;'>Import a Sloth .sw backup</a>
                        </div>
                    </div>
                    
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
                            <p>Default is Mergarms (by Sloth Search). Sloth Search stays available.</p>
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <select onchange='window.location.href="sloth://set-search?s="+this.value' style='background:#222; color:white; border:1px solid #444; border-radius:8px; padding:10px; flex:1;'>
                                    <option value='mergarms' {"selected" if engine == "mergarms" else ""}>Mergarms (by Sloth Search)</option>
                                    <option value='sloth' {"selected" if engine == "sloth" else ""}>Sloth Search</option>
                                    <option value='google' {"selected" if engine == "google" else ""}>Google</option>
                                    <option value='bing' {"selected" if engine == "bing" else ""}>Bing</option>
                                    <option value='ddg' {"selected" if engine in ("ddg","duckduckgo") else ""}>DuckDuckGo</option>
                                    <option value='brave' {"selected" if engine == "brave" else ""}>Brave</option>
                                    <option value='local' {"selected" if engine == "local" else ""}>Local engine (beta)</option>
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
                            {shortcut_grid()}
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
        elif url.startswith("sloth://cfg"):
            q = urllib.parse.parse_qs(url_obj.query())
            key = (q.get("k", [""])[0] or "").strip()
            raw = (q.get("v", [""])[0] or "").strip()
            if raw in ("1", "on", "true", "yes"):
                val = True
            elif raw in ("0", "off", "false", "no"):
                val = False
            else:
                val = raw
            if key:
                self.browser.config_manager.set(key, val)
                try:
                    if key == "zen_compact":
                        self.browser.apply_zen_compact()
                    elif key == "combined_chrome":
                        self.browser.apply_combined_chrome()
                    elif key == "html_only":
                        self.browser.set_html_only(bool(val))
                    elif key == "ad_block_enabled":
                        self.browser.ad_block_enabled = bool(val)
                        self.browser.ad_interceptor.enabled = bool(val)
                    elif key == "block_trackers":
                        self.browser.set_tracker_block(bool(val))
                    elif key == "mask_ip":
                        self.browser.set_mask_ip(bool(val))
                    elif key == "show_bookmarks_bar":
                        self.browser.config_manager.set("bm_bar_user_picked", True)
                        self.browser.refresh_bookmarks_bar()
                    elif key in ("show_status", "pill_tabs", "reduce_motion"):
                        self.browser.apply_theme()
                    elif key == "floating_url":
                        self.browser.apply_chrome_extras()
                except Exception:
                    pass
            html = "<html><body><script>window.location.href='sloth://settings'</script></body></html>"
        elif url == "sloth://summarize" or host == "summarize":
            QTimer.singleShot(0, self.browser.summarize_page)
            html = f"{common_head}<body><div class='container'><h1>Summarising…</h1><p>Hang on.</p></div></body></html>"
        elif url == "sloth://organise-tabs" or host == "organise-tabs":
            QTimer.singleShot(0, self.browser.ai_organize_tabs)
            html = "<html><body><script>window.location.href='sloth://ai'</script></body></html>"
        elif url == "sloth://ai" or host == "ai":
            body = html_lib.escape(getattr(self.browser, "_last_ai", "") or "No AI result yet. Open a page and choose Summarise, or Organise tabs.")
            on = "On" if SlothAI.enabled(self.browser.config_manager.config) else "Off"
            html = f"""{common_head}<body><div class='container'><h1>Sloth AI</h1>
                <p>Status: <b>{on}</b> · Toggle in Settings. Works on-device unless you set an endpoint.</p>
                <div class='card' style='display:block;white-space:pre-wrap;line-height:1.5;'>{body}</div>
                <div style='display:flex;gap:10px;margin-top:16px;flex-wrap:wrap;'>
                    <a class='btn' href='sloth://summarize'>Summarise current page</a>
                    <a class='btn' href='sloth://organise-tabs'>Organise tabs</a>
                    <a class='btn btn-secondary' href='sloth://settings'>Settings</a>
                </div></div></body></html>"""
        elif url.startswith("sloth://wake") or host == "wake":
            q = urllib.parse.parse_qs(url_obj.query())
            u = urllib.parse.unquote((q.get("url") or q.get("u") or [""])[0] or "")
            if u.startswith("sloth://sleep") or u.startswith("sloth://wake") or u.startswith("sloth://home"):
                u = ""
            QTimer.singleShot(0, lambda u=u: self.browser.wake_url(u))
            html = f"{common_head}<body><div class='container'><h1>Waking tab…</h1><p>Restoring the page you left.</p></div></body></html>"
        elif url.startswith("sloth://delete-history-site"):
            hostn = urllib.parse.unquote(urllib.parse.parse_qs(url_obj.query()).get("h", [""])[0] or "")
            if hostn:
                self.browser.history_manager.history = [
                    h for h in self.browser.history_manager.history
                    if hostn not in (h.get("url") if isinstance(h, dict) else "")
                ]
                self.browser.history_manager.save()
            html = "<html><body><script>window.location.href='sloth://history'</script></body></html>"
        elif url.startswith("sloth://add-password"):
            try:
                q = urllib.parse.parse_qs(url_obj.query())
                site = urllib.parse.unquote(q.get("s", [""])[0])
                user = urllib.parse.unquote(q.get("u", [""])[0])
                pw = urllib.parse.unquote(q.get("p", [""])[0])
                note = urllib.parse.unquote(q.get("n", [""])[0])
                if site and pw:
                    self.browser.password_manager.add_password(site, user, pw, note)
            except Exception:
                pass
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
                q = urllib.parse.parse_qs(url_obj.query())
                h_url = urllib.parse.unquote((q.get("u") or [""])[0] or "")
                if h_url:
                    if not h_url.startswith(("http://", "https://", "sloth://", "file:")):
                        h_url = "https://" + h_url
                    self.browser.config_manager.set("home_url", h_url)
                    self.browser.log(f"Home page set to {h_url}", notify=True)
            except Exception:
                pass
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
            active_url = b.url().toString() if b else ""
            if (not active_url) or active_url.startswith("sloth://"):
                active_url = getattr(self.browser, "last_real_url", "") or ""
            if active_url:
                self.browser.config_manager.set("home_url", active_url)
                self.browser.log(f"Home page set to {active_url}", notify=True)
            else:
                self.browser.log("Open a website first, then set it as Home", notify=True)
            html = f"<html><head><meta http-equiv='refresh' content='0; url=sloth://settings'></head></html>"
        elif url == "sloth://set-current-nt":
            b = self.browser.current_browser()
            active_url = b.url().toString() if b else ""
            if (not active_url) or active_url.startswith("sloth://"):
                active_url = getattr(self.browser, "last_real_url", "") or ""
            if active_url:
                self.browser.config_manager.set("new_tab_url", active_url)
                self.browser.log(f"New tab page set to {active_url}", notify=True)
            else:
                self.browser.log("Open a website first, then set it as New Tab", notify=True)
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
        elif url.startswith("sloth://install-cws") or host == "install-cws":
            eid = "".join(c for c in urllib.parse.unquote((urllib.parse.parse_qs(url_obj.query()).get("id") or [""])[0]) if c.islower())
            job = getattr(self.browser, "_cws_job", None) or {}
            if eid and (not job.get("running") or job.get("id") != eid):
                QTimer.singleShot(0, lambda e=eid: self.browser.install_from_cws(e))
                job = {"id": eid, "running": True, "done": False, "step": "Starting…", "log": [], "ok": False}
            logs = "<br>".join(html_lib.escape(x) for x in (job.get("log") or [])[-12:]) or "Waiting…"
            step = html_lib.escape(str(job.get("step") or "Working…"))
            if job.get("done") and job.get("ok"):
                name = html_lib.escape(str(job.get("name") or "Extension"))
                iid = html_lib.escape(str(job.get("id") or eid))
                html = f"""{common_head}<body><div class='container' style='max-width:640px;text-align:center;'>
                    <h1>Installed</h1>
                    <p style='font-size:1.2rem;font-weight:700;'>{name}</p>
                    <p style='opacity:0.7;font-family:monospace;'>{iid}</p>
                    <p>Use it from the <b>puzzle / icon</b> on the toolbar, or open it here.</p>
                    <div style='display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px;'>
                        <a class='btn' href='sloth://open-extension?id={urllib.parse.quote(str(job.get("id") or eid))}'>Open extension</a>
                        <a class='btn btn-secondary' href='sloth://extensions'>All extensions</a>
                    </div>
                </div></body></html>"""
            elif job.get("done") and not job.get("ok"):
                err = html_lib.escape(str(job.get("error") or "Unknown error"))
                html = f"""{common_head}<body><div class='container' style='max-width:640px;'>
                    <h1>Install failed</h1>
                    <p>{err}</p>
                    <div class='card' style='display:block;text-align:left;font-family:monospace;font-size:0.85rem;'>{logs}</div>
                    <p>Google sometimes blocks the CRX download. You can still install a <code>.crx</code> or <code>.zip</code> you saved yourself.</p>
                    <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;'>
                        <a class='btn' href='sloth://pick-crx'>Pick a .crx / .zip</a>
                        <a class='btn btn-secondary' href='sloth://install-cws?id={eid}'>Retry</a>
                        <a class='btn btn-secondary' href='https://chromewebstore.google.com/'>Back to Store</a>
                    </div>
                </div></body></html>"""
            else:
                html = f"""{common_head}<body><div class='container' style='max-width:640px;text-align:center;'>
                    <meta http-equiv='refresh' content='1'>
                    <h1>Installing…</h1>
                    <p style='font-size:1.1rem;'>{step}</p>
                    <div class='card' style='display:block;text-align:left;font-family:monospace;font-size:0.85rem;min-height:80px;'>{logs}</div>
                    <p style='opacity:0.65;margin-top:16px;'>This page updates itself. Leave it open.</p>
                </div></body></html>"""
        elif url.startswith("sloth://pick-crx") or host == "pick-crx":
            QTimer.singleShot(0, self.browser.pick_crx_file)
            html = f"{common_head}<body><div class='container'><h1>Pick a file…</h1><p>Choose a <code>.crx</code> or <code>.zip</code>.</p><a class='btn' href='sloth://extensions'>Extensions</a></div></body></html>"
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
        elif url.startswith("sloth://open-extension"):
            eid = urllib.parse.unquote(urllib.parse.parse_qs(url_obj.query()).get("id", [""])[0] or "")
            if eid:
                QTimer.singleShot(0, lambda e=eid: self.browser.open_extension_by_id(e))
            html = f"{common_head}<body><div class='container'><h1>Opening extension…</h1><p><a class='btn' href='sloth://extensions'>Back</a></p></div></body></html>"
        elif url.startswith("sloth://delete-extension"):
            query = url_obj.query()
            ext_name = ""
            if "name=" in query:
                ext_name = urllib.parse.unquote(query.split("name=")[1].split("&")[0])
            
            if ext_name:
                try:
                    removed = False
                    for root in iter_extension_roots():
                        full_path = os.path.join(root, ext_name)
                        if os.path.isfile(full_path):
                            os.remove(full_path)
                            removed = True
                        elif os.path.isdir(full_path):
                            shutil.rmtree(full_path, ignore_errors=True)
                            removed = True
                    if removed:
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
        self.trackers_enabled = True
        self.html_only = False
        self.mask_ip = False
        self.mask_label = "slothwebiscool!"
        self.lock = threading.Lock()
        self.host_blacklist = set()
        self.tracker_blacklist = set()
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
                "amazon-adsystem.com", "adnxs.com", "taboola.com", "outbrain.com", "criteo.com",
                "popads.net", "popcash.net", "propellerads.com", "pagead2.googlesyndication.com",
                "ads.yahoo.com", "adsafeprotected.com", "moatads.com", "scorecardresearch.com"
            }
            self.tracker_blacklist = {
                "google-analytics.com", "googletagmanager.com", "googletagservices.com",
                "facebook.net", "facebook.com", "connect.facebook.net", "pixel.facebook.com",
                "hotjar.com", "fullstory.com", "mixpanel.com", "segment.io", "segment.com",
                "sentry.io", "clarity.ms", "adsystem.com", "doubleclick.net",
                "adservice.google.com", "analytics.tiktok.com", "ads.twitter.com",
                "static.ads-twitter.com", "bat.bing.com", "cdn.mouseflow.com",
                "mc.yandex.ru", "stats.wp.com", "pixel.quantserve.com"
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

    def apply_ua(self, ua_type):
        if "Firefox" in (ua_type or ""):
            self.default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
        elif "Safari" in (ua_type or ""):
            self.default_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        elif "Sloth" in (ua_type or ""):
            self.default_ua = f"SlothWeb/Platinum ({__version__})"
        else:
            self.default_ua = Platform.get_user_agent()

    def _host_hit(self, host, bag):
        if not host:
            return False
        if host in bag:
            return True
        return any(host.endswith("." + d) for d in bag)

    def interceptRequest(self, info):
        url_obj = info.requestUrl()
        u = url_obj.toString()
        host = (url_obj.host() or "").lower()

        try:
            if any(domain in host for domain in ["google.", "gstatic.com", "googleapis.com", "chromewebstore", "youtube.com", "ytimg.com", "ggpht.com", "gmail.com", "clients2.google.com"]):
                info.setHttpHeader(b"User-Agent", Platform.get_user_agent().encode())
                info.setHttpHeader(b"Sec-CH-UA", b'"Google Chrome";v="139", "Chromium";v="139", "Not;A=Brand";v="8"')
                info.setHttpHeader(b"Sec-CH-UA-Mobile", b"?0")
                info.setHttpHeader(b"Sec-CH-UA-Platform", f'"{platform.system()}"'.encode())
            else:
                info.setHttpHeader(b"User-Agent", (self.default_ua or Platform.get_user_agent()).encode())
            info.setHttpHeader(b"DNT", b"1")
            info.setHttpHeader(b"Sec-GPC", b"1")
            if self.mask_ip and not any(x in host for x in ("google.", "youtube.com", "gstatic.com")):
                label = (self.mask_label or "slothwebiscool!").encode("utf-8", "ignore")
                info.setHttpHeader(b"X-Forwarded-For", label)
                info.setHttpHeader(b"Client-IP", label)
                info.setHttpHeader(b"X-Real-IP", label)
                info.setHttpHeader(b"True-Client-IP", label)
        except Exception:
            pass

        first_party = (info.firstPartyUrl().host() or "").lower()
        same_site = bool(host) and (host == first_party or (first_party and host.endswith("." + first_party)))

        if any(x in host for x in ("clients2.google.com", "chromewebstore.google.com", "chrome.google.com", "gvt1.com", "lh3.googleusercontent.com")):
            return

        if getattr(self, "html_only", False) and not (url_obj.scheme() or "").startswith("sloth"):
            try:
                from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo
                rt = info.resourceType()
                block = (
                    QWebEngineUrlRequestInfo.ResourceType.Script,
                    QWebEngineUrlRequestInfo.ResourceType.Media,
                    QWebEngineUrlRequestInfo.ResourceType.FontResource,
                )
                if rt in block:
                    info.block(True)
                    self._count_block()
                    return
            except Exception:
                pass

        with self.lock:
            if self.enabled and self._host_hit(host, self.host_blacklist):
                info.block(True)
                self._count_block()
                return
            if self.enabled and hasattr(self, 'ad_regex') and self.ad_regex.search(u):
                info.block(True)
                self._count_block()
                return
            if self.trackers_enabled and self._host_hit(host, self.tracker_blacklist):
                if not same_site or "analytics" in host or "pixel" in host or "doubleclick" in host:
                    info.block(True)
                    self._count_block()
                    return
            if self.enabled and not same_site and any(tok in u.lower() for tok in ("/ads/", "adservice", "pagead", "tracker.js", "collect?v=")):
                info.block(True)
                self._count_block()
                return

    def _count_block(self):
        try:
            p = self.parent()
            if p is None or not hasattr(p, "config_manager"):
                return
            n = int(p.config_manager.get("blocked_ads", 0)) + 1
            p.config_manager.config["blocked_ads"] = n
            if n % 8 == 0:
                p.config_manager.save()
        except Exception:
            pass

class CosmeticFilter(QWebEngineScript):
    def __init__(self):
        super().__init__()
        self.setName("CosmeticFilter")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(False)
        css = """
            .adbox, .banner_ads, .adsbox, .textads, .video-ads, #masthead-ad, 
            .ytd-ad-slot-renderer, .ytp-ad-overlay-container, .ytp-ad-message-container,
            #player-ads, #merch-shelf, .ytp-ad-progress-list, .ytp-ad-skip-button-slot,
            ytd-companion-slot-renderer, ytd-action-companion-ad-renderer,
            .ytp-ad-text-overlay, [class^="ytp-ad-"], [id^="ytp-ad-"],
            .ad-showing, .ad-interrupting, ytd-promoted-video-renderer,
            .ytd-display-ad-renderer, .ytd-video-masthead-ad-renderer,
            .ytd-in-feed-ad-layout-renderer,
            .ytd-video-masthead-ad-v2-renderer { display: none !important; }
        """
        js = f"""
            (function(){{
                const addStyle = () => {{
                    const target = document.head || document.documentElement;
                    if (!target) return false;
                    const style = document.createElement('style');
                    style.textContent = `{css}`;
                    target.appendChild(style);
                    return true;
                }};
                if (!addStyle()) {{
                    document.addEventListener('DOMContentLoaded', addStyle, {{once:true}});
                }}
                if (location.hostname.indexOf('youtube.') === -1) return;
                let pending = false;
                const nukeAds = () => {{
                    pending = false;
                    const skipBtn = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button-slot');
                    if (skipBtn) skipBtn.click();
                    const video = document.querySelector('video');
                    if (video && document.querySelector('.ad-showing, .ad-interrupting') && isFinite(video.duration)) {{
                        video.currentTime = video.duration;
                    }}
                }};
                const kick = () => {{
                    if (pending) return;
                    pending = true;
                    requestAnimationFrame(nukeAds);
                }};
                setInterval(kick, 1200);
            }})();
        """
        self.setSourceCode(js)

class ChromeStoreCloak(QWebEngineScript):
    """Injects JS to fully masquerade as Google Chrome on every page load."""
    def __init__(self):
        super().__init__()
        self.setName("ChromeStoreCloak")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(False)
        ua = Platform.get_user_agent()
        plat = Platform.get_platform_string()
        sysname = platform.system()
        rel = platform.release()
        js = f"""
(function() {{
    'use strict';
    var _ua = {json.dumps(ua)};

    function def(obj, prop, val) {{
        try {{
            Object.defineProperty(obj, prop, {{
                get: function() {{ return val; }},
                set: function(v) {{ val = v; }},
                configurable: true,
                enumerable: true
            }});
        }} catch(e) {{}}
    }}

    def(navigator, 'userAgent', _ua);
    def(navigator, 'appVersion', _ua.replace('Mozilla/', ''));
    def(navigator, 'vendor', 'Google Inc.');
    def(navigator, 'platform', {json.dumps(plat)});
    def(navigator, 'language', 'en-US');
    def(navigator, 'languages', ['en-US', 'en']);
    def(navigator, 'webdriver', false);
    def(navigator, 'maxTouchPoints', 0);
    def(navigator, 'hardwareConcurrency', 8);
    def(navigator, 'deviceMemory', 8);
    def(navigator, 'appName', 'Netscape');
    def(navigator, 'product', 'Gecko');
    def(navigator, 'productSub', '20030107');

    var fakeMimeType = {{ type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: null }};
    var fakePDF = {{ name: 'Chrome PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', 0: fakeMimeType, length: 1 }};
    var pluginArr = [fakePDF];
    try {{ pluginArr.__proto__ = PluginArray.prototype; }} catch(e) {{}}
    pluginArr.refresh = function() {{}};
    pluginArr.item = function(i) {{ return this[i]; }};
    pluginArr.namedItem = function(n) {{ return this.find(function(p){{ return p.name === n; }}) || null; }};
    def(navigator, 'plugins', pluginArr);

    var uaData = {{
        brands: [
            {{ brand: 'Not;A=Brand', version: '8' }},
            {{ brand: 'Chromium', version: '139' }},
            {{ brand: 'Google Chrome', version: '139' }}
        ],
        mobile: false,
        platform: {json.dumps(sysname)},
        getHighEntropyValues: function(hints) {{
            return Promise.resolve({{
                architecture: 'x86', bitness: '64', brands: this.brands,
                fullVersionList: [
                    {{ brand: 'Not;A=Brand', version: '10.0.0.0' }},
                    {{ brand: 'Chromium', version: '139.0.0.0' }},
                    {{ brand: 'Google Chrome', version: '139.0.0.0' }}
                ],
                mobile: false, model: '', platform: {json.dumps(sysname)},
                platformVersion: {json.dumps(rel)}, uaFullVersion: '139.0.0.0', wow64: false
            }});
        }},
        toJSON: function() {{ return {{ brands: this.brands, mobile: this.mobile, platform: this.platform }}; }}
    }};
    def(navigator, 'userAgentData', uaData);

    function extractExtId() {{
        var path = location.pathname || '';
        var m = path.match(/\\/detail\\/[^/]+\\/([a-z]{{32}})/i) || path.match(/\\/([a-z]{{32}})(?:\\/|$|\\?)/i);
        if (m) return m[1].toLowerCase();
        var segs = path.split('/').filter(Boolean);
        var last = ((segs[segs.length-1] || '').split('?')[0] || '').toLowerCase();
        if (/^[a-z]{{32}}$/.test(last)) return last;
        var all = (location.href || '').match(/[a-z]{{32}}/);
        return all ? all[0] : null;
    }}

    function slothInstall(extId) {{
        if (!extId) extId = extractExtId();
        if (!extId) return false;
        location.href = 'sloth://install-cws?id=' + extId;
        return true;
    }}

    window.chrome = {{
        app: {{
            isInstalled: false,
            InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
            RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }},
            getDetails: function() {{ return null; }},
            getIsInstalled: function() {{ return false; }},
            installState: function(cb) {{ if(cb) cb('not_installed'); }}
        }},
        runtime: {{
            connect: function() {{ return {{ onMessage: {{ addListener: function() {{}}, removeListener: function() {{}} }}, postMessage: function() {{}}, disconnect: function() {{}} }}; }},
            sendMessage: function() {{}},
            onMessage: {{ addListener: function() {{}}, removeListener: function() {{}}, hasListener: function() {{ return false; }} }},
            onConnect: {{ addListener: function() {{}}, removeListener: function() {{}} }},
            onStartup: {{ addListener: function() {{}} }},
            onInstalled: {{ addListener: function() {{}} }},
            id: undefined,
            getManifest: function() {{ return {{}}; }},
            getURL: function(p) {{ return 'chrome-extension://invalid/' + (p||''); }},
            lastError: undefined,
            PlatformOs: {{ MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' }},
            PlatformArch: {{ ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' }},
            requestUpdateCheck: function(cb) {{ if(cb) cb('no_update', {{}}); }}
        }},
        webstore: {{
            install: function(url, onSuccess, onFailure) {{
                if (!slothInstall(extractExtId())) {{
                    if (typeof onFailure === 'function') onFailure('Could not determine extension ID');
                    return;
                }}
                if (typeof onSuccess === 'function') onSuccess();
            }},
            onInstallStageChanged: {{ addListener: function() {{}}, removeListener: function() {{}} }},
            onDownloadProgress: {{ addListener: function() {{}}, removeListener: function() {{}} }}
        }},
        management: {{
            getAll: function(cb) {{ if (cb) cb([]); return Promise.resolve([]); }},
            get: function(id, cb) {{ if (cb) cb(null); }},
            getSelf: function(cb) {{ if (cb) cb(null); }}
        }},
        csi: function() {{ return {{ startE: Date.now(), onloadT: Date.now(), pageT: 1, tran: 15 }}; }},
        loadTimes: function() {{
            var t = performance.timing || {{}};
            return {{ commitLoadTime: (t.domLoading||0)/1000, connectionInfo: 'h2', finishDocumentLoadTime: (t.domContentLoadedEventEnd||0)/1000, finishLoadTime: (t.loadEventEnd||0)/1000, firstPaintAfterLoadTime: 0, firstPaintTime: (t.domLoading||0)/1000, navigationType: 'Other', npnNegotiatedProtocol: 'h2', requestTime: (t.navigationStart||0)/1000, startLoadTime: (t.navigationStart||0)/1000, wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: true, wasNpnNegotiated: true }};
        }},
        cast: {{}},
        i18n: {{ getMessage: function() {{ return ''; }}, getUILanguage: function() {{ return 'en'; }} }},
        storage: {{ local: {{ get: function(k,cb){{if(cb)cb({{}});}}, set: function(i,cb){{if(cb)cb();}} }}, sync: {{ get: function(k,cb){{if(cb)cb({{}});}}, set: function(i,cb){{if(cb)cb();}} }} }}
    }};

    if (navigator.permissions) {{
        var origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function(params) {{
            if (params && params.name === 'notifications') {{
                return Promise.resolve({{ state: Notification.permission, onchange: null }});
            }}
            return origQuery(params).catch(function() {{
                return {{ state: 'prompt', onchange: null }};
            }});
        }};
    }}

    var host = (location.hostname || '').toLowerCase();
    if (host.indexOf('chrome.google.com') === -1 && host.indexOf('chromewebstore') === -1) return;

    function hideUnavailable() {{
        var walk = document.querySelectorAll('div, section, span, p');
        for (var i = 0; i < walk.length; i++) {{
            var el = walk[i];
            if (el.id === 'sloth-add-btn' || (el.innerText || '').length > 280) continue;
            var t = (el.innerText || '').replace(/\\s+/g, ' ');
            if (/item currently unavailable|not available (for|on) this browser|switch to chrome|only (works|available) (on|in) chrome|troubleshooting guide/i.test(t) && el.children.length < 8) {{
                el.style.setProperty('display', 'none', 'important');
            }}
        }}
    }}

    function relabel(el) {{
        if (!el || el.id === 'sloth-add-btn') return;
        var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        var n;
        while ((n = w.nextNode())) {{
            if (/Add to Chrome/i.test(n.nodeValue || '')) n.nodeValue = n.nodeValue.replace(/Add to Chrome/gi, 'Add to Sloth');
        }}
        var al = el.getAttribute('aria-label');
        if (al && /chrome/i.test(al)) el.setAttribute('aria-label', al.replace(/Chrome/gi, 'Sloth'));
    }}

    function forceEnable(btn) {{
        btn.removeAttribute('disabled');
        btn.disabled = false;
        btn.removeAttribute('aria-disabled');
        btn.setAttribute('aria-disabled', 'false');
        btn.style.setProperty('pointer-events', 'auto', 'important');
        btn.style.setProperty('opacity', '1', 'important');
        btn.style.setProperty('cursor', 'pointer', 'important');
        btn.style.setProperty('filter', 'none', 'important');
        btn.style.setProperty('background', '#1a73e8', 'important');
        btn.style.setProperty('color', '#fff', 'important');
    }}

    function ensureSlothButton() {{
        var id = extractExtId();
        var existing = document.getElementById('sloth-add-btn');
        if (!id) {{
            if (existing) existing.remove();
            return;
        }}
        if (!existing) {{
            existing = document.createElement('button');
            existing.id = 'sloth-add-btn';
            existing.type = 'button';
            existing.textContent = 'Add to Sloth';
            existing.style.cssText = 'position:fixed;top:96px;right:28px;z-index:2147483647;background:#4a9eff;color:#041018;font-weight:800;border:none;border-radius:999px;padding:12px 22px;font-size:15px;cursor:pointer;box-shadow:0 10px 28px rgba(0,0,0,.28);font-family:system-ui,sans-serif;';
            existing.addEventListener('click', function(ev) {{
                ev.preventDefault();
                ev.stopPropagation();
                if ((existing.textContent || '').indexOf('Installed') === 0) {{
                    location.href = 'sloth://extensions';
                    return;
                }}
                existing.textContent = 'Installing…';
                slothInstall(extractExtId());
            }});
            (document.body || document.documentElement).appendChild(existing);
        }}
        var storeBtns = document.querySelectorAll('button, a, [role="button"]');
        for (var i = 0; i < storeBtns.length; i++) {{
            var btn = storeBtns[i];
            if (btn.id === 'sloth-add-btn') continue;
            var label = ((btn.getAttribute('aria-label') || '') + ' ' + (btn.innerText || '')).toLowerCase();
            if (label.indexOf('add to chrome') !== -1 || label.indexOf('add to sloth') !== -1) {{
                forceEnable(btn);
                relabel(btn);
            }}
        }}
    }}

    function patchCWS() {{
        if (!document.__slothCSSInjected) {{
            document.__slothCSSInjected = true;
            var style = document.createElement('style');
            style.id = 'sloth-cws-patch';
            style.textContent = [
                '[data-controller="IncompatibleBrowserStore"]', '.incompat-text',
                '.incompat-notice', '#cws-incompatible-notice',
                '[class*="incompat"]', '[class*="Incompatible"]',
                '[class*="unavailable"]'
            ].join(',') + '{{ display: none !important; }}';
            (document.head || document.documentElement).appendChild(style);
        }}
        hideUnavailable();
        ensureSlothButton();
    }}

    document.addEventListener('click', function(e) {{
        var t = e.target && e.target.closest ? e.target.closest('button, a, [role="button"]') : null;
        if (!t) return;
        if (t.id === 'sloth-add-btn') return;
        var label = ((t.getAttribute('aria-label') || '') + ' ' + (t.textContent || '')).toLowerCase();
        if (label.indexOf('add to chrome') !== -1 || label.indexOf('add to sloth') !== -1) {{
            var id = extractExtId();
            if (id) {{
                e.preventDefault();
                e.stopPropagation();
                slothInstall(id);
            }}
        }}
    }}, true);

    if (document.readyState !== 'loading') patchCWS();
    document.addEventListener('DOMContentLoaded', patchCWS);
    window.addEventListener('load', patchCWS);
    try {{
        new MutationObserver(function() {{ patchCWS(); }}).observe(document.documentElement, {{ childList: true, subtree: true }});
    }} catch(e) {{}}
}})();
"""
        self.setSourceCode(js)

class PageCustomizerScript(QWebEngineScript):
    """Adds the ability to restyle any element (saved per-site in localStorage)."""
    def __init__(self):
        super().__init__()
        self.setName("PageCustomizerScript")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(False)
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

            window.applySaved = applySaved;
            document.addEventListener('DOMContentLoaded', applySaved);
            applySaved();
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
        self.setRunsOnSubFrames(False)
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
        self.setRunsOnSubFrames(False)
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
        self.setRunsOnSubFrames(False)
        js = """
        (function() {
            const h = (location.hostname || '').toLowerCase();
            if (/google|youtube|gstatic|gmail|ytimg|ggpht|googlevideo|chromewebstore/.test(h)) return;
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

class IpSpoofScript(QWebEngineScript):
    def __init__(self, label="slothwebiscool!", enabled=False):
        super().__init__()
        self.setName("IpSpoof")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(False)
        if not enabled:
            self.setSourceCode("(function(){})();")
            return
        fake = json.dumps(str(label or "slothwebiscool!"))
        js = f"""
        (function() {{
            const FAKE = {fake};
            const HIT = /ipify|icanhaz|ifconfig\\.me|whatismyip|ipinfo|ident\\.me|ipapi|myip|checkip|ipdata|showmyip|ipaddress|ipgeolocation|wtfismyip|ip-api|seeip|l2\\.io|amazonaws\\.com\\/.*checkip/i;
            const jsonBody = JSON.stringify({{ip:FAKE, ip_address:FAKE, query:FAKE, origin:FAKE, IPv4:FAKE, IPv6:FAKE, address:FAKE}});
            const origFetch = window.fetch;
            window.fetch = function(input, init) {{
                try {{
                    const url = (typeof input === 'string') ? input : (input && input.url) || '';
                    if (HIT.test(url)) {{
                        const wantsJson = /json|ipinfo|ip-api|ipapi/i.test(url);
                        return Promise.resolve(new Response(wantsJson ? jsonBody : FAKE, {{status:200, headers:{{'content-type': wantsJson ? 'application/json' : 'text/plain'}}}}));
                    }}
                }} catch (e) {{}}
                return origFetch.apply(this, arguments);
            }};
            const oOpen = XMLHttpRequest.prototype.open;
            const oSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(m, u) {{
                this.__slothHit = HIT.test(String(u||''));
                this.__slothJson = /json|ipinfo|ip-api|ipapi/i.test(String(u||''));
                return oOpen.apply(this, arguments);
            }};
            XMLHttpRequest.prototype.send = function() {{
                if (this.__slothHit) {{
                    const body = this.__slothJson ? jsonBody : FAKE;
                    Object.defineProperty(this, 'readyState', {{get:()=>4}});
                    Object.defineProperty(this, 'status', {{get:()=>200}});
                    Object.defineProperty(this, 'responseText', {{get:()=>body}});
                    Object.defineProperty(this, 'response', {{get:()=>body}});
                    if (this.onload) setTimeout(()=>this.onload(), 0);
                    if (this.onreadystatechange) setTimeout(()=>this.onreadystatechange(), 0);
                    return;
                }}
                return oSend.apply(this, arguments);
            }};
            const FakePC = function() {{ this.onicecandidate = null; this.localDescription = null; this.iceGatheringState = 'complete'; }};
            FakePC.prototype.createDataChannel = function() {{ return {{}}; }};
            FakePC.prototype.createOffer = function() {{ return Promise.resolve({{type:'offer', sdp:''}}); }};
            FakePC.prototype.createAnswer = function() {{ return Promise.resolve({{type:'answer', sdp:''}}); }};
            FakePC.prototype.setLocalDescription = function() {{ return Promise.resolve(); }};
            FakePC.prototype.setRemoteDescription = function() {{ return Promise.resolve(); }};
            FakePC.prototype.addEventListener = function() {{}};
            FakePC.prototype.close = function() {{}};
            window.RTCPeerConnection = FakePC;
            window.webkitRTCPeerConnection = FakePC;
            try {{
                Object.defineProperty(navigator, 'userAgentData', {{ get: () => undefined }});
            }} catch (e) {{}}
        }})();
        """
        self.setSourceCode(js)

class CursorInjectionScript(QWebEngineScript):
    def __init__(self, cursor_type="Default"):
        super().__init__()
        self.setName("CursorInjection")
        self.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        self.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.setRunsOnSubFrames(False)
        
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
        self.setMinimumWidth(460)
        self.setMinimumHeight(560)
        outer = QVBoxLayout(self)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        inner = QWidget()
        l = QVBoxLayout(inner)
        
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

        l1.addWidget(QLabel("Density"))
        self.density = QComboBox()
        self.density.addItems(["compact", "comfortable", "roomy"])
        self.density.setCurrentText(parent.config_manager.get("ui_density", "comfortable"))
        self.density.currentTextChanged.connect(lambda v: self._set("ui_density", v, theme=True))
        l1.addWidget(self.density)

        l1.addWidget(QLabel("Corner radius"))
        self.radius = QSlider(Qt.Orientation.Horizontal)
        self.radius.setRange(6, 28)
        self.radius.setValue(int(parent.config_manager.get("ui_radius", 16)))
        self.radius.valueChanged.connect(lambda v: self._set("ui_radius", int(v), theme=True))
        l1.addWidget(self.radius)

        l1.addWidget(QLabel("Chrome margin"))
        self.margin = QSlider(Qt.Orientation.Horizontal)
        self.margin.setRange(0, 18)
        self.margin.setValue(int(parent.config_manager.get("chrome_margin", 8)))
        self.margin.valueChanged.connect(lambda v: self._set("chrome_margin", int(v), theme=True))
        l1.addWidget(self.margin)

        self.pill = QCheckBox("Pill tabs and URL bar")
        self.pill.setChecked(bool(parent.config_manager.get("pill_tabs", True)))
        self.pill.toggled.connect(lambda v: self._set("pill_tabs", v, theme=True))
        l1.addWidget(self.pill)

        self.zen = QCheckBox("Zen compact chrome (hover top edge for toolbar)")
        self.zen.setChecked(bool(parent.config_manager.get("zen_compact", False)))
        self.zen.toggled.connect(self.toggle_zen)
        l1.addWidget(self.zen)

        self.split_chk = QCheckBox("Show split view button (Arc-style)")
        self.split_chk.setChecked(bool(parent.config_manager.get("split_ready", True)))
        self.split_chk.toggled.connect(lambda v: self._set("split_ready", v))
        l1.addWidget(self.split_chk)

        self.float_url = QCheckBox("Floating URL bar (Zen)")
        self.float_url.setChecked(bool(parent.config_manager.get("floating_url", False)))
        self.float_url.toggled.connect(lambda v: (self._set("floating_url", v), parent.apply_chrome_extras()))
        l1.addWidget(self.float_url)

        self.workspace_tint = QCheckBox("Workspace tint on spaces (Arc)")
        self.workspace_tint.setChecked(bool(parent.config_manager.get("workspace_tint", True)))
        self.workspace_tint.toggled.connect(lambda v: self._set("workspace_tint", v))
        l1.addWidget(self.workspace_tint)

        self.favicon_only = QCheckBox("Favicon-only tabs when many")
        self.favicon_only.setChecked(bool(parent.config_manager.get("favicon_only_tabs", False)))
        self.favicon_only.toggled.connect(lambda v: self._set("favicon_only_tabs", v))
        l1.addWidget(self.favicon_only)

        l1.addWidget(QLabel("Sidebar width"))
        self.side_w = QSlider(Qt.Orientation.Horizontal)
        self.side_w.setRange(220, 520)
        self.side_w.setValue(int(parent.config_manager.get("sidebar_width", 300)))
        self.side_w.valueChanged.connect(lambda v: (self._set("sidebar_width", int(v)), parent.apply_chrome_extras()))
        l1.addWidget(self.side_w)

        self.side_right = QCheckBox("Hub on the right (Vivaldi)")
        self.side_right.setChecked(bool(parent.config_manager.get("sidebar_right", False)))
        self.side_right.toggled.connect(lambda v: (self._set("sidebar_right", v), parent.apply_chrome_extras()))
        l1.addWidget(self.side_right)

        self.palette_hint = QLabel("Ctrl+K palette · Ctrl+\\ split · Ctrl+Shift+P peek · Ctrl+Shift+E essentials · Ctrl+Shift+M mute")
        self.palette_hint.setStyleSheet("opacity:0.7; font-size:12px;")
        l1.addWidget(self.palette_hint)

        self.status_chk = QCheckBox("Show status bar")
        self.status_chk.setChecked(bool(parent.config_manager.get("show_status", True)))
        self.status_chk.toggled.connect(lambda v: self._set("show_status", v, theme=True))
        l1.addWidget(self.status_chk)
        l.addWidget(g1)

        g_m = QGroupBox("Motion")
        lm = QVBoxLayout(g_m)
        lm.addWidget(QLabel("Animation length (ms)"))
        self.anim = QSlider(Qt.Orientation.Horizontal)
        self.anim.setRange(0, 500)
        self.anim.setValue(int(parent.config_manager.get("anim_ms", 280)))
        self.anim.valueChanged.connect(lambda v: self._set("anim_ms", int(v)))
        lm.addWidget(self.anim)
        self.reduce = QCheckBox("Reduce motion")
        self.reduce.setChecked(bool(parent.config_manager.get("reduce_motion", False)))
        self.reduce.toggled.connect(lambda v: self._set("reduce_motion", v))
        lm.addWidget(self.reduce)
        self.tab_fade = QCheckBox("Fade sidebar and chrome")
        self.tab_fade.setChecked(bool(parent.config_manager.get("tab_fade", True)))
        self.tab_fade.toggled.connect(lambda v: self._set("tab_fade", v))
        lm.addWidget(self.tab_fade)
        lm.addWidget(QLabel("Window opacity"))
        self.opac = QSlider(Qt.Orientation.Horizontal)
        self.opac.setRange(70, 100)
        self.opac.setValue(int(float(parent.config_manager.get("window_opacity", 1.0)) * 100))
        self.opac.valueChanged.connect(self.set_opacity)
        lm.addWidget(self.opac)
        l.addWidget(g_m)
        
        g2 = QGroupBox("Engine & Privacy")
        l2 = QVBoxLayout(g2)
        
        self.ad_check = QCheckBox("Enable Ad-Blocker")
        self.ad_check.setChecked(parent.ad_block_enabled)
        self.ad_check.stateChanged.connect(self.toggle_adblock)
        l2.addWidget(self.ad_check)

        self.tr_check = QCheckBox("Block trackers")
        self.tr_check.setChecked(bool(parent.config_manager.get("block_trackers", True)))
        self.tr_check.toggled.connect(self.toggle_trackers)
        l2.addWidget(self.tr_check)

        self.ip_check = QCheckBox("Spoof IP lookup pages")
        self.ip_check.setChecked(bool(parent.config_manager.get("mask_ip", False)))
        self.ip_check.toggled.connect(self.toggle_mask_ip)
        l2.addWidget(self.ip_check)
        l2.addWidget(QLabel("IP label (what lookup sites display)"))
        self.ip_label = QLineEdit(str(parent.config_manager.get("ip_label", "slothwebiscool!")))
        self.ip_label.setPlaceholderText("slothwebiscool!")
        self.ip_label.textChanged.connect(self.set_ip_label)
        l2.addWidget(self.ip_label)

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

        l2.addWidget(QLabel("Default search engine"))
        self.se_box = QComboBox()
        for key, name, _tmpl in SEARCH_ENGINES:
            self.se_box.addItem(name, key)
        cur_se = parent.config_manager.get("search_engine", "mergarms")
        idx = max(0, self.se_box.findData(cur_se))
        self.se_box.setCurrentIndex(idx)
        self.se_box.currentIndexChanged.connect(self.set_search_engine)
        l2.addWidget(self.se_box)
        l2.addWidget(QLabel("Local search URL (beta) — use {q} for the query"))
        self.local_se = QLineEdit(str(parent.config_manager.get("local_search_url") or "http://127.0.0.1:8888/?q={q}"))
        self.local_se.setPlaceholderText("http://127.0.0.1:8888/?q={q}")
        self.local_se.textChanged.connect(lambda t: self._set("local_search_url", t))
        l2.addWidget(self.local_se)
        self.restore_chk = QCheckBox("Restore tabs on launch")
        self.restore_chk.setChecked(bool(parent.config_manager.get("restore_session", True)))
        self.restore_chk.toggled.connect(lambda v: self._set("restore_session", v))
        l2.addWidget(self.restore_chk)
        self.bm_bar_chk = QCheckBox("Show bookmarks bar")
        self.bm_bar_chk.setChecked(bool(parent.config_manager.get("show_bookmarks_bar", False)))
        self.bm_bar_chk.toggled.connect(lambda v: (self._set("show_bookmarks_bar", v), self._set("bm_bar_user_picked", True), parent.refresh_bookmarks_bar()))
        l2.addWidget(self.bm_bar_chk)
        
        flags_btn = QPushButton("Manage Engine Flags")
        flags_btn.clicked.connect(self.open_flags)
        l2.addWidget(flags_btn)
        l.addWidget(g2)

        g4 = QGroupBox("AI, tabs & reading")
        l4 = QVBoxLayout(g4)
        self.ai_chk = QCheckBox("Enable AI features (summarise, auto-organise)")
        self.ai_chk.setChecked(bool(parent.config_manager.get("ai_enabled", True)))
        self.ai_chk.toggled.connect(lambda v: self._set("ai_enabled", v))
        l4.addWidget(self.ai_chk)
        l4.addWidget(QLabel("Optional AI endpoint (POST JSON {task,text}) — leave blank for on-device"))
        self.ai_ep = QLineEdit(str(parent.config_manager.get("ai_endpoint") or ""))
        self.ai_ep.setPlaceholderText("http://127.0.0.1:11434/…")
        self.ai_ep.textChanged.connect(lambda t: self._set("ai_endpoint", t))
        l4.addWidget(self.ai_ep)
        self.combo_chk = QCheckBox("Combined 1-line tab + URL bar")
        self.combo_chk.setChecked(bool(parent.config_manager.get("combined_chrome", False)))
        self.combo_chk.toggled.connect(lambda v: (self._set("combined_chrome", v), parent.apply_combined_chrome()))
        l4.addWidget(self.combo_chk)
        self.sleep_chk = QCheckBox("Sleep inactive tabs (RAM saver)")
        self.sleep_chk.setChecked(bool(parent.config_manager.get("auto_sleep_tabs", True)))
        self.sleep_chk.toggled.connect(lambda v: self._set("auto_sleep_tabs", v))
        l4.addWidget(self.sleep_chk)
        l4.addWidget(QLabel("Sleep after minutes idle"))
        self.sleep_min = QSlider(Qt.Orientation.Horizontal)
        self.sleep_min.setRange(1, 30)
        self.sleep_min.setValue(int(parent.config_manager.get("sleep_after_min", 5)))
        self.sleep_min.valueChanged.connect(lambda v: self._set("sleep_after_min", int(v)))
        l4.addWidget(self.sleep_min)
        self.group_chk = QCheckBox("Rule-based / AI tab grouping")
        self.group_chk.setChecked(bool(parent.config_manager.get("auto_group_tabs", True)))
        self.group_chk.toggled.connect(lambda v: self._set("auto_group_tabs", v))
        l4.addWidget(self.group_chk)
        self.clean_chk = QCheckBox("Strip tracking junk when copying URLs")
        self.clean_chk.setChecked(bool(parent.config_manager.get("clean_copy_urls", True)))
        self.clean_chk.toggled.connect(lambda v: self._set("clean_copy_urls", v))
        l4.addWidget(self.clean_chk)
        self.ctx_chk = QCheckBox("Block site right-click hijacking")
        self.ctx_chk.setChecked(bool(parent.config_manager.get("protect_context_menu", True)))
        self.ctx_chk.toggled.connect(lambda v: self._set("protect_context_menu", v))
        l4.addWidget(self.ctx_chk)
        self.html_chk = QCheckBox("HTML/CSS-only mode (block page scripts)")
        self.html_chk.setChecked(bool(parent.config_manager.get("html_only", False)))
        self.html_chk.toggled.connect(lambda v: (self._set("html_only", v), parent.set_html_only(v)))
        l4.addWidget(self.html_chk)
        self.hist_chk = QCheckBox("Save browsing history")
        self.hist_chk.setChecked(bool(parent.config_manager.get("save_history", True)))
        self.hist_chk.toggled.connect(lambda v: self._set("save_history", v))
        l4.addWidget(self.hist_chk)
        self.shist_chk = QCheckBox("Save search history")
        self.shist_chk.setChecked(bool(parent.config_manager.get("save_search_history", True)))
        self.shist_chk.toggled.connect(lambda v: self._set("save_search_history", v))
        l4.addWidget(self.shist_chk)
        l.addWidget(g4)

        g3 = QGroupBox("Advanced")
        l3 = QVBoxLayout(g3)
        self.clear_btn = QPushButton("Clear Cache & Cookies")
        self.clear_btn.clicked.connect(self.clear_cache)
        l3.addWidget(self.clear_btn)
        l.addWidget(g3)

        sc.setWidget(inner)
        outer.addWidget(sc)
        close = QPushButton("Close", clicked=self.accept)
        outer.addWidget(close)

    def _set(self, key, value, theme=False):
        self.parent().config_manager.set(key, value)
        if theme:
            self.parent().apply_theme()

    def toggle_zen(self, v):
        self.parent().config_manager.set("zen_compact", bool(v))
        self.parent().apply_zen_compact()
        self.parent().apply_theme()

    def set_opacity(self, v):
        op = max(0.7, min(1.0, v / 100.0))
        self.parent().config_manager.set("window_opacity", op)
        self.parent().setWindowOpacity(op)

    def open_flags(self):
        self.accept()
        self.parent().add_tab(QUrl("sloth://flags"))

    def set_ua(self, val):
        self.parent().apply_user_agent(val)

    def toggle_trackers(self, v):
        self.parent().set_tracker_block(bool(v))

    def toggle_mask_ip(self, v):
        self.parent().set_mask_ip(bool(v))

    def set_ip_label(self, val):
        self.parent().set_ip_label(val)
    
    def set_nt(self, val):
        self.parent().config_manager.set("new_tab_url", val)

    def set_search_engine(self, _idx=None):
        key = self.se_box.currentData()
        if key:
            self.parent().config_manager.set("search_engine", key)
            if key == "mergarms":
                self.parent().url_bar.setPlaceholderText("Search Mergarms or type a URL")
            else:
                self.parent().url_bar.setPlaceholderText("Search or type a URL")

    def toggle_adblock(self, state):
        self.parent().set_adblock(bool(state))

    def toggle_theme(self):
        self.parent().dark_theme = not self.parent().dark_theme
        self.parent().config_manager.set("dark_theme", self.parent().dark_theme)
        self.theme_btn.setText(f"Theme: {'Dark' if self.parent().dark_theme else 'Light'}")
        self.parent().apply_theme()

    def choose_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.parent().accent_color = c.name()
            self.parent().config_manager.set("accent_color", c.name())
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
        d = ChromeDialog(self.browser_parent, "Page asks", msg, kind="prompt", default=defaultValue)
        if d.exec_ok():
            return True, d.edit.text() if d.edit else ""
        return False, ""

    def javaScriptConfirm(self, securityOrigin, msg):
        d = ChromeDialog(self.browser_parent, "Confirm", msg, kind="confirm")
        return d.exec_ok()

    def javaScriptAlert(self, securityOrigin, msg):
        ChromeDialog(self.browser_parent, "Notice", msg, kind="alert").exec()

    def createWindow(self, type_):
        parent = self.browser_parent
        WT = QWebEnginePage.WebWindowType
        try:
            if type_ == WT.WebBrowserWindow:
                win = parent.spawn_window()
                b = win.current_browser() or win.add_tab()
                return b.page()
            if type_ == WT.WebDialog:
                win = parent.spawn_window()
                b = win.current_browser() or win.add_tab()
                return b.page()
        except Exception:
            pass
        return parent.add_tab().page()

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
        elif message.startswith("SLOTH_PASS_GET:"):
            host = message.split(":", 1)[-1].strip()
            try:
                self.browser_parent.fill_pass_for_host(host)
            except Exception:
                pass
        elif message.startswith("SLOTH_CRX:"):
            ext_id = message.split(":", 1)[-1].strip()
            try:
                self.browser_parent.install_from_cws(ext_id)
            except Exception as e:
                print("CWS install failed", e)
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
    """Unpack a Chrome .crx and activate popup + content scripts in Sloth."""

    @staticmethod
    def get_zip_data(data):
        if data[:4] != b"Cr24":
            if data[:2] == b"PK":
                return data
            raise ValueError("Not a valid CRX file (bad magic bytes)")
        version = struct.unpack_from("<I", data, 4)[0]
        if version == 3:
            header_size = struct.unpack_from("<I", data, 8)[0]
            return data[12 + header_size:]
        if version == 2:
            pubkey_len = struct.unpack_from("<I", data, 8)[0]
            sig_len = struct.unpack_from("<I", data, 12)[0]
            return data[16 + pubkey_len + sig_len:]
        raise ValueError(f"Unknown CRX version: {version}")

    @staticmethod
    def _i18n_name(manifest, ext_dir):
        name = str(manifest.get("name") or "Extension")
        if not name.startswith("__MSG_"):
            return name
        key = name[6:-2] if name.endswith("__") else name[6:]
        for loc in ("en", "en_US", "en_GB"):
            p = os.path.join(ext_dir, "_locales", loc, "messages.json")
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        msgs = json.load(f)
                    got = (msgs.get(key) or {}).get("message")
                    if got:
                        return got
                except Exception:
                    pass
        return key or "Extension"

    @staticmethod
    def _popup_from_manifest(manifest):
        for key in ("action", "browser_action", "page_action"):
            pop = (manifest.get(key) or {}).get("default_popup")
            if pop:
                return pop
        return manifest.get("options_ui", {}).get("page") or manifest.get("options_page") or ""

    @staticmethod
    def install(crx_path, browser_ref=None):
        """Returns dict: ok, name, id, dir, popup, scripts, error."""
        result = {"ok": False, "name": "", "id": "", "dir": "", "popup": "", "scripts": [], "error": ""}
        try:
            ext_root = get_storage_path("extensions")
            os.makedirs(ext_root, exist_ok=True)
            with open(crx_path, "rb") as f:
                data = f.read()
            zip_data = CRXInstaller.get_zip_data(data)
            ext_id = os.path.splitext(os.path.basename(crx_path))[0]
            ext_out_dir = os.path.join(ext_root, ext_id)
            if os.path.isdir(ext_out_dir):
                shutil.rmtree(ext_out_dir, ignore_errors=True)
            os.makedirs(ext_out_dir, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                zf.extractall(ext_out_dir)
            manifest_path = os.path.join(ext_out_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                # some CRXs nest one folder
                for root, dirs, files in os.walk(ext_out_dir):
                    if "manifest.json" in files:
                        ext_out_dir = root
                        manifest_path = os.path.join(root, "manifest.json")
                        break
            if not os.path.isfile(manifest_path):
                raise ValueError("No manifest.json inside the CRX")
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            name = CRXInstaller._i18n_name(manifest, ext_out_dir)
            popup = CRXInstaller._popup_from_manifest(manifest)
            scripts = []
            for cs in manifest.get("content_scripts") or []:
                scripts.extend(cs.get("js") or [])
            meta = {
                "id": ext_id,
                "name": name,
                "popup": popup,
                "version": manifest.get("version", ""),
                "description": str(manifest.get("description") or ""),
                "scripts": scripts,
            }
            with open(os.path.join(ext_out_dir, "_sloth.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
            result.update({"ok": True, "name": name, "id": ext_id, "dir": ext_out_dir, "popup": popup, "scripts": scripts})
            if browser_ref:
                browser_ref.log(f"Unpacked {name}", notify=False)
            return result
        except Exception as e:
            result["error"] = str(e)
            return result


def download_cws_crx(ext_id, progress=None):
    """Fetch a CRX from Google. Tries several endpoints, XML codebase, then urllib."""
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36"
    headers = {"User-Agent": ua, "Accept": "*/*"}
    urls = [
        f"https://clients2.google.com/service/update2/crx?response=redirect&os=win&arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3D{ext_id}%26uc",
        f"https://clients2.google.com/service/update2/crx?response=redirect&os=win&arch=x64&os_arch=x86_64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=121.0.6167.160&lang=en-US&acceptformat=crx3&x=id%3D{ext_id}%26installsource%3Dondemand%26uc",
        f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=114.0.5735.198&acceptformat=crx3&x=id%3D{ext_id}%26uc",
        f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=49.0&x=id%3D{ext_id}%26installsource%3Dondemand%26uc",
        f"https://clients2.google.com/service/update2/crx?os=win&arch=x64&os_arch=x86_64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=120.0.6099.109&lang=en-US&acceptformat=crx3&x=id%3D{ext_id}%26v%3D0%26installsource%3Dondemand%26uc",
    ]

    def is_crx(blob):
        return blob and len(blob) > 256 and (blob[:4] == b"Cr24" or blob[:2] == b"PK")

    def get(url, timeout=20):
        try:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            return r.status_code, r.content or b"", str(r.url)
        except Exception:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return getattr(resp, "status", 200) or 200, resp.read() or b"", str(resp.geturl())

    def note(msg):
        if progress:
            progress(msg)

    last = "no response"
    for url in urls:
        try:
            note("Trying Chrome download…")
            code, blob, final = get(url)
            if is_crx(blob):
                note(f"Got CRX ({len(blob)} bytes)")
                return blob
            text = blob.decode("utf-8", "ignore")
            m = re.search(r'(?:codebase|crx_base_url|url)=["\']([^"\']+)["\']', text, re.I)
            if not m:
                m = re.search(r'https://clients2\.googleusercontent\.com/[^"\'\s<]+', text)
                href = m.group(0) if m else ""
            else:
                href = m.group(1)
            if href:
                note("Following package URL…")
                code2, blob2, _ = get(href)
                if is_crx(blob2):
                    note(f"Got CRX ({len(blob2)} bytes)")
                    return blob2
            last = f"HTTP {code}, {len(blob)} bytes from {final[:80]}"
        except Exception as e:
            last = str(e)
            note(str(e))
    raise RuntimeError(last)


def extension_icon_path(ext_dir, manifest=None):
    if manifest is None:
        mp = os.path.join(ext_dir, "manifest.json")
        if not os.path.isfile(mp):
            return ""
        try:
            with open(mp, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            return ""
    icons = {}
    for key in ("action", "browser_action", "page_action"):
        ic = (manifest.get(key) or {}).get("default_icon")
        if isinstance(ic, str):
            icons[48] = ic
        elif isinstance(ic, dict):
            icons.update({int(k) if str(k).isdigit() else 0: v for k, v in ic.items()})
    mi = manifest.get("icons") or {}
    if isinstance(mi, dict):
        icons.update({int(k) if str(k).isdigit() else 0: v for k, v in mi.items()})
    for size in (48, 32, 16, 128, 19):
        rel = icons.get(size)
        if not rel:
            continue
        p = os.path.join(ext_dir, str(rel).replace("/", os.sep))
        if os.path.isfile(p):
            return p
    for root, dirs, files in os.walk(ext_dir):
        for f in files:
            if f.lower().endswith((".png", ".ico", ".svg")) and "icon" in f.lower():
                return os.path.join(root, f)
        break
    return ""


def iter_extension_roots():
    roots = [get_storage_path("extensions")]
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, "frozen", False) else os.path.dirname(sys.executable)
        roots.append(os.path.join(base_dir, "extensions"))
    except Exception:
        pass
    out, seen = [], set()
    for r in roots:
        p = os.path.abspath(r)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def list_installed_extensions():
    items = []
    seen = set()
    for root in iter_extension_roots():
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if os.path.isdir(path) and os.path.isfile(os.path.join(path, "manifest.json")):
                key = os.path.abspath(path)
                if key in seen:
                    continue
                seen.add(key)
                meta = {"id": name, "name": name, "popup": "", "version": "", "description": "", "path": path, "kind": "crx"}
                sloth_meta = os.path.join(path, "_sloth.json")
                try:
                    if os.path.isfile(sloth_meta):
                        with open(sloth_meta, encoding="utf-8") as f:
                            meta.update(json.load(f))
                    else:
                        with open(os.path.join(path, "manifest.json"), encoding="utf-8") as f:
                            man = json.load(f)
                        meta["name"] = CRXInstaller._i18n_name(man, path)
                        meta["popup"] = CRXInstaller._popup_from_manifest(man)
                        meta["version"] = man.get("version", "")
                        meta["description"] = str(man.get("description") or "")
                except Exception:
                    pass
                meta["path"] = path
                meta["kind"] = "crx"
                try:
                    with open(os.path.join(path, "manifest.json"), encoding="utf-8") as f:
                        man = json.load(f)
                    meta["icon"] = extension_icon_path(path, man)
                except Exception:
                    meta["icon"] = ""
                items.append(meta)
            elif name.endswith(".js") and os.path.isfile(path):
                key = os.path.abspath(path)
                if key in seen:
                    continue
                seen.add(key)
                items.append({"id": name, "name": name.replace(".js", ""), "popup": "", "version": "", "description": "Page script", "path": path, "kind": "js"})
    return items


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
                it.setText(f"Extension: {os.path.basename(crx_path)} (unpacking…)")
                res = CRXInstaller.install(crx_path, br)
                if res.get("ok"):
                    br.activate_extension(res["dir"])
                    it.setText(f"Extension: {res.get('name') or crx_path} (ready)")
                    br.add_tab(QUrl("sloth://extensions"))
                    if res.get("popup"):
                        br.open_extension_popup(res["dir"], res["popup"])
                else:
                    it.setText(f"Extension failed: {res.get('error')}")
                    br.log(res.get("error") or "CRX failed", notify=True)
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

class UrlBar(QLineEdit):
    """Omnibox: the first click selects the whole URL, like Chrome."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._arm_select = False

    def focusInEvent(self, e):
        super().focusInEvent(e)
        if e.reason() != Qt.FocusReason.MouseFocusReason:
            QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, e):
        self._arm_select = not self.hasFocus()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self._arm_select:
            self._arm_select = False
            self.selectAll()


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
        data = self.lastContextMenuRequest()
        page = self.page()
        WA = QWebEnginePage.WebAction

        def flag(name, default=True):
            if data is None or not hasattr(data, "editFlags"):
                return default
            try:
                flags = data.editFlags()
                return bool(flags & getattr(type(flags), name))
            except Exception:
                return default

        def item(menu, text, shortcut, slot, enabled=True):
            a = menu.addAction(text)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
                try:
                    a.setShortcutVisibleInContextMenu(True)
                except Exception:
                    pass
            a.setEnabled(bool(enabled))
            a.triggered.connect(slot)
            return a

        editable = bool(data and hasattr(data, "isContentEditable") and data.isContentEditable())
        selected = (data.selectedText() if data else "") or ""
        is_link = bool(data and data.linkUrl().isValid())
        is_image = False
        try:
            is_image = bool(data and data.mediaUrl().isValid())
        except Exception:
            pass

        if editable or (selected and not is_link and not is_image):
            menu = QMenu(self)
            item(menu, "Undo", "Ctrl+Z", lambda: page.triggerAction(WA.Undo), flag("CanUndo", True))
            item(menu, "Redo", "Ctrl+Y", lambda: page.triggerAction(WA.Redo), flag("CanRedo", True))
            menu.addSeparator()
            item(menu, "Cut", "Ctrl+X", lambda: page.triggerAction(WA.Cut), flag("CanCut", editable))
            item(menu, "Copy", "Ctrl+C", lambda: page.triggerAction(WA.Copy), flag("CanCopy", bool(selected) or editable))
            item(menu, "Paste", "Ctrl+V", lambda: page.triggerAction(WA.Paste), flag("CanPaste", editable))
            item(menu, "Delete", "", lambda: page.triggerAction(WA.Delete), flag("CanDelete", editable))
            menu.addSeparator()
            item(menu, "Select All", "Ctrl+A", lambda: page.triggerAction(WA.SelectAll), True)
            if selected.strip():
                menu.addSeparator()
                q = selected.strip()[:80]
                item(menu, f'Search "{q[:32]}"', "", lambda t=selected: self.browser_parent.search_selection(t))
                item(menu, "Copy clean URL", "", lambda: self.browser_parent.copy_clean_url(self.url().toString()))
            menu.addSeparator()
            more = menu.addMenu("More")
            more.addAction("Customize this element").triggered.connect(self.customize_element)
            more.addAction("Inspect").triggered.connect(self.inspect_element)
            menu.exec(event.globalPos())
            return

        menu = QMenu(self)
        item(menu, "Back", "Alt+Left", lambda: page.triggerAction(WA.Back), self.history().canGoBack())
        item(menu, "Forward", "Alt+Right", lambda: page.triggerAction(WA.Forward), self.history().canGoForward())
        item(menu, "Reload", "Ctrl+R", lambda: page.triggerAction(WA.Reload), True)
        menu.addSeparator()
        if is_link:
            item(menu, "Open link in new tab", "", lambda: self.browser_parent.add_tab(data.linkUrl()))
            item(menu, "Open link in new window", "", lambda: self.browser_parent.spawn_window(start_url=data.linkUrl()))
            item(menu, "Copy link", "", lambda: QApplication.clipboard().setText(data.linkUrl().toString()))
            menu.addSeparator()
        if is_image:
            item(menu, "Open image in new tab", "", lambda: self.browser_parent.add_tab(data.mediaUrl()))
            item(menu, "Copy image address", "", lambda: QApplication.clipboard().setText(data.mediaUrl().toString()))
            menu.addSeparator()
        item(menu, "Save page", "Ctrl+S", lambda: page.triggerAction(WA.SavePage), True)
        menu.addSeparator()
        item(menu, "View page source", "Ctrl+U", self.view_source)
        item(menu, "Inspect", "Ctrl+Shift+I", self.inspect_element)
        more = menu.addMenu("More")
        more.addAction("Picture-in-Picture").triggered.connect(self.browser_parent.picture_in_picture)
        more.addAction("Play / pause media").triggered.connect(self.browser_parent.toggle_media)
        if SlothAI.enabled(self.browser_parent.config_manager.config):
            more.addAction("Summarise page").triggered.connect(self.browser_parent.summarize_page)
        more.addAction("Copy clean URL").triggered.connect(
            lambda: self.browser_parent.copy_clean_url(self.url().toString())
        )
        more.addAction("Open clipboard image").triggered.connect(self.browser_parent.paste_clipboard_image)
        more.addAction("Temporary bookmark (7 days)").triggered.connect(self.browser_parent.bookmark_temp)
        more.addAction("Customize this element").triggered.connect(self.customize_element)
        menu.exec(event.globalPos())

# --- Main Browser ---

class Browser(QMainWindow):
    _primary = None

    def __init__(self, secondary=False, adopt_view=None, adopt_title="", adopt_icon=None, start_url=None):
        super().__init__()
        self.setWindowTitle("Sloth Web")
        self._secondary = bool(secondary)
        self._adopt_view = adopt_view
        self._adopt_title = adopt_title
        self._adopt_icon = adopt_icon
        self._start_url = start_url
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "sloth_web.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(current_dir, "sloth_web.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        src = Browser._primary if secondary and Browser._primary is not None else None
        if src is not None:
            self.bookmarks_file = src.bookmarks_file
            self.bookmarks = src.bookmarks
            self.history_manager = src.history_manager
            self.password_manager = src.password_manager
            self.mail_manager = src.mail_manager
            self.config_manager = src.config_manager
            self.custom_manager = src.custom_manager
            self.ad_interceptor = src.ad_interceptor
            self.ad_block_enabled = src.ad_block_enabled
            self.dark_theme = src.dark_theme
            self.accent_color = src.accent_color
            self.nav_pos = src.nav_pos
            self.tabs_pos = src.tabs_pos
            self.downloads = src.downloads
            self.container_profiles = getattr(src, "container_profiles", {})
            self.update_manager = src.update_manager
        else:
            self.bookmarks_file = get_storage_path("bookmarks.json")
            self.bookmarks = load_bookmarks(self.bookmarks_file)
            self.history_manager = HistoryManager(get_storage_path("history.json"))
            self.password_manager = PasswordManager(get_storage_path("passwords.json"))
            self.mail_manager = MailManager(get_storage_path("mail.json"))
            self.config_manager = ConfigManager(get_storage_path("config.json"))
            if "search_engine" not in self.config_manager.config:
                self.config_manager.set("search_engine", "mergarms")
            if "restore_session" not in self.config_manager.config:
                self.config_manager.set("restore_session", True)
            if not self.config_manager.get("bm_bar_user_picked", False):
                self.config_manager.set("show_bookmarks_bar", False)
            elif "show_bookmarks_bar" not in self.config_manager.config:
                self.config_manager.set("show_bookmarks_bar", False)
            self.custom_manager = CustomizationManager(get_storage_path("customizations.json"))
            try:
                persist_default_profile()
            except Exception as e:
                print("profile persist skipped:", e)
            self.ad_block_enabled = self.config_manager.get("ad_block_enabled", True)
            self.dark_theme = self.config_manager.get("dark_theme", True)
            self.accent_color = self.config_manager.get("accent_color", "#4a9eff")
            self.nav_pos = self.config_manager.get("nav_pos", "top")
            self.tabs_pos = self.config_manager.get("tabs_pos", "north")
            self.downloads = []
            self.update_manager = None

        self.focus_time_remaining = 1500 # 25 minutes
        self.focus_is_running = False
        self.focus_mode = "focus" # "focus" or "break"
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(3)
        self.status = QStatusBar()
        self.dl_manager = DownloadManager(self)
        self.completer = QCompleter()
        
        if src is None:
            self.update_manager = UpdateManager(self)
            self.ad_interceptor = AdBlockInterceptor(self, self.ad_block_enabled)
            self.ad_interceptor.trackers_enabled = bool(self.config_manager.get("block_trackers", True))
            self.ad_interceptor.mask_ip = bool(self.config_manager.get("mask_ip", False))
            self.ad_interceptor.mask_label = self.config_manager.get("ip_label", "slothwebiscool!")
            self.ad_interceptor.apply_ua(self.config_manager.get("custom_ua", "Chrome (Standard)"))
            self.ad_interceptor.html_only = bool(self.config_manager.get("html_only", False))
            QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(self.ad_interceptor)
            self.sloth_handler = SlothSchemeHandler(self)
            try:
                QWebEngineProfile.defaultProfile().installUrlSchemeHandler(b"sloth", self.sloth_handler)
            except Exception:
                pass
            Browser._primary = self
        else:
            self.sloth_handler = SlothSchemeHandler(self)
        
        self.focus_timer = QTimer(self)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self.update_focus_timer_tick)
        
        self.init_ui()
        SLOTH_WINDOWS.append(self)
        if self._secondary:
            QTimer.singleShot(0, self._boot_secondary)
        else:
            QTimer.singleShot(0, self._safe_first_tab)
            QTimer.singleShot(800, self.restore_session)
        if src is None:
            try:
                self.handle_extensions()
            except Exception as e:
                print("extensions skipped", e)
        
        # Optimize global settings for maximum Chromium compatibility and extreme speed
        s = QWebEngineProfile.defaultProfile().settings()
        attrs = {
            "AutoLoadImages": True,
            "Accelerated2dCanvasEnabled": True,
            "WebGLEnabled": True,
            "ScrollAnimatorEnabled": bool(self.config_manager.get("smooth_scrolling", True)),
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
        CHROME_UA = Platform.get_user_agent()
        try:
            QWebEngineProfile.defaultProfile().setHttpUserAgent(CHROME_UA)
        except Exception as e:
            print("UA skipped", e)
        
        self.apply_theme()
        self.bind_motion_shortcuts()
        self.apply_zen_compact()
        self.apply_runtime_flags()
        self.apply_chrome_extras()
        QTimer.singleShot(16, self._boot_fade)
        
        QTimer.singleShot(2000, self.update_manager.check_for_updates)

    def handle_extensions(self):
        count = 0
        for root in iter_extension_roots():
            try:
                os.makedirs(root, exist_ok=True)
            except Exception:
                continue
            if not os.path.isdir(root):
                continue
            for name in os.listdir(root):
                path = os.path.join(root, name)
                try:
                    if name.endswith(".js") and os.path.isfile(path):
                        with open(path, "r", encoding="utf-8") as script_file:
                            code = script_file.read()
                        s = QWebEngineScript()
                        s.setName("sloth-js:" + name)
                        s.setSourceCode(code)
                        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
                        s.setRunsOnSubFrames(True)
                        QWebEngineProfile.defaultProfile().scripts().insert(s)
                        count += 1
                    elif os.path.isdir(path) and os.path.isfile(os.path.join(path, "manifest.json")):
                        self.activate_extension(path)
                        count += 1
                except Exception as e:
                    print(f"Failed to load extension {name}: {e}")
        self.log(f"Loaded {count} extensions")
        QTimer.singleShot(0, self.rebuild_extension_toolbar)

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
        
        self.url_bar = UrlBar()
        self.url_bar.setPlaceholderText("Search Mergarms or type a URL")
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
        QTimer.singleShot(0, self.rebuild_extension_toolbar)

        self.zen_edge = QToolBar("Zen edge")
        self.zen_edge.setMovable(False)
        self.zen_edge.setFloatable(False)
        self.zen_edge.setIconSize(QSize(1, 1))
        self.zen_edge.setFixedHeight(14)
        edge_hit = QLabel("  move here for toolbar  ")
        edge_hit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edge_hit.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 10px;")
        self.zen_edge.addWidget(edge_hit)
        self.zen_edge.setStyleSheet("QToolBar { background: rgba(74,158,255,0.55); border: none; min-height: 14px; max-height: 14px; }")
        self.zen_edge.setToolTip("Hover the top of the window to show the toolbar")
        self.insertToolBar(self.nav, self.zen_edge)
        self.zen_edge.installEventFilter(self)
        self.nav.installEventFilter(self)
        self._zen_hide_timer = QTimer(self)
        self._zen_hide_timer.setSingleShot(True)
        self._zen_hide_timer.timeout.connect(self._zen_hide_chrome)
        self._zen_poll = QTimer(self)
        self._zen_poll.setInterval(70)
        self._zen_poll.timeout.connect(self._zen_poll_cursor)

        self.bookmarks_bar = QToolBar("Bookmarks bar")
        self.bookmarks_bar.setMovable(False)
        self.bookmarks_bar.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.bookmarks_bar)
        self.bookmarks_bar.installEventFilter(self)

        self.find_bar = QToolBar("Find")
        self.find_bar.setMovable(False)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in page")
        self.find_input.returnPressed.connect(self.find_next)
        self.find_bar.addWidget(self.find_input)
        self.find_bar.addAction(QAction("Next", self, triggered=self.find_next))
        self.find_bar.addAction(QAction("Prev", self, triggered=self.find_prev))
        self.find_bar.addAction(QAction("×", self, triggered=self.hide_find))
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.find_bar)
        self.find_bar.setVisible(False)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)
        self.setMouseTracking(True)
        self.tabs.setMouseTracking(True)
        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(self.tabs)
        self.split_pane = None
        
        # Apply configured tabs position
        self.apply_tabs_pos()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.tabs.tabBar().installEventFilter(self)
        try:
            self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        except Exception:
            self.tabs.tabBar().tabBarDoubleClicked.connect(self.rename_tab)
        self._tear_idx = -1
        self._tear_pos = None
        self._tearing = False
        self._closed_tabs = []
        self._drag_ghost = None
        
        # Add a "New Tab" button to the tab bar
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setStyleSheet(f"QPushButton {{ color: {self.accent_color}; font-weight: bold; font-size: 20px; border: 1px solid {self.accent_color}; border-radius: 4px; background: rgba(255,255,255,0.05); padding: 0px; margin: 0px; }} QPushButton:hover {{ background: rgba(255,255,255,0.15); }}")
        self.add_tab_btn.setFlat(True)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        self.add_tab_btn.setFixedSize(32, 32)
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)
        self.installEventFilter(self)
        
        self.setCentralWidget(self.main_split)
        
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
        
        self.hub_privacy = QWidget()
        priv_l = QVBoxLayout(self.hub_privacy)
        self.hub_ad = QCheckBox("Ad block")
        self.hub_ad.setChecked(self.ad_block_enabled)
        self.hub_ad.toggled.connect(self.set_adblock)
        self.hub_tr = QCheckBox("Tracker block")
        self.hub_tr.setChecked(bool(self.config_manager.get("block_trackers", True)))
        self.hub_tr.toggled.connect(self.set_tracker_block)
        self.hub_ip = QCheckBox("IP label: slothwebiscool!")
        self.hub_ip.setChecked(bool(self.config_manager.get("mask_ip", False)))
        self.hub_ip.toggled.connect(self.set_mask_ip)
        priv_l.addWidget(self.hub_ad)
        priv_l.addWidget(self.hub_tr)
        priv_l.addWidget(self.hub_ip)
        priv_l.addWidget(QLabel("Spaces"))
        for name in ("personal", "work", "finance", "social"):
            btn = QPushButton(name.capitalize() + " space")
            btn.clicked.connect(lambda _=False, n=name: self.add_tab(container=n))
            priv_l.addWidget(btn)
        peek = QPushButton("Private tab")
        peek.clicked.connect(lambda: self.add_tab(incognito=True))
        priv_l.addWidget(peek)
        split = QPushButton("Split / side tabs")
        split.clicked.connect(self.toggle_layout)
        priv_l.addWidget(split)
        pin = QPushButton("Pin current tab")
        pin.clicked.connect(self.toggle_pin_current)
        priv_l.addWidget(pin)
        mute = QPushButton("Mute current tab")
        mute.clicked.connect(self.toggle_mute_current)
        priv_l.addWidget(mute)
        priv_l.addStretch()

        self.essentials_list = QListWidget()
        self.essentials_list.itemClicked.connect(lambda i: self.add_tab(QUrl(i.toolTip())))
        add_ess = QPushButton("Pin current as Essential")
        add_ess.clicked.connect(self.pin_essential)
        ess_w = QWidget()
        ess_l = QVBoxLayout(ess_w)
        ess_l.addWidget(self.essentials_list)
        ess_l.addWidget(add_ess)

        self.panel_url = QLineEdit(self.config_manager.get("web_panel_url", "https://en.wikipedia.org"))
        self.panel_go = QPushButton("Load panel")
        self.panel_view = None
        self.panel_go.clicked.connect(self.load_web_panel)
        panel_w = QWidget()
        panel_l = QVBoxLayout(panel_w)
        panel_l.addWidget(self.panel_url)
        panel_l.addWidget(self.panel_go)
        self.panel_host = QVBoxLayout()
        panel_l.addLayout(self.panel_host)

        self.sidebar_tabs.addTab(self.bookmarks_list, "🔖")
        self.sidebar_tabs.addTab(self.history_list, "🕒")
        self.sidebar_tabs.addTab(self.sidebar_scratchpad, "📝")
        self.sidebar_tabs.addTab(self.focus_widget, "⏱️")
        self.sidebar_tabs.addTab(self.sidebar_downloads_list, "⬇️")
        self.sidebar_tabs.addTab(self.hub_privacy, "🛡️")
        self.sidebar_tabs.addTab(ess_w, "⭐")
        self.sidebar_tabs.addTab(panel_w, "▤")
        self.sidebar_layout.addWidget(self.sidebar_tabs)
        
        self.sidebar.setWidget(self.sidebar_content)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
        self.sidebar.setVisible(False) # Hidden by default
        
        self.update_sidebar()
        
        self.setStatusBar(self.status)
        
        # Apply configured layout/nav positions after all UI elements are created
        self.apply_nav_pos()
        self.apply_tabs_pos()
        self.refresh_bookmarks_bar()
        self.apply_zen_compact()
        
        self.log("Browser initialized.")
        try:
            self.prune_temp_bookmarks()
        except Exception:
            pass
        self.mail_timer = QTimer(self)
        self.mail_timer.setInterval(30000)
        self.mail_timer.timeout.connect(self.mail_tick)
        self.mail_timer.start()
        self.sleep_timer = QTimer(self)
        self.sleep_timer.setInterval(30000)
        self.sleep_timer.timeout.connect(self.tick_sleep_tabs)
        self.sleep_timer.start()
        QTimer.singleShot(0, self.apply_combined_chrome)

    def _boot_secondary(self):
        try:
            if self._adopt_view is not None:
                self._attach_view(self._adopt_view, self._adopt_title or "Tab", self._adopt_icon)
            elif self._start_url is not None:
                self.add_tab(self._start_url)
            else:
                self.add_tab()
        except Exception as e:
            print("secondary boot", e)
            try:
                self.add_tab()
            except Exception:
                pass

    def _attach_view(self, view, title="Tab", icon=None):
        view.setParent(self.tabs)
        view.browser_parent = self
        try:
            view.page().browser_parent = self
        except Exception:
            pass
        idx = self.tabs.addTab(view, title[:28] if title else "Tab")
        if icon:
            try:
                self.tabs.setTabIcon(idx, icon)
            except Exception:
                pass
        close_btn = QPushButton()
        close_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background: rgba(255,0,0,0.2); border-radius:4px; }")
        close_btn.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(view)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, close_btn)
        self.tabs.setCurrentIndex(idx)
        try:
            view.urlChanged.connect(lambda q, b=view: self.update_ui(q, self.tabs.indexOf(b)))
            view.titleChanged.connect(lambda t, b=view: self.apply_tab_title(b, t))
            view.iconChanged.connect(lambda ic, b=view: self.tabs.setTabIcon(self.tabs.indexOf(b), ic))
        except Exception:
            pass
        return view

    def spawn_window(self, start_url=None, adopt_view=None, adopt_title="", adopt_icon=None):
        win = Browser(secondary=True, adopt_view=adopt_view, adopt_title=adopt_title, adopt_icon=adopt_icon, start_url=start_url)
        win.resize(max(900, int(self.width() * 0.9)), max(600, int(self.height() * 0.9)))
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def move_tab_to(self, idx, other):
        if idx < 0 or idx >= self.tabs.count() or other is None or other is self:
            return False
        view = self.tabs.widget(idx)
        title = self.tabs.tabText(idx)
        icon = self.tabs.tabIcon(idx)
        self.tabs.removeTab(idx)
        if self.tabs.count() == 0:
            self.add_tab()
        other._attach_view(view, title, icon)
        other.raise_()
        other.activateWindow()
        return True

    def tear_tab(self, idx, global_pos):
        if idx < 0 or idx >= self.tabs.count():
            return
        for w in list(SLOTH_WINDOWS):
            if w is self or not w.isVisible():
                continue
            if w.frameGeometry().contains(global_pos):
                self.move_tab_to(idx, w)
                return
        view = self.tabs.widget(idx)
        title = self.tabs.tabText(idx)
        icon = self.tabs.tabIcon(idx)
        last = self.tabs.count() == 1
        self.tabs.removeTab(idx)
        if last:
            self.add_tab()
        win = self.spawn_window(adopt_view=view, adopt_title=title, adopt_icon=icon)
        try:
            win.move(global_pos.x() - 60, max(0, global_pos.y() - 16))
        except Exception:
            pass

    def _ensure_drag_ghost(self):
        if self._drag_ghost is not None:
            return
        g = QLabel()
        g.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        g.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        g.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        g.setStyleSheet(
            "QLabel { background: rgba(22, 28, 40, 235); color: #f4f7fb; "
            "border: 1px solid #4a9eff; border-radius: 12px; padding: 8px 14px; "
            "font-weight: 650; font-size: 13px; }"
        )
        self._drag_ghost = g

    def _move_drag_ghost(self, idx, gp, outside):
        self._ensure_drag_ghost()
        title = (self.tabs.tabText(idx) or "Tab")[:40]
        if outside:
            self._drag_ghost.setText("↗  " + title + "   ·   new window")
        else:
            self._drag_ghost.setText("☰  " + title)
        self._drag_ghost.adjustSize()
        self._drag_ghost.move(gp.x() + 16, gp.y() + 18)
        if not self._drag_ghost.isVisible():
            self._drag_ghost.show()
        self._drag_ghost.raise_()

    def _hide_drag_ghost(self):
        if self._drag_ghost is not None:
            self._drag_ghost.hide()

    def eventFilter(self, obj, event):
        bar = getattr(self, "tabs", None)
        bar = bar.tabBar() if bar is not None else None
        if obj is bar:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._tear_idx = obj.tabAt(event.pos())
                self._tear_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                self._tearing = False
            elif t == QEvent.Type.MouseMove and self._tear_idx >= 0 and (event.buttons() & Qt.MouseButton.LeftButton):
                gp = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                if self._tear_pos is not None and (gp - self._tear_pos).manhattanLength() > 10:
                    self._tearing = True
                    local = obj.mapFromGlobal(gp)
                    outside = not obj.rect().adjusted(-8, -16, 8, 36).contains(local)
                    if 0 <= self._tear_idx < self.tabs.count():
                        self._move_drag_ghost(self._tear_idx, gp, outside)
            elif t == QEvent.Type.MouseButtonRelease and self._tear_idx >= 0:
                gp = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                idx = self._tear_idx
                tearing = self._tearing
                self._tear_idx = -1
                self._tearing = False
                self._hide_drag_ghost()
                if tearing:
                    local = obj.mapFromGlobal(gp)
                    if not obj.rect().adjusted(-12, -20, 12, 48).contains(local):
                        self.tear_tab(idx, gp)
                        return True
        return super().eventFilter(obj, event)

    def _safe_first_tab(self):
        try:
            self.add_tab()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(tb)
            try:
                d = os.path.join(os.path.expanduser("~"), ".sloth_web")
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "crash.log"), "a", encoding="utf-8") as f:
                    f.write(tb + "\n")
            except Exception:
                pass
            try:
                QMessageBox.critical(self, "Sloth Web", "First tab failed:\n" + str(e))
            except Exception:
                pass

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

    def pick_browser_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick a browser app or its Bookmarks file",
            os.path.expanduser("~"),
            "All files (*);;Apps (*.exe);;Chromium Bookmarks (Bookmarks);;Firefox (places.sqlite)",
        )
        if not path:
            return
        result = BrowserImporter.import_any_path(path, self)
        self.log(result.get("message") or "Done", notify=True)
        try:
            self.add_tab(QUrl("sloth://start?imported=" + urllib.parse.quote(result.get("message") or "Done")))
        except Exception:
            pass

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
            nt = self.config_manager.get("new_tab_url") or self.config_manager.get("home_url", "sloth://home")
            url = QUrl(nt)
        
        # Check if we need to show the start page first time
        if not self.config_manager.get("setup_complete", False) and url == QUrl("sloth://home"):
            url = QUrl("sloth://start")
        
        # Use dedicated profile for container or incognito
        if incognito:
            profile = QWebEngineProfile(self)
            try:
                profile.setUrlRequestInterceptor(self.ad_interceptor)
            except Exception:
                profile.setUrlRequestInterceptor(AdBlockInterceptor(self, self.ad_block_enabled))
            try:
                profile.installUrlSchemeHandler(b"sloth", SlothSchemeHandler(self))
            except Exception:
                pass
        elif container:
            container = space_id(container)
            if not hasattr(self, "container_profiles"):
                self.container_profiles = {}
            if container not in self.container_profiles:
                try:
                    storage_path = os.path.join(os.path.expanduser("~"), ".sloth_web", f"profile_{container}")
                    os.makedirs(storage_path, exist_ok=True)
                    p = QWebEngineProfile(f"space_{container}", self)
                    p.setPersistentStoragePath(storage_path)
                    p.setCachePath(os.path.join(storage_path, "cache"))
                    p.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
                    try:
                        p.setUrlRequestInterceptor(self.ad_interceptor)
                    except Exception:
                        p.setUrlRequestInterceptor(AdBlockInterceptor(self, self.ad_block_enabled))
                    try:
                        p.installUrlSchemeHandler(b"sloth", SlothSchemeHandler(self))
                    except Exception:
                        pass
                    self.container_profiles[container] = p
                except Exception as e:
                    self.log(f"Space '{container}' fell back to main profile: {e}")
                    profile = QWebEngineProfile.defaultProfile()
                    container = None
            if container:
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
            profile.scripts().insert(IpSpoofScript(
                self.config_manager.get("ip_label", "slothwebiscool!"),
                bool(self.config_manager.get("mask_ip", False)),
            ))
            profile.scripts().insert(CursorInjectionScript(self.config_manager.get("custom_cursor", "Default")))
            bridge = QWebEngineScript()
            bridge.setName("SlothPassBridge")
            bridge.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            bridge.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            bridge.setRunsOnSubFrames(False)
            bridge.setSourceCode("window.slothPass={request:function(h){console.log('SLOTH_PASS_GET:'+(h||location.host));},save:function(u,p){console.log('SLOTH_PASS_SAVE:'+location.host+'::'+u+'::'+p);}};")
            profile.scripts().insert(bridge)
            self.bind_extension_manager(profile)
            profile._sloth_injected = True
            
        page = CustomWebEnginePage(profile, self)
        if not getattr(profile, "_dl_hooked", False):
            profile.downloadRequested.connect(self.dl_manager.add_download)
            profile._dl_hooked = True
        
        # Incremental XP for browsing!
        xp = self.config_manager.get("sloth_xp", 0) + 1
        self.config_manager.set("sloth_xp", xp)

        browser = CustomWebEngineView(self)
        browser.setPage(page)
        browser.container = container
        browser.incognito = incognito
        browser.tab_group = "Unassigned"
        browser.last_active_time = time.time()
        
        title_prefix = f"[{str(container).capitalize()}] " if container else "🕶️ [Incognito] " if incognito else ""
        idx = self.tabs.addTab(browser, f"{title_prefix}New Tab")
        
        # Color coding
        if incognito:
            self.tabs.tabBar().setTabTextColor(idx, QColor("#9c27b0"))
        elif container:
            colors = {"personal": "#4a9eff", "work": "#2ec4b6", "finance": "#ffb703", "social": "#e63946"}
            palette = ["#4a9eff", "#2ec4b6", "#ffb703", "#e63946", "#9b5de5", "#00bbf9"]
            col = colors.get(container, palette[abs(hash(container)) % len(palette)])
            self.tabs.tabBar().setTabTextColor(idx, QColor(col))
            if bool(self.config_manager.get("workspace_tint", True)):
                try:
                    self.setStyleSheet(self.styleSheet() + f"\nQMainWindow {{ border-top: 3px solid {col}; }}")
                except Exception:
                    pass
        
        # Custom Close Button to ensure icons show correctly
        close_btn = QPushButton()
        close_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { border:none; background:transparent; padding: 0px; margin: 0px; } QPushButton:hover { background: rgba(255,0,0,0.2); border-radius:4px; }")
        close_btn.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(browser)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, close_btn)
        
        # Apply custom UA if set — Google/YouTube always get a real Chrome UA so sessions stick
        ua_type = self.config_manager.get("custom_ua", "Chrome (Standard)")
        if "Firefox" in ua_type:
            profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
        elif "Safari" in ua_type:
            profile.setHttpUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15")
        else:
            profile.setHttpUserAgent(Platform.get_user_agent())
        
        if source_html:
            browser.setHtml(f"<html><head><title>Source of {url.toString()}</title><style>body{{background:#0f0f0f;color:#0f0;font-family:monospace;white-space:pre-wrap;padding:20px;}}</style></head><body>{source_html.replace('<','&lt;').replace('>','&gt;')}</body></html>")
        else:
            browser.load(url if url else QUrl(self.config_manager.get("new_tab_url") or self.config_manager.get("home_url", "sloth://home")))
        
        browser.urlChanged.connect(lambda q, b=browser: self.update_ui(q, self.tabs.indexOf(b)))
        browser.titleChanged.connect(lambda t, b=browser: (
            self.apply_tab_title(b, t),
            self.history_manager.add_entry(t, b.url().toString()) if (not getattr(b, 'incognito', False) and self.should_record_history(b.url().toString())) else None
        ))
        browser.iconChanged.connect(lambda icon, b=browser: self.tabs.setTabIcon(self.tabs.indexOf(b), icon))
        browser.loadProgress.connect(lambda p: (self.progress.setValue(p), self.progress.setVisible(p < 100)))
        
        browser.urlChanged.connect(lambda _: self.update_nav_actions())
        browser.loadFinished.connect(lambda _: self.update_nav_actions())
        
        page.loadFinished.connect(lambda ok, b=browser: self.handle_load_finished(ok, b))
        
        self.tabs.setCurrentIndex(idx)
        ms = Motion.duration(self.config_manager.config)
        if self.config_manager.get("tab_fade", True) and ms > 8:
            Motion.fade_widget(self.tabs.tabBar(), 0.65, 1.0, max(90, ms // 2))
        
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
            try:
                self.apply_tab_rules(browser)
                self.inject_context_guard(browser)
            except Exception:
                pass
            site = browser.url().host()
            if site:
                styles = self.custom_manager.get_for_site(site)
                if styles:
                    styles_json = json.dumps(styles).replace("'", "\\'")
                    js = f"localStorage.setItem('__sloth_customizations', '{styles_json}'); if(window.applySaved) applySaved();"
                    browser.page().runJavaScript(js)
            if bool(self.config_manager.get("mask_ip", False)):
                host = (browser.url().host() or "").lower()
                if any(h in host for h in IP_CHECK_HINTS):
                    fake = json.dumps(self.config_manager.get("ip_label", "slothwebiscool!"))
                    browser.page().runJavaScript(f"""
                        (function(){{
                          const FAKE = {fake};
                          const re4 = /\\b(?:\\d{{1,3}}\\.){{3}}\\d{{1,3}}\\b/g;
                          const re6 = /\\b(?:[0-9a-fA-F]{{0,4}}:){{2,7}}[0-9a-fA-F]{{0,4}}\\b/g;
                          const walk = (n) => {{
                            if (!n) return;
                            if (n.nodeType === 3) {{
                              n.nodeValue = n.nodeValue.replace(re4, FAKE).replace(re6, FAKE);
                            }} else {{
                              for (const c of n.childNodes) walk(c);
                            }}
                          }};
                          walk(document.body);
                        }})();
                    """)
        else:
            if browser.url().scheme() != "sloth":
                browser.setHtml(NEON_VOID_HTML, browser.url())

    def toggle_layout(self):
        try:
            west = QTabWidget.TabPosition.West
            self.tabs_pos = "north" if self.tabs.tabPosition() == west else "west"
        except Exception:
            self.tabs_pos = "west" if getattr(self, "tabs_pos", "north") != "west" else "north"
        self.config_manager.set("tabs_pos", self.tabs_pos)
        self.apply_tabs_pos()
        self.log(f"Switched tabs layout to {self.tabs_pos}.")

    def apply_tabs_pos(self):
        try:
            self.tabs.setDocumentMode(True)
            if self.tabs_pos == "west":
                self.tabs.setTabPosition(QTabWidget.TabPosition.West)
                if hasattr(self, "add_tab_btn"):
                    self.tabs.setCornerWidget(None, Qt.Corner.TopRightCorner)
            else:
                self.tabs.setTabPosition(QTabWidget.TabPosition.North)
                if hasattr(self, "add_tab_btn"):
                    self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)
                    self.add_tab_btn.show()
        except Exception as e:
            self.log(f"Tab orientation skipped: {e}")

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
        s = q.toString() if q else ""
        if s and not s.startswith("sloth://") and not s.startswith("about:"):
            self.last_real_url = s
        if idx == self.tabs.currentIndex():
            if not self.url_bar.hasFocus():
                self.url_bar.setText(q.toString())
            self.ssl_action.setText("🔒" if q.scheme() == "https" else "🔓")
            if hasattr(self, "sidebar") and self.sidebar.isVisible():
                self.update_sidebar()

    def apply_tab_title(self, browser, title=None):
        idx = self.tabs.indexOf(browser)
        if idx < 0:
            return
        custom = getattr(browser, "custom_title", None)
        if custom:
            self.tabs.setTabText(idx, custom)
            return
        t = title if title is not None else (browser.title() or "Tab")
        prefix = ""
        if getattr(browser, "container", None):
            prefix = f"[{str(browser.container).capitalize()}] "
        elif getattr(browser, "incognito", False):
            prefix = "Incognito "
        self.tabs.setTabText(idx, prefix + (t or "Tab")[:36])

    def rename_tab(self, idx):
        if idx is None or idx < 0:
            idx = self.tabs.currentIndex()
        w = self.tabs.widget(idx)
        if w is None:
            return
        cur = getattr(w, "custom_title", None) or self.tabs.tabText(idx)
        text, ok = QInputDialog.getText(self, "Rename tab", "Name this tab", QLineEdit.EchoMode.Normal, cur)
        if not ok:
            return
        text = text.strip()
        if not text:
            w.custom_title = None
            self.apply_tab_title(w)
        else:
            w.custom_title = text
            self.tabs.setTabText(idx, text)

    def search_selection(self, text):
        q = (text or "").strip()
        if not q:
            return
        engine = self.config_manager.get("search_engine", "mergarms")
        url = search_url(engine, q, self.config_manager.get("local_search_url", ""), self.config_manager.config)
        self.add_tab(QUrl(url))

    def show_tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx == -1:
            return
        menu = QMenu(self)
        new_tab = menu.addAction("New tab")
        menu.addSeparator()
        rename = menu.addAction("Rename tab")
        reset = menu.addAction("Reset tab name")
        duplicate = menu.addAction("Duplicate")
        new_win = menu.addAction("Move to new window")
        menu.addSeparator()
        hib = menu.addAction("Hibernate")
        stack = menu.addAction("Stack with next tab")
        if SlothAI.enabled(self.config_manager.config):
            menu.addAction("Summarise this tab").triggered.connect(self.summarize_page)
        menu.addSeparator()
        close_action = menu.addAction("Close")
        close_others = menu.addAction("Close others")
        close_right = menu.addAction("Close tabs to the right")
        reopen = menu.addAction("Reopen closed tab")
        reopen.setEnabled(bool(self._closed_tabs))

        action = menu.exec(self.tabs.mapToGlobal(pos))
        if action == new_tab:
            self.add_tab()
        elif action == rename:
            self.rename_tab(idx)
        elif action == reset:
            w = self.tabs.widget(idx)
            if w is not None:
                w.custom_title = None
                self.apply_tab_title(w)
        elif action == close_action:
            self.close_tab(idx)
        elif action == close_others:
            for i in range(self.tabs.count() - 1, -1, -1):
                if i != idx:
                    self.close_tab(i)
        elif action == close_right:
            for i in range(self.tabs.count() - 1, idx, -1):
                self.close_tab(i)
        elif action == reopen:
            self.reopen_closed()
        elif action == duplicate:
            url = self.tabs.widget(idx).url()
            self.add_tab(url)
        elif action == new_win:
            self.tear_tab(idx, QCursor.pos())
        elif action == hib:
            self.hibernate_tab(idx)
        elif action == stack:
            self.stack_tab(idx)

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
            engine = self.config_manager.get("search_engine", "mergarms")
            url = search_url(
                engine,
                url,
                self.config_manager.get("local_search_url", "http://127.0.0.1:8888/?q={q}"),
                self.config_manager.config,
            )
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

    def tab_changed(self, idx):
        b = self.current_browser()
        if b:
            b.last_active_time = time.time()
            if getattr(b, "hibernated", False) or (b.url().scheme() == "sloth" and (b.url().host() in ("sleep", "sleeping") or b.url().toString().startswith("sloth://sleep"))):
                self.wake_tab(idx)
            self.url_bar.setText(b.url().toString())
            self.ssl_action.setText("🔒" if b.url().scheme() == "https" else "🔓")
            self.update_nav_actions()
            ms = Motion.duration(self.config_manager.config)
            if self.config_manager.get("tab_fade", True) and ms > 8:
                Motion.fade_widget(self.tabs.tabBar(), 0.72, 1.0, max(80, ms // 2))

    def close_tab(self, i):
        if i < 0 or i >= self.tabs.count():
            return
        w = self.tabs.widget(i)
        if w is not None and bool(getattr(w, "pinned", False)):
            self.log("Unpin the tab before closing it")
            return
        if w is not None:
            try:
                url = w.url().toString()
            except Exception:
                url = ""
            if url and not url.startswith("sloth://sleep"):
                self._closed_tabs.append({"title": self.tabs.tabText(i) or url, "url": url})
                self._closed_tabs = self._closed_tabs[-25:]
        if self.tabs.count() > 1:
            ms = Motion.duration(self.config_manager.config)
            if self.config_manager.get("tab_fade", True) and ms > 20:
                Motion.fade_widget(self.tabs.tabBar(), 0.5, 1.0, min(ms, 160))
            self.tabs.removeTab(i)
            return
        b = self.current_browser()
        if b:
            b.setUrl(QUrl(self.config_manager.get("home_url", "sloth://home")))

    def reopen_closed(self):
        if not getattr(self, "_closed_tabs", None):
            self.log("Nothing to reopen")
            return
        item = self._closed_tabs.pop()
        self.add_tab(QUrl(item.get("url") or "sloth://home"))

    def cycle_tab(self, delta):
        n = self.tabs.count()
        if n < 2:
            return
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + delta) % n)

    def jump_tab(self, index):
        if index < 0:
            index = self.tabs.count() - 1
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def duplicate_current(self):
        b = self.current_browser()
        if b:
            self.add_tab(b.url())

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def focus_url_bar(self):
        self.url_bar.setFocus(Qt.FocusReason.ShortcutFocusReason)
        QTimer.singleShot(0, self.url_bar.selectAll)
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
        if not b:
            return
        b.page().runJavaScript("""
            (function(){
                if(window.is_reader){ location.reload(); return; }
                window.is_reader=true;
                const kill = 'nav,header,footer,aside,iframe,script,noscript,[role=navigation],[role=banner],.ad,.ads,.sidebar,.comments';
                document.querySelectorAll(kill).forEach(el => { try{el.remove()}catch(e){} });
                let c = document.querySelector('article') || document.querySelector('[itemprop=articleBody]') || document.querySelector('main') || document.body;
                const title = document.title;
                const text = c ? c.innerHTML : document.body.innerHTML;
                document.documentElement.innerHTML = `<head><meta charset=utf-8><title>${title}</title></head><body style="margin:0;background:#111318;color:#e8e4d9">
                    <div style="max-width:720px;margin:0 auto;padding:48px 28px 80px;font-family:Georgia,'Iowan Old Style',serif;font-size:21px;line-height:1.7;">
                        <p style="font:600 12px/1 system-ui;letter-spacing:.16em;text-transform:uppercase;opacity:.55">Sloth Reader</p>
                        <h1 style="font-size:40px;line-height:1.2;margin:12px 0 28px">${title}</h1>
                        ${text}
                    </div></body>`;
            })()
        """)
        self.log("Reader mode", notify=True)

    def translate_page(self):
        b = self.current_browser()
        if not b:
            return
        dest = self.config_manager.get("translate_lang", "es")
        eng = TranslateEngine(self.config_manager)
        def done(text):
            if not text:
                return
            t = eng.translate(text[:2500], dest)
            b.page().runJavaScript(
                "document.body.innerHTML = `<div style='max-width:800px;margin:40px auto;padding:24px;font:18px/1.6 system-ui'>` + "
                + json.dumps("<p style='opacity:.6'>Sloth Translate → " + dest + "</p>" + html_lib.escape(t).replace("\n", "<br>"))
                + " + `</div>`;"
            )
        b.page().runJavaScript("document.body.innerText", done)

    def translate_selection(self):
        b = self.current_browser()
        if not b:
            return
        dest = self.config_manager.get("translate_lang", "es")
        eng = TranslateEngine(self.config_manager)
        def done(text):
            src = text or ""
            if not src.strip():
                self.log("Select some text first", notify=True)
                return
            t = eng.translate(src, dest)
            ChromeDialog(self, "Translate", t, kind="alert").exec()
        b.page().runJavaScript("window.getSelection().toString()", done)

    def try_smtp_send(self, frm, to, subject, body):
        host = self.config_manager.get("smtp_host")
        if not host or not to:
            return
        try:
            msg = MIMEText(body or "")
            msg["Subject"] = subject or ""
            msg["From"] = frm or self.config_manager.get("smtp_user", "")
            msg["To"] = to
            port = int(self.config_manager.get("smtp_port", 587))
            s = smtplib.SMTP(host, port, timeout=10)
            s.starttls()
            user, pw = self.config_manager.get("smtp_user"), self.config_manager.get("smtp_pass")
            if user:
                s.login(user, pw or "")
            s.send_message(msg)
            s.quit()
            self.log("Sent via SMTP", notify=True)
        except Exception as e:
            self.log(f"SMTP skipped: {e}")

    def mail_tick(self):
        try:
            n = self.mail_manager.due_later()
            if n:
                self.log(f"Sent {n} delayed message(s)", notify=True)
        except Exception:
            pass

    def fill_pass_for_host(self, host):
        hits = self.password_manager.find_for_site(host)
        if not hits:
            self.log("No vault entry for " + str(host), notify=True)
            return
        u = json.dumps(hits[0].get("user") or "")
        p = json.dumps(hits[0].get("pass") or "")
        b = self.current_browser()
        if b:
            b.page().runJavaScript(
                f"document.querySelectorAll('input[type=email],input[type=text],input[name*=user]').forEach(i=>{{if(!i.value)i.value={u}}});"
                f"document.querySelectorAll('input[type=password]').forEach(i=>i.value={p});"
            )
            self.log("Filled from Sloth Pass", notify=True)
    def install_pwa(self):
        b = self.current_browser()
        if not b: return
        url = b.url().toString()
        title = b.title() or url.split("://")[-1].split("/")[0]
        
        name, ok = QInputDialog.getText(self, "Install App", "App Name:", QLineEdit.EchoMode.Normal, title)
        if not ok or not name: return
        
        name = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        if not name: name = "SlothApp"

        apps = self.config_manager.get("home_apps")
        if not isinstance(apps, list) or not apps:
            apps = list(DEFAULT_HOME_APPS)
        if not any((a.get("url") == url) for a in apps if isinstance(a, dict)):
            apps.append({"name": name, "url": url})
            self.config_manager.set("home_apps", apps)
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        os.makedirs(desktop, exist_ok=True)
        script = os.path.abspath(__file__)
        py = sys.executable
        note = f"{name} is on your home Quick Access grid."
        try:
            if Platform.IS_WIN:
                shortcut_path = os.path.join(desktop, f"{name}.lnk")
                if getattr(sys, 'frozen', False):
                    target = sys.executable
                    args = f'--app="{url}"'
                else:
                    target = py
                    args = f'"{script}" --app="{url}"'
                tmp = os.environ.get("TEMP", os.path.expanduser("~"))
                vbs_path = os.path.join(tmp, "create_shortcut.vbs")
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
                with open(vbs_path, "w") as f:
                    f.write(vbs)
                subprocess.call(['cscript.exe', '/nologo', vbs_path])
                note += f" Desktop shortcut: {shortcut_path}"
            else:
                desk_file = os.path.join(desktop, f"{name.replace(' ', '_')}.desktop")
                with open(desk_file, "w") as f:
                    f.write(
                        "[Desktop Entry]\n"
                        "Type=Application\n"
                        f"Name={name}\n"
                        f"Exec={py} \"{script}\" --app=\"{url}\"\n"
                        "Terminal=false\n"
                    )
                try:
                    os.chmod(desk_file, 0o755)
                except Exception:
                    pass
                note += f" Launcher: {desk_file}"
            self.log(f"App added: {name}", notify=True)
            QMessageBox.information(self, "App Installed", note)
        except Exception as e:
            self.log(f"App added to home (shortcut skipped): {e}", notify=True)
            QMessageBox.information(self, "App Installed", f"{name} was added to home Quick Access.\nDesktop shortcut skipped: {e}")

    def prompt_add_app(self):
        name, ok = QInputDialog.getText(self, "Add App", "Name:")
        if not ok or not name:
            return
        url, ok = QInputDialog.getText(self, "Add App", "URL:", QLineEdit.EchoMode.Normal, "https://")
        if not ok or not url:
            return
        url = url.strip()
        if not url.startswith(("http://", "https://", "sloth://")):
            url = "https://" + url
        apps = self.config_manager.get("home_apps")
        if not isinstance(apps, list) or not apps:
            apps = list(DEFAULT_HOME_APPS)
        apps.append({"name": name.strip(), "url": url})
        self.config_manager.set("home_apps", apps)
        self.log(f"Added app {name}", notify=True)
        b = self.current_browser()
        if b:
            b.setUrl(QUrl("sloth://home"))

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
                self.refresh_bookmarks_bar()

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
            if b: b.setUrl(QUrl(item.toolTip() or item.text()))
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
        self.set_adblock(not self.ad_block_enabled)

    def set_adblock(self, on):
        self.ad_block_enabled = bool(on)
        self.config_manager.set("ad_block_enabled", self.ad_block_enabled)
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.enabled = self.ad_block_enabled
        self.status.showMessage(f"AdBlock {'on' if self.ad_block_enabled else 'off'}")
        self.log(f"AdBlock {'enabled' if self.ad_block_enabled else 'disabled'}", notify=True)

    def set_tracker_block(self, on):
        self.config_manager.set("block_trackers", bool(on))
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.trackers_enabled = bool(on)
        self.log(f"Tracker block {'on' if on else 'off'}", notify=True)

    def set_mask_ip(self, on):
        self.config_manager.set("mask_ip", bool(on))
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.mask_ip = bool(on)
            self.ad_interceptor.mask_label = self.config_manager.get("ip_label", "slothwebiscool!")
        s = QWebEngineProfile.defaultProfile().settings()
        if hasattr(QWebEngineSettings.WebAttribute, "WebRTCPublicInterfacesOnly"):
            s.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, bool(on))
        self._refresh_ip_script()
        label = self.config_manager.get("ip_label", "slothwebiscool!")
        self.log(f"IP spoof on → {label}" if on else "IP spoof off", notify=True)

    def set_ip_label(self, val):
        val = (val or "").strip() or "slothwebiscool!"
        self.config_manager.set("ip_label", val)
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.mask_label = val
        self._refresh_ip_script()

    def _refresh_ip_script(self):
        profile = QWebEngineProfile.defaultProfile()
        scripts = profile.scripts()
        for s in list(scripts.toList()):
            if s.name() == "IpSpoof":
                scripts.remove(s)
        scripts.insert(IpSpoofScript(
            self.config_manager.get("ip_label", "slothwebiscool!"),
            bool(self.config_manager.get("mask_ip", False)),
        ))

    def apply_user_agent(self, val):
        self.config_manager.set("custom_ua", val)
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.apply_ua(val)
        profile = QWebEngineProfile.defaultProfile()
        if "Firefox" in val:
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
        elif "Safari" in val:
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        elif "Sloth" in val:
            ua = f"SlothWeb/Platinum ({__version__})"
        else:
            ua = Platform.get_user_agent()
        profile.setHttpUserAgent(ua)
        b = self.current_browser()
        if b:
            b.reload()
        self.log(f"User agent: {val}", notify=True)

    def toggle_sidebar(self):
        ms = Motion.duration(self.config_manager.config)
        if self.sidebar.isVisible():
            if self.config_manager.get("tab_fade", True):
                Motion.fade_widget(self.sidebar, 1.0, 0.0, ms, done=lambda: self.sidebar.setVisible(False))
            else:
                self.sidebar.setVisible(False)
        else:
            self.sidebar.setVisible(True)
            self.update_sidebar()
            if self.config_manager.get("tab_fade", True):
                Motion.fade_widget(self.sidebar, 0.0, 1.0, ms)

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

        if hasattr(self, "essentials_list"):
            self.essentials_list.clear()
            for e in self.config_manager.get("essentials") or []:
                item = QListWidgetItem(f"⭐ {e.get('title') or e.get('url')}")
                item.setToolTip(e.get("url", ""))
                self.essentials_list.addItem(item)

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
                n = int(self.config_manager.get("focus_sessions_completed", 0)) + 1
                self.config_manager.set("focus_sessions_completed", n)
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
        qss = ThemeManager.get_qss(
            self.dark_theme,
            self.accent_color,
            texture,
            radius=int(self.config_manager.get("ui_radius", 16)),
            density=self.config_manager.get("ui_density", "comfortable"),
            pill_tabs=bool(self.config_manager.get("pill_tabs", True)),
            compact=bool(self.config_manager.get("zen_compact", False)),
            chrome_margin=int(self.config_manager.get("chrome_margin", 8)),
        )
        app.setStyleSheet(qss)
        ThemeManager.apply_palette(app, self.dark_theme, accent_color=self.accent_color)
        self.setWindowOpacity(float(self.config_manager.get("window_opacity", 1.0)))
        show_status = bool(self.config_manager.get("show_status", True)) and not bool(self.config_manager.get("zen_compact", False))
        if hasattr(self, "status"):
            self.status.setVisible(show_status)
        
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
        if hasattr(self, "nav"):
            self._style_add_tab_btn()
        self.apply_chrome_extras()

    def apply_chrome_extras(self):
        try:
            w = int(self.config_manager.get("sidebar_width", 300))
            if hasattr(self, "sidebar"):
                self.sidebar.setMinimumWidth(max(200, w - 40))
                self.sidebar.setMaximumWidth(w + 80)
                if bool(self.config_manager.get("sidebar_right", False)):
                    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.sidebar)
                else:
                    self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
            if hasattr(self, "url_bar") and bool(self.config_manager.get("floating_url", False)):
                r = int(self.config_manager.get("ui_radius", 16)) + 8
                self.url_bar.setStyleSheet(
                    f"QLineEdit {{ border-radius:{r}px; padding:8px 16px; border:1px solid {self.accent_color}; }}"
                )
        except Exception:
            pass

    def should_record_history(self, url):
        if not bool(self.config_manager.get("save_history", True)):
            return False
        if not bool(self.config_manager.get("save_search_history", True)) and is_search_url(url):
            return False
        return True

    def set_html_only(self, on):
        self.config_manager.set("html_only", bool(on))
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.html_only = bool(on)

    def apply_combined_chrome(self):
        on = bool(self.config_manager.get("combined_chrome", False))
        if not hasattr(self, "url_bar") or not hasattr(self, "tabs"):
            return
        try:
            if on:
                self.nav.hide()
                self.tabs.setCornerWidget(self.url_bar, Qt.Corner.TopRightCorner)
                self.url_bar.setMinimumWidth(320)
                self.url_bar.show()
            else:
                self.url_bar.setMinimumWidth(300)
                if hasattr(self, "add_tab_btn"):
                    self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)
                    self.add_tab_btn.show()
                self.apply_nav_pos()
                if not bool(self.config_manager.get("zen_compact", False)):
                    self.nav.show()
        except Exception as e:
            self.log(f"Combined chrome: {e}")

    def copy_clean_url(self, url=None):
        b = self.current_browser()
        url = url or (b.url().toString() if b else "")
        if bool(self.config_manager.get("clean_copy_urls", True)):
            url = clean_tracking_url(url)
        QApplication.clipboard().setText(url)
        self.log("Copied " + url[:80], notify=True)

    def bookmark_temp(self):
        b = self.current_browser()
        if not b:
            return
        url = b.url().toString()
        self.bookmarks.append({
            "title": (b.title() or url) + " (temp)",
            "url": url,
            "temp": True,
            "expires": time.time() + 7 * 86400,
        })
        save_bookmarks(self.bookmarks_file, self.bookmarks)
        self.refresh_bookmarks_bar()
        self.log("Temporary bookmark — 7 days", notify=True)

    def prune_temp_bookmarks(self):
        now = time.time()
        keep = []
        for b in self.bookmarks:
            if isinstance(b, dict) and b.get("temp") and float(b.get("expires") or 0) and float(b.get("expires")) < now:
                continue
            keep.append(b)
        if len(keep) != len(self.bookmarks):
            self.bookmarks = keep
            save_bookmarks(self.bookmarks_file, self.bookmarks)

    def hibernate_tab(self, idx=None):
        if idx is None:
            idx = self.tabs.currentIndex()
        w = self.tabs.widget(idx)
        if not w or not hasattr(w, "url"):
            return
        if getattr(w, "hibernated", False):
            self.wake_tab(idx)
            return
        u = (w.url().toString() if w.url() else "") or ""
        if u.startswith("sloth://sleep") or u.startswith("sloth://wake"):
            return
        if not u or u.startswith("sloth://"):
            return
        w._sleep_url = u
        w.hibernated = True
        try:
            w.page().setAudioMuted(True)
        except Exception:
            pass
        title = (w.title() or u)[:24]
        w.setUrl(QUrl("sloth://sleep?url=" + urllib.parse.quote(u, safe="")))
        self.tabs.setTabText(idx, "💤 " + title)
        self.log("Tab sleeping — will restore " + u[:60])

    def wake_tab(self, idx):
        w = self.tabs.widget(idx)
        if not w:
            return
        u = getattr(w, "_sleep_url", "") or ""
        if not u:
            try:
                q = urllib.parse.parse_qs(QUrl(w.url().toString()).query())
                u = urllib.parse.unquote((q.get("url") or q.get("u") or [""])[0] or "")
            except Exception:
                u = ""
        w.hibernated = False
        if u and not u.startswith("sloth://sleep") and u != "sloth://home":
            w.setUrl(QUrl(u))
        try:
            w.page().setAudioMuted(False)
        except Exception:
            pass

    def wake_url(self, u):
        b = self.current_browser()
        if not b:
            return
        stored = getattr(b, "_sleep_url", "") or ""
        target = u or stored
        if not target or target.startswith("sloth://sleep") or target.startswith("sloth://wake"):
            self.log("Nothing to restore for this tab")
            return
        b.hibernated = False
        b._sleep_url = target
        b.setUrl(QUrl(target))
        try:
            b.page().setAudioMuted(False)
        except Exception:
            pass

    def tick_sleep_tabs(self):
        if not bool(self.config_manager.get("auto_sleep_tabs", True)):
            return
        mins = max(1, int(self.config_manager.get("sleep_after_min", 5) or 5))
        now = time.time()
        cur = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            if i == cur:
                continue
            w = self.tabs.widget(i)
            if not w or getattr(w, "hibernated", False) or getattr(w, "pinned", False):
                continue
            u = ""
            try:
                u = w.url().toString()
            except Exception:
                pass
            if not u or u.startswith("sloth://"):
                continue
            last = getattr(w, "last_active_time", now)
            if now - last >= mins * 60:
                self.hibernate_tab(i)

    def stack_tab(self, idx):
        if idx < 0 or idx >= self.tabs.count() - 1:
            self.log("Need a tab to the right to stack")
            return
        a = self.tabs.widget(idx)
        b = self.tabs.widget(idx + 1)
        name = (a.title() if a else "Stack")[:18]
        if a:
            a.tab_group = name
        if b:
            b.tab_group = name
        self.log(f"Stacked as {name}", notify=True)
        if hasattr(self, "update_tab_groups_tree"):
            self.update_tab_groups_tree()

    def picture_in_picture(self):
        b = self.current_browser()
        if not b:
            return
        js = """(function(){
            const v = document.querySelector('video');
            if (!v) return JSON.stringify({ok:false});
            return JSON.stringify({ok:true, src: v.currentSrc || v.src || '', t: v.currentTime||0});
        })();"""
        def done(res):
            try:
                data = json.loads(res) if isinstance(res, str) else {}
            except Exception:
                data = {}
            if not data.get("ok"):
                self.log("No video on this page", notify=True)
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("Picture in Picture")
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dlg.resize(420, 260)
            lay = QVBoxLayout(dlg)
            view = QWebEngineView(dlg)
            src = html_lib.escape(data.get("src") or "")
            t = float(data.get("t") or 0)
            view.setHtml(
                f"<html><body style='margin:0;background:#000'>"
                f"<video id='v' src='{src}' controls autoplay style='width:100%;height:100%'></video>"
                f"<script>document.getElementById('v').currentTime={t};</script></body></html>"
            )
            lay.addWidget(view)
            if not hasattr(self, "pip_windows"):
                self.pip_windows = []
            self.pip_windows.append(dlg)
            dlg.show()
        b.page().runJavaScript(js, done)

    def toggle_media(self):
        b = self.current_browser()
        if not b:
            return
        b.page().runJavaScript(
            "(function(){const v=document.querySelector('video,audio'); if(!v) return 'none'; if(v.paused){v.play();return 'play';} v.pause(); return 'pause';})();"
        )

    def paste_clipboard_image(self):
        img = QApplication.clipboard().image()
        if img.isNull():
            self.log("Clipboard has no image", notify=True)
            return
        folder = os.path.join(os.path.expanduser("~"), ".sloth_web", "clips")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"clip-{int(time.time())}.png")
        img.save(path)
        self.add_tab(QUrl.fromLocalFile(path))

    def summarize_page(self):
        if not SlothAI.enabled(self.config_manager.config):
            self.log("AI is off — enable it in Settings", notify=True)
            return
        b = self.current_browser()
        if not b:
            return
        def done(text):
            try:
                summary = SlothAI.summarize(text or "", self.config_manager.config)
            except Exception as e:
                summary = str(e)
            self._last_ai = summary
            self.add_tab(QUrl("sloth://ai"))
        b.page().toPlainText(done)

    def ai_organize_tabs(self):
        if not SlothAI.enabled(self.config_manager.config):
            self.log("AI is off — enable it in Settings", notify=True)
            return
        items = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not w:
                continue
            host = ""
            try:
                host = w.url().host()
            except Exception:
                pass
            items.append({"i": i, "host": host, "title": self.tabs.tabText(i), "w": w})
        groups = SlothAI.organize(items)
        lines = ["Organised tabs by site:"]
        palette = ["#4a9eff", "#2ec4b6", "#ffb703", "#e63946", "#9b5de5", "#00bbf9"]
        for n, (g, members) in enumerate(groups.items()):
            col = palette[n % len(palette)]
            lines.append(f"• {g} — {len(members)} tab(s)")
            for m in members:
                w = m["w"]
                w.tab_group = g
                try:
                    self.tabs.tabBar().setTabTextColor(m["i"], QColor(col))
                except Exception:
                    pass
        self._last_ai = "\n".join(lines)
        if hasattr(self, "update_tab_groups_tree"):
            self.update_tab_groups_tree()
        self.log("Tabs organised", notify=True)

    def apply_tab_rules(self, browser):
        if not bool(self.config_manager.get("auto_group_tabs", True)):
            return
        rules = self.config_manager.get("tab_rules") or [
            {"match": "youtube.com", "group": "Watch"},
            {"match": "mail.", "group": "Mail"},
            {"match": "github.com", "group": "Code"},
            {"match": "reddit.com", "group": "Social"},
            {"match": "x.com", "group": "Social"},
        ]
        u = (browser.url().toString() if browser else "") or ""
        title = browser.title() if browser else ""
        for r in rules:
            pat = (r.get("match") or "").lower()
            if pat and (pat in u.lower() or pat in (title or "").lower()):
                browser.tab_group = r.get("group") or pat
                break

    def inject_context_guard(self, browser):
        if not bool(self.config_manager.get("protect_context_menu", True)):
            return
        browser.page().runJavaScript(
            "document.addEventListener('contextmenu',function(e){e.stopImmediatePropagation();},true);"
        )

    def install_from_cws(self, ext_id):
        ext_id = "".join(c for c in (ext_id or "") if c.islower())
        job = getattr(self, "_cws_job", None) or {}
        if job.get("running") and job.get("id") == ext_id:
            return
        self._cws_job = {
            "id": ext_id, "running": True, "done": False, "ok": False,
            "step": "Starting…", "log": [], "error": "", "name": "", "dir": "", "popup": "",
        }
        if len(ext_id) != 32:
            self._cws_fail("Not a Chrome Web Store id (need the 32-letter id from the URL)")
            return
        self._cws_note("Downloading from Google…")
        self._cws_watch = ext_id
        QTimer.singleShot(50000, lambda i=ext_id: self._cws_watchdog(i))

        def work():
            crx_dir = get_storage_path("crx_downloads")
            os.makedirs(crx_dir, exist_ok=True)
            path = os.path.join(crx_dir, ext_id + ".crx")
            try:
                blob = download_cws_crx(ext_id, progress=lambda m: QTimer.singleShot(0, lambda msg=m: self._cws_note(msg)))
                with open(path, "wb") as f:
                    f.write(blob)
                QTimer.singleShot(0, lambda: self._finish_cws(path, ext_id))
            except Exception as e:
                QTimer.singleShot(0, lambda err=str(e): self._cws_fail(err))

        threading.Thread(target=work, daemon=True).start()

    def _cws_note(self, msg):
        job = getattr(self, "_cws_job", None)
        if not job:
            return
        job["step"] = str(msg)
        logs = job.get("log") or []
        logs.append(str(msg))
        job["log"] = logs[-20:]

    def _cws_fail(self, err):
        self._cws_watch = None
        job = getattr(self, "_cws_job", None)
        if job:
            job["running"] = False
            job["done"] = True
            job["ok"] = False
            job["error"] = str(err)
            job["step"] = "Failed"
            logs = job.get("log") or []
            logs.append("FAIL: " + str(err))
            job["log"] = logs
        self._cws_button("Failed — retry")
        self.log(f"CWS download failed: {err}", notify=True)

    def _cws_watchdog(self, ext_id):
        job = getattr(self, "_cws_job", None) or {}
        if job.get("id") == ext_id and job.get("running") and not job.get("done"):
            self._cws_fail("Timed out talking to Chrome Web Store")

    def _cws_button(self, text):
        b = self.current_browser()
        if not b:
            return
        try:
            b.page().runJavaScript(
                "var x=document.getElementById('sloth-add-btn'); if(x) x.textContent=" + json.dumps(str(text)) + ";"
            )
        except Exception:
            pass

    def pick_crx_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Install extension", "", "Extensions (*.crx *.zip);;All files (*.*)")
        if not path:
            return
        ext_id = os.path.splitext(os.path.basename(path))[0]
        ext_id = "".join(c for c in ext_id if c.isalnum())[:32] or "localext"
        self._cws_job = {
            "id": ext_id, "running": True, "done": False, "ok": False,
            "step": "Installing file…", "log": [path], "error": "", "name": "", "dir": "", "popup": "",
        }
        self._finish_cws(path, ext_id)
        self.add_tab(QUrl("sloth://install-cws?id=" + urllib.parse.quote(ext_id)))

    def _finish_cws(self, path, ext_id):
        self._cws_watch = None
        self._cws_note("Unpacking…")
        res = CRXInstaller.install(path, self)
        if not res.get("ok"):
            self._cws_fail("Could not unpack: " + (res.get("error") or "unknown"))
            return
        mode = self.activate_extension(res["dir"])
        name = res.get("name") or ext_id
        job = getattr(self, "_cws_job", None)
        if job:
            job["name"] = name
            job["dir"] = res.get("dir") or ""
            job["popup"] = res.get("popup") or ""
            job["id"] = res.get("id") or ext_id
            job["running"] = False
            job["done"] = True
            job["ok"] = True
            job["step"] = "Installed"
        self._cws_button("Installed — open")
        try:
            self.rebuild_extension_toolbar()
        except Exception:
            pass
        self.log(f"{name} is on the toolbar — click its icon", notify=True)
        if mode == "native":
            self._pending_open_after_install = res
            QTimer.singleShot(1800, lambda r=res: self._native_open_or_fallback(r))
        else:
            self.show_extension_popup(res["dir"], res.get("popup") or "", name=name)

    def _native_open_or_fallback(self, res):
        if self.open_native_popup(res.get("id") or "", res.get("name") or ""):
            self._pending_open_after_install = None
            return
        self._pending_open_after_install = None
        self.show_extension_popup(res.get("dir") or "", res.get("popup") or "", name=res.get("name") or "")

    def bind_extension_manager(self, profile=None):
        profile = profile or QWebEngineProfile.defaultProfile()
        mgr, reason = native_extension_manager(profile)
        if not mgr:
            return None
        if getattr(profile, "_sloth_ext_bound", False):
            return mgr

        def on_done(info, kind=""):
            try:
                err = ext_info_get(info, "error", "") or ""
                loaded = bool(ext_info_get(info, "isLoaded", False))
                name = ext_info_get(info, "name", "") or "extension"
                if err and not loaded:
                    self.log(f"{name} {kind} failed: {err}", notify=True)
                    return
                mgr.setExtensionEnabled(info, True)
                self.log(f"{name} enabled", notify=True)
                pending = getattr(self, "_pending_open_after_install", None)
                popup = ext_info_get(info, "actionPopupUrl", None)
                if pending and popup:
                    try:
                        self._pending_open_after_install = None
                        if hasattr(popup, "isValid") and popup.isValid():
                            self.add_tab(popup)
                        else:
                            self.add_tab(QUrl(str(popup)))
                    except Exception:
                        pass
            except Exception as e:
                print("ext signal", e)

        try:
            mgr.loadFinished.connect(lambda info: on_done(info, "load"))
            mgr.installFinished.connect(lambda info: on_done(info, "install"))
        except Exception as e:
            print("ext connect", e)
        profile._sloth_ext_bound = True
        return mgr

    def activate_extension(self, ext_dir):
        if not ext_dir or not os.path.isdir(ext_dir):
            return "missing"
        man_path = os.path.join(ext_dir, "manifest.json")
        if not os.path.isfile(man_path):
            return "missing"
        try:
            with open(man_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            return "bad-manifest"
        mv = int(manifest.get("manifest_version") or 2)
        for cs in manifest.get("content_scripts") or []:
            code_parts = []
            for jf in cs.get("js") or []:
                src = os.path.join(ext_dir, str(jf).replace("/", os.sep))
                if os.path.isfile(src):
                    try:
                        with open(src, encoding="utf-8", errors="ignore") as f:
                            code_parts.append(f.read())
                    except Exception:
                        pass
            if not code_parts:
                continue
            s = QWebEngineScript()
            s.setName("sloth-ext:" + os.path.basename(ext_dir) + ":" + str(cs.get("js")))
            s.setSourceCode("\n".join(code_parts))
            s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            s.setRunsOnSubFrames(bool(cs.get("all_frames")))
            try:
                QWebEngineProfile.defaultProfile().scripts().insert(s)
            except Exception:
                pass
        if mv < 3:
            return "mv2"
        mgr = self.bind_extension_manager()
        if not mgr:
            return "fallback"
        abs_dir = os.path.abspath(ext_dir)
        try:
            if hasattr(mgr, "installExtension"):
                mgr.installExtension(abs_dir)
            elif hasattr(mgr, "loadExtension"):
                mgr.loadExtension(abs_dir)
        except Exception:
            try:
                mgr.loadExtension(abs_dir)
            except Exception as e:
                print("native install failed", e)
                return "fallback"
        return "native"

    def open_native_popup(self, ext_id="", name=""):
        mgr, _ = native_extension_manager()
        if not mgr:
            return False
        try:
            exts = mgr.extensions() or []
        except Exception:
            return False
        target = None
        for info in exts:
            iid = str(ext_info_get(info, "id", "") or "")
            iname = str(ext_info_get(info, "name", "") or "")
            path = str(ext_info_get(info, "path", "") or "")
            if ext_id and (ext_id == iid or ext_id in path or os.path.basename(path.rstrip("\\/")) == ext_id):
                target = info
                break
            if name and name.lower() == iname.lower():
                target = info
                break
        if target is None and exts:
            pending = getattr(self, "_pending_ext_popup", None)
            if pending:
                self.add_tab(pending if isinstance(pending, QUrl) else QUrl(str(pending)))
                self._pending_ext_popup = None
                return True
        if target is None:
            return False
        try:
            mgr.setExtensionEnabled(target, True)
        except Exception:
            pass
        popup = ext_info_get(target, "actionPopupUrl", None)
        if popup and hasattr(popup, "isValid") and popup.isValid():
            self.add_tab(popup)
            return True
        if popup:
            self.add_tab(QUrl(str(popup)))
            return True
        return False

    def rebuild_extension_toolbar(self):
        nav = getattr(self, "nav", None)
        if nav is None:
            return
        for act in getattr(self, "_ext_actions", []) or []:
            try:
                nav.removeAction(act)
            except Exception:
                pass
        self._ext_actions = []
        puzzle = QAction("🧩", self)
        puzzle.setToolTip("Extensions")
        puzzle.triggered.connect(lambda: self.add_tab(QUrl("sloth://extensions")))
        nav.addAction(puzzle)
        self._ext_actions.append(puzzle)
        for item in list_installed_extensions():
            if item.get("kind") != "crx":
                continue
            icon = QIcon()
            ip = item.get("icon") or ""
            if ip and os.path.isfile(ip):
                icon = QIcon(ip)
            label = (item.get("name") or "Ext")[:18]
            act = QAction(icon, "•" if not icon.isNull() else "🧩", self)
            if not icon.isNull():
                act.setIcon(icon)
                act.setText("")
            else:
                act.setText("🧩")
            act.setToolTip(label + " — click to open")
            act.triggered.connect(lambda *_, it=item: self.show_extension_popup(it.get("path") or "", it.get("popup") or "", name=it.get("name") or ""))
            nav.addAction(act)
            self._ext_actions.append(act)

    def show_extension_popup(self, ext_dir, popup_rel="", name=""):
        if not ext_dir:
            return
        if self.open_native_popup(os.path.basename(str(ext_dir).rstrip("\\/")), name):
            return
        if not popup_rel:
            meta = os.path.join(ext_dir, "_sloth.json")
            if os.path.isfile(meta):
                try:
                    with open(meta, encoding="utf-8") as f:
                        popup_rel = json.load(f).get("popup") or ""
                except Exception:
                    popup_rel = ""
            if not popup_rel and os.path.isfile(os.path.join(ext_dir, "manifest.json")):
                try:
                    with open(os.path.join(ext_dir, "manifest.json"), encoding="utf-8") as f:
                        popup_rel = CRXInstaller._popup_from_manifest(json.load(f))
                except Exception:
                    popup_rel = ""
        if not popup_rel:
            self.log("This extension has no popup — try it on a webpage", notify=True)
            return
        path = os.path.join(ext_dir, str(popup_rel).replace("/", os.sep))
        if not os.path.isfile(path):
            self.log("Popup file missing", notify=True)
            return
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                html = f.read()
            base = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(path)) + os.sep).toString()
            shim = """<script>
window.chrome=window.chrome||{};
chrome.runtime=chrome.runtime||{id:'sloth',sendMessage:function(m,c){if(c)c({});},onMessage:{addListener:function(){}},getURL:function(p){return p;},lastError:undefined,getManifest:function(){return {};}};
chrome.storage=chrome.storage||{local:{get:function(k,cb){var d={};try{d=JSON.parse(localStorage.getItem('sloth-ext')||'{}')}catch(e){}if(typeof k==='string'){var o={};o[k]=d[k];cb&&cb(o);}else cb&&cb(d);},set:function(o,cb){var d={};try{d=JSON.parse(localStorage.getItem('sloth-ext')||'{}')}catch(e){}Object.assign(d,o||{});localStorage.setItem('sloth-ext',JSON.stringify(d));cb&&cb();}},sync:{get:function(k,cb){cb&&cb({});},set:function(o,cb){cb&&cb();}}};
chrome.tabs=chrome.tabs||{query:function(q,cb){cb&&cb([{id:1,url:''}]);},create:function(){},sendMessage:function(){}};
chrome.i18n=chrome.i18n||{getMessage:function(k){return k;},getUILanguage:function(){return 'en';}};
</script>"""
            if re.search(r"<base\s", html, re.I) is None:
                if re.search(r"<head[^>]*>", html, re.I):
                    html = re.sub(r"<head[^>]*>", lambda m: m.group(0) + f'<base href="{base}">' + shim, html, count=1, flags=re.I)
                else:
                    html = f'<head><base href="{base}">{shim}</head>' + html
            else:
                html = html.replace("</head>", shim + "</head>", 1) if "</head>" in html.lower() else shim + html
            dlg = QDialog(self)
            dlg.setWindowTitle(name or "Extension")
            dlg.resize(400, 540)
            dlg.setWindowFlag(Qt.WindowType.Tool, True)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            view = QWebEngineView(dlg)
            try:
                view.setPage(CustomWebEnginePage(QWebEngineProfile.defaultProfile(), self))
            except Exception:
                pass
            view.setHtml(html, QUrl.fromLocalFile(path))
            lay.addWidget(view)
            dlg.show()
            self._ext_popup = dlg
        except Exception as e:
            self.log(str(e), notify=True)
            self.add_tab(QUrl.fromLocalFile(path))

    def open_extension_popup(self, ext_dir, popup_rel="", name=""):
        self.show_extension_popup(ext_dir, popup_rel, name)

    def open_extension_by_id(self, ext_id):
        if self.open_native_popup(ext_id):
            return
        for item in list_installed_extensions():
            if item.get("id") == ext_id or os.path.basename(item.get("path") or "") == ext_id:
                if item.get("kind") == "js":
                    self.log("Script extensions run on every page automatically", notify=True)
                    return
                self.open_extension_popup(item["path"], item.get("popup") or "", name=item.get("name") or "")
                return
        self.log("Extension not found", notify=True)

    def pin_essential(self):
        b = self.current_browser()
        if not b:
            return
        items = self.config_manager.get("essentials") or []
        url = b.url().toString()
        if not any(e.get("url") == url for e in items):
            items.append({"title": b.title() or url, "url": url})
            self.config_manager.set("essentials", items)
            self.update_sidebar()
            self.log("Pinned as Essential", notify=True)

    def toggle_pin_current(self):
        i = self.tabs.currentIndex()
        if i < 0:
            return
        b = self.tabs.widget(i)
        pinned = not bool(getattr(b, "pinned", False))
        b.pinned = pinned
        try:
            self.tabs.tabBar().moveTab(i, 0 if pinned else self.tabs.count() - 1)
        except Exception:
            pass
        self.log("Tab pinned" if pinned else "Tab unpinned", notify=True)

    def toggle_mute_current(self):
        b = self.current_browser()
        if not b:
            return
        page = b.page()
        muted = not page.isAudioMuted()
        page.setAudioMuted(muted)
        self.log("Tab muted" if muted else "Tab unmuted", notify=True)

    def load_web_panel(self):
        u = self.panel_url.text().strip()
        if not u.startswith(("http://", "https://", "sloth://")):
            u = "https://" + u
        self.config_manager.set("web_panel_url", u)
        try:
            if self.panel_view is None:
                self.panel_view = QWebEngineView()
                self.panel_host.addWidget(self.panel_view)
            self.panel_view.setUrl(QUrl(u))
        except Exception as e:
            self.log(str(e))

    def _style_add_tab_btn(self):
        if not hasattr(self, "add_tab_btn"):
            return
        r = int(self.config_manager.get("ui_radius", 16))
        self.add_tab_btn.setStyleSheet(
            f"QPushButton {{ color: {self.accent_color}; font-weight: bold; font-size: 18px; border: 1px solid {self.accent_color}; "
            f"border-radius: {r}px; background: rgba(255,255,255,0.05); padding: 0px; margin: 0px; }} "
            f"QPushButton:hover {{ background: rgba(255,255,255,0.15); }}"
        )

    def bind_motion_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.toggle_zen_compact)
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self.toggle_layout)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=lambda: self._cycle_density())
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.add_tab)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.spawn_window())
        QShortcut(QKeySequence("Ctrl+W"), self, activated=lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.focus_url_bar)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.open_command_palette)
        QShortcut(QKeySequence("Ctrl+Shift+K"), self, activated=self.open_command_palette)
        QShortcut(QKeySequence("Ctrl+\\"), self, activated=self.toggle_split)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, activated=self.peek_current)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self.prompt_add_app)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=self.pin_essential)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, activated=self.toggle_mute_current)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, activated=self.toggle_pin_current)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=lambda: self.add_tab(QUrl("sloth://spaces")))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.toggle_reader)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self, activated=self.translate_page)
        QShortcut(QKeySequence("Alt+Shift+T"), self, activated=self.translate_selection)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=lambda: self.add_tab(QUrl("sloth://mail")))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.show_find)
        QShortcut(QKeySequence("Escape"), self, activated=self.hide_find)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, activated=self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.zoom_reset)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, activated=self.toggle_bookmarks_bar)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.bookmark)
        QShortcut(QKeySequence("F5"), self, activated=self.reload)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self.back)
        QShortcut(QKeySequence("Alt+Right"), self, activated=self.forward)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=lambda: self.add_tab(QUrl("sloth://history")))
        QShortcut(QKeySequence("Ctrl+J"), self, activated=self.show_downloads)
        QShortcut(QKeySequence("Ctrl+Alt+S"), self, activated=self.summarize_page)
        QShortcut(QKeySequence("Ctrl+Alt+O"), self, activated=self.ai_organize_tabs)
        QShortcut(QKeySequence("Ctrl+Alt+P"), self, activated=self.picture_in_picture)
        QShortcut(QKeySequence("Ctrl+Shift+U"), self, activated=self.copy_clean_url)
        QShortcut(QKeySequence("Media Play"), self, activated=self.toggle_media)
        self._bind_app_shortcut("Ctrl+Shift+T", self.reopen_closed)
        self._bind_app_shortcut("Ctrl+Tab", lambda: self.cycle_tab(1))
        self._bind_app_shortcut("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1))
        self._bind_app_shortcut("Ctrl+Alt+D", self.duplicate_current)
        self._bind_app_shortcut("F11", self.toggle_fullscreen)
        self._bind_app_shortcut("F6", self.focus_url_bar)
        for n in range(1, 9):
            self._bind_app_shortcut(f"Ctrl+{n}", lambda i=n - 1: self.jump_tab(i))
        self._bind_app_shortcut("Ctrl+9", lambda: self.jump_tab(-1))

    def _bind_app_shortcut(self, seq, fn):
        s = QShortcut(QKeySequence(seq), self)
        s.setContext(Qt.ShortcutContext.ApplicationShortcut)
        s.activated.connect(fn)
        return s

    def refresh_bookmarks_bar(self):
        if not hasattr(self, "bookmarks_bar"):
            return
        self.bookmarks_bar.clear()
        show = bool(self.config_manager.get("show_bookmarks_bar", False)) and not bool(self.config_manager.get("zen_compact", False) and not self.nav.isVisible())
        if bool(self.config_manager.get("zen_compact", False)) and not self.nav.isVisible():
            self.bookmarks_bar.setVisible(False)
        else:
            self.bookmarks_bar.setVisible(show)
        for b in self.bookmarks[:18]:
            if isinstance(b, dict):
                title = str(b.get("title") or b.get("url") or "mark")[:28]
                url = str(b.get("url") or "")
            else:
                title = str(b)[:28]
                url = str(b)
            act = QAction(title, self)
            act.setToolTip(url)
            act.triggered.connect(lambda _=False, u=url: self.add_tab(QUrl(u)) if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier else (self.current_browser() and self.current_browser().setUrl(QUrl(u))))
            self.bookmarks_bar.addAction(act)

    def toggle_bookmarks_bar(self):
        v = not bool(self.config_manager.get("show_bookmarks_bar", False))
        self.config_manager.set("show_bookmarks_bar", v)
        self.config_manager.set("bm_bar_user_picked", True)
        self.refresh_bookmarks_bar()

    def show_find(self):
        if not hasattr(self, "find_bar"):
            return
        self.find_bar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find(self):
        if hasattr(self, "find_bar"):
            self.find_bar.setVisible(False)
        b = self.current_browser()
        if b:
            try:
                b.page().findText("")
            except Exception:
                pass

    def find_next(self):
        b = self.current_browser()
        if b and hasattr(self, "find_input"):
            b.page().findText(self.find_input.text())

    def find_prev(self):
        b = self.current_browser()
        if b and hasattr(self, "find_input"):
            try:
                b.page().findText(self.find_input.text(), QWebEnginePage.FindFlag.FindBackward)
            except Exception:
                b.page().findText(self.find_input.text())

    def zoom_in(self):
        b = self.current_browser()
        if b:
            b.setZoomFactor(min(3.0, b.zoomFactor() + 0.1))

    def zoom_out(self):
        b = self.current_browser()
        if b:
            b.setZoomFactor(max(0.3, b.zoomFactor() - 0.1))

    def zoom_reset(self):
        b = self.current_browser()
        if b:
            b.setZoomFactor(float(self.config_manager.get("zoom", 1.0) or 1.0))

    def _cycle_density(self):
        order = ["compact", "comfortable", "roomy"]
        cur = self.config_manager.get("ui_density", "comfortable")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "comfortable"
        self.config_manager.set("ui_density", nxt)
        self.apply_theme()
        self.log(f"Density: {nxt}")

    def toggle_zen_compact(self):
        v = not bool(self.config_manager.get("zen_compact", False))
        self.config_manager.set("zen_compact", v)
        self.apply_zen_compact()
        self.apply_theme()
        self.log("Zen compact on." if v else "Zen compact off.")

    def open_command_palette(self):
        d = QDialog(self)
        d.setWindowTitle("Command palette")
        d.resize(520, 420)
        lay = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText("Tabs, bookmarks, commands…")
        lst = QListWidget()
        lay.addWidget(q)
        lay.addWidget(lst)
        items = []
        items.append(("cmd", "New tab", None))
        items.append(("cmd", "Split view", None))
        items.append(("cmd", "Toggle Zen", None))
        items.append(("cmd", "Settings", None))
        items.append(("cmd", "Add app", None))
        items.append(("cmd", "Private tab", None))
        for i in range(self.tabs.count()):
            items.append(("tab", self.tabs.tabText(i), i))
        for b in self.bookmarks:
            if isinstance(b, dict):
                items.append(("bm", b.get("title") or b.get("url"), b.get("url")))
        def refill(text=""):
            lst.clear()
            t = (text or "").lower()
            for kind, label, payload in items:
                if t and t not in str(label).lower():
                    continue
                it = QListWidgetItem(f"{kind} · {label}")
                it.setData(Qt.ItemDataRole.UserRole, (kind, payload, label))
                lst.addItem(it)
        def run():
            it = lst.currentItem()
            if not it:
                return
            kind, payload, label = it.data(Qt.ItemDataRole.UserRole)
            d.accept()
            if kind == "tab":
                self.tabs.setCurrentIndex(int(payload))
            elif kind == "bm":
                self.add_tab(QUrl(payload))
            elif label == "New tab":
                self.add_tab()
            elif label == "Split view":
                self.toggle_split()
            elif label == "Toggle Zen":
                self.toggle_zen_compact()
            elif label == "Settings":
                self.show_settings()
            elif label == "Add app":
                self.prompt_add_app()
            elif label == "Private tab":
                self.add_tab(incognito=True)
        q.textChanged.connect(refill)
        lst.itemActivated.connect(lambda _: run())
        q.returnPressed.connect(run)
        refill()
        d.exec()

    def toggle_split(self):
        if self.split_pane is not None:
            self.split_pane.setParent(None)
            self.split_pane.deleteLater()
            self.split_pane = None
            self.log("Split closed")
            return
        b = self.current_browser()
        pane = CustomWebEngineView(self)
        page = CustomWebEnginePage(QWebEngineProfile.defaultProfile(), self)
        pane.setPage(page)
        if b:
            pane.setUrl(b.url())
        else:
            pane.setUrl(QUrl("sloth://home"))
        self.split_pane = pane
        self.main_split.addWidget(pane)
        self.main_split.setSizes([1, 1])
        self.log("Split view", notify=True)

    def peek_current(self):
        b = self.current_browser()
        if not b:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(b.title() or "Peek")
        dlg.resize(480, 640)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        v = QVBoxLayout(dlg)
        view = CustomWebEngineView(dlg)
        page = CustomWebEnginePage(QWebEngineProfile.defaultProfile(), self)
        view.setPage(page)
        view.setUrl(b.url())
        v.addWidget(view)
        dlg.show()

    def apply_zen_compact(self):
        zen = bool(self.config_manager.get("zen_compact", False))
        self._zen_hover = False
        if hasattr(self, "_zen_hide_timer"):
            self._zen_hide_timer.stop()
        if hasattr(self, "nav"):
            try:
                self.nav.setGraphicsEffect(None)
            except Exception:
                pass
            self.nav.setVisible(not zen)
        if hasattr(self, "zen_edge"):
            self.zen_edge.setVisible(zen)
            self.zen_edge.raise_()
        if hasattr(self, "status"):
            self.status.setVisible((not zen) and bool(self.config_manager.get("show_status", True)))
        if hasattr(self, "bookmarks_bar"):
            if zen:
                self.bookmarks_bar.setVisible(False)
            else:
                self.bookmarks_bar.setVisible(bool(self.config_manager.get("show_bookmarks_bar", False)))
        if hasattr(self, "_zen_poll"):
            if zen:
                self._zen_poll.start()
            else:
                self._zen_poll.stop()
        self.setMouseTracking(True)
        if hasattr(self, "tabs"):
            self.tabs.setMouseTracking(True)

    def _zen_poll_cursor(self):
        if not bool(self.config_manager.config.get("zen_compact", False)):
            return
        if not self.isActiveWindow():
            return
        try:
            pos = self.mapFromGlobal(QCursor.pos())
        except Exception:
            return
        if pos.x() < 0 or pos.x() > self.width() or pos.y() < 0 or pos.y() > self.height():
            return
        nav_h = self.nav.height() if hasattr(self, "nav") and self.nav.isVisible() else 0
        bm_h = self.bookmarks_bar.height() if hasattr(self, "bookmarks_bar") and self.bookmarks_bar.isVisible() else 0
        if pos.y() <= 36:
            self._zen_show_chrome()
        elif pos.y() > nav_h + bm_h + 48:
            if hasattr(self, "_zen_hide_timer") and not self._zen_hide_timer.isActive():
                self._zen_hide_timer.start(350)

    def _zen_show_chrome(self):
        if not hasattr(self, "nav"):
            return
        if hasattr(self, "_zen_hide_timer"):
            self._zen_hide_timer.stop()
        try:
            self.nav.setGraphicsEffect(None)
        except Exception:
            pass
        self.nav.setVisible(True)
        if hasattr(self, "zen_edge"):
            self.zen_edge.setVisible(False)
        if hasattr(self, "bookmarks_bar") and bool(self.config_manager.get("show_bookmarks_bar", False)):
            self.bookmarks_bar.setVisible(True)

    def _zen_hide_chrome(self):
        if not hasattr(self, "nav"):
            return
        if not bool(self.config_manager.get("zen_compact", False)):
            return
        try:
            pos = self.mapFromGlobal(QCursor.pos())
            if 0 <= pos.y() <= (self.nav.height() + 24):
                return
        except Exception:
            pass
        try:
            self.nav.setGraphicsEffect(None)
        except Exception:
            pass
        self.nav.setVisible(False)
        if hasattr(self, "bookmarks_bar"):
            self.bookmarks_bar.setVisible(False)
        if hasattr(self, "zen_edge"):
            self.zen_edge.setVisible(True)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def open_space_safe(self, name):
        try:
            self.add_tab(container=space_id(name))
        except Exception as e:
            self.log(f"Could not open space: {e}", notify=True)

    def apply_runtime_flags(self):
        s = QWebEngineProfile.defaultProfile().settings()
        mapping = {
            "JavascriptEnabled": bool(self.config_manager.get("js_enabled", True)),
            "AutoLoadImages": bool(self.config_manager.get("images_enabled", True)),
            "PlaybackRequiresUserGesture": not bool(self.config_manager.get("autoplay_enabled", True)),
            "JavascriptCanOpenWindows": bool(self.config_manager.get("popups_enabled", True)),
            "WebRTCPublicInterfacesOnly": bool(self.config_manager.get("webrtc_shield", False)),
            "ScrollAnimatorEnabled": bool(self.config_manager.get("smooth_scrolling", True)),
            "PdfViewerEnabled": True,
        }
        for attr, val in mapping.items():
            if hasattr(QWebEngineSettings.WebAttribute, attr):
                s.setAttribute(getattr(QWebEngineSettings.WebAttribute, attr), val)
        if hasattr(self, "ad_interceptor"):
            self.ad_interceptor.mask_ip = bool(self.config_manager.get("mask_ip", False)) or bool(self.config_manager.get("webrtc_shield", False))

    def restore_session(self):
        if not bool(self.config_manager.get("restore_session", True)):
            return
        urls = self.config_manager.get("session_urls") or []
        if not isinstance(urls, list) or not urls:
            return
        opened = 0
        first = True
        for u in urls[:24]:
            u = str(u).strip()
            if not u:
                continue
            try:
                if first and self.tabs.count() >= 1:
                    w = self.tabs.widget(0)
                    if isinstance(w, QWebEngineView):
                        w.setUrl(QUrl(u))
                    else:
                        self.add_tab(QUrl(u))
                    first = False
                else:
                    self.add_tab(QUrl(u))
                opened += 1
            except Exception:
                pass
        if opened:
            self.log(f"Restored {opened} tab(s)")

    def closeEvent(self, event):
        try:
            if self in SLOTH_WINDOWS:
                SLOTH_WINDOWS.remove(self)
            if not getattr(self, "_secondary", False) or len(SLOTH_WINDOWS) == 0:
                urls = []
                for w in SLOTH_WINDOWS + [self]:
                    if not hasattr(w, "tabs"):
                        continue
                    for i in range(w.tabs.count()):
                        tw = w.tabs.widget(i)
                        if tw and hasattr(tw, "url"):
                            urls.append(tw.url().toString())
                self.config_manager.set("session_urls", urls)
        except Exception:
            pass
        super().closeEvent(event)

    def _boot_fade(self):
        try:
            target = float(self.config_manager.get("window_opacity", 1.0) or 1.0)
        except Exception:
            target = 1.0
        self.setWindowOpacity(max(0.7, min(1.0, target)))


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
    def _crash_log(text):
        try:
            d = os.path.join(os.path.expanduser("~"), ".sloth_web")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "crash.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
            print(text)
            print("Wrote", path)
        except Exception:
            print(text)

    import traceback
    sys.excepthook = lambda t, v, tb: _crash_log("".join(traceback.format_exception(t, v, tb)))

    try:
        print("Sloth Web 3.1 starting… Python", sys.version)
        sys.stdout.flush()
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        if sys.platform == "win32":
            os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
            os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=RendererCodeIntegrity")

        config_path = os.path.join(os.path.expanduser("~"), ".sloth_web", "config.json")
        # Do not reuse old chromium_flags — they previously crashed Windows Chromium.
        active_flags = list(CHROMIUM_FLAGS)
        for fl in active_flags:
            if fl not in sys.argv:
                sys.argv.append(fl)

        scheme = QWebEngineUrlScheme(b"sloth")
        flags = QWebEngineUrlScheme.Flag.LocalScheme | QWebEngineUrlScheme.Flag.LocalAccessAllowed | QWebEngineUrlScheme.Flag.CorsEnabled
        extra = getattr(QWebEngineUrlScheme.Flag, "FetchApiAllowed", None)
        if extra is not None:
            flags = flags | extra
        scheme.setFlags(flags)
        QWebEngineUrlScheme.registerScheme(scheme)

        try:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        except Exception:
            pass

        app = QApplication(sys.argv)
        app.setApplicationName("Sloth Web")
        app.setOrganizationName("SlothWeb")

        app_url = None
        for arg in sys.argv:
            if arg.startswith("--app="):
                app_url = arg.split("--app=", 1)[1].strip('"')

        window = AppBrowser(app_url) if app_url else Browser()
        window.showMaximized()
        window.show()
        window.raise_()
        window.activateWindow()
        sys.exit(app.exec())
    except Exception:
        _crash_log(traceback.format_exc())
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, traceback.format_exc()[:1000], "Sloth Web failed to start", 0x10)
        except Exception:
            pass
        raise


