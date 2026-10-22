"""Reusable glass-style widgets."""

from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QScrollArea, QSizePolicy,
                               QSpinBox, QStyledItemDelegate, QStyleOptionViewItem,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.status import Status
from ..i18n import tr
from . import icons, theme

STATUS_ROLE = Qt.ItemDataRole.UserRole + 1
SORT_ROLE = Qt.ItemDataRole.UserRole + 2


class GradientBackground(QWidget):
    """Navy-to-turquoise backdrop with a soft light bloom."""

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        rect = self.rect()
        grad = QLinearGradient(QPointF(0, 0), QPointF(rect.width(), rect.height()))
        grad.setColorAt(0.0, QColor(theme.BG_START))
        grad.setColorAt(0.55, QColor(theme.BG_MID))
        grad.setColorAt(1.0, QColor(theme.BG_END))
        p.fillRect(rect, grad)
        glow = QRadialGradient(QPointF(rect.width() * 0.92, rect.height() * 0.35),
                               max(rect.width(), rect.height()) * 0.55)
        glow.setColorAt(0.0, QColor(140, 220, 230, 70))
        glow.setColorAt(1.0, QColor(140, 220, 230, 0))
        p.fillRect(rect, glow)


class Card(QFrame):
    """Rounded translucent panel with an optional title row."""

    def __init__(self, title: str = "", hint: str = "", parent: QWidget | None = None,
                 strong: bool = False, margins: int = 18):
        super().__init__(parent)
        self.setObjectName("Card")
        if strong:
            self.setProperty("strong", True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(margins, margins - 2, margins, margins)
        outer.setSpacing(10)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("Hint")
        self.hint_label.setWordWrap(True)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addWidget(self.title_label)
        titles.addWidget(self.hint_label)
        self.title_label.setVisible(bool(title))
        self.hint_label.setVisible(bool(hint))
        self.header.addLayout(titles, 1)
        if title or hint:
            outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)

    def set_title(self, title: str, hint: str | None = None) -> None:
        self.title_label.setText(title)
        if hint is not None:
            self.hint_label.setText(hint)
            self.hint_label.setVisible(bool(hint))

    def add_header_widget(self, widget: QWidget) -> None:
        self.header.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)


class StatusBadge(QLabel):
    """Pill-shaped PASS / WARN / FAIL badge."""

    def __init__(self, status: Status | None = None, large: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._large = large
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: Status | None, text: str | None = None) -> None:
        color = theme.status_color(status)
        label = text or (tr(f"status.{status.value}") if status else tr("status.none"))
        pad = "6px 18px" if self._large else "2px 10px"
        size = "13pt" if self._large else "9pt"
        self.setText(label)
        self.setStyleSheet(
            f"QLabel {{ background: rgba({color.red()}, {color.green()}, {color.blue()}, 0.22);"
            f" border: 1px solid {color.name()}; color: {color.lighter(125).name()};"
            f" border-radius: {16 if self._large else 10}px; padding: {pad};"
            f" font-weight: 700; font-size: {size}; }}")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)


class Pill(QLabel):
    """Small coloured chip (wavelength tags, counts)."""

    def __init__(self, text: str, color: str = "#8fb4ff", parent: QWidget | None = None):
        super().__init__(text, parent)
        c = QColor(color)
        self.setStyleSheet(
            f"QLabel {{ background: rgba({c.red()}, {c.green()}, {c.blue()}, 0.20);"
            f" border: 1px solid rgba({c.red()}, {c.green()}, {c.blue()}, 0.65);"
            f" border-radius: 9px; padding: 1px 8px; font-size: 9pt; color: {c.lighter(130).name()}; }}")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)


def icon_label(name: str, size: int = 20, color: str = "#ffffff") -> QLabel:
    label = QLabel()
    label.setPixmap(icons.pixmap(name, size, color))
    label.setFixedSize(size + 4, size + 4)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        texts.addWidget(t)
        texts.addWidget(s)
        lay.addLayout(texts, 1)
        self.right = QHBoxLayout()
        self.right.setSpacing(8)
        lay.addLayout(self.right)


class StatCard(Card):
    def __init__(self, icon_name: str, label: str, parent: QWidget | None = None):
        super().__init__(parent=parent, margins=16)
        row = QHBoxLayout()
        row.setSpacing(14)
        badge = QLabel()
        badge.setPixmap(icons.pixmap(icon_name, 22))
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background: rgba(255,255,255,0.14); border-radius: 14px;")
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.value = QLabel("0")
        self.value.setObjectName("BigValue")
        self.caption = QLabel(label)
        self.caption.setObjectName("StatLabel")
        texts.addWidget(self.value)
        texts.addWidget(self.caption)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(texts, 1)
        self.body.addLayout(row)

    def set_value(self, value: object) -> None:
        self.value.setText(str(value))


class SegmentBar(QWidget):
    """Horizontal bar split into coloured segments proportional to their values."""

    def __init__(self, parent: QWidget | None = None, height: int = 12):
        super().__init__(parent)
        self._segments: list[tuple[float, QColor]] = []
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_segments(self, segments: Iterable[tuple[float, QColor | str]]) -> None:
        self._segments = [(max(0.0, v), QColor(c)) for v, c in segments]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        radius = r.height() / 2
        clip = QPainterPath()
        clip.addRoundedRect(r, radius, radius)
        p.setClipPath(clip)
        p.fillRect(r, QColor(255, 255, 255, 30))
        total = sum(v for v, _ in self._segments)
        if total <= 0:
            return
        x = r.left()
        for value, color in self._segments:
            w = r.width() * value / total
            p.fillRect(QRectF(x, r.top(), w, r.height()), color)
            x += w


class BreakdownChart(QWidget):
    """Labelled horizontal bars: one row per item, scaled to a common maximum."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._rows: list[tuple[str, float, str, str]] = []  # label, value, colour, value text
        self._scale = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_rows(self, rows: Sequence[tuple[str, float, str, str]], scale: float | None = None):
        self._rows = list(rows)
        self._scale = scale or max((abs(v) for _, v, _, _ in rows), default=1.0) or 1.0
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, max(1, len(self._rows)) * 30 + 4)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, max(1, len(self._rows)) * 26)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.tabular(self.font())
        p.setFont(font)
        fm = p.fontMetrics()
        label_w = max((fm.horizontalAdvance(r[0]) for r in self._rows), default=0) + 14
        value_w = max((fm.horizontalAdvance(r[3]) for r in self._rows), default=0) + 12
        n = max(1, len(self._rows))
        row_h = min(34.0, self.height() / n)
        bar_h = min(14.0, row_h * 0.5)
        track_w = max(10.0, self.width() - label_w - value_w)
        for i, (label, value, color, text) in enumerate(self._rows):
            y = i * row_h
            mid = y + row_h / 2
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(0, y, label_w, row_h), Qt.AlignmentFlag.AlignVCenter, label)
            track = QRectF(label_w, mid - bar_h / 2, track_w, bar_h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawRoundedRect(track, bar_h / 2, bar_h / 2)
            w = track_w * min(1.0, abs(value) / self._scale)
            if w > 0.5:
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(label_w, track.top(), max(w, bar_h), bar_h),
                                  bar_h / 2, bar_h / 2)
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(label_w + track_w, y, value_w, row_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, text)


class ElidedLabel(QLabel):
    """Single-line label that elides with an ellipsis instead of forcing its width."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        self.setToolTip(text)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def _elide(self) -> None:
        elided = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight,
                                               max(10, self.width()))
        super().setText(elided)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.fontMetrics().horizontalAdvance(self._full) + 4, super().sizeHint().height())


class RowWidget(QWidget):
    """List row: icon, title + subtitle, then right-aligned widgets and a chevron."""

    def __init__(self, icon_name: str, title: str, subtitle: str = "",
                 right: Sequence[QWidget] = (), chevron: bool = True,
                 parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(10)
        lay.addWidget(icon_label(icon_name, 18, theme.TEXT_2))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        t = ElidedLabel(title)
        t.setStyleSheet("font-weight: 600;")
        texts.addWidget(t)
        if subtitle:
            s = ElidedLabel(subtitle)
            s.setObjectName("Muted")
            texts.addWidget(s)
        lay.addLayout(texts, 1)
        for w in right:
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        if chevron:
            lay.addWidget(icon_label("chevron", 14, theme.TEXT_MUTED))


class RowList(QWidget):
    """Vertical list of clickable :class:`RowWidget` rows with thin separators."""

    activated = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)

    def clear(self) -> None:
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_row(self, row: QWidget, key: object) -> None:
        frame = ClickableFrame()
        frame.setObjectName("RowItem")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(row)
        frame.clicked.connect(lambda k=key: self.activated.emit(k))
        self._lay.insertWidget(self._lay.count() - 1, frame)


class FlowGrid(QWidget):
    """Lays child widgets out in as many equal columns as the width allows."""

    def __init__(self, min_column_width: int = 320, parent: QWidget | None = None):
        super().__init__(parent)
        self._min_w = min_column_width
        self._items: list[QWidget] = []
        self._cols = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(14)

    def set_widgets(self, widgets: Sequence[QWidget]) -> None:
        for w in self._items:
            self._grid.removeWidget(w)
            w.deleteLater()
        self._items = list(widgets)
        self._cols = 0
        self._relayout()

    def _relayout(self) -> None:
        cols = max(1, self.width() // self._min_w) if self.width() > 0 else 1
        if cols == self._cols:
            return
        self._cols = cols
        for w in self._items:
            self._grid.removeWidget(w)
        for i, w in enumerate(self._items):
            self._grid.addWidget(w, i // cols, i % cols, Qt.AlignmentFlag.AlignTop)
        for c in range(self._grid.columnCount()):
            self._grid.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()


class StatusDelegate(QStyledItemDelegate):
    """Draws a status pill in table cells that carry a :data:`STATUS_ROLE`."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        status = index.data(STATUS_ROLE)
        if not status:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.widget.style().drawControl(opt.widget.style().ControlElement.CE_ItemViewItem,
                                       opt, painter, opt.widget)
        st = Status(status)
        color = theme.status_color(st)
        text = index.data(Qt.ItemDataRole.DisplayRole) or st.value
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(max(7.5, font.pointSizeF() - 1))
        painter.setFont(font)
        w = painter.fontMetrics().horizontalAdvance(text) + 18
        h = min(20, option.rect.height() - 6)
        r = QRectF(option.rect.left() + 8, option.rect.center().y() - h / 2 + 0.5, w, h)
        fill = QColor(color)
        fill.setAlpha(55)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(r, h / 2, h / 2)
        painter.setPen(color.lighter(125))
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class Item(QTableWidgetItem):
    """Table item that sorts by an explicit key (numbers sort numerically)."""

    def __init__(self, text: str, sort_key: object = None, align_right: bool = False):
        super().__init__(text)
        self.setData(SORT_ROLE, text if sort_key is None else sort_key)
        self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if align_right:
            self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        a, b = self.data(SORT_ROLE), other.data(SORT_ROLE)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


def num_item(value: float | None, decimals: int = 2) -> Item:
    if value is None:
        return Item("—", float("-inf"), align_right=True)
    return Item(f"{value:.{decimals}f}", float(value), align_right=True)


def status_item(status: Status | None) -> Item:
    item = Item(status.value if status else "—", status.rank if status else -1)
    if status:
        item.setData(STATUS_ROLE, status.value)
    return item


def make_table(headers: Sequence[str], stretch_column: int | None = None,
               sortable: bool = True) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(32)
    table.setFont(theme.tabular(table.font()))
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(stretch_column is None)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if stretch_column is not None:
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    table.setItemDelegate(StatusDelegate(table))
    table.setSortingEnabled(sortable)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    return table


def fit_columns(table: QTableWidget, minimum: int = 40) -> None:
    """Size columns to their content and header text (Qt's own sizing reserves room
    for a sort arrow in every header, which wastes a lot of width)."""
    header = table.horizontalHeader()
    bold = header.font()
    bold.setBold(True)
    fm = QFontMetrics(bold)
    sorted_col = header.sortIndicatorSection() if table.isSortingEnabled() else -1
    for c in range(table.columnCount()):
        if header.sectionResizeMode(c) == QHeaderView.ResizeMode.Stretch:
            continue
        item = table.horizontalHeaderItem(c)
        title = fm.horizontalAdvance(item.text() if item else "") + 20 + (16 if c == sorted_col else 0)
        table.setColumnWidth(c, max(minimum, title, table.sizeHintForColumn(c) + 6))


def dspin(minimum: float, maximum: float, value: float, step: float = 0.1,
          decimals: int = 2, suffix: str = "") -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    if suffix:
        box.setSuffix(f" {suffix}")
    box.setKeyboardTracking(False)
    box.setFont(theme.tabular(box.font()))
    box.lineEdit().setTextMargins(6, 0, 0, 0)
    return box


def ispin(minimum: int, maximum: int, value: int, suffix: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    if suffix:
        box.setSuffix(f" {suffix}")
    box.setKeyboardTracking(False)
    box.setFont(theme.tabular(box.font()))
    box.lineEdit().setTextMargins(6, 0, 0, 0)
    return box


def scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(widget)
    area.viewport().setAutoFillBackground(False)
    widget.setAutoFillBackground(False)
    return area


class ClickableFrame(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
