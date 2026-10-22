"""PON splitter cascade and GPON class check."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget)

from ...core.defaults import SPLITTER_RATIOS
from ...core.pon import PonInput, PonResult, calculate_pon
from ...i18n import tr
from .. import icons, theme
from ..context import AppContext
from ..widgets import Card, FlowGrid, PageHeader, StatusBadge, dspin, ispin, scrollable

PRESETS = ((32,), (4, 8), (8, 8), (2, 16), (4, 16), (64,))


def step_label(label: str) -> str:
    key = f"pon.step.{label}"
    text = tr(key)
    return label if text == key else text


class Waterfall(QWidget):
    """Power after each element of the path, drawn as descending bars."""

    def __init__(self):
        super().__init__()
        self._result: PonResult | None = None
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_result(self, result: PonResult) -> None:
        self._result = result
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(500, 260)

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._result:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.tabular(self.font())
        font.setPointSizeF(8.5)
        p.setFont(font)
        steps = self._result.steps
        top_val = max(s.power_dbm for s in steps) + 2
        bottom_val = min(s.power_dbm for s in steps) - 4
        left, right, top, bottom = 46, self.width() - 8, 10, self.height() - 34
        span = top_val - bottom_val or 1

        def y_of(v: float) -> float:
            return top + (top_val - v) / span * (bottom - top)

        # Horizontal grid lines every 5 dB.
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        v = int(top_val // 5 * 5)
        while v >= bottom_val:
            y = y_of(v)
            p.drawLine(left, int(y), right, int(y))
            p.setPen(QColor(theme.TEXT_MUTED))
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight
                       | Qt.AlignmentFlag.AlignVCenter, f"{v}")
            p.setPen(QPen(QColor(255, 255, 255, 28), 1))
            v -= 5
        zero = y_of(0) if bottom_val < 0 < top_val else None
        if zero is not None:
            p.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine))
            p.drawLine(left, int(zero), right, int(zero))

        n = len(steps)
        slot = (right - left) / n
        bar_w = min(54.0, slot * 0.62)
        base = y_of(bottom_val)
        for i, s in enumerate(steps):
            x = left + i * slot + (slot - bar_w) / 2
            y = y_of(s.power_dbm)
            color = QColor(theme.WAVELENGTH_COLORS[1490] if i == 0 else
                           theme.LOSS_COLORS["splitters"] if s.label.startswith("1:") else
                           theme.LOSS_COLORS["fiber"] if s.label == "fiber" else
                           theme.LOSS_COLORS["connectors"])
            color.setAlpha(210)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, y, bar_w, base - y), 5, 5)
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(x - 20, y - 18, bar_w + 40, 16), Qt.AlignmentFlag.AlignCenter,
                       f"{s.power_dbm:.1f}")
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(left + i * slot, bottom + 4, slot, 28),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                       | Qt.TextFlag.TextWordWrap, step_label(s.label))


class ClassCard(Card):
    def __init__(self, name: str):
        super().__init__(tr("pon.class", name=name), margins=16)
        self.badge = StatusBadge(None)
        self.add_header_widget(self.badge)
        self.detail = QLabel()
        self.detail.setObjectName("StatLabel")
        self.detail.setFont(theme.tabular(self.detail.font()))
        self.body.addWidget(self.detail)


class PonPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("pon.title"), tr("pon.subtitle")))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(14)

        inputs = Card(tr("pon.inputs"))
        form = QFormLayout()
        form.setSpacing(10)
        self.olt = dspin(-5.0, 12.0, 3.0, 0.5, 1, tr("common.dbm"))
        self.wavelength = QComboBox()
        for wl in (1490, 1310, 1550):
            self.wavelength.addItem(f"{wl} nm", wl)
        self.length = dspin(0.0, 60.0, 5.0, 0.5, 2, tr("common.km"))
        self.connectors = ispin(0, 20, 2)
        self.splices = ispin(0, 60, 2)
        for label, widget in (("pon.olt", self.olt), ("pon.wavelength", self.wavelength),
                              ("pon.length", self.length), ("pon.connectors", self.connectors),
                              ("pon.splices", self.splices)):
            form.addRow(tr(label), widget)
        inputs.body.addLayout(form)

        stage_title = QLabel(tr("pon.stages"))
        stage_title.setObjectName("CardTitle")
        inputs.body.addWidget(stage_title)
        self.stages = QListWidget()
        self.stages.setObjectName("StageList")
        self.stages.setFixedHeight(126)
        inputs.body.addWidget(self.stages)
        row = QHBoxLayout()
        self.ratio = QComboBox()
        for r in SPLITTER_RATIOS:
            self.ratio.addItem(f"1:{r}", r)
        self.ratio.setCurrentIndex(SPLITTER_RATIOS.index(8))
        add = QPushButton(tr("pon.add_stage"))
        add.setIcon(icons.icon("plus", "#ffffff", 16))
        add.clicked.connect(lambda: self._add_stage(self.ratio.currentData()))
        remove = QPushButton(tr("pon.remove_stage"))
        remove.setObjectName("Danger")
        remove.clicked.connect(self._remove_stage)
        row.addWidget(self.ratio, 1)
        row.addWidget(add)
        row.addWidget(remove)
        inputs.body.addLayout(row)

        presets_label = QLabel(tr("pon.presets"))
        presets_label.setObjectName("Muted")
        inputs.body.addWidget(presets_label)
        presets = QGridLayout()
        presets.setSpacing(6)
        for i, preset in enumerate(PRESETS):
            chip = QPushButton(" + ".join(f"1:{r}" for r in preset))
            chip.setObjectName("Chip")
            chip.clicked.connect(lambda _=False, p=preset: self._set_stages(p))
            presets.addWidget(chip, i // 3, i % 3)
        inputs.body.addLayout(presets)
        inputs.body.addStretch(1)
        inputs.setMinimumWidth(330)

        results = QWidget()
        rlay = QVBoxLayout(results)
        rlay.setContentsMargins(0, 0, 6, 0)
        rlay.setSpacing(14)
        summary = Card(tr("pon.result"), strong=True)
        metrics = []
        self.onu = QLabel()
        self.onu.setObjectName("BigValue")
        self.loss = QLabel()
        self.loss.setObjectName("MidValue")
        self.split = QLabel()
        self.split.setObjectName("MidValue")
        for value, caption in ((self.onu, "pon.onu_power"), (self.loss, "pon.total_loss"),
                               (self.split, "pon.split")):
            cell = QWidget()
            box = QVBoxLayout(cell)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(0)
            box.addStretch(1)
            box.addWidget(value)
            cap = QLabel(tr(caption))
            cap.setObjectName("StatLabel")
            box.addWidget(cap)
            metrics.append(cell)
        nums = FlowGrid(230)
        nums.set_widgets(metrics)
        summary.body.addWidget(nums)
        rlay.addWidget(summary)

        self.class_cards = [ClassCard("B+"), ClassCard("C+")]
        classes = FlowGrid(300)
        classes.set_widgets(self.class_cards)
        rlay.addWidget(classes)

        chart = Card(tr("pon.waterfall"))
        self.waterfall = Waterfall()
        chart.body.addWidget(self.waterfall, 1)
        rlay.addWidget(chart, 1)

        splitter.addWidget(scrollable(inputs))
        splitter.addWidget(scrollable(results))
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 820])
        lay.addWidget(splitter, 1)

        for w in (self.olt, self.length):
            w.valueChanged.connect(self.recalculate)
        for w in (self.connectors, self.splices):
            w.valueChanged.connect(self.recalculate)
        self.wavelength.currentIndexChanged.connect(self.recalculate)
        ctx.settings_changed.connect(self.recalculate)
        self._set_stages((4, 8))

    def _stage_values(self) -> tuple[int, ...]:
        return tuple(self.stages.item(i).data(Qt.ItemDataRole.UserRole)
                     for i in range(self.stages.count()))

    def _set_stages(self, ratios: tuple[int, ...]) -> None:
        self.stages.clear()
        for r in ratios:
            self._append_item(r)
        self.recalculate()

    def _append_item(self, ratio: int) -> None:
        n = self.stages.count() + 1
        loss = self.ctx.defaults.splitter(ratio)
        self.stages.addItem(f"{tr('pon.stage_n', n=n)}   1:{ratio}   ({loss:.1f} dB)")
        self.stages.item(n - 1).setData(Qt.ItemDataRole.UserRole, ratio)

    def _add_stage(self, ratio: int) -> None:
        self._append_item(ratio)
        self.recalculate()

    def _remove_stage(self) -> None:
        row = self.stages.currentRow()
        if row < 0:
            row = self.stages.count() - 1
        if row >= 0:
            remaining = list(self._stage_values())
            remaining.pop(row)
            self._set_stages(tuple(remaining))

    def recalculate(self) -> None:
        ratios = self._stage_values()
        # Relabel in case splitter losses changed in Settings.
        self.stages.blockSignals(True)
        for i, r in enumerate(ratios):
            self.stages.item(i).setText(
                f"{tr('pon.stage_n', n=i + 1)}   1:{r}   ({self.ctx.defaults.splitter(r):.1f} dB)")
        self.stages.blockSignals(False)
        res = calculate_pon(PonInput(self.olt.value(), ratios, self.length.value(),
                                     self.wavelength.currentData(), self.connectors.value(),
                                     self.splices.value()), self.ctx.defaults)
        self.onu.setText(f"{res.onu_power_dbm:+.2f} dBm")
        self.loss.setText(f"{res.total_loss_db:.2f} dB")
        self.split.setText(tr("pon.split_value", ratio=res.split_ratio))
        for card, verdict in zip(self.class_cards, res.classes, strict=True):
            card.badge.set_status(verdict.status)
            card.detail.setText(tr("pon.class_budget", budget=f"{verdict.budget_db:.1f}",
                                   remaining=f"{verdict.remaining_db:+.2f}"))
        self.waterfall.set_result(res)
