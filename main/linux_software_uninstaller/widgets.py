"""Custom widgets of Linux Software Uninstaller."""

from PyQt6.QtCore import (Qt, QSize, QRect, QRectF, QTimer, QPointF, QEvent, QModelIndex,
                          QAbstractListModel, QPropertyAnimation, QEasingCurve, QThread,
                          pyqtSignal, pyqtProperty)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPainterPath, QIcon
from PyQt6.QtWidgets import (QAbstractButton, QWidget, QPushButton, QFrame, QLabel, QHBoxLayout,
                             QVBoxLayout, QStyledItemDelegate, QStyle, QGraphicsOpacityEffect,
                             QStackedLayout, QGridLayout, QSizePolicy)

from . import core, theme
from .i18n import tr

APP_ROLE = Qt.ItemDataRole.UserRole + 1


# ───────────────────────────── threads ─────────────────────────────

class Worker(QThread):
    done = pyqtSignal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self.fn, self.args = fn, args

    def run(self):
        try:
            res = self.fn(*self.args)
        except Exception as e:  # noqa: BLE001
            res = e
        self.done.emit(res)


class BgMixin:
    def bg(self, fn, *args, cb=None):
        if not hasattr(self, "_workers"):
            self._workers = []
        w = Worker(fn, *args, parent=self)
        if cb:
            w.done.connect(cb)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()
        return w


# ───────────────────────────── small widgets ─────────────────────────────

class ToggleSwitch(QAbstractButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._p = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(46, 26)

    def _get(self):
        return self._p

    def _set(self, v):
        self._p = v
        self.update()

    knob = pyqtProperty(float, _get, _set)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._p)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e):
        th = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, (self.height() - 24) / 2, 44, 24)
        track = theme.mix(th.border.darker(115) if not th.dark else th.border.lighter(130), th.accent, self._p)
        if not self.isEnabled():
            track.setAlphaF(0.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, 12, 12)
        d = 18
        x = r.left() + 3 + (r.width() - 6 - d) * self._p
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))
        p.setBrush(QColor("white") if self.isEnabled() else QColor(230, 230, 230))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Spinner(QWidget):
    def __init__(self, size=22, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle - 7) % 360
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = max(2.0, self.width() / 9)
        r = QRectF(w, w, self.width() - 2 * w, self.height() - 2 * w)
        bg = QColor(theme.current().accent)
        bg.setAlphaF(0.18)
        p.setPen(QPen(bg, w))
        p.drawEllipse(r)
        pen = QPen(theme.current().accent, w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, self._angle * 16, 100 * 16)


class StatusIcon(QWidget):
    """Large status icon: spinner, green tick or red cross."""

    def __init__(self, size=44, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state = "busy"
        self.spin = Spinner(size, self)

    def set_state(self, state):
        self.state = state
        self.spin.setVisible(state == "busy")
        self.update()

    def paintEvent(self, _e):
        if self.state == "busy":
            return
        th = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = th.success if self.state == "ok" else th.danger
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        s = self.width()
        p.drawEllipse(QRectF(1, 1, s - 2, s - 2))
        pen = QPen(QColor("white"), s / 11)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        if self.state == "ok":
            path = QPainterPath(QPointF(s * 0.29, s * 0.52))
            path.lineTo(s * 0.44, s * 0.66)
            path.lineTo(s * 0.72, s * 0.36)
            p.drawPath(path)
        else:
            p.drawLine(QPointF(s * 0.34, s * 0.34), QPointF(s * 0.66, s * 0.66))
            p.drawLine(QPointF(s * 0.66, s * 0.34), QPointF(s * 0.34, s * 0.66))


class NavButton(QPushButton):
    def __init__(self, icon_name, text, parent=None):
        super().__init__(QIcon.fromTheme(icon_name), "  " + text, parent)
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.count = None

    def set_count(self, n):
        self.count = n
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = theme.current()
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() * 0.85))
        f.setBold(True)
        p.setFont(f)
        txt = str(self.count)
        w = QFontMetrics(f).horizontalAdvance(txt) + 14
        r = QRectF(self.width() - w - 22, (self.height() - 18) / 2, w, 18)
        bg = QColor(th.accent if self.isChecked() else th.muted)
        bg.setAlphaF(0.22 if self.isChecked() else 0.16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 9, 9)
        p.setPen(th.text if not self.isChecked() else th.accent.lighter(130) if th.dark else th.accent.darker(115))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)


class StatCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon_name, title, color, clickable=False, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setProperty("clickable", "true" if clickable else "false")
        self.clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color = QColor(color)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)
        self.bubble = QLabel()
        self.bubble.setFixedSize(46, 46)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_name = icon_name
        lay.addWidget(self.bubble)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.value = QLabel("—")
        self.value.setObjectName("CardValue")
        self.title = QLabel(title)
        self.title.setObjectName("CardLabel")
        col.addWidget(self.value)
        col.addWidget(self.title)
        lay.addLayout(col, 1)
        self.restyle()

    def restyle(self):
        self.bubble.setStyleSheet(f"background: {theme.rgba(self.color, 0.16)}; border-radius: 13px;")
        self.bubble.setPixmap(QIcon.fromTheme(self.icon_name).pixmap(24, 24))

    def set_value(self, v, sub=None):
        self.value.setText(v)
        if sub is not None:
            self.title.setText(sub)

    def mouseReleaseEvent(self, e):
        if self.clickable and e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.hide()
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.finished.connect(self._done)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fade_out)
        self._hiding = False
        parent.installEventFilter(self)

    def show_msg(self, text, ms=3800):
        self.setText(text)
        self.adjustSize()
        self._place()
        self.raise_()
        self.show()
        self._hiding = False
        self._anim.stop()
        self._anim.setStartValue(self._eff.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)

    def fade_out(self):
        self._hiding = True
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _done(self):
        if self._hiding:
            self.hide()

    def _place(self):
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 30)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False


class SettingRow(QFrame):
    def __init__(self, title, desc, switch, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        f = t.font()
        f.setBold(True)
        t.setFont(f)
        self.desc = QLabel(desc)
        self.desc.setObjectName("Muted")
        self.desc.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(self.desc)
        lay.addLayout(col, 1)
        lay.addSpacing(16)
        lay.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)


def badge_label(kind):
    th = theme.current()
    lab = QLabel(tr(core.KIND_LONG.get(kind, kind)))
    c = th.kind_color(kind)
    lab.setStyleSheet(f"background: {theme.rgba(c, 0.16)}; color: {c.name()}; border-radius: 10px;"
                      f" padding: 3px 12px; font-weight: 600;")
    lab.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lab


# ───────────────────────────── program list ─────────────────────────────

class AppModel(QAbstractListModel):
    checkedChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.checked = set()

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if not idx.isValid():
            return None
        a = self.rows[idx.row()]
        if role == APP_ROLE:
            return a
        if role == Qt.ItemDataRole.DisplayRole:
            return a.name
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if a.key in self.checked else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = f"<b>{a.name}</b><br>{a.ident}<br>{a.summary}"
            if a.essential:
                tip += "<br><i>" + tr("Essential system package — cannot be removed.") + "</i>"
            return tip
        return None

    def toggle(self, idx, state=None):
        a = self.rows[idx.row()]
        if a.essential:
            return
        on = (a.key not in self.checked) if state is None else state
        if on:
            self.checked.add(a.key)
        else:
            self.checked.discard(a.key)
        self.dataChanged.emit(idx, idx)
        self.checkedChanged.emit()

    def set_all(self, keys):
        self.checked = set(keys)
        if self.rows:
            self.dataChanged.emit(self.index(0), self.index(len(self.rows) - 1))
        self.checkedChanged.emit()


class AppDelegate(QStyledItemDelegate):
    ROW_H = 66

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = {}

    def clear_cache(self):
        self._pix.clear()

    def sizeHint(self, opt, idx):
        return QSize(opt.rect.width(), self.ROW_H)

    @staticmethod
    def _cb_rect(r):
        return QRect(r.left() + 14, r.center().y() - 10, 20, 20)

    def _pixmap(self, a, size):
        k = (a.key, size)
        if k not in self._pix:
            self._pix[k] = theme.pixmap_for(a, size)
        return self._pix[k]

    def paint(self, p, opt, idx):
        a = idx.data(APP_ROLE)
        checked = idx.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        th = theme.current()
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = opt.rect.adjusted(6, 2, -6, -2)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        sel = bool(opt.state & QStyle.StateFlag.State_Selected)

        if sel or checked or hover:
            c = QColor(th.accent)
            c.setAlphaF(0.20 if sel else 0.12 if checked else 0.07)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(r), 11, 11)
        if sel:
            bar = QRectF(r.left() + 1, r.top() + 14, 3, r.height() - 28)
            p.setBrush(th.accent)
            p.drawRoundedRect(bar, 1.5, 1.5)

        # checkbox
        cb = QRectF(self._cb_rect(r))
        if a.essential:
            p.drawPixmap(cb.toRect(), QIcon.fromTheme("object-locked").pixmap(20, 20))
        elif checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(th.accent)
            p.drawRoundedRect(cb, 6, 6)
            pen = QPen(th.accent_text, 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath(QPointF(cb.left() + 5, cb.top() + 10.5))
            path.lineTo(cb.left() + 8.5, cb.top() + 14)
            path.lineTo(cb.left() + 15, cb.top() + 6.5)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        else:
            p.setPen(QPen(th.muted if hover else th.border.darker(105) if not th.dark else th.border.lighter(140), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(cb.adjusted(0.8, 0.8, -0.8, -0.8), 6, 6)

        # icon
        ir = QRect(int(cb.right()) + 14, r.center().y() - 20, 40, 40)
        p.drawPixmap(ir, self._pixmap(a, 40 * max(1, int(p.device().devicePixelRatioF()))))

        right = r.right() - 16
        base = QFont(opt.font)

        # size and date
        f_size = QFont(base)
        f_size.setBold(True)
        p.setFont(f_size)
        p.setPen(th.text if not a.essential else th.muted)
        size_rect = QRect(right - 90, r.top() + 13, 90, 20)
        p.drawText(size_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, core.human(a.size))
        f_small = QFont(base)
        f_small.setPointSizeF(base.pointSizeF() * 0.88)
        p.setFont(f_small)
        p.setPen(th.muted)
        p.drawText(QRect(right - 110, r.top() + 34, 110, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, core.fmt_date(a.installed))

        # source badge
        f_badge = QFont(base)
        f_badge.setPointSizeF(base.pointSizeF() * 0.8)
        f_badge.setBold(True)
        p.setFont(f_badge)
        label = core.KIND_LABEL[a.kind]
        bw = QFontMetrics(f_badge).horizontalAdvance(label) + 18
        br = QRectF(right - 128 - bw, r.center().y() - 10, bw, 20)
        kc = th.kind_color(a.kind)
        bgc = QColor(kc)
        bgc.setAlphaF(0.16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bgc)
        p.drawRoundedRect(br, 10, 10)
        p.setPen(kc)
        p.drawText(br, Qt.AlignmentFlag.AlignCenter, label)

        # name and description
        tx = ir.right() + 14
        tw = int(br.left()) - 14 - tx
        f_name = QFont(base)
        f_name.setPointSizeF(base.pointSizeF() * 1.08)
        f_name.setBold(True)
        p.setFont(f_name)
        p.setPen(th.text if not a.essential else th.muted)
        name = QFontMetrics(f_name).elidedText(a.name, Qt.TextElideMode.ElideRight, tw)
        p.drawText(QRect(tx, r.top() + 11, tw, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        p.setFont(f_small)
        p.setPen(th.muted)
        sub = a.summary or a.ident
        if a.kind == "apt" and a.name != a.ident.split(":")[0]:
            sub = f"{a.ident} · {sub}"
        sub = QFontMetrics(f_small).elidedText(sub, Qt.TextElideMode.ElideRight, tw)
        p.drawText(QRect(tx, r.top() + 34, tw, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
        p.restore()

    def editorEvent(self, ev, model, opt, idx):
        if ev.type() == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.LeftButton:
            hit = self._cb_rect(opt.rect.adjusted(6, 2, -6, -2)).adjusted(-10, -14, 10, 14)
            if hit.contains(ev.position().toPoint()):
                model.toggle(idx)
                return True
        if ev.type() == QEvent.Type.MouseButtonDblClick and ev.button() == Qt.MouseButton.LeftButton:
            model.toggle(idx)
            return True
        return False


# ───────────────────────────── details panel ─────────────────────────────

class DetailPanel(QFrame):
    uninstall = pyqtSignal(object)
    scan = pyqtSignal(object)
    details = pyqtSignal(object)
    open_loc = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(330)
        self.app = None
        self.stack = QStackedLayout(self)

        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch()
        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_icon)
        t = QLabel(tr("Pick a program from the list\nto see its details"))
        t.setObjectName("Muted")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        tip = QLabel(tr("Click the checkbox or double-click\nto select several programs at once."))
        tip.setObjectName("Muted")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addSpacing(14)
        el.addWidget(tip)
        el.addStretch()
        self.stack.addWidget(empty)

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 26, 22, 20)
        lay.setSpacing(8)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedHeight(104)
        lay.addWidget(self.icon)
        self.name = QLabel()
        self.name.setObjectName("DetailName")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name.setWordWrap(True)
        lay.addWidget(self.name)
        self.badge_row = QHBoxLayout()
        self.badge_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(self.badge_row)
        lay.addSpacing(8)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(7)
        self.grid.setColumnStretch(1, 1)
        lay.addLayout(self.grid)
        lay.addSpacing(6)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setObjectName("Muted")
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.desc)
        lay.addStretch()
        self.warn = QLabel(tr("🔒 Essential system package — it cannot be uninstalled."))
        self.warn.setObjectName("Warn")
        self.warn.setWordWrap(True)
        lay.addWidget(self.warn)
        self.btn_uninst = QPushButton(QIcon.fromTheme("edit-delete"), tr("  Uninstall"))
        self.btn_uninst.setObjectName("Danger")
        self.btn_uninst.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_uninst.clicked.connect(lambda: self.uninstall.emit(self.app))
        lay.addWidget(self.btn_uninst)
        row = QHBoxLayout()
        self.btn_scan = QPushButton(QIcon.fromTheme("edit-find"), tr(" Find leftovers"))
        self.btn_scan.setObjectName("Ghost")
        self.btn_scan.setToolTip(tr("Show the files this program left in the system (without uninstalling)"))
        self.btn_scan.clicked.connect(lambda: self.scan.emit(self.app))
        self.btn_more = QPushButton(QIcon.fromTheme("documentinfo"), tr(" Details"))
        self.btn_more.setObjectName("Ghost")
        self.btn_more.clicked.connect(self._more)
        row.addWidget(self.btn_scan)
        row.addWidget(self.btn_more)
        lay.addLayout(row)
        self.stack.addWidget(page)
        self.restyle()

    def restyle(self):
        self.empty_icon.setPixmap(theme.app_icon().pixmap(72, 72))
        if self.app:
            self.set_app(self.app)

    def _more(self):
        if self.app and self.app.kind in ("appimage", "opt"):
            self.open_loc.emit(self.app)
        else:
            self.details.emit(self.app)

    def set_app(self, a):
        self.app = a
        if a is None:
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        self.icon.setPixmap(theme.pixmap_for(a, 96))
        self.name.setText(a.name)
        while self.badge_row.count():
            w = self.badge_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.badge_row.addWidget(badge_label(a.kind))
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        rows = [(tr("Version"), a.version or "—"), (tr("Size"), core.human(a.size)),
                (tr("Installed"), core.fmt_date(a.installed)), (tr("Identifier"), a.ident)]
        if a.kind == "flatpak":
            rows.append((tr("Installation"), tr("per-user") if a.extra == "user" else tr("system-wide")))
        if a.kind == "apt":
            rows.append((tr("Installation"), tr("manual") if a.manual else tr("as a dependency")))
        for i, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setObjectName("InfoKey")
            vl = QLabel(v)
            vl.setWordWrap(True)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.grid.addWidget(kl, i, 0, Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(vl, i, 1)
        self.desc.setText(a.summary if a.summary and a.summary != a.ident else "")
        self.warn.setVisible(a.essential)
        self.btn_uninst.setEnabled(not a.essential)
        if a.kind in ("appimage", "opt"):
            self.btn_more.setText(tr(" Location"))
            self.btn_more.setIcon(QIcon.fromTheme("document-open-folder"))
        else:
            self.btn_more.setText(tr(" Details"))
            self.btn_more.setIcon(QIcon.fromTheme("documentinfo"))
