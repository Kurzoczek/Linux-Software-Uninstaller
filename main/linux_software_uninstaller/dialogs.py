"""Dialogs of Linux Software Uninstaller."""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QTimer, QUrl, QSize
from PyQt6.QtGui import QIcon, QTextCursor, QFontDatabase, QDesktopServices, QBrush, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
                             QCheckBox, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QHeaderView, QMenu, QApplication, QMessageBox, QWidget)

from . import core, theme, APP_NAME, VERSION
from .i18n import tr, n_
from .widgets import StatusIcon, BgMixin


def mono_font():
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def header(icon_widget, title, subtitle):
    row = QHBoxLayout()
    row.setSpacing(16)
    row.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(3)
    t = QLabel(title)
    t.setObjectName("SectionTitle")
    t.setWordWrap(True)
    s = QLabel(subtitle)
    s.setObjectName("Muted")
    s.setWordWrap(True)
    col.addWidget(t)
    col.addWidget(s)
    row.addLayout(col, 1)
    return row, t, s


def icon_label(name, size=44):
    lab = QLabel()
    lab.setFixedSize(size, size)
    ic = QIcon.fromTheme(name)
    lab.setPixmap((ic if not ic.isNull() else theme.app_icon()).pixmap(size, size))
    return lab


class ProcessDialog(QDialog):
    """Runs steps (commands or Python functions) and shows progress."""

    def __init__(self, parent, title, steps):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(620)
        self.steps, self.idx, self.ok, self.results = steps, -1, True, []
        self.proc, self.running, self.cur_argv = None, True, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(14)
        self.status = StatusIcon(44)
        row, self.title, self.sub = header(self.status, title, tr("Preparing…"))
        lay.addLayout(row)
        self.text = QPlainTextEdit(readOnly=True)
        self.text.setObjectName("Console")
        self.text.setFont(mono_font())
        self.text.setMinimumHeight(260)
        self.text.setVisible(False)
        lay.addWidget(self.text, 1)
        btns = QHBoxLayout()
        self.toggle = QPushButton(tr("Show details"))
        self.toggle.setObjectName("Link")
        self.toggle.clicked.connect(self._toggle)
        btns.addWidget(self.toggle)
        btns.addStretch()
        self.btn = QPushButton(tr("Close"))
        self.btn.setObjectName("Primary")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.accept)
        btns.addWidget(self.btn)
        lay.addLayout(btns)
        QTimer.singleShot(0, self.next_step)

    def _toggle(self):
        vis = not self.text.isVisible()
        self.text.setVisible(vis)
        self.toggle.setText(tr("Hide details") if vis else tr("Show details"))
        self.adjustSize()

    def append(self, s):
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.insertPlainText(s)
        self.text.ensureCursorVisible()
        last = [ln for ln in s.splitlines() if ln.strip()]
        if last:
            self.sub.setText(last[-1].strip()[:110])

    def next_step(self):
        self.idx += 1
        if self.idx >= len(self.steps):
            return self.finish()
        label, action = self.steps[self.idx]
        self.title.setText(label)
        self.append(f"\n━━━ {label} ━━━\n")
        if callable(action):
            try:
                self.append(action() or "")
                self.results.append((label, True))
            except Exception as e:  # noqa: BLE001
                self.ok = False
                self.results.append((label, False))
                self.append(tr("Error: {e}\n", e=e))
            QTimer.singleShot(0, self.next_step)
            return
        if action[0] == "pkexec":
            self.sub.setText(tr("Waiting for the administrator password…"))
        self.cur_argv = action
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.step_done)
        self.proc.errorOccurred.connect(self.proc_error)
        self.proc.start(action[0], action[1:])

    def read(self):
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        self.append(data.replace("\r\n", "\n").replace("\r", "\n"))

    def proc_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self.append(tr("Cannot start: {p}\n", p=self.cur_argv[0]))
            self.step_done(-1, QProcess.ExitStatus.CrashExit)

    def step_done(self, code, status):
        label = self.steps[self.idx][0]
        good = status == QProcess.ExitStatus.NormalExit and code == 0
        self.results.append((label, good))
        if not good:
            self.ok = False
            if self.cur_argv[0] == "pkexec" and code in (126, 127):
                self.append(tr("\n✗ Password entry cancelled or permission denied.\n"))
            else:
                self.append(tr("\n✗ Finished with an error (code {code}).\n", code=code))
        else:
            self.append(tr("\n✓ Done.\n"))
        if self.proc:
            self.proc.deleteLater()
            self.proc = None
        QTimer.singleShot(0, self.next_step)

    def finish(self):
        self.running = False
        self.status.set_state("ok" if self.ok else "error")
        if self.ok:
            self.title.setText(tr("Done!"))
            self.sub.setText(tr("All operations completed successfully."))
        else:
            self.title.setText(tr("Not everything worked"))
            self.sub.setText(tr("Some operations failed — see the details below."))
            if not self.text.isVisible():
                self._toggle()
        self.btn.setEnabled(True)
        self.btn.setFocus()

    def reject(self):
        if not self.running:
            super().reject()

    def closeEvent(self, ev):
        if self.running:
            ev.ignore()
        else:
            super().closeEvent(ev)


class ConfirmDialog(QDialog):
    def __init__(self, parent, apps, extras, critical, snapshot):
        super().__init__(parent)
        self.setWindowTitle(tr("Confirm uninstall"))
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)
        total = sum(a.size for a in apps)
        row, _t, _s = header(icon_label("edit-delete", 44), tr("Uninstall {programs}?", programs=n_(len(apps), "program")),
                             tr("You will free about {size}. The programs' configuration and data will be removed "
                                "with them.", size=core.human(total)))
        lay.addLayout(row)
        lst = QListWidget()
        lst.setObjectName("Mini")
        lst.setIconSize(QSize(28, 28))
        for a in apps:
            it = QListWidgetItem(QIcon(theme.pixmap_for(a, 56)),
                                 f"{a.name}   ·   {core.KIND_LABEL[a.kind]}   ·   {core.human(a.size)}")
            lst.addItem(it)
        lay.addWidget(lst, 1)
        if extras:
            n = QLabel(tr("<b>apt will also remove</b> (they depend on the removed ones):<br>{list}", list=", ".join(extras)))
            n.setObjectName("Note")
            n.setWordWrap(True)
            lay.addWidget(n)
        if snapshot:
            s = QLabel("🛟 " + snapshot)
            s.setObjectName("Note")
            s.setWordWrap(True)
            lay.addWidget(s)
        self.risk = None
        if critical:
            w = QLabel(tr("⚠ <b>Warning:</b> the removal includes packages important for the system: <b>{list}</b>. "
                          "This may break the system or the KDE desktop.", list=", ".join(critical)))
            w.setObjectName("Warn")
            w.setWordWrap(True)
            lay.addWidget(w)
            self.risk = QCheckBox(tr("I understand the risk and want to continue"))
            lay.addWidget(self.risk)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(tr("Cancel"))
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        self.ok_btn = QPushButton(QIcon.fromTheme("edit-delete"), tr("  Uninstall ({n})", n=len(apps)))
        self.ok_btn.setObjectName("Danger")
        self.ok_btn.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(self.ok_btn)
        lay.addLayout(btns)
        if self.risk:
            self.ok_btn.setEnabled(False)
            self.risk.toggled.connect(self.ok_btn.setEnabled)
        cancel.setFocus()


class TextDialog(QDialog):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 540)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        t = QPlainTextEdit(readOnly=True)
        t.setObjectName("Console")
        t.setFont(mono_font())
        t.setPlainText(text)
        lay.addWidget(t)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton(tr("Close"))
        b.setObjectName("Primary")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)


class LeftoverDialog(BgMixin, QDialog):
    def __init__(self, parent, cands, title, to_trash=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(940, 600)
        self.cands = cands
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)
        total = sum(c.size for c in cands)
        sure = sum(c.sure for c in cands)
        row, _t, self.sub = header(
            icon_label("edit-clear-all", 44),
            tr("Found {leftovers} ({size})", leftovers=n_(len(cands), "leftover"), size=core.human(total)),
            tr("{sure} confirmed matches are selected. Check items marked “possible” before deleting them.", sure=sure))
        lay.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setObjectName("Leftovers")
        self.tree.setHeaderLabels([tr("Path"), tr("Type"), tr("Size"), tr("Certainty")])
        self.tree.setAlternatingRowColors(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.menu)
        self.groups = {}
        th = theme.current()
        for root, label, icon in ((False, tr("Your files — go to the Trash"), "user-home"),
                                  (True, tr("System files — need a password, deleted permanently"), "folder-root")):
            g = QTreeWidgetItem([label])
            g.setFlags(g.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            g.setIcon(0, QIcon.fromTheme(icon))
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            self.groups[root] = g
        for c in cands:
            it = QTreeWidgetItem([c.path, tr(c.where), core.human(c.size), tr("confirmed") if c.sure else tr("possible")])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if c.sure else Qt.CheckState.Unchecked)
            it.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it.setIcon(0, QIcon.fromTheme("folder" if os.path.isdir(c.path) else "text-x-generic"))
            it.setForeground(3, QBrush(th.success if c.sure else th.warning))
            it.cand = c
            self.groups[c.root].addChild(it)
        for g in self.groups.values():
            if g.childCount():
                self.tree.addTopLevelItem(g)
                g.setExpanded(True)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2, 3):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tree, 1)

        r1 = QHBoxLayout()
        for text, mode in ((tr("Select confirmed"), "sure"), (tr("Select all"), "all"), (tr("Select none"), "none")):
            b = QPushButton(text)
            b.setObjectName("Ghost")
            b.clicked.connect(lambda _=False, m=mode: self.mark(m))
            r1.addWidget(b)
        r1.addStretch()
        self.trash_cb = QCheckBox(tr("Move your files to the Trash"))
        self.trash_cb.setChecked(to_trash)
        r1.addWidget(self.trash_cb)
        lay.addLayout(r1)

        r2 = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        r2.addWidget(self.status, 1)
        close = QPushButton(tr("Close"))
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        self.del_btn = QPushButton(QIcon.fromTheme("edit-delete"), tr("  Delete selected"))
        self.del_btn.setObjectName("Danger")
        self.del_btn.clicked.connect(self.delete)
        r2.addWidget(close)
        r2.addWidget(self.del_btn)
        lay.addLayout(r2)

    def leaves(self):
        for g in self.groups.values():
            for i in range(g.childCount()):
                yield g.child(i)

    def mark(self, mode):
        for it in self.leaves():
            on = mode == "all" or (mode == "sure" and it.cand.sure)
            it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it or not hasattr(it, "cand"):
            return
        m = QMenu(self)
        m.addAction(QIcon.fromTheme("document-open-folder"), tr("Open location"),
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(it.cand.path).parent))))
        m.addAction(QIcon.fromTheme("edit-copy"), tr("Copy path"),
                    lambda: QApplication.clipboard().setText(it.cand.path))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def delete(self):
        sel = [it for it in self.leaves() if it.checkState(0) == Qt.CheckState.Checked]
        if not sel:
            self.status.setText(tr("Nothing selected."))
            return
        cands = [it.cand for it in sel]
        n_root = sum(c.root for c in cands)
        msg = tr("Delete {items} ({size})?", items=n_(len(cands), "item"), size=core.human(sum(c.size for c in cands)))
        if n_root:
            msg += tr("\n\n{n} of them are system files — you will be asked for a password.", n=n_root)
        if QMessageBox.question(self, tr("Delete leftovers"), msg) != QMessageBox.StandardButton.Yes:
            return
        self.del_btn.setEnabled(False)
        self.status.setText(tr("Deleting…"))
        self._pending = sel
        self.bg(core.delete_candidates, cands, self.trash_cb.isChecked(), cb=self.deleted)

    def deleted(self, res):
        self.del_btn.setEnabled(True)
        if isinstance(res, Exception):
            self.status.setText(tr("Error: {e}", e=res))
            return
        ok, msgs = res
        for it in self._pending:
            if not os.path.lexists(it.cand.path):
                it.parent().removeChild(it)
        self.freed = True
        self.status.setText(tr("✓ Deleted: {n}.", n=ok) + (tr(" Problems: ") + "; ".join(msgs) if msgs else ""))


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("About {app}", app=APP_NAME))
        self.setFixedWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 22)
        lay.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(theme.app_icon().pixmap(96, 96))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        t = QLabel(APP_NAME)
        t.setObjectName("PageTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        v = QLabel(tr("Version {v}", v=VERSION))
        v.setObjectName("Muted")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(v)
        d = QLabel(tr("Uninstalls programs from APT, Flatpak, Snap, AppImage and /opt — together with their configuration "
                      "and leftovers. An IObit Uninstaller–style tool for Debian and KDE Plasma."))
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(8)
        lay.addWidget(d)
        lay.addSpacing(10)
        b = QPushButton(tr("Close"))
        b.setObjectName("Primary")
        b.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
