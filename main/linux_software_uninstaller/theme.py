"""Kolory i arkusz stylów — wyliczane z palety KDE, więc działa w jasnym i ciemnym motywie."""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPalette, QIcon, QPixmap, QPainter, QFont

from . import core

KIND_COLORS = {"apt": "#d70a53", "flatpak": "#4a86cf", "snap": "#e95420",
               "appimage": "#2ea44f", "opt": "#8e6ad8"}
DANGER = "#e5484d"
WARNING = "#e8a23a"
SUCCESS = "#30a46c"

_current = None


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() * (1 - t) + b.red() * t),
                  round(a.green() * (1 - t) + b.green() * t),
                  round(a.blue() * (1 - t) + b.blue() * t))


def rgba(c, alpha):
    c = QColor(c)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha:.3f})"


class Theme:
    def __init__(self, pal: QPalette):
        self.window = pal.color(QPalette.ColorRole.Window)
        self.base = pal.color(QPalette.ColorRole.Base)
        self.text = pal.color(QPalette.ColorRole.WindowText)
        self.accent = pal.color(QPalette.ColorRole.Highlight)
        self.accent_text = pal.color(QPalette.ColorRole.HighlightedText)
        self.dark = self.window.lightness() < 128
        if self.dark:
            self.sidebar = mix(self.window, QColor("black"), 0.22)
            self.surface = mix(self.window, QColor("white"), 0.035)
        else:
            self.sidebar = mix(self.window, self.text, 0.035)
            self.surface = self.base
        self.border = mix(self.window, self.text, 0.14 if self.dark else 0.12)
        self.muted = mix(self.text, self.window, 0.45)
        self.danger = QColor(DANGER)
        self.warning = QColor(WARNING)
        self.success = QColor(SUCCESS)

    def kind_color(self, kind):
        c = QColor(KIND_COLORS.get(kind, "#888888"))
        return c.lighter(135) if self.dark else c

    def hover(self):
        return rgba(self.accent, 0.10)

    def selected(self):
        return rgba(self.accent, 0.20)

    def qss(self):
        t = self
        accent_strong = t.accent.lighter(140) if t.dark else t.accent.darker(110)
        return f"""
QMainWindow, QDialog {{ background: {t.window.name()}; }}
#Sidebar {{ background: {t.sidebar.name()}; border-right: 1px solid {t.border.name()}; }}
#AppTitle {{ font-size: 12.5pt; font-weight: 700; }}
#AppSubtitle {{ color: {t.muted.name()}; font-size: 8.5pt; }}
#NavSection {{ color: {t.muted.name()}; font-size: 7.5pt; font-weight: 700; padding: 14px 20px 4px 20px; }}
QPushButton#Nav {{ text-align: left; padding: 8px 12px; border: none; border-radius: 8px;
    background: transparent; margin: 1px 10px; }}
QPushButton#Nav:hover {{ background: {t.hover()}; }}
QPushButton#Nav:checked {{ background: {t.selected()}; color: {accent_strong.name()}; font-weight: 600; }}
#PageTitle {{ font-size: 19pt; font-weight: 700; }}
#PageSubtitle, #Muted {{ color: {t.muted.name()}; }}
#SectionTitle {{ font-size: 11pt; font-weight: 700; }}
QLineEdit#Search {{ padding: 9px 12px; border: 1px solid {t.border.name()}; border-radius: 10px;
    background: {t.surface.name()}; font-size: 10.5pt; }}
QLineEdit#Search:focus {{ border: 1px solid {t.accent.name()}; }}
QLineEdit#Field {{ padding: 7px 10px; border: 1px solid {t.border.name()}; border-radius: 8px;
    background: {t.surface.name()}; }}
QLineEdit#Field:focus {{ border: 1px solid {t.accent.name()}; }}
#Card {{ background: {t.surface.name()}; border: 1px solid {t.border.name()}; border-radius: 14px; }}
#Card[clickable="true"]:hover {{ border: 1px solid {t.accent.name()}; }}
#CardValue {{ font-size: 16pt; font-weight: 700; }}
#CardLabel {{ color: {t.muted.name()}; }}
QListView#AppList {{ background: {t.surface.name()}; border: 1px solid {t.border.name()};
    border-radius: 14px; padding: 6px 2px; outline: none; }}
#DetailPanel {{ background: {t.surface.name()}; border: 1px solid {t.border.name()}; border-radius: 14px; }}
#DetailName {{ font-size: 15pt; font-weight: 700; }}
#InfoKey {{ color: {t.muted.name()}; }}
QPushButton#Danger {{ background: {t.danger.name()}; color: white; border: none; border-radius: 9px;
    padding: 9px 18px; font-weight: 600; }}
QPushButton#Danger:hover {{ background: {t.danger.lighter(112).name()}; }}
QPushButton#Danger:pressed {{ background: {t.danger.darker(110).name()}; }}
QPushButton#Danger:disabled {{ background: {t.border.name()}; color: {t.muted.name()}; }}
QPushButton#Primary {{ background: {t.accent.name()}; color: {t.accent_text.name()}; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {t.accent.lighter(112).name()}; }}
QPushButton#Primary:disabled {{ background: {t.border.name()}; color: {t.muted.name()}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {t.border.name()}; border-radius: 9px;
    padding: 8px 14px; }}
QPushButton#Ghost:hover {{ background: {t.hover()}; border-color: {t.accent.name()}; }}
QPushButton#Ghost:disabled {{ color: {t.muted.name()}; }}
QPushButton#Link {{ background: transparent; border: none; color: {accent_strong.name()}; padding: 4px; }}
QPushButton#Link:hover {{ text-decoration: underline; }}
#ActionBar {{ background: {rgba(t.accent, 0.16 if t.dark else 0.11)}; border: 1px solid {rgba(t.accent, 0.45)};
    border-radius: 14px; }}
#ActionText {{ font-weight: 600; }}
QProgressBar#Busy {{ border: none; background: transparent; max-height: 3px; min-height: 3px; }}
QProgressBar#Busy::chunk {{ background: {t.accent.name()}; border-radius: 1px; }}
QComboBox#Sort {{ padding: 7px 10px; border: 1px solid {t.border.name()}; border-radius: 9px;
    background: {t.surface.name()}; min-width: 150px; }}
QPlainTextEdit#Console {{ background: {t.sidebar.name()}; border: 1px solid {t.border.name()};
    border-radius: 10px; padding: 6px; }}
QListWidget#Mini, QTreeWidget#Leftovers {{ background: {t.surface.name()}; border: 1px solid {t.border.name()};
    border-radius: 10px; padding: 4px; outline: none; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 6px 2px; }}
QScrollBar::handle:vertical {{ background: {rgba(t.text, 0.22)}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {rgba(t.text, 0.38)}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
#Toast {{ background: {rgba(QColor('#1d1f23'), 0.94)}; color: white; border-radius: 12px; padding: 11px 18px; }}
#Warn {{ background: {rgba(t.danger, 0.12)}; border: 1px solid {rgba(t.danger, 0.5)}; border-radius: 10px; padding: 10px; }}
#Note {{ background: {rgba(t.accent, 0.08)}; border-radius: 10px; padding: 10px; }}
QToolTip {{ padding: 4px 6px; }}
"""


def current():
    return _current


def apply(app):
    global _current
    _current = Theme(app.palette())
    app.setStyleSheet(_current.qss())
    return _current


# ───────────────────────────── ikony ─────────────────────────────

_icon_cache = {}


def app_icon():
    ic = QIcon.fromTheme("linux-software-uninstaller")
    if ic.isNull():
        for p in (Path(__file__).resolve().parent.parent / "data" / "linux-software-uninstaller.svg",
                  Path("/usr/share/icons/hicolor/scalable/apps/linux-software-uninstaller.svg")):
            if p.exists():
                return QIcon(str(p))
        ic = QIcon.fromTheme("edit-delete")
    return ic


def icon_for(name, kind):
    k = (name, kind)
    if k in _icon_cache:
        return _icon_cache[k]
    ic = QIcon()
    if name:
        if os.path.isabs(name):
            ic = QIcon(name) if os.path.exists(name) else QIcon()
        else:
            ic = QIcon.fromTheme(name)
    _icon_cache[k] = ic
    return ic


def letter_pixmap(text, color, size):
    """Zastępcza ikona: kolorowy kafelek z pierwszą literą nazwy."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 0, size, size, size * 0.28, size * 0.28)
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(size * 0.5))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, (text or "?")[:1].upper())
    p.end()
    return pm


def pixmap_for(app, size):
    ic = icon_for(app.icon, app.kind)
    if ic.isNull():
        return letter_pixmap(app.name, current().kind_color(app.kind) if current() else "#888", size)
    return ic.pixmap(QSize(size, size))
