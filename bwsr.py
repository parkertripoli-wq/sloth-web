import sys
import os
import json
import requests
from PyQt5.QtCore import QUrl, Qt, QDir, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QToolBar, QAction, QStatusBar, QFileDialog, QDialog, QListWidget, QDialogButtonBox, QVBoxLayout, QWidget, QTabWidget, QPushButton, QMenu, QProgressBar, QHBoxLayout, QTabBar, QLabel, QTextEdit, QMessageBox, QSlider, QCheckBox, QColorDialog, QInputDialog, QFormLayout, QGroupBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineDownloadItem
from PyQt5.QtGui import QIcon, QPalette, QColor, QCursor
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor

class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None, enabled=True, privacy_enabled=False):
        super().__init__(parent)
        self.enabled = enabled
        self.privacy_enabled = privacy_enabled
        self.blocked_domains = [
            "||adtago.s3.amazonaws.com^", "||analyticsengine.s3.amazonaws.com^", "||analytics.s3.amazonaws.com^",
            "||advice-ads.s3.amazonaws.com^", "||pagead2.googlesyndication.com^", "||adservice.google.com^",
            "||pagead2.googleadservices.com^", "||afs.googlesyndication.com^", "||stats.g.doubleclick.net^",
            "||ad.doubleclick.net^", "||static.doubleclick.net^", "||m.doubleclick.net^", "||mediavisor.doubleclick.net^",
            "||ads30.adcolony.com^", "||adc3-launch.adcolony.com^", "||events3alt.adcolony.com^", "||wd.adcolony.com^",
            "||static.media.net^", "||media.net^", "||adservetx.media.net^", "||analytics.google.com^",
            "||click.googleanalytics.com^", "||google-analytics.com^", "||ssl.google-analytics.com^", "||adm.hotjar.com^",
            "||identify.hotjar.com^", "||insights.hotjar.com^", "||script.hotjar.com^", "||surveys.hotjar.com^",
            "||careers.hotjar.com^", "||events.hotjar.io^", "||mouseflow.com^", "||cdn.mouseflow.com^",
            "||o2.mouseflow.com^", "||gtm.mouseflow.com^", "||api.mouseflow.com^", "||tools.mouseflow.com^",
            "||cdn-test.mouseflow.com^", "||freshmarketer.com^", "||claritybt.freshmarketer.com^",
            "||fwtracks.freshmarketer.com^", "||luckyorange.com^", "||api.luckyorange.com^", "||realtime.luckyorange.com^",
            "||cdn.luckyorange.com^", "||w1.luckyorange.com^", "||upload.luckyorange.net^", "||cs.luckyorange.net^",
            "||settings.luckyorange.net^", "||stats.wp.com^", "||notify.bugsnag.com^", "||sessions.bugsnag.com^",
            "||api.bugsnag.com^", "||app.bugsnag.com^", "||browser.sentry-cdn.com^", "||app.getsentry.com^",
            "||pixel.facebook.com^", "||an.facebook.com^", "||static.ads-twitter.com^", "||ads-api.twitter.com^",
            "||ads.linkedin.com^", "||analytics.pointdrive.linkedin.com^", "||ads.pinterest.com^", "||log.pinterest.com^",
            "||analytics.pinterest.com^", "||trk.pinterest.com^", "||events.reddit.com^", "||events.redditmedia.com^",
            "||ads.youtube.com^", "||ads-api.tiktok.com^", "||analytics.tiktok.com^", "||ads-sg.tiktok.com^",
            "||analytics-sg.tiktok.com^", "||business-api.tiktok.com^", "||ads.tiktok.com^", "||log.byteoversea.com^",
            "||ads.yahoo.com^", "||analytics.yahoo.com^", "||geo.yahoo.com^", "||udcm.yahoo.com^",
            "||analytics.query.yahoo.com^", "||partnerads.ysm.yahoo.com^", "||log.fc.yahoo.com^", "||gemini.yahoo.com^",
            "||adtech.yahooinc.com^", "||extmaps-api.yandex.net^", "||appmetrica.yandex.ru^", "||adfstat.yandex.ru^",
            "||metrika.yandex.ru^", "||offerwall.yandex.net^", "||adfox.yandex.ru^", "||auction.unityads.unity3d.com^",
            "||webview.unityads.unity3d.com^", "||config.unityads.unity3d.com^", "||adserver.unityads.unity3d.com^",
            "||iot-eu-logser.realme.com^", "||iot-logser.realme.com^", "||bdapi-ads.realmemobile.com^",
            "||bdapi-in-ads.realmemobile.com^", "||api.ad.xiaomi.com^", "||data.mistat.xiaomi.com^",
            "||data.mistat.india.xiaomi.com^", "||data.mistat.rus.xiaomi.com^", "||sdkconfig.ad.xiaomi.com^",
            "||sdkconfig.ad.intl.xiaomi.com^", "||tracking.rus.miui.com^", "||adsfs.oppomobile.com^",
            "||adx.ads.oppomobile.com^", "||ck.ads.oppomobile.com^", "||data.ads.oppomobile.com^",
            "||metrics.data.hicloud.com^", "||metrics2.data.hicloud.com^", "||grs.hicloud.com^",
            "||logservice.hicloud.com^", "||logservice1.hicloud.com^", "||logbak.hicloud.com^", "||click.oneplus.cn^",
            "||open.oneplus.net^", "||samsungads.com^", "||smetrics.samsung.com^", "||nmetrics.samsung.com^",
            "||samsung-com.112.2o7.net^", "||analytics-api.samsunghealthcn.com^", "||iadsdk.apple.com^",
            "||metrics.icloud.com^", "||metrics.mzstatic.com^", "||api-adservices.apple.com^",
            "||books-analytics-events.apple.com^", "||weather-analytics-events.apple.com^",
            "||notes-analytics-events.apple.com^"
        ]

    def interceptRequest(self, info):
        if self.enabled:
            url = info.requestUrl().toString()
            for rule in self.blocked_domains:
                if rule.startswith("||") and rule.endswith("^"):
                    domain = rule[2:-1]
                    if domain in url:
                        if self.privacy_enabled:
                            reply = QMessageBox.question(None, "Privacy Alert", f"Site {domain} is attempting to access your data. Allow?", QMessageBox.Yes | QMessageBox.No)
                            if reply == QMessageBox.No:
                                info.block(True)
                                print(f"Blocked privacy tracker: {url}")
                                return
                        else:
                            info.block(True)
                            print(f"Blocked network: {url}")
                            return
            if "youtube.com" in url and any(ad_term in url.lower() for ad_term in ["/get_video_info", "/ptracking", "/pagead/", "/ads", "admodule"]):
                info.block(True)
                print(f"Blocked YouTube ad: {url}")

class CosmeticFilterScript(QWebEngineScript):
    def __init__(self, parent=None):
        super().__init__()
        self.setName("CosmeticFilterScript")
        self.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self.setWorldId(QWebEngineScript.MainWorld)
        css = """
            /* General ad hiding */
            .adbox, .banner_ads, .adsbox, .textads, .video-ads, #masthead-ad, .ytp-ad-module {
                display: none !important;
            }
            /* Site-specific rules */
            adblock.turtlecute.org##.adbox.banner_ads.adsbox
            d3ward.github.io##.textads
            /* YouTube cosmetic filters */
            ytd-page-manager#cinematic-container > .ytd-watch-flexy[overlay-style="AD"] {
                display: none !important;
            }
            ytd-player-legacy-ad-slot-renderer, .ytd-player-legacy-ad-slot-renderer {
                display: none !important;
            }
        """
        self.setSourceCode(f"""
            var style = document.createElement('style');
            style.textContent = `{css}`;
            var head = document.head || document.documentElement;
            if (head) head.appendChild(style);
            else document.addEventListener('DOMContentLoaded', function() {{
                var head = document.head || document.documentElement;
                if (head) head.appendChild(style);
            }});
        """)

class DownloadManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Manager")
        self.setMinimumWidth(400)
        layout = QVBoxLayout()
        self.download_list = QListWidget()
        layout.addWidget(self.download_list)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.downloads = []
        self.parent().current_browser().page().profile().downloadRequested.connect(self.add_download)

    def add_download(self, download):
        self.downloads.append(download)
        item = QListWidgetItem(f"{download.path()} - {download.totalBytes()} bytes")
        self.download_list.addItem(item)
        download.downloadProgress.connect(lambda received, total: self.update_progress(item, received, total))
        download.finished.connect(lambda: self.update_status(item, "Completed"))
        download.stateChanged.connect(lambda state: self.update_status(item, "Cancelled") if state == QWebEngineDownloadItem.DownloadCancelled else None)
        download.accept()

    def update_progress(self, item, received, total):
        item.setText(f"{item.text().split(' - ')[0]} - {received}/{total} bytes")

    def update_status(self, item, status):
        current_text = item.text()
        if status in current_text:
            return
        new_text = f"{current_text} - {status}"
        item.setText(new_text)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sloth Web Settings")
        layout = QVBoxLayout()
        self.ad_block_toggle = QPushButton("Toggle Ad Blocker (Enabled)")
        self.ad_block_toggle.clicked.connect(self.toggle_ad_blocker)
        layout.addWidget(self.ad_block_toggle)
        self.theme_select = QPushButton("Switch Theme (Dark)")
        self.theme_select.clicked.connect(self.switch_theme)
        layout.addWidget(self.theme_select)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.parent().ad_block_enabled = True
        self.parent().dark_theme = True

    def toggle_ad_blocker(self):
        self.parent().ad_block_enabled = not self.parent().ad_block_enabled
        self.ad_block_toggle.setText(f"Toggle Ad Blocker ({'Enabled' if self.parent().ad_block_enabled else 'Disabled'})")
        for i in range(self.parent().tab_widget.count()):
            browser = self.parent().tab_widget.widget(i).layout().itemAt(0).widget()
            profile = browser.page().profile()
            interceptor = AdBlockInterceptor(self.parent(), self.parent().ad_block_enabled, self.parent().privacy_enabled)
            profile.setUrlRequestInterceptor(interceptor)

    def switch_theme(self):
        self.parent().dark_theme = not self.parent().dark_theme
        self.theme_select.setText(f"Switch Theme ({'Dark' if self.parent().dark_theme else 'Light'})")
        self.parent().apply_theme()

class BookmarkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sloth Web Bookmarks")
        self.setMinimumWidth(400)
        layout = QVBoxLayout()
        self.bookmark_list = QListWidget()
        self.bookmarks = parent.bookmarks
        for url in self.bookmarks:
            self.bookmark_list.addItem(url)
        self.bookmark_list.itemDoubleClicked.connect(self.load_bookmark)
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_bookmark)
        layout.addWidget(self.bookmark_list)
        layout.addWidget(self.delete_btn)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def load_bookmark(self, item):
        self.parent().current_browser().setUrl(QUrl(item.text()))
        self.accept()

    def delete_bookmark(self):
        selected = self.bookmark_list.currentItem()
        if selected:
            url = selected.text()
            self.bookmarks.remove(url)
            self.bookmark_list.takeItem(self.bookmark_list.currentRow())
            self.parent().save_bookmarks()
            self.parent().status.showMessage(f"Deleted bookmark: {url}")

class CustomWebEnginePage(QWebEnginePage):
    linkHovered = pyqtSignal(str)

    def __init__(self, parent=None, incognito=False):
        super().__init__(parent)
        self.parent = parent
        self.incognito = incognito
        self.profile().scripts().insert(CosmeticFilterScript(self))
        self.linkHovered.connect(self.handle_link_hovered)
        if incognito:
            self.profile().setHttpCacheType(QWebEngineProfile.NoCache)
            self.profile().setPersistentStoragePath("")

    def createStandardContextMenu(self):
        menu = super().createStandardContextMenu()
        if menu is None:
            from PyQt5.QtWidgets import QMenu
            menu = QMenu(self.view())
        save_image_action = QAction("Save Image As...", self)
        save_image_action.triggered.connect(self.save_image)
        menu.addAction(save_image_action)
        inspect_action = QAction("Inspect", self)
        inspect_action.triggered.connect(self.inspect_element)
        menu.addAction(inspect_action)
        view_source_action = QAction("View Page Source", self)
        view_source_action.triggered.connect(self.view_page_source)
        menu.addAction(view_source_action)
        if self.current_link:
            new_tab_action = QAction("Open Link in New Tab", self)
            new_tab_action.triggered.connect(self.open_link_in_new_tab)
            menu.addAction(new_tab_action)
            new_window_action = QAction("Open Link in New Window", self)
            new_window_action.triggered.connect(self.open_link_in_new_window)
            menu.addAction(new_window_action)
        return menu

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            self.current_link = url.toString()
            self.linkHovered.emit(self.current_link)
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def handle_link_hovered(self, link):
        self.current_link = link if link else None

    def save_image(self):
        self.triggerAction(QWebEnginePage.WebAction.CopyImageUrlToClipboard)
        clipboard = QApplication.clipboard()
        image_url = clipboard.text()
        if image_url:
            file_path, _ = QFileDialog.getSaveFileName(self.view(), "Save Image As", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if file_path:
                self.profile().downloadRequested.connect(lambda item: self.handle_download(item, file_path))
                self.view().page().download(QUrl(image_url), file_path)

    def inspect_element(self):
        print("Attempting to inspect element...")
        try:
            self.triggerAction(QWebEnginePage.InspectElement)
        except Exception as e:
            print(f"InspectElement failed: {e}")

    def view_page_source(self):
        print("Attempting to view page source...")
        try:
            QTimer.singleShot(0, lambda: self.toHtml(self.show_source_dialog))
        except Exception as e:
            print(f"View Page Source failed: {e}")

    def show_source_dialog(self, html):
        if html:
            dialog = QDialog(self.view())
            dialog.setWindowTitle("Page Source")
            layout = QVBoxLayout()
            source_view = QTextEdit()
            source_view.setPlainText(html)
            layout.addWidget(source_view)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            dialog.setLayout(layout)
            dialog.setMinimumSize(600, 400)
            dialog.exec_()
        else:
            print("No HTML content retrieved")

    def open_link_in_new_tab(self):
        if self.current_link:
            self.parent.add_new_tab(QUrl(self.current_link), self.incognito)

    def open_link_in_new_window(self):
        if self.current_link:
            from browser import Browser
            new_window = Browser()
            new_window.add_new_tab(QUrl(self.current_link), True)
            new_window.show()

    def handle_download(self, download, file_path):
        download.setPath(file_path)
        download.accept()
        download.finished.connect(lambda: self.view().parent().status.showMessage(f"Saved image to {file_path}"))

class UpdateManager:
    def __init__(self, parent):
        self.parent = parent
        self.local_version = "1.0.4"
        self.version_url = "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/version.txt"
        self.update_url = "https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/bwsr.py"
        self.script_path = os.path.abspath(__file__)

    def check_for_updates(self):
        try:
            response = requests.get(self.version_url, timeout=5)
            response.raise_for_status()
            remote_version = response.text.strip()
            print(f"Local version: {self.local_version}, Remote version: {remote_version}")
            if remote_version > self.local_version:
                reply = QMessageBox.question(self.parent, "Update Available", f"A new version ({remote_version}) is available. Would you like to update now?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.perform_update(remote_version)
            else:
                self.parent.status.showMessage("No updates available.")
        except requests.RequestException as e:
            print(f"Update check failed: {e}")
            self.parent.status.showMessage("Failed to check for updates.")

    def perform_update(self, remote_version):
        try:
            backup_path = self.script_path + ".bak"
            with open(self.script_path, "rb") as f:
                backup_data = f.read()
            with open(backup_path, "wb") as f:
                f.write(backup_data)
            response = requests.get(self.update_url, timeout=5)
            response.raise_for_status()
            new_script = response.content
            with open(self.script_path, "wb") as f:
                f.write(new_script)
            self.parent.status.showMessage(f"Updated to version {remote_version}. Restart the application.")
            QMessageBox.information(self.parent, "Update Complete", "Please restart the application to apply the update.")
        except requests.RequestException as e:
            print(f"Update download failed: {e}")
            self.parent.status.showMessage("Update failed. Reverting to backup.")
            with open(self.script_path, "wb") as f:
                f.write(backup_data)
        except Exception as e:
            print(f"Update error: {e}")
            self.parent.status.showMessage("Update failed. Check console for details.")

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "sloth_web.ico")
        self.setWindowIcon(QIcon(icon_path) if os.path.exists(icon_path) else QIcon())
        self.setWindowTitle("Sloth Web")
        self.showMaximized()
        self.bookmarks_file = os.path.join(script_dir, "bookmarks.json")
        self.bookmarks = self.load_bookmarks()
        self.history = []
        self.downloads = []
        self.ad_block_enabled = True
        self.dark_theme = True
        self.privacy_enabled = False
        self.window_color = QColor(53, 53, 53) if self.dark_theme else QColor(240, 240, 240)
        self.text_color = Qt.white if self.dark_theme else Qt.black
        self.zoom_factor = 1.0
        self.fun_mode = False  # Initialize fun_mode here
        self.update_manager = UpdateManager(self)
        nav_bar = QToolBar("Navigation")
        nav_bar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, nav_bar)
        back_btn = QAction("⬅️", self)
        back_btn.setToolTip("Back")
        back_btn.setShortcut("Alt+Left")
        back_btn.triggered.connect(self.navigate_back)
        nav_bar.addAction(back_btn)
        forward_btn = QAction("➡️", self)
        forward_btn.setToolTip("Forward")
        forward_btn.setShortcut("Alt+Right")
        forward_btn.triggered.connect(self.navigate_forward)
        nav_bar.addAction(forward_btn)
        reload_btn = QAction("🔄", self)
        reload_btn.setToolTip("Reload")
        reload_btn.setShortcut("Ctrl+R")
        reload_btn.triggered.connect(self.reload_page)
        nav_bar.addAction(reload_btn)
        home_btn = QAction("🏠", self)
        home_btn.setToolTip("Home")
        home_btn.setShortcut("Ctrl+H")
        home_btn.triggered.connect(self.navigate_home)
        nav_bar.addAction(home_btn)
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter URL...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)
        nav_bar.addWidget(self.progress_bar)
        new_tab_btn = QAction("➕", self)
        new_tab_btn.setToolTip("New Tab")
        new_tab_btn.setShortcut("Ctrl+T")
        new_tab_btn.triggered.connect(self.add_new_tab)
        nav_bar.addAction(new_tab_btn)
        save_page_btn = QAction("💾", self)
        save_page_btn.setToolTip("Save Page")
        save_page_btn.setShortcut("Ctrl+S")
        save_page_btn.triggered.connect(self.save_page_as)
        nav_bar.addAction(save_page_btn)
        bookmark_btn = QAction("🔖", self)
        bookmark_btn.setToolTip("Add Bookmark")
        bookmark_btn.setShortcut("Ctrl+B")
        bookmark_btn.triggered.connect(self.add_bookmark)
        nav_bar.addAction(bookmark_btn)
        bookmarks_btn = QAction("📑", self)
        bookmarks_btn.setToolTip("Show Bookmarks")
        bookmarks_btn.setShortcut("Ctrl+Shift+B")
        bookmarks_btn.triggered.connect(self.show_bookmarks)
        nav_bar.addAction(bookmarks_btn)
        history_btn = QAction("🕘", self)
        history_btn.setToolTip("Show History")
        history_btn.triggered.connect(self.show_history)
        nav_bar.addAction(history_btn)
        settings_btn = QAction("⚙️", self)
        settings_btn.setToolTip("Settings")
        settings_btn.triggered.connect(self.show_settings)
        nav_bar.addAction(settings_btn)
        download_mgr_btn = QAction("⬇️", self)
        download_mgr_btn.setToolTip("Download Manager")
        download_mgr_btn.triggered.connect(self.show_download_manager)
        nav_bar.addAction(download_mgr_btn)
        update_btn = QAction("🔄 Update", self)
        update_btn.setToolTip("Check for Updates")
        update_btn.triggered.connect(self.update_manager.check_for_updates)
        nav_bar.addAction(update_btn)
        page_settings_btn = QAction("🗏", self)
        page_settings_btn.setToolTip("Page Settings")
        page_settings_btn.triggered.connect(self.show_page_settings)
        nav_bar.addAction(page_settings_btn)
        privacy_btn = QAction("🕶️", self)
        privacy_btn.setToolTip("Toggle Privacy")
        privacy_btn.triggered.connect(self.toggle_privacy)
        nav_bar.addAction(privacy_btn)
        incognito_btn = QAction("Incognito", self)
        incognito_btn.setToolTip("Toggle Incognito")
        incognito_btn.triggered.connect(self.toggle_incognito)
        nav_bar.addAction(incognito_btn)
        fun_btn = QAction("🎉 Fun Mode", self)
        fun_btn.setToolTip("Enable Fun Features")
        fun_btn.triggered.connect(self.toggle_fun_mode)
        nav_bar.addAction(fun_btn)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.update_url_bar)
        self.add_new_tab()
        self.setCentralWidget(self.tab_widget)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.current_browser().loadProgress.connect(self.update_progress)
        self.current_browser().loadFinished.connect(self.on_load_finished)
        self.current_browser().urlChanged.connect(self.update_url)
        self.current_browser().page().profile().downloadRequested.connect(self.add_download)
        self.apply_theme()

    def current_browser(self):
        widget = self.tab_widget.currentWidget()
        if widget and widget.layout():
            return widget.layout().itemAt(0).widget()
        return None

    def add_new_tab(self, url=None, incognito=False):
        home_url = QUrl("https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort=")
        if url is None or not isinstance(url, QUrl):
            url = home_url
        elif not url.isValid():
            url = home_url
        browser = QWebEngineView()
        browser.setPage(CustomWebEnginePage(self, incognito))
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(browser)
        profile = browser.page().profile()
        interceptor = AdBlockInterceptor(self, self.ad_block_enabled, self.privacy_enabled)
        profile.setUrlRequestInterceptor(interceptor)
        index = self.tab_widget.addTab(container, "New Tab" + (" (Incognito)" if incognito else ""))
        self.tab_widget.setTabToolTip(index, "Double-click to rename")
        close_button = QPushButton("✖️")
        self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, close_button)
        close_button.clicked.connect(lambda: self.close_tab(index))
        browser.load(url)
        browser.urlChanged.connect(lambda q: self.update_url(q))
        browser.titleChanged.connect(lambda title: self.tab_widget.setTabText(index, title + (" (Incognito)" if incognito else "")))
        browser.loadStarted.connect(lambda: self.status.showMessage("Loading..."))
        browser.loadFinished.connect(self.on_load_finished)
        self.tab_widget.setCurrentIndex(index)
        self.update_url_bar(index)

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            if widget:
                browser = widget.layout().itemAt(0).widget()
                if browser:
                    try:
                        browser.urlChanged.disconnect()
                        browser.titleChanged.disconnect()
                        browser.loadStarted.disconnect()
                        browser.loadFinished.disconnect()
                    except TypeError:
                        pass
            self.tab_widget.removeTab(index)
            self.update_url_bar(self.tab_widget.currentIndex())

    def update_url(self, q):
        self.url_bar.setText(q.toString())
        if q.toString() not in self.history:
            self.history.append(q.toString())

    def update_url_bar(self, index):
        if index >= 0 and index < self.tab_widget.count():
            browser = self.current_browser()
            if browser:
                self.url_bar.setText(browser.url().toString())

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
        self.progress_bar.setVisible(progress < 100)

    def navigate_back(self):
        browser = self.current_browser()
        if browser:
            browser.back()

    def navigate_forward(self):
        browser = self.current_browser()
        if browser:
            browser.forward()

    def reload_page(self):
        browser = self.current_browser()
        if browser:
            browser.reload()

    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl("https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort="))

    def navigate_to_url(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if not (text.startswith("http://") or text.startswith("https://")):
            if "." not in text and " " in text:
                query = text.replace(" ", "%20")
                text = f"https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort=&gsc.q={query}"
            else:
                text = "https://" + text
        try:
            url = QUrl(text)
            if url.isValid():
                browser = self.current_browser()
                if browser:
                    browser.setUrl(url)
            else:
                self.status.showMessage("Invalid URL")
        except Exception as e:
            self.status.showMessage(f"Error: {str(e)}")

    def on_load_finished(self, ok):
        self.progress_bar.setVisible(False)
        self.status.showMessage("Loaded" if ok else "Failed to load")
        if self.fun_mode and ok:
            self.apply_fun_effects()

    def save_page_as(self):
        browser = self.current_browser()
        if browser:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Page As", "", "HTML Files (*.html);;All Files (*)")
            if file_path:
                browser.page().toHtml(lambda html: self.save_html(file_path, html))

    def save_html(self, file_path, html):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            self.status.showMessage(f"Saved page to {file_path}")
        except Exception as e:
            self.status.showMessage(f"Error saving page: {str(e)}")

    def add_download(self, download):
        self.downloads.append(download)
        download.stateChanged.connect(lambda state: self.update_download_status(download))
        download.accept()

    def update_download_status(self, download):
        if download.state() == QWebEngineDownloadItem.DownloadCompleted:
            self.status.showMessage(f"Download completed: {download.path()}")
        elif download.state() == QWebEngineDownloadItem.DownloadInterrupted:
            self.status.showMessage(f"Download interrupted: {download.path()}")

    def handle_download(self, download):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", os.path.basename(download.url().toString()), "All Files (*)")
        if file_path:
            download.setPath(file_path)
            download.accept()
            download.downloadProgress.connect(lambda received, total: self.status.showMessage(f"Downloading: {received / total * 100:.1f}% - {download.path()}"))
            download.finished.connect(lambda: self.status.showMessage(f"Saved to {download.path()}"))

    def load_bookmarks(self):
        try:
            with open(self.bookmarks_file, "r") as f:
                bookmarks = json.load(f)
                print(f"Loaded bookmarks: {bookmarks}")
                return bookmarks
        except FileNotFoundError:
            print("Bookmarks file not found, using default")
            return ["https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort="]
        except json.JSONDecodeError as e:
            print(f"Error decoding bookmarks: {e}")
            return ["https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort="]
        except Exception as e:
            print(f"Unexpected error loading bookmarks: {e}")
            return ["https://cse.google.com/cse?cx=666b70a81f11c4eb9#gsc.tab=0&gsc.sort="]

    def save_bookmarks(self):
        try:
            with open(self.bookmarks_file, "w") as f:
                json.dump(self.bookmarks, f, indent=2)
            print(f"Saved bookmarks: {self.bookmarks}")
            self.status.showMessage("Bookmarks saved")
        except Exception as e:
            print(f"Error saving bookmarks: {e}")
            self.status.showMessage(f"Error saving bookmarks: {str(e)}")

    def add_bookmark(self):
        current_url = self.current_browser().url().toString()
        if current_url and current_url not in self.bookmarks:
            self.bookmarks.append(current_url)
            self.save_bookmarks()
            self.status.showMessage(f"Bookmarked: {current_url}")
            print(f"Added bookmark: {current_url}")
        else:
            self.status.showMessage("Already bookmarked or invalid URL")
            print("Bookmark add failed: already exists or invalid")

    def show_bookmarks(self):
        dialog = BookmarkDialog(self)
        dialog.exec_()

    def show_history(self):
        menu = QMenu(self)
        for url in reversed(self.history[-10:]):
            action = QAction(url, self)
            action.triggered.connect(lambda checked, u=url: self.current_browser().setUrl(QUrl(u)))
            menu.addAction(action)
        menu.exec_(QCursor.pos())

    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()

    def show_download_manager(self):
        dialog = DownloadManager(self)
        dialog.exec_()

    def toggle_privacy(self):
        self.privacy_enabled = not self.privacy_enabled
        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i).layout().itemAt(0).widget()
            profile = browser.page().profile()
            interceptor = AdBlockInterceptor(self, self.ad_block_enabled, self.privacy_enabled)
            profile.setUrlRequestInterceptor(interceptor)
        self.status.showMessage(f"Privacy mode {'enabled' if self.privacy_enabled else 'disabled'}")

    def show_page_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Page Settings")
        layout = QFormLayout()

        # Audio Controller
        audio_group = QGroupBox("🔊 Audio Controller")
        audio_layout = QHBoxLayout()
        self.audio_slider = QSlider(Qt.Horizontal)
        self.audio_slider.setRange(0, 100)
        self.audio_slider.setValue(50)
        self.audio_slider.valueChanged.connect(self.adjust_audio)
        audio_play = QPushButton("Play")
        audio_play.clicked.connect(self.play_audio)
        audio_pause = QPushButton("Pause")
        audio_pause.clicked.connect(self.pause_audio)
        audio_mute = QPushButton("Mute")
        audio_mute.clicked.connect(self.mute_audio)
        audio_layout.addWidget(self.audio_slider)
        audio_layout.addWidget(audio_play)
        audio_layout.addWidget(audio_pause)
        audio_layout.addWidget(audio_mute)
        audio_group.setLayout(audio_layout)
        layout.addRow(audio_group)

        # Zoom Manager
        zoom_group = QGroupBox("🔍 Zoom Manager")
        zoom_layout = QHBoxLayout()
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(int(self.zoom_factor * 100))
        self.zoom_slider.valueChanged.connect(self.adjust_zoom)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_group.setLayout(zoom_layout)
        layout.addRow(zoom_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        dialog.setLayout(layout)
        dialog.exec_()

    def adjust_audio(self, value):
        browser = self.current_browser()
        if browser:
            browser.page().runJavaScript(f"document.querySelector('video, audio').volume = {value / 100};")

    def play_audio(self):
        browser = self.current_browser()
        if browser:
            browser.page().runJavaScript("document.querySelector('video, audio').play();")

    def pause_audio(self):
        browser = self.current_browser()
        if browser:
            browser.page().runJavaScript("document.querySelector('video, audio').pause();")

    def mute_audio(self):
        browser = self.current_browser()
        if browser:
            browser.page().runJavaScript("document.querySelector('video, audio').muted = true;")

    def adjust_zoom(self, value):
        self.zoom_factor = value / 100
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(self.zoom_factor)

    def find_on_page(self):
        text, ok = QInputDialog.getText(self, "Find on Page", "Enter text to find:")
        if ok and text:
            browser = self.current_browser()
            if browser:
                browser.page().findText(text)

    def toggle_incognito(self):
        self.add_new_tab(incognito=True)
        self.status.showMessage("Incognito mode enabled for new tab")

    def toggle_fun_mode(self):
        self.fun_mode = not self.fun_mode
        self.status.showMessage(f"Fun mode {'enabled' if self.fun_mode else 'disabled'}")
        if self.fun_mode:
            self.apply_fun_effects()

    def apply_fun_effects(self):
        browser = self.current_browser()
        if browser and self.fun_mode:
            # Add random background color and confetti effect
            browser.page().runJavaScript("""
                document.body.style.backgroundColor = `hsl(${Math.random() * 360}, 70%, 80%)`;
                function createConfetti() {
                    const confetti = document.createElement('div');
                    confetti.style.position = 'absolute';
                    confetti.style.width = '10px';
                    confetti.style.height = '10px';
                    confetti.style.backgroundColor = `hsl(${Math.random() * 360}, 70%, 50%)`;
                    confetti.style.borderRadius = '50%';
                    confetti.style.top = `${Math.random() * 100}vh`;
                    confetti.style.left = `${Math.random() * 100}vw`;
                    confetti.style.animation = `fall ${Math.random() * 2 + 1}s linear`;
                    document.body.appendChild(confetti);
                    setTimeout(() => confetti.remove(), 3000);
                }
                for (let i = 0; i < 20; i++) createConfetti();
                const style = document.createElement('style');
                style.textContent = `@keyframes fall { to { transform: translateY(100vh); } }`;
                document.head.appendChild(style);
            """)

    def apply_theme(self):
        app = QApplication.instance()
        color = QColorDialog.getColor(self.window_color, self, "Choose Theme Color")
        if color.isValid():
            self.window_color = color
            self.text_color = Qt.white if color.lightness() < 128 else Qt.black
        if self.dark_theme:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.Window, self.window_color)
            palette.setColor(QPalette.WindowText, self.text_color)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, self.window_color.darker(110))
            palette.setColor(QPalette.ToolTipBase, self.text_color)
            palette.setColor(QPalette.ToolTipText, self.text_color)
            palette.setColor(QPalette.Text, self.text_color)
            palette.setColor(QPalette.Button, self.window_color)
            palette.setColor(QPalette.ButtonText, self.text_color)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            # Set window bar color for dark theme
            self.setStyleSheet(f"QMainWindow {{ background-color: {self.window_color.name()}; }}")
        else:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.Window, self.window_color)
            palette.setColor(QPalette.WindowText, self.text_color)
            palette.setColor(QPalette.Base, Qt.white)
            palette.setColor(QPalette.AlternateBase, self.window_color.lighter(110))
            palette.setColor(QPalette.ToolTipBase, self.text_color)
            palette.setColor(QPalette.ToolTipText, self.text_color)
            palette.setColor(QPalette.Text, self.text_color)
            palette.setColor(QPalette.Button, self.window_color)
            palette.setColor(QPalette.ButtonText, self.text_color)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(0, 120, 215))
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            # Set window bar color for light theme
            self.setStyleSheet(f"QMainWindow {{ background-color: {self.window_color.lighter(110).name()}; }}")
        app.setPalette(palette)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    sys.exit(app.exec_())
