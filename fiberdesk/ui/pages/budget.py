"""Link budget calculator."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from ...core.budget import BudgetInput, BudgetResult, calculate_budget, parse_splitters
from ...core.defaults import WAVELENGTHS_NM
from ...core.status import Status
from ...i18n import tr
from .. import icons, theme
from ..context import AppContext
from ..widgets import (BreakdownChart, Card, PageHeader, SegmentBar, StatusBadge, dspin,
                       ispin, scrollable)

SPLITTER_PRESETS = ("", "1:2", "1:4", "1:8", "1:16", "1:32", "1:64", "1:4 + 1:8", "1:8 + 1:8",
                    "1:2 + 1:16", "1:4 + 1:16")


def metric(label: str) -> tuple[QWidget, QLabel]:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    value = QLabel("—")
    value.setObjectName("MidValue")
    caption = QLabel(label)
    caption.setObjectName("StatLabel")
    lay.addWidget(value)
    lay.addWidget(caption)
    return box, value


class BudgetPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._result: BudgetResult | None = None
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("budget.title"), tr("budget.subtitle")))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(14)

        # Inputs
        inputs = Card(tr("budget.inputs"))
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.line_combo = QComboBox()
        self.line_combo.currentIndexChanged.connect(self._line_selected)
        self.tx = dspin(-20.0, 20.0, 3.0, 0.5, 1, tr("common.dbm"))
        self.rx = dspin(-45.0, 0.0, -28.0, 0.5, 1, tr("common.dbm"))
        self.length = dspin(0.0, 200.0, 10.0, 0.5, 2, tr("common.km"))
        self.wavelength = QComboBox()
        for wl in WAVELENGTHS_NM:
            self.wavelength.addItem(f"{wl} nm", wl)
        self.splices = ispin(0, 200, 4)
        self.connectors = ispin(0, 60, 2)
        self.splitters = QComboBox()
        self.splitters.setEditable(True)
        for preset in SPLITTER_PRESETS:
            self.splitters.addItem(preset or tr("common.none"), preset)
        self.splitters.lineEdit().setPlaceholderText(tr("line.splitters_hint"))
        self.safety = dspin(0.0, 20.0, ctx.defaults.safety_margin_db, 0.5, 1, tr("common.db"))
        for label, widget in (("budget.linked", self.line_combo), ("budget.tx", self.tx),
                              ("budget.rx", self.rx), ("budget.length", self.length),
                              ("budget.wavelength", self.wavelength),
                              ("budget.splices", self.splices),
                              ("budget.connectors", self.connectors),
                              ("budget.splitters", self.splitters),
                              ("budget.safety", self.safety)):
            form.addRow(tr(label), widget)
        inputs.body.addLayout(form)
        self.error = QLabel()
        self.error.setStyleSheet(f"color: {theme.STATUS_COLORS[Status.FAIL]};")
        self.error.setWordWrap(True)
        self.error.hide()
        inputs.body.addWidget(self.error)
        inputs.body.addSpacing(6)
        buttons = QHBoxLayout()
        self.reset_btn = QPushButton(tr("budget.reset"))
        self.reset_btn.clicked.connect(self._reset)
        self.save_btn = QPushButton(tr("budget.save"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.setIcon(icons.icon("file", "#08321c", 16))
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.reset_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.save_btn)
        inputs.body.addLayout(buttons)
        self.saved_label = QLabel()
        self.saved_label.setObjectName("Hint")
        self.saved_label.setWordWrap(True)
        inputs.body.addWidget(self.saved_label)
        inputs.body.addStretch(1)
        inputs.setMinimumWidth(340)

        # Results
        results = QWidget()
        rlay = QVBoxLayout(results)
        rlay.setContentsMargins(0, 0, 6, 0)
        rlay.setSpacing(14)
        summary = Card(tr("budget.result"), strong=True)
        top = QHBoxLayout()
        self.badge = StatusBadge(None, large=True)
        top.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addSpacing(10)
        remaining_box = QVBoxLayout()
        remaining_box.setSpacing(0)
        self.remaining = QLabel("—")
        self.remaining.setObjectName("BigValue")
        cap = QLabel(tr("budget.remaining"))
        cap.setObjectName("StatLabel")
        remaining_box.addWidget(self.remaining)
        remaining_box.addWidget(cap)
        top.addLayout(remaining_box, 1)
        summary.body.addLayout(top)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        boxes = [metric(tr("budget.available")), metric(tr("budget.total_loss")),
                 metric(tr("budget.safety"))]
        for i, (box, _) in enumerate(boxes):
            grid.addWidget(box, 0, i)
        self.available, self.total, self.safety_value = (v for _, v in boxes)
        summary.body.addLayout(grid)
        self.usage = SegmentBar(height=14)
        summary.body.addWidget(self.usage)
        self.legend = QLabel()
        self.legend.setObjectName("Hint")
        self.legend.setWordWrap(True)
        summary.body.addWidget(self.legend)
        self.rule = QLabel()
        self.rule.setObjectName("Hint")
        self.rule.setWordWrap(True)
        summary.body.addWidget(self.rule)
        rlay.addWidget(summary)

        breakdown = Card(tr("budget.breakdown"), tr("budget.breakdown_hint"))
        self.chart = BreakdownChart()
        breakdown.body.addWidget(self.chart)
        self.details = QLabel()
        self.details.setObjectName("Muted")
        self.details.setWordWrap(True)
        self.details.setFont(theme.tabular(self.details.font()))
        breakdown.body.addWidget(self.details)
        rlay.addWidget(breakdown)
        rlay.addStretch(1)

        splitter.addWidget(scrollable(inputs))
        splitter.addWidget(scrollable(results))
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 800])
        lay.addWidget(splitter, 1)

        for w in (self.tx, self.rx, self.length, self.safety):
            w.valueChanged.connect(self.recalculate)
        for w in (self.splices, self.connectors):
            w.valueChanged.connect(self.recalculate)
        self.wavelength.currentIndexChanged.connect(self.recalculate)
        self.splitters.currentTextChanged.connect(self.recalculate)

        ctx.data_changed.connect(self._reload_lines)
        ctx.settings_changed.connect(self._settings_changed)
        self._reload_lines()
        self.recalculate()

    # --- helpers -------------------------------------------------------------

    def on_show(self, payload: object = None) -> None:
        if isinstance(payload, dict) and "line" in payload:
            idx = self.line_combo.findData(payload["line"])
            if idx >= 0:
                self.line_combo.setCurrentIndex(idx)

    def _reload_lines(self) -> None:
        current = self.line_combo.currentData()
        projects = {p.id: p.name for p in self.ctx.db.projects()}
        self._lines = {ln.id: ln for ln in self.ctx.db.lines()}
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        self.line_combo.addItem(tr("budget.unlinked"), None)
        for ln in self._lines.values():
            self.line_combo.addItem(f"{ln.name} · {projects.get(ln.project_id, '')}", ln.id)
        idx = self.line_combo.findData(current)
        self.line_combo.setCurrentIndex(max(0, idx))
        self.line_combo.blockSignals(False)
        self._update_saved_label()

    def _settings_changed(self) -> None:
        if self.line_combo.currentData() is None:
            self.safety.setValue(self.ctx.defaults.safety_margin_db)
        self.recalculate()

    def _line_selected(self) -> None:
        line = self._lines.get(self.line_combo.currentData())
        if line is not None:
            self._loading = True
            self.tx.setValue(line.tx_power_dbm)
            self.rx.setValue(line.rx_sensitivity_dbm)
            self.length.setValue(line.length_km)
            self.wavelength.setCurrentIndex(max(0, self.wavelength.findData(line.wavelength_nm)))
            self.splices.setValue(line.splices)
            self.connectors.setValue(line.connectors)
            self.splitters.setEditText(line.splitters or tr("common.none"))
            self.safety.setValue(self.ctx.defaults.safety_margin_db)
            self._loading = False
        self._update_saved_label()
        self.recalculate()

    def _update_saved_label(self) -> None:
        line = self._lines.get(self.line_combo.currentData())
        if line is None:
            self.saved_label.setText("")
        elif line.budget_saved_at:
            self.saved_label.setText(tr(
                "budget.last_saved", time=line.budget_saved_at.replace("T", " "),
                status=line.budget_status.value if line.budget_status else "—",
                margin=f"{line.budget_remaining_db:.2f}"))
        else:
            self.saved_label.setText(tr("budget.never_saved"))

    def _splitter_ratios(self) -> tuple[int, ...]:
        text = self.splitters.currentText().strip()
        if text == tr("common.none"):
            return ()
        ratios = parse_splitters(text)
        for r in ratios:
            self.ctx.defaults.splitter(r)
        return tuple(ratios)

    def _reset(self) -> None:
        self.line_combo.setCurrentIndex(0)
        self._loading = True
        self.tx.setValue(3.0)
        self.rx.setValue(-28.0)
        self.length.setValue(10.0)
        self.wavelength.setCurrentIndex(0)
        self.splices.setValue(4)
        self.connectors.setValue(2)
        self.splitters.setCurrentIndex(0)
        self.safety.setValue(self.ctx.defaults.safety_margin_db)
        self._loading = False
        self.recalculate()

    # --- calculation ---------------------------------------------------------

    def recalculate(self) -> None:
        if self._loading:
            return
        try:
            ratios = self._splitter_ratios()
        except ValueError:
            self.error.setText(tr("budget.bad_splitter"))
            self.error.show()
            self.save_btn.setEnabled(False)
            return
        self.error.hide()
        inp = BudgetInput(
            tx_power_dbm=self.tx.value(), rx_sensitivity_dbm=self.rx.value(),
            length_km=self.length.value(), wavelength_nm=self.wavelength.currentData(),
            splices=self.splices.value(), connectors=self.connectors.value(),
            splitters=ratios, safety_margin_db=self.safety.value())
        res = calculate_budget(inp, self.ctx.defaults)
        self._result = res
        self.badge.set_status(res.status)
        self.remaining.setText(f"{res.remaining_db:+.2f} dB")
        self.remaining.setStyleSheet(f"color: {theme.status_color(res.status).name()};")
        self.available.setText(f"{res.available_db:.2f} dB")
        self.total.setText(f"{res.total_loss_db:.2f} dB")
        self.safety_value.setText(f"{res.safety_margin_db:.2f} dB")

        segments = [(i.loss_db, theme.LOSS_COLORS[i.key]) for i in res.items]
        segments.append((res.safety_margin_db, theme.LOSS_COLORS["safety"]))
        segments.append((max(0.0, res.remaining_db), theme.LOSS_COLORS["remaining"]))
        self.usage.set_segments(segments)
        legend = [(tr(f"loss.{i.key}"), theme.LOSS_COLORS[i.key]) for i in res.items]
        legend += [(tr("loss.safety"), theme.LOSS_COLORS["safety"]),
                   (tr("loss.remaining"), theme.LOSS_COLORS["remaining"])]
        self.legend.setText("   ".join(f"<span style='color:{c}'>●</span> {t}" for t, c in legend))
        self.rule.setText(tr("budget.rule", warn=f"{self.ctx.defaults.warn_band_db:g}"))

        rows = [(tr(f"loss.{i.key}"), i.loss_db, theme.LOSS_COLORS[i.key], f"{i.loss_db:.2f} dB")
                for i in res.items]
        rows.append((tr("loss.safety"), res.safety_margin_db, theme.LOSS_COLORS["safety"],
                     f"{res.safety_margin_db:.2f} dB"))
        self.chart.set_rows(rows, scale=max(res.available_db, res.total_loss_db
                                            + res.safety_margin_db, 1.0))
        self.details.setText("<br>".join(
            f"<b>{tr(f'loss.{i.key}')}</b>: {i.detail}" for i in res.items))
        self.save_btn.setEnabled(self.line_combo.currentData() is not None)

    def _save(self) -> None:
        line_id = self.line_combo.currentData()
        if line_id is None or self._result is None:
            return
        line = self._lines[line_id]
        # The saved verdict must match the line's own parameters, so write the inputs back too.
        line.tx_power_dbm = self.tx.value()
        line.rx_sensitivity_dbm = self.rx.value()
        line.length_km = self.length.value()
        line.wavelength_nm = self.wavelength.currentData()
        line.splices = self.splices.value()
        line.connectors = self.connectors.value()
        line.splitters = " + ".join(f"1:{r}" for r in self._splitter_ratios())
        self.ctx.db.save_line(line)
        now = datetime.now()
        self.ctx.db.save_line_budget(line_id, self._result, now)
        self.ctx.data_changed.emit()
        self.saved_label.setText(tr("budget.saved", line=line.name,
                                    time=now.strftime("%Y-%m-%d %H:%M")))
