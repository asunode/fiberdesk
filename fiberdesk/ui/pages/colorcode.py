"""TIA-598 colour code lookup and cable grid."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from ...core.colorcode import (CABLE_SIZES, TIA598_COLORS, ColorSpec, cable_grid, locate_fiber,
                               tracer_hex)
from ...i18n import tr
from .. import theme
from ..context import AppContext
from ..widgets import Card, PageHeader, ispin, scrollable


def _text_on(color: QColor) -> QColor:
    return QColor("#111111") if color.lightnessF() > 0.6 else QColor("#ffffff")


def paint_swatch(p: QPainter, rect: QRectF, spec: ColorSpec, radius: float) -> None:
    """A filled circle/rounded rect in ``spec``'s colour, with a tracer stripe if any."""
    color = QColor(spec.hex)
    p.setPen(QPen(QColor(255, 255, 255, 90), 1))
    p.setBrush(color)
    p.drawRoundedRect(rect, radius, radius)
    stripe = tracer_hex(spec)
    if stripe:
        p.save()
        p.setClipRect(rect)
        p.setPen(QPen(QColor(stripe), max(2.0, rect.height() * 0.16)))
        p.drawLine(QPointF(rect.left(), rect.bottom()), QPointF(rect.right(), rect.top()))
        p.restore()


class Swatch(QWidget):
    def __init__(self, size: int = 64):
        super().__init__()
        self._spec: ColorSpec | None = None
        self.setFixedSize(size, size)

    def set_spec(self, spec: ColorSpec) -> None:
        self._spec = spec
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._spec:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        paint_swatch(p, r, self._spec, r.width() / 2)


class FiberGrid(QWidget):
    """One row per buffer tube; each fibre drawn as a numbered dot."""

    fiber_clicked = Signal(int)

    LABEL_W = 118
    MIN_CELL = 26
    MAX_CELL = 44

    def __init__(self):
        super().__init__()
        self._rows = cable_grid(48)
        self._selected = 1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_cable(self, size: int, selected: int) -> None:
        self._rows = cable_grid(size)
        self._selected = selected
        self.updateGeometry()
        self.update()

    def set_selected(self, fiber: int) -> None:
        self._selected = fiber
        self.update()

    def _cell(self) -> float:
        cols = max(len(r) for r in self._rows)
        return max(self.MIN_CELL, min(self.MAX_CELL, (self.width() - self.LABEL_W) / cols))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        cols = max(len(r) for r in self._rows)
        cell = max(self.MIN_CELL, min(self.MAX_CELL, (width - self.LABEL_W) / cols))
        return int(len(self._rows) * cell) + 4

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.LABEL_W + 12 * 36, self.heightForWidth(self.LABEL_W + 12 * 36))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.LABEL_W + 12 * self.MIN_CELL, len(self._rows) * self.MIN_CELL)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.tabular(self.font())
        cell = self._cell()
        for r, row in enumerate(self._rows):
            y = r * cell
            tube = row[0].tube
            tube_rect = QRectF(4, y + cell * 0.18, 22, cell * 0.64)
            paint_swatch(p, tube_rect, tube, 6)
            p.setPen(QColor(theme.TEXT_2))
            font.setBold(False)
            font.setPointSizeF(9)
            p.setFont(font)
            p.drawText(QRectF(32, y, self.LABEL_W - 34, cell), Qt.AlignmentFlag.AlignVCenter,
                       f"{tr('color.tube')} {tube.position} · {tube.name}")
            for c, addr in enumerate(row):
                d = cell * 0.78
                rect = QRectF(self.LABEL_W + c * cell + (cell - d) / 2, y + (cell - d) / 2, d, d)
                selected = addr.fiber == self._selected
                if selected:
                    p.setPen(QPen(QColor("#ffffff"), 2.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(rect.adjusted(-3, -3, 3, 3))
                paint_swatch(p, rect, addr.color, d / 2)
                font.setPointSizeF(max(6.5, d * 0.27))
                font.setBold(selected)
                p.setFont(font)
                p.setPen(_text_on(QColor(addr.color.hex)))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(addr.fiber))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        cell = self._cell()
        row = int(event.position().y() // cell)
        col = int((event.position().x() - self.LABEL_W) // cell)
        if 0 <= row < len(self._rows) and 0 <= col < len(self._rows[row]) \
                and event.position().x() >= self.LABEL_W:
            self.fiber_clicked.emit(self._rows[row][col].fiber)


class ColorCodePage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("color.title"), tr("color.subtitle")))

        top = QHBoxLayout()
        top.setSpacing(14)
        lookup = Card(tr("color.lookup"), strong=True)
        form = QFormLayout()
        form.setSpacing(10)
        self.size = QComboBox()
        for n in CABLE_SIZES:
            self.size.addItem(tr("color.fibers", n=n), n)
        self.size.setCurrentIndex(CABLE_SIZES.index(48))
        self.fiber = ispin(1, 48, 37)
        form.addRow(tr("color.cable"), self.size)
        form.addRow(tr("color.fiber"), self.fiber)
        lookup.body.addLayout(form)

        result = QHBoxLayout()
        result.setSpacing(18)
        self.tube_swatch = Swatch(60)
        self.fiber_swatch = Swatch(60)
        self.tube_label = QLabel()
        self.fiber_label = QLabel()
        for swatch, label, caption in ((self.tube_swatch, self.tube_label, "color.tube"),
                                       (self.fiber_swatch, self.fiber_label, "color.fiber_in_tube")):
            box = QHBoxLayout()
            box.setSpacing(10)
            box.addWidget(swatch)
            texts = QVBoxLayout()
            texts.setSpacing(0)
            cap = QLabel(tr(caption))
            cap.setObjectName("StatLabel")
            label.setObjectName("MidValue")
            texts.addStretch(1)
            texts.addWidget(label)
            texts.addWidget(cap)
            texts.addStretch(1)
            box.addLayout(texts)
            result.addLayout(box)
        result.addStretch(1)
        lookup.body.addLayout(result)
        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        lookup.body.addWidget(self.summary)

        legend = Card(tr("color.sequence"))
        legend_grid = QHBoxLayout()
        legend_grid.setSpacing(6)
        cols = [QVBoxLayout(), QVBoxLayout()]
        for i, (name, hex_) in enumerate(TIA598_COLORS):
            row = QHBoxLayout()
            row.setSpacing(8)
            sw = Swatch(18)
            sw.set_spec(ColorSpec(i + 1, name, hex_))
            row.addWidget(sw)
            lbl = QLabel(f"{i + 1:>2}  {name}")
            lbl.setFont(theme.tabular(lbl.font()))
            row.addWidget(lbl, 1)
            cols[i // 6].addLayout(row)
        for c in cols:
            legend_grid.addLayout(c, 1)
        legend.body.addLayout(legend_grid)
        top.addWidget(lookup, 3)
        top.addWidget(legend, 2)
        lay.addLayout(top)

        self.grid_card = Card(tr("color.grid"), " ")
        self.grid = FiberGrid()
        self.grid.fiber_clicked.connect(self.fiber.setValue)
        self.grid_card.body.addWidget(self.grid)
        lay.addWidget(self.grid_card)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        self.size.currentIndexChanged.connect(self._size_changed)
        self.fiber.valueChanged.connect(self._update)
        self._size_changed()

    def _size_changed(self) -> None:
        size = self.size.currentData()
        self.fiber.setMaximum(size)
        self.grid.set_cable(size, self.fiber.value())
        self.grid_card.set_title(tr("color.grid"), tr("color.grid_hint", tubes=size // 12))
        self._update()

    def _update(self) -> None:
        size = self.size.currentData()
        addr = locate_fiber(self.fiber.value(), size)
        self.tube_swatch.set_spec(addr.tube)
        self.fiber_swatch.set_spec(addr.color)
        self.tube_label.setText(f"{addr.tube.position} · {addr.tube.label}")
        self.fiber_label.setText(f"{addr.color.position} · {addr.color.label}")
        self.summary.setText(tr("color.summary", fiber=addr.fiber, size=size,
                                tube=addr.tube.position, tube_color=addr.tube.label,
                                pos=addr.color.position, fiber_color=addr.color.label))
        self.grid.set_selected(addr.fiber)
