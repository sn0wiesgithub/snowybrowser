#!/usr/bin/env python3
import sys
import os
import json
import shutil

from PyQt6.QtWidgets import *
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# ---------------- CONFIG ----------------
SESSION_FILE = "session.json"
BOOKMARKS_FILE = "bookmarks.json"
EXTENSIONS_DIR = "extensions"

START_WIDTH = 1300
START_HEIGHT = 850
DEFAULT_ZOOM = 1.0

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# ---------------- MAIN BROWSER ----------------
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern PyQt6 Browser")
        self.resize(START_WIDTH, START_HEIGHT)

        # Default profile
        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setHttpUserAgent(CHROME_UA)

        self.tabs = {}
        self.init_ui()
        self.load_bookmarks()
        self.load_extensions()
        self.restore_session()

    # ---------------- UI ----------------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)

        # URL + Navigation
        nav_bar = QHBoxLayout()
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)

        self.back_btn = QPushButton("◀")
        self.forward_btn = QPushButton("▶")
        self.refresh_btn = QPushButton("⟳")
        self.kill_btn = QPushButton("Kill All Data")
        self.devtools_btn = QPushButton("DevTools")  # DevTools button
        self.kill_btn.setFixedWidth(120)
        self.devtools_btn.setFixedWidth(90)
        self.kill_btn.clicked.connect(self.kill_all_data)
        self.devtools_btn.clicked.connect(self.toggle_devtools)  # Connect to toggle function

        for b in (self.back_btn, self.forward_btn, self.refresh_btn):
            b.setFixedWidth(35)

        nav_bar.addWidget(self.url_bar)
        nav_bar.addWidget(self.back_btn)
        nav_bar.addWidget(self.forward_btn)
        nav_bar.addWidget(self.refresh_btn)
        nav_bar.addWidget(self.kill_btn)
        nav_bar.addWidget(self.devtools_btn)
        main_layout.addLayout(nav_bar)

        # Bookmark bar
        self.bookmark_bar = QHBoxLayout()
        self.bookmark_bar.setSpacing(5)
        main_layout.addLayout(self.bookmark_bar)

        # Tab row (left-aligned)
        self.tab_bar_layout = QHBoxLayout()
        self.tab_bar_layout.setSpacing(4)
        self.tab_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.tabs_container = QHBoxLayout()
        self.tabs_container.setSpacing(4)
        self.tabs_container.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.setFixedWidth(30)
        self.new_tab_btn.clicked.connect(lambda: self.new_tab())

        self.tab_bar_layout.addLayout(self.tabs_container)
        self.tab_bar_layout.addWidget(self.new_tab_btn)
        main_layout.addLayout(self.tab_bar_layout)

        # Web content
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Extensions panel
        self.extension_dock = QDockWidget("Extensions", self)
        self.extension_list = QListWidget()
        self.extension_dock.setWidget(self.extension_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.extension_dock)
        self.extension_dock.hide()

        # Navigation buttons
        self.back_btn.clicked.connect(lambda: self.current_tab().back())
        self.forward_btn.clicked.connect(lambda: self.current_tab().forward())
        self.refresh_btn.clicked.connect(lambda: self.current_tab().reload())

        self.apply_style()

    # ---------------- Tabs ----------------
    def new_tab(self, url="https://www.google.com"):
        view = QWebEngineView()
        view.setUrl(QUrl.fromUserInput(url))
        view.setZoomFactor(DEFAULT_ZOOM)

        self.stack.addWidget(view)

        # Tab button
        frame = QFrame()
        frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        frame.setMaximumWidth(200)

        h = QHBoxLayout(frame)
        h.setContentsMargins(6,2,6,2)

        icon_label = QLabel()
        title_btn = QPushButton("New Tab")
        title_btn.setFixedWidth(120)
        close_btn = QPushButton("x")
        close_btn.setFixedWidth(20)

        h.addWidget(icon_label)
        h.addWidget(title_btn)
        h.addWidget(close_btn)
        self.tabs_container.addWidget(frame)

        # Track per-tab info including DevTools
        self.tabs[view] = {
            "frame": frame,
            "title": title_btn,
            "icon": icon_label,
            "devtools": None  # <-- per-tab DevTools
        }

        title_btn.clicked.connect(lambda: self.switch_tab(view))
        close_btn.clicked.connect(lambda: self.close_tab(view))

        view.titleChanged.connect(lambda t, v=view: self.tabs[v]["title"].setText(t[:20]))
        view.iconChanged.connect(lambda ic, v=view: self.tabs[v]["icon"].setPixmap(ic.pixmap(16,16)))

        self.switch_tab(view)

    def switch_tab(self, view):
        self.stack.setCurrentWidget(view)
        self.url_bar.setText(view.url().toString())
        for v in self.tabs:
            self.tabs[v]["frame"].setStyleSheet("")
        self.tabs[view]["frame"].setStyleSheet("background:#3c4043;border-radius:6px;")

    def close_tab(self, view):
        info = self.tabs[view]
        if info.get("devtools"):
            info["devtools"].close()
        self.stack.removeWidget(view)
        info["frame"].deleteLater()
        view.deleteLater()
        del self.tabs[view]
        if self.tabs:
            self.switch_tab(next(iter(self.tabs)))
        else:
            self.new_tab()

    def current_tab(self):
        return self.stack.currentWidget()

    # ---------------- Navigation ----------------
    def load_url(self):
        text = self.url_bar.text()
        qurl = QUrl.fromUserInput(text)
        if qurl.scheme() == "":
            qurl = QUrl(f"https://www.google.com/search?q={text}")
        self.current_tab().setUrl(qurl)

    # ---------------- Bookmarks ----------------
    def load_bookmarks(self):
        if not os.path.exists(BOOKMARKS_FILE):
            self.bookmarks = []
            return
        with open(BOOKMARKS_FILE) as f:
            self.bookmarks = json.load(f)
        self.refresh_bookmark_bar()

    def save_bookmarks(self):
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(self.bookmarks, f, indent=4)

    def refresh_bookmark_bar(self):
        while self.bookmark_bar.count():
            itm = self.bookmark_bar.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        for bm in self.bookmarks:
            btn = QPushButton(bm["title"][:15])
            btn.clicked.connect(lambda _, url=bm["url"]: self.new_tab(url))
            self.bookmark_bar.addWidget(btn)

    def add_bookmark(self):
        tab = self.current_tab()
        if not tab:
            return
        self.bookmarks.append({"title": tab.title(), "url": tab.url().toString()})
        self.save_bookmarks()
        self.refresh_bookmark_bar()

    # ---------------- Extensions ----------------
    def load_extensions(self):
        if not os.path.exists(EXTENSIONS_DIR):
            os.makedirs(EXTENSIONS_DIR)
        self.extension_list.clear()
        self.profile.scripts().clear()
        for file in os.listdir(EXTENSIONS_DIR):
            if file.endswith(".js"):
                item = QListWidgetItem(file)
                self.extension_list.addItem(item)
                with open(os.path.join(EXTENSIONS_DIR,file),"r",encoding="utf-8") as f:
                    code = f.read()
                script = QWebEngineScript()
                script.setName(file)
                script.setSourceCode(code)
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                script.setRunsOnSubFrames(True)
                script.setWorldId(QWebEngineScript.ScriptWorld.MainWorld)
                self.profile.scripts().insert(script)

    # ---------------- Kill All Data ----------------
    def kill_all_data(self):
        reply = QMessageBox.question(self, "Kill All Data",
            "Are you sure you want to delete all browser data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        self.profile.cookieStore().deleteAllCookies()
        self.profile.clearHttpCache()
        self.profile.clearAllVisitedLinks()
        storage = self.profile.persistentStoragePath()
        if os.path.exists(storage):
            shutil.rmtree(storage)
        for tab in list(self.tabs.keys()):
            self.close_tab(tab)
        self.new_tab("about:blank")

    # ---------------- DevTools per tab ----------------
    def toggle_devtools(self):
        tab = self.current_tab()
        if not tab:
            return

        tab_info = self.tabs[tab]

        # If DevTools exists and is visible, hide it
        if tab_info["devtools"] and tab_info["devtools"].isVisible():
            tab_info["devtools"].hide()
            return

        # Create DevTools for this tab if it doesn't exist
        if not tab_info["devtools"]:
            dev_dock = QDockWidget(f"DevTools - {tab.title()}", self)
            dev_view = QWebEngineView()
            dev_dock.setWidget(dev_view)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dev_dock)
            tab.page().setDevToolsPage(dev_view.page())
            tab_info["devtools"] = dev_dock

        tab_info["devtools"].show()

    # ---------------- Session ----------------
    def closeEvent(self, event):
        urls = [v.url().toString() for v in self.tabs]
        with open(SESSION_FILE,"w") as f:
            json.dump(urls,f)
        super().closeEvent(event)

    def restore_session(self):
        if not os.path.exists(SESSION_FILE):
            self.new_tab()
            return
        with open(SESSION_FILE) as f:
            for u in json.load(f):
                self.new_tab(u)

    # ---------------- Style ----------------
    def apply_style(self):
        self.setStyleSheet("""
        QMainWindow { background: #202124; }
        QLineEdit {
            background: #3c4043;
            border-radius: 18px;
            padding: 6px 12px;
            color: white;
        }
        QPushButton {
            background: transparent;
            color: white;
            border: none;
        }
        QPushButton:hover {
            background: #3c4043;
            border-radius: 6px;
        }
        """)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = Browser()
    browser.show()
    sys.exit(app.exec())
