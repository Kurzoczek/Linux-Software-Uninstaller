"""Main window of Linux Software Uninstaller."""

import os
import re
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QUrl, QEvent, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut, QDesktopServices, QTextCursor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
                             QLabel, QPushButton, QLineEdit, QComboBox, QListView, QStackedWidget,
                             QButtonGroup, QProgressBar, QMessageBox, QMenu, QPlainTextEdit,
                             QListWidget, QDialog, QAbstractItemView, QScrollArea, QGridLayout)

from . import core, theme, i18n, APP_NAME, APP_ID, VERSION
from .i18n import tr, n_
from .widgets import (BgMixin, NavButton, StatCard, Toast, ToggleSwitch, SettingRow, Spinner,
                      AppModel, AppDelegate, DetailPanel, APP_ROLE)
from .dialogs import ProcessDialog, ConfirmDialog, TextDialog, LeftoverDialog, AboutDialog, mono_font

VIEWS = {
    "all": ("All programs", ["applications-all", "view-list-icons", "applications-other"]),
    "recent": ("Recently installed", ["document-open-recent", "chronometer"]),
    "largest": ("Largest programs", ["drive-harddisk", "disk-quota"]),
    "apt": ("APT packages", ["debian-logo", "package-x-generic"]),
    "flatpak": ("Flatpak", ["flatpak-discover", "package-x-generic"]),
    "snap": ("Snap", ["snap", "package-x-generic"]),
    "appimage": ("AppImage", ["appimage", "application-x-executable"]),
    "opt": ("Manually in /opt", ["folder", "folder-open"]),
}
KINDS = ("apt", "flatpak", "snap", "appimage", "opt")


def first_icon(names):
    for n in names:
        if not QIcon.fromTheme(n).isNull():
            return n
    return names[-1]


def page_header(title, subtitle):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    s = QLabel(subtitle)
    s.setObjectName("PageSubtitle")
    s.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(s)
    return w, t, s


class CleanupCard(QFrame):
    def __init__(self, icon, color, title, desc, button_text, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        top = QHBoxLayout()
        self.bubble = QLabel()
        self.bubble.setFixedSize(42, 42)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setStyleSheet(f"background: {theme.rgba(color, 0.16)}; border-radius: 12px;")
        self.bubble.setPixmap(QIcon.fromTheme(icon).pixmap(22, 22))
        top.addWidget(self.bubble)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("SectionTitle")
        self.value = QLabel("…")
        self.value.setObjectName("Muted")
        col.addWidget(t)
        col.addWidget(self.value)
        top.addLayout(col, 1)
        lay.addLayout(top)
        d = QLabel(desc)
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        self.list = QListWidget()
        self.list.setObjectName("Mini")
        self.list.setMaximumHeight(150)
        self.list.setVisible(False)
        lay.addWidget(self.list)
        lay.addStretch()
        row = QHBoxLayout()
        self.show_btn = QPushButton(tr("Show list"))
        self.show_btn.setObjectName("Link")
        self.show_btn.clicked.connect(self._toggle)
        row.addWidget(self.show_btn)
        row.addStretch()
        self.btn = QPushButton(button_text)
        self.btn.setObjectName("Ghost")
        self.btn.setEnabled(False)
        row.addWidget(self.btn)
        lay.addLayout(row)

    def _toggle(self):
        self.list.setVisible(not self.list.isVisible())
        self.show_btn.setText(tr("Hide list") if self.list.isVisible() else tr("Show list"))

    def set_data(self, value_text, items, enabled):
        self.value.setText(value_text)
        self.list.clear()
        self.list.addItems(items or [tr("None — all clean ✨")])
        self.show_btn.setVisible(bool(items))
        self.btn.setEnabled(enabled)


class MainWindow(BgMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme.app_icon())
        self.settings = QSettings("linux-software-uninstaller", "linux-software-uninstaller")
        self.apps, self.view, self.backup = [], "all", None
        self.pending_removal, self.cleanup = [], None
        self._theme_key = None

        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self.build_sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_programs_page())
        self.pages.addWidget(self.build_cleanup_page())
        self.pages.addWidget(self.build_log_page())
        self.pages.addWidget(self.build_settings_page())
        h.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.toast = Toast(self)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.list, activated=self.uninstall_shortcut)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self.list, activated=self.toggle_current)

        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1320, 820)
        self._theme_key = theme.current().window.name()
        self.bg(core.backup_method, cb=self.set_backup)
        self.refresh()
        self.refresh_cleanup()

    # ───────────────────────── sidebar ─────────────────────────
    def build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(250)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 18, 0, 14)
        lay.setSpacing(0)
        logo = QHBoxLayout()
        logo.setContentsMargins(20, 0, 16, 10)
        self.logo_icon = QLabel()
        self.logo_icon.setPixmap(theme.app_icon().pixmap(38, 38))
        logo.addWidget(self.logo_icon)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel("Linux Software\nUninstaller")
        t.setObjectName("AppTitle")
        s = QLabel(tr("clean uninstalling"))
        s.setObjectName("AppSubtitle")
        col.addWidget(t)
        col.addWidget(s)
        logo.addSpacing(6)
        logo.addLayout(col, 1)
        lay.addLayout(logo)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav = {}

        def section(text):
            lab = QLabel(tr(text).upper())
            lab.setObjectName("NavSection")
            lay.addWidget(lab)

        def add(key, icon, text, handler):
            b = NavButton(icon, tr(text))
            b.clicked.connect(handler)
            self.nav_group.addButton(b)
            self.nav[key] = b
            lay.addWidget(b)

        section("Programs")
        for key in ("all", "recent", "largest"):
            add(key, first_icon(VIEWS[key][1]), VIEWS[key][0], lambda _=False, k=key: self.set_view(k))
        section("Sources")
        for key in KINDS:
            add(key, first_icon(VIEWS[key][1]), VIEWS[key][0], lambda _=False, k=key: self.set_view(k))
        section("Tools")
        add("cleanup", "edit-clear-all", "Cleanup", lambda: self.set_page(1, "cleanup"))
        add("log", "view-history", "Activity log", lambda: self.set_page(2, "log"))
        lay.addStretch()
        add("settings", "configure", "Settings", lambda: self.set_page(3, "settings"))
        about = NavButton("help-about", tr("About"))
        about.setCheckable(False)
        about.clicked.connect(lambda: AboutDialog(self).exec())
        lay.addWidget(about)
        self.nav["all"].setChecked(True)
        return side

    def set_page(self, idx, key):
        self.pages.setCurrentIndex(idx)
        self.nav[key].setChecked(True)
        if key == "log":
            self.load_log()

    def set_view(self, key):
        self.view = key
        self.nav[key].setChecked(True)
        self.pages.setCurrentIndex(0)
        self.sort.blockSignals(True)
        self.sort.setCurrentIndex({"recent": 2, "largest": 1}.get(key, 0))
        self.sort.blockSignals(False)
        self.rebuild()
        self.list.scrollToTop()

    # ───────────────────────── Programs page ─────────────────────────
    def build_programs_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)

        top = QHBoxLayout()
        head, self.title, self.subtitle = page_header(tr("All programs"), tr("Loading…"))
        top.addWidget(head, 1)
        self.sort = QComboBox()
        self.sort.setObjectName("Sort")
        self.sort.addItems([tr("Sort: name"), tr("Sort: size"), tr("Sort: install date")])
        self.sort.currentIndexChanged.connect(self.rebuild)
        top.addWidget(self.sort, 0, Qt.AlignmentFlag.AlignBottom)
        self.refresh_btn = QPushButton(QIcon.fromTheme("view-refresh"), "")
        self.refresh_btn.setObjectName("Ghost")
        self.refresh_btn.setToolTip(tr("Reload the list (F5)"))
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(top)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText(tr("Search programs by name, package or description…   (Ctrl+F)"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(QIcon.fromTheme("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self.rebuild)
        lay.addWidget(self.search)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.card_count = StatCard("applications-all", tr("installed programs"), theme.current().accent)
        self.card_size = StatCard("drive-harddisk", tr("used on disk"), "#4a86cf")
        self.card_free = StatCard("edit-clear-all", tr("can be freed — click to clean up"), "#30a46c",
                                  clickable=True)
        self.card_free.clicked.connect(lambda: self.set_page(1, "cleanup"))
        for c in (self.card_count, self.card_size, self.card_free):
            cards.addWidget(c, 1)
        lay.addLayout(cards)

        content = QHBoxLayout()
        content.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(10)
        self.busy = QProgressBar()
        self.busy.setObjectName("Busy")
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        left.addWidget(self.busy)

        self.list_stack = QStackedWidget()
        self.model = AppModel(self)
        self.model.checkedChanged.connect(self.update_action_bar)
        self.list = QListView()
        self.list.setObjectName("AppList")
        self.list.setModel(self.model)
        self.delegate = AppDelegate(self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.setUniformItemSizes(True)
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.verticalScrollBar().setSingleStep(22)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.context_menu)
        self.list.selectionModel().currentChanged.connect(self.current_changed)
        self.list_stack.addWidget(self.list)

        empty = QFrame()
        empty.setObjectName("Card")
        el = QVBoxLayout(empty)
        el.addStretch()
        ei = QLabel()
        ei.setPixmap(QIcon.fromTheme("edit-find").pixmap(64, 64))
        ei.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(ei)
        self.empty_text = QLabel(tr("Nothing found"))
        self.empty_text.setObjectName("SectionTitle")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_text)
        self.empty_sub = QLabel(tr("Try another name or turn on showing libraries in Settings."))
        self.empty_sub.setObjectName("Muted")
        self.empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_sub)
        el.addStretch()
        self.list_stack.addWidget(empty)

        loading = QFrame()
        loading.setObjectName("Card")
        ll = QVBoxLayout(loading)
        ll.addStretch()
        sp_row = QHBoxLayout()
        sp_row.addStretch()
        sp_row.addWidget(Spinner(40))
        sp_row.addStretch()
        ll.addLayout(sp_row)
        lt = QLabel(tr("Collecting the list of programs…"))
        lt.setObjectName("Muted")
        lt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addSpacing(10)
        ll.addWidget(lt)
        ll.addStretch()
        self.list_stack.addWidget(loading)
        left.addWidget(self.list_stack, 1)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("ActionBar")
        ab = QHBoxLayout(self.action_bar)
        ab.setContentsMargins(16, 10, 12, 10)
        self.action_text = QLabel()
        self.action_text.setObjectName("ActionText")
        ab.addWidget(self.action_text, 1)
        clr = QPushButton(tr("Untick all"))
        clr.setObjectName("Ghost")
        clr.clicked.connect(lambda: self.model.set_all([]))
        ab.addWidget(clr)
        self.uninst_btn = QPushButton(QIcon.fromTheme("edit-delete"), tr("  Uninstall selected"))
        self.uninst_btn.setObjectName("Danger")
        self.uninst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uninst_btn.clicked.connect(lambda: self.uninstall(self.checked_apps()))
        ab.addWidget(self.uninst_btn)
        self.action_bar.setMaximumHeight(0)
        self._bar_anim = QPropertyAnimation(self.action_bar, b"maximumHeight", self)
        self._bar_anim.setDuration(200)
        self._bar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        left.addWidget(self.action_bar)
        content.addLayout(left, 1)

        self.detail = DetailPanel()
        self.detail.uninstall.connect(lambda a: self.uninstall([a]))
        self.detail.scan.connect(lambda a: self.start_scan(core.tokens_for_app(a), tr("Leftovers: {name}", name=a.name)))
        self.detail.details.connect(self.show_details)
        self.detail.open_loc.connect(self.open_location)
        content.addWidget(self.detail)
        lay.addLayout(content, 1)
        return page

    def focus_search(self):
        if self.pages.currentIndex() != 0:
            self.set_view(self.view)
        self.search.setFocus()
        self.search.selectAll()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self.search.text():
            self.search.clear()
            return
        super().keyPressEvent(e)

    def refresh(self):
        self.refresh_btn.setEnabled(False)
        self.busy.setVisible(True)
        if not self.apps:
            self.list_stack.setCurrentIndex(2)
        self.bg(core.collect_all, cb=self.loaded)

    def loaded(self, res):
        self.refresh_btn.setEnabled(True)
        self.busy.setVisible(False)
        if isinstance(res, Exception):
            self.subtitle.setText(tr("Loading failed: {e}", e=res))
            return
        self.apps = res
        self.delegate.clear_cache()
        keys = {a.key for a in res}
        self.model.checked &= keys
        progs = [a for a in res if a.is_program]
        for k in KINDS:
            self.nav[k].set_count(sum(1 for a in progs if a.kind == k))
            self.nav[k].setVisible(k == "apt" or (k == "flatpak" and core.have("flatpak")) or any(a.kind == k for a in res))
        self.nav["all"].set_count(len(progs))
        self.card_count.set_value(str(len(progs)))
        self.card_size.set_value(core.human(sum(a.size for a in progs)))
        self.rebuild()
        if self.pending_removal:
            removed = [a for a in self.pending_removal if a.key not in keys]
            failed = [a for a in self.pending_removal if a.key in keys]
            self.pending_removal = []
            self.after_uninstall(removed, failed)

    def rows_for_view(self):
        q = self.search.text().strip().lower()
        show_libs = self.settings.value("show_libs", False, type=bool)
        rows = []
        for a in self.apps:
            if self.view in KINDS and a.kind != self.view:
                continue
            if self.view == "recent" and not a.installed:
                continue
            if q:
                if q not in a.name.lower() and q not in a.ident.lower() and q not in a.summary.lower():
                    continue
            elif not show_libs and not a.is_program:
                continue
            rows.append(a)
        mode = self.sort.currentIndex()
        if mode == 1:
            rows.sort(key=lambda a: -a.size)
        elif mode == 2:
            rows.sort(key=lambda a: -a.installed)
        else:
            rows.sort(key=lambda a: a.name.lower())
        if self.view == "largest" and not q:
            rows = rows[:100]
        return rows, q

    def rebuild(self):
        if self.pages.currentIndex() != 0 and self.search.text():
            self.pages.setCurrentIndex(0)
            self.nav[self.view].setChecked(True)
        cur = self.detail.app
        rows, q = self.rows_for_view()
        self.model.set_rows(rows)
        self.title.setText(tr(VIEWS[self.view][0]))
        total = sum(a.size for a in rows)
        sub = f"{n_(len(rows), 'program')} · {core.human(total)}"
        if q:
            sub = tr("Search results for “{q}”: {sub}", q=q, sub=sub)
        elif self.view == "largest":
            sub = tr("The 100 programs taking the most space · {size}", size=core.human(total))
        self.subtitle.setText(sub)
        if self.apps:
            self.list_stack.setCurrentIndex(0 if rows else 1)
        if cur and cur in rows:
            idx = self.model.index(rows.index(cur))
            self.list.setCurrentIndex(idx)
        else:
            self.detail.set_app(None)
        self.update_action_bar()

    def current_changed(self, cur, _prev):
        self.detail.set_app(cur.data(APP_ROLE) if cur.isValid() else None)

    def toggle_current(self):
        idx = self.list.currentIndex()
        if idx.isValid():
            self.model.toggle(idx)

    def uninstall_shortcut(self):
        apps = self.checked_apps()
        if not apps and self.list.currentIndex().isValid():
            apps = [self.list.currentIndex().data(APP_ROLE)]
        self.uninstall(apps)

    def checked_apps(self):
        return [a for a in self.apps if a.key in self.model.checked]

    def update_action_bar(self):
        sel = self.checked_apps()
        if sel:
            self.action_text.setText(tr("✓  Selected {programs} · {size}", programs=n_(len(sel), "program"),
                                        size=core.human(sum(a.size for a in sel))))
            self.uninst_btn.setText(tr("  Uninstall selected ({n})", n=len(sel)))
        target = 64 if sel else 0
        if self.action_bar.maximumHeight() != target and self._bar_anim.endValue() != target:
            self._bar_anim.stop()
            self._bar_anim.setStartValue(self.action_bar.maximumHeight())
            self._bar_anim.setEndValue(target)
            self._bar_anim.start()

    def context_menu(self, pos):
        idx = self.list.indexAt(pos)
        if not idx.isValid():
            return
        a = idx.data(APP_ROLE)
        m = QMenu(self)
        act = m.addAction(QIcon.fromTheme("edit-delete"), tr("Uninstall"), lambda: self.uninstall([a]))
        act.setEnabled(not a.essential)
        checked = a.key in self.model.checked
        m.addAction(QIcon.fromTheme("checkbox"), tr("Untick") if checked else tr("Tick"),
                    lambda: self.model.toggle(idx)).setEnabled(not a.essential)
        m.addAction(QIcon.fromTheme("edit-find"), tr("Find leftovers (without uninstalling)"),
                    lambda: self.start_scan(core.tokens_for_app(a), tr("Leftovers: {name}", name=a.name)))
        m.addSeparator()
        if a.kind in ("apt", "flatpak", "snap"):
            m.addAction(QIcon.fromTheme("documentinfo"), tr("Details"), lambda: self.show_details(a))
        if a.kind == "apt":
            m.addAction(QIcon.fromTheme("document-properties"), tr("Package files"),
                        lambda: TextDialog(self, tr("Files of package {p}", p=a.ident),
                                           core.out(["dpkg", "-L", a.ident])).exec())
        if a.kind in ("appimage", "opt"):
            m.addAction(QIcon.fromTheme("document-open-folder"), tr("Open location"), lambda: self.open_location(a))
        m.addAction(QIcon.fromTheme("edit-copy"), tr("Copy identifier"),
                    lambda: QApplication.clipboard().setText(a.ident))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def show_details(self, a):
        if a.kind == "apt":
            text = core.out(["apt-cache", "show", "--no-all-versions", a.ident])
        elif a.kind == "flatpak":
            where = [f"--{a.extra}"] if a.extra in ("user", "system") else [f"--installation={a.extra}"]
            text = core.out(["flatpak", "info", *where, a.ident])
        elif a.kind == "snap":
            text = core.out(["snap", "info", a.ident])
        else:
            text = a.ident
        TextDialog(self, a.name, text or tr("No information.")).exec()

    def open_location(self, a):
        p = a.ident if a.kind == "opt" else str(Path(a.ident).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    # ───────────────────────── uninstalling ─────────────────────────
    def uninstall(self, apps):
        apps = [a for a in apps if a and not a.essential]
        if not apps:
            return
        apt_pkgs = [a.ident for a in apps if a.kind == "apt"]
        self.busy.setVisible(True)
        self.bg(lambda: core.simulate_purge(apt_pkgs) if apt_pkgs else (0, [], ""),
                cb=lambda res: self.confirm_uninstall(apps, res))

    def confirm_uninstall(self, apps, sim):
        self.busy.setVisible(False)
        if isinstance(sim, Exception):
            QMessageBox.critical(self, APP_NAME, tr("Dependency check failed: {e}", e=sim))
            return
        rc, removed, err = sim
        if rc != 0:
            QMessageBox.critical(self, APP_NAME, tr("apt does not allow removing these packages:\n\n{err}", err=err.strip()))
            return
        by_name = {a.ident.split(":")[0]: a for a in self.apps if a.kind == "apt"}
        selected = {a.ident.split(":")[0] for a in apps if a.kind == "apt"}
        extras = [p for p in removed if p.split(":")[0] not in selected]
        running_kernel = f"linux-image-{os.uname().release}"
        critical = []
        for p in removed:
            b = p.split(":")[0]
            info = by_name.get(b)
            if (b in core.CRITICAL or b == running_kernel
                    or (info and (info.essential or info.priority in ("required", "important")))):
                critical.append(b)
        snapshot = bool(self.backup) and self.settings.value("snapshot", True, type=bool)
        note = core.backup_text(self.backup) if snapshot else None
        if ConfirmDialog(self, apps, extras, critical, note).exec() != QDialog.DialogCode.Accepted:
            return
        self.run_uninstall(apps, snapshot)

    def run_uninstall(self, apps, snapshot):
        args = []
        apt = [a.ident for a in apps if a.kind == "apt"]
        snaps = [a.ident for a in apps if a.kind == "snap"]
        flat_sys = [a.ident if a.extra == "system" else f"{a.ident}@{a.extra}"
                    for a in apps if a.kind == "flatpak" and a.extra != "user"]
        opts = [a.ident for a in apps if a.kind == "opt"]
        sys_desktops = [d for a in apps if a.kind == "opt" for d in a.desktops
                        if os.path.dirname(d) in ("/usr/share/applications", "/usr/local/share/applications")]
        for flag, vals in (("--apt", apt), ("--snap", snaps), ("--flatpak", flat_sys),
                           ("--opt", opts), ("--desktop", sys_desktops)):
            if vals:
                args += [flag, *vals]
        steps = []
        if args:
            if snapshot:
                args.insert(0, "--snapshot")
            steps.append((tr("Uninstalling programs"), core.helper_argv("uninstall", *args)))
        for a in apps:
            if a.kind == "flatpak" and a.extra == "user":
                steps.append((tr("Removing {name} (Flatpak)", name=a.name),
                              ["flatpak", "uninstall", "--user", "-y", "--noninteractive", "--delete-data", a.ident]))
        for a in apps:
            if a.kind == "appimage" or (a.kind == "opt" and any(d.startswith(str(core.HOME)) for d in a.desktops)):
                steps.append((tr("Removing {name}", name=a.name), lambda a=a: self.remove_user_files(a)))
        ProcessDialog(self, tr("Uninstalling"), steps).exec()
        self.pending_removal = apps
        self.refresh()

    @staticmethod
    def remove_user_files(a):
        msg, targets = [], []
        if a.kind == "appimage":
            targets.append(a.ident)
        targets += [d for d in a.desktops if d.startswith(str(core.HOME))]
        for t in targets:
            if os.path.lexists(t):
                if os.access(os.path.dirname(t), os.W_OK):
                    core.move_to_trash(t)
                    msg.append(tr("→ Trash: {p}", p=t))
                else:
                    raise PermissionError(tr("no permission for {p}", p=t))
        return "\n".join(msg) + "\n"

    def after_uninstall(self, removed, failed):
        for a in removed:
            core.log(tr("UNINSTALLED [{kind}] {name} ({ident})", kind=core.KIND_LABEL[a.kind], name=a.name, ident=a.ident))
        for a in failed:
            core.log(tr("FAILED [{kind}] {name} ({ident})", kind=core.KIND_LABEL[a.kind], name=a.name, ident=a.ident))
        self.model.checked -= {a.key for a in removed}
        self.update_action_bar()
        self.refresh_cleanup()
        if removed:
            self.toast.show_msg(tr("✓  Uninstalled: {names}", names=", ".join(a.name for a in removed[:3])
                                   + ("…" if len(removed) > 3 else "")))
        if failed:
            QMessageBox.warning(self, APP_NAME, tr("Could not uninstall:\n{names}",
                                                   names="\n".join(f"• {a.name}" for a in failed)))
        if removed and self.settings.value("scan_after", True, type=bool):
            tokens = set()
            for a in removed:
                tokens |= core.tokens_for_app(a)
            names = ", ".join(a.name for a in removed[:3]) + ("…" if len(removed) > 3 else "")
            self.start_scan(tokens, tr("Leftovers of: {names}", names=names))

    def start_scan(self, tokens, title):
        self.busy.setVisible(True)
        self.toast.show_msg(tr("🔍  Looking for leftovers…"), 2500)
        self.bg(core.scan_leftovers, tokens, cb=lambda res: self.scan_done(res, title))

    def scan_done(self, res, title):
        self.busy.setVisible(False)
        if isinstance(res, Exception):
            QMessageBox.critical(self, APP_NAME, tr("Scan failed: {e}", e=res))
            return
        if not res:
            self.toast.show_msg(tr("✨  No leftovers found — all clean!"))
            return
        LeftoverDialog(self, res, title, self.settings.value("to_trash", True, type=bool)).exec()

    # ───────────────────────── Cleanup page ─────────────────────────
    def build_cleanup_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)
        head, _t, _s = page_header(tr("System cleanup"), tr("Remove what no program needs any more."))
        lay.addWidget(head)

        hero = QFrame()
        hero.setObjectName("Card")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(22, 18, 22, 18)
        self.hero_spin = Spinner(34)
        hl.addWidget(self.hero_spin)
        hcol = QVBoxLayout()
        hcol.setSpacing(0)
        self.hero_value = QLabel(tr("Checking…"))
        self.hero_value.setObjectName("PageTitle")
        self.hero_sub = QLabel(tr("Analysing packages and caches"))
        self.hero_sub.setObjectName("Muted")
        hcol.addWidget(self.hero_value)
        hcol.addWidget(self.hero_sub)
        hl.addSpacing(8)
        hl.addLayout(hcol, 1)
        rb = QPushButton(QIcon.fromTheme("view-refresh"), "")
        rb.setObjectName("Ghost")
        rb.setToolTip(tr("Check again"))
        rb.clicked.connect(self.refresh_cleanup)
        hl.addWidget(rb)
        self.clean_all_btn = QPushButton(QIcon.fromTheme("edit-clear-all"), tr("  Clean up everything"))
        self.clean_all_btn.setObjectName("Primary")
        self.clean_all_btn.setEnabled(False)
        self.clean_all_btn.clicked.connect(lambda: self.run_cleanup(all_=True))
        hl.addWidget(self.clean_all_btn)
        lay.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.cc_orph = CleanupCard("edit-delete", "#e5484d", tr("Orphaned dependencies"),
                                   tr("Packages installed automatically for programs that are gone."),
                                   tr("Remove"))
        self.cc_orph.btn.clicked.connect(lambda: self.run_cleanup(autoremove=True))
        self.cc_rc = CleanupCard("configure", "#e8a23a", tr("Leftover configuration"),
                                 tr("Settings files in /etc left by packages removed without purge (“rc” state)."),
                                 tr("Clean"))
        self.cc_rc.btn.clicked.connect(lambda: self.run_cleanup(purge_rc=True))
        self.cc_cache = CleanupCard("folder-download", "#4a86cf", tr("Downloaded APT packages"),
                                    tr(".deb files in /var/cache/apt/archives — not needed after installation."),
                                    tr("Clean"))
        self.cc_cache.btn.clicked.connect(lambda: self.run_cleanup(apt_clean=True))
        grid.addWidget(self.cc_orph, 0, 0)
        grid.addWidget(self.cc_rc, 0, 1)
        grid.addWidget(self.cc_cache, 0, 2)
        lay.addLayout(grid)

        old = QFrame()
        old.setObjectName("Card")
        ol = QVBoxLayout(old)
        ol.setContentsMargins(18, 16, 18, 16)
        t = QLabel(tr("Leftovers of programs removed earlier"))
        t.setObjectName("SectionTitle")
        d = QLabel(tr("Type the name of a program you removed in the past (e.g. spotify, zoom, discord) — I will find "
                      "its files in configuration, caches, autostart and APT repositories."))
        d.setObjectName("Muted")
        d.setWordWrap(True)
        row = QHBoxLayout()
        self.old_q = QLineEdit()
        self.old_q.setObjectName("Field")
        self.old_q.setPlaceholderText(tr("Program name…"))
        self.old_q.returnPressed.connect(self.manual_scan)
        b = QPushButton(QIcon.fromTheme("edit-find"), tr("  Search"))
        b.setObjectName("Primary")
        b.clicked.connect(self.manual_scan)
        row.addWidget(self.old_q, 1)
        row.addWidget(b)
        ol.addWidget(t)
        ol.addWidget(d)
        ol.addLayout(row)
        lay.addWidget(old)
        lay.addStretch()
        return page

    def refresh_cleanup(self):
        self.hero_spin.setVisible(True)
        self.hero_value.setText(tr("Checking…"))
        self.clean_all_btn.setEnabled(False)
        self.bg(core.check_cleanup, cb=self.cleanup_loaded)

    def cleanup_loaded(self, res):
        self.hero_spin.setVisible(False)
        if isinstance(res, Exception):
            self.hero_value.setText(tr("Error"))
            self.hero_sub.setText(str(res))
            return
        self.cleanup = res
        total = res["orphan_size"] + res["cache"]
        self.hero_value.setText(tr("You can free {size}", size=core.human(total)) if total or res["rc"]
                                else tr("All clean ✨"))
        self.hero_sub.setText(tr("{orphans} · {rc} · {debs}", orphans=n_(len(res["orphans"]), "orphan"),
                                 rc=n_(len(res["rc"]), "rcconf"), debs=n_(res["cache_files"], "debfile")))
        self.clean_all_btn.setEnabled(bool(res["orphans"] or res["rc"] or res["cache"]))
        self.cc_orph.set_data(tr("{packages} · {size}", packages=n_(len(res["orphans"]), "package"),
                                 size=core.human(res["orphan_size"])),
                              res["orphans"], bool(res["orphans"]))
        self.cc_rc.set_data(n_(len(res["rc"]), "package"), res["rc"], bool(res["rc"]))
        self.cc_cache.set_data(tr("{files} · {size}", files=n_(res["cache_files"], "file"), size=core.human(res["cache"])), [],
                               res["cache"] > 0)
        self.card_free.set_value(core.human(total) if total else "0 B")

    def run_cleanup(self, all_=False, autoremove=False, purge_rc=False, apt_clean=False):
        res = self.cleanup or {}
        args = []
        if (all_ or autoremove) and res.get("orphans"):
            args.append("--autoremove")
        if (all_ or purge_rc) and res.get("rc"):
            args += ["--purge-rc", *res["rc"]]
        if (all_ or apt_clean) and res.get("cache"):
            args.append("--apt-clean")
        if not args:
            return
        if autoremove or all_:
            n = len(res.get("orphans", []))
            if QMessageBox.question(self, tr("Cleanup"),
                                    tr("{n} orphaned packages will be removed. Review the list in the “Orphaned "
                                       "dependencies” card if you are not sure.\n\nContinue?", n=n)
                                    ) != QMessageBox.StandardButton.Yes:
                return
        dlg = ProcessDialog(self, tr("System cleanup"), [(tr("System cleanup"), core.helper_argv("cleanup", *args))])
        dlg.exec()
        core.log(tr("CLEANUP {what} — {result}", what=" ".join(a for a in args if a.startswith("--")),
                    result="OK" if dlg.ok else tr("error")))
        if dlg.ok:
            self.toast.show_msg(tr("✨  All cleaned up!"))
        self.refresh_cleanup()
        self.refresh()

    def manual_scan(self):
        txt = self.old_q.text().strip()
        if not txt:
            return
        tokens = core.norm_tokens([txt] + re.split(r"[,\s]+", txt))
        if not tokens:
            QMessageBox.information(self, APP_NAME, tr("This name is too short or too generic to search for "
                                                       "leftovers safely."))
            return
        self.start_scan(tokens, tr("Leftovers: {name}", name=txt))

    # ───────────────────────── Activity log page ─────────────────────────
    def build_log_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)
        head, _t, _s = page_header(tr("Activity log"), tr("History of uninstalled programs and deleted files."))
        lay.addWidget(head)
        self.log_view = QPlainTextEdit(readOnly=True)
        self.log_view.setObjectName("Console")
        self.log_view.setFont(mono_font())
        lay.addWidget(self.log_view, 1)
        row = QHBoxLayout()
        path = QLabel(str(core.LOG_FILE))
        path.setObjectName("Muted")
        row.addWidget(path, 1)
        for text, icon, fn in ((tr("Reload"), "view-refresh", self.load_log),
                               (tr("Open folder"), "document-open-folder", self.open_log_dir),
                               (tr("Clear log"), "edit-clear-history", self.clear_log)):
            b = QPushButton(QIcon.fromTheme(icon), " " + text)
            b.setObjectName("Ghost")
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        return page

    def load_log(self):
        try:
            self.log_view.setPlainText(core.LOG_FILE.read_text(encoding="utf-8"))
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        except OSError:
            self.log_view.setPlainText(tr("The log is empty."))

    def open_log_dir(self):
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.STATE_DIR)))

    def clear_log(self):
        if QMessageBox.question(self, APP_NAME, tr("Clear the whole log?")) == QMessageBox.StandardButton.Yes:
            try:
                core.LOG_FILE.unlink()
            except OSError:
                pass
            self.load_log()

    # ───────────────────────── Settings page ─────────────────────────
    def build_settings_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(12)
        head, _t, _s = page_header(tr("Settings"), tr("Changes are saved immediately."))
        lay.addWidget(head)
        lay.addSpacing(6)
        s = self.settings

        def switch(key, default):
            sw = ToggleSwitch(s.value(key, default, type=bool))
            sw.toggled.connect(lambda v: (s.setValue(key, v), self._setting_changed(key)))
            return sw

        self.sw_snapshot = switch("snapshot", True)
        self.row_snapshot = SettingRow(tr("Backup before uninstalling"),
                                       tr("Checking the file system…"), self.sw_snapshot)
        self.sw_snapshot.setEnabled(False)
        lay.addWidget(self.row_snapshot)
        lay.addWidget(SettingRow(tr("Find leftovers after uninstalling"),
                                 tr("After every uninstall, show the files the program left in the system."),
                                 switch("scan_after", True)))
        lay.addWidget(SettingRow(tr("Move files to the Trash"),
                                 tr("Leftovers from your home folder go to the Trash, where you can restore them in Dolphin."),
                                 switch("to_trash", True)))
        lay.addWidget(SettingRow(tr("Show libraries and system packages"),
                                 tr("By default the list shows only programs and tools. Turn on to see every APT "
                                    "package (advanced)."), switch("show_libs", False)))
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("Sort")
        for code, name in i18n.LANGUAGES.items():
            self.lang_combo.addItem(tr(name), code)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(s.value("language", "en"))))
        self.lang_combo.currentIndexChanged.connect(self.language_changed)
        lay.addWidget(SettingRow(tr("Language"), tr("Language of the interface. The change takes effect after a restart."),
                                 self.lang_combo))
        lay.addStretch()
        return page

    def _setting_changed(self, key):
        if key == "show_libs":
            self.rebuild()

    def set_backup(self, res):
        self.backup = res if isinstance(res, str) else "config"
        self.sw_snapshot.setEnabled(True)
        extra = {"config": " A full system snapshot is possible on btrfs or with Timeshift installed.",
                 "timeshift": " Timeshift must be configured first (running it once is enough)."}
        self.row_snapshot.desc.setText(core.backup_text(self.backup) + (tr(extra[self.backup]) if self.backup in extra else ""))

    def language_changed(self):
        code = self.lang_combo.currentData()
        self.settings.setValue("language", code)
        self.settings.sync()
        if i18n.detect() == i18n.LANG and code == "auto":
            return
        if QMessageBox.question(self, APP_NAME, tr("Restart now to switch the language?")) == QMessageBox.StandardButton.Yes:
            self.restart()

    def restart(self):
        from PyQt6.QtCore import QProcess
        argv0 = os.path.abspath(sys.argv[0])
        if argv0.endswith("__main__.py"):
            prog, args, cwd = sys.executable, ["-m", "linux_software_uninstaller", *sys.argv[1:]], str(Path(argv0).parent.parent)
        else:
            prog, args, cwd = sys.executable, [argv0, *sys.argv[1:]], os.getcwd()
        QProcess.startDetached(prog, args, cwd)
        self.close()
        QApplication.instance().quit()

    # ───────────────────────── theme ─────────────────────────
    def changeEvent(self, e):
        if e.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            key = QApplication.palette().color(QApplication.palette().ColorRole.Window).name()
            if key != self._theme_key:
                self._theme_key = key
                QTimer.singleShot(0, self.retheme)
        super().changeEvent(e)

    def retheme(self):
        theme.apply(QApplication.instance())
        theme._icon_cache.clear()
        self.delegate.clear_cache()
        for c in (self.card_count, self.card_size, self.card_free):
            c.restyle()
        self.detail.restyle()
        self.list.viewport().update()

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


def migrate_old_files():
    """Copies settings and the log from the old version (when the program was called “Deinstalator”)."""
    import shutil
    pairs = [(core.HOME / ".config/deinstalator/deinstalator.conf",
              core.HOME / ".config/linux-software-uninstaller/linux-software-uninstaller.conf"),
             (core.HOME / ".local/state/deinstalator/dziennik.log", core.LOG_FILE),
             (core.STATE_DIR / "dziennik.log", core.LOG_FILE)]
    for old, new in pairs:
        try:
            if old.exists() and not new.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, new)
        except OSError:
            pass


def main():
    migrate_old_files()
    i18n.set_language(QSettings("linux-software-uninstaller", "linux-software-uninstaller").value("language", "en"))
    if "--version" in sys.argv:
        print(f"{APP_NAME} {VERSION}")
        return
    if "--help" in sys.argv or "-h" in sys.argv:
        print(tr("{app} {ver} — uninstall programs together with their leftovers.\n"
                 "Usage: linux-software-uninstaller [--version]", app=APP_NAME, ver=VERSION))
        return
    if os.geteuid() == 0 and "--allow-root" not in sys.argv:
        print(tr("Run Linux Software Uninstaller as a normal user (without sudo).\n"
                 "It will ask for the administrator password itself when needed."))
        sys.exit(1)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("linux-software-uninstaller")
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(theme.app_icon())
    theme.apply(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
