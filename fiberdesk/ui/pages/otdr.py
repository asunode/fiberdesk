"""OTDR results: measurement list, trace plot, event table and expected vs measured."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSplitter, QVBoxLayout,
                               QWidget)

from ...core.budget import calculate_budget
from ...core.otdr import (EventKind, compare_expected, evaluate_event, link_breakdown,
                          synthesize_trace)
from ...core.status import Status
from ...i18n import format_date, tr
from ...storage.db import MeasurementView
from .. import icons, theme
from ..context import AppContext
from ..widgets import (Card, ElidedLabel, Item, PageHeader, StatusBadge, fit_columns,
                       make_table, num_item, status_item)

pg.setConfigOptions(antialias=True)


def trace_for(view: MeasurementView, defaults) -> tuple[np.ndarray, np.ndarray]:
    m = view.measurement
    dr = view.device.profile.dynamic_range_db.get(m.wavelength_nm, 30.0)
    return synthesize_trace(view.events, m.wavelength_nm, dr, m.trace_seed, defaults)


def related_views(view: MeasurementView, views: list[MeasurementView]) -> dict[int, MeasurementView]:
    """Latest measurement of the same line per wavelength (``views`` is newest first)."""
    result: dict[int, MeasurementView] = {}
    for v in views:
        if v.line.id == view.line.id and v.measurement.wavelength_nm not in result:
            result[v.measurement.wavelength_nm] = v
    result[view.measurement.wavelength_nm] = view
    return dict(sorted(result.items()))


class TracePlot(pg.PlotWidget):
    def __init__(self):
        super().__init__(background=theme.PLOT_BG)
        self.setMinimumHeight(220)
        item = self.getPlotItem()
        item.showGrid(x=True, y=True, alpha=0.12)
        font = QFont(theme.app_font(9))
        for name in ("left", "bottom"):
            axis = item.getAxis(name)
            axis.setPen(pg.mkPen(255, 255, 255, 70))
            axis.setTextPen(pg.mkPen(theme.TEXT_2))
            axis.setStyle(tickFont=font)
        item.setLabel("bottom", tr("otdr.axis_x"), color=theme.TEXT_2)
        item.setLabel("left", tr("otdr.axis_y"), color=theme.TEXT_2)
        item.setMenuEnabled(False)
        self.legend = item.addLegend(offset=(12, -12), labelTextColor=theme.TEXT_2,
                                     brush=pg.mkBrush(11, 22, 69, 200), pen=pg.mkPen(255, 255, 255, 50))
        self.curves: dict[int, pg.PlotDataItem] = {}
        self.markers: list[pg.InfiniteLine] = []

    def clear_all(self) -> None:
        self.getPlotItem().clear()
        self.legend.clear()
        self.curves.clear()
        self.markers.clear()

    def add_curve(self, wavelength: int, x: np.ndarray, y: np.ndarray, primary: bool) -> None:
        color = QColor(theme.WAVELENGTH_COLORS.get(wavelength, "#ffffff"))
        if not primary:
            color.setAlpha(170)
        curve = self.plot(x, y, pen=pg.mkPen(color, width=1.6 if primary else 1.1),
                          name=f"{wavelength} nm")
        curve.setZValue(10 if primary else 5)
        curve.setClipToView(True)
        curve.setDownsampling(auto=True, method="peak")
        self.curves[wavelength] = curve

    def add_marker(self, distance: float, number: int, status: Status) -> pg.InfiniteLine:
        color = QColor(theme.STATUS_COLORS[status]) if status is not Status.PASS \
            else QColor(255, 255, 255, 120)
        line = pg.InfiniteLine(
            pos=distance, angle=90, movable=False,
            pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
            label=str(number),
            labelOpts={"position": 0.96, "color": color, "fill": pg.mkBrush(11, 22, 69, 220),
                       "anchors": [(0.5, 0), (0.5, 0)]})
        line.setZValue(1)
        self.addItem(line)
        self.markers.append(line)
        return line


class OtdrPage(QWidget):
    LIST_COLUMNS = ("otdr.col_line", "otdr.col_wl", "otdr.col_date", "otdr.col_result")
    EVENT_COLUMNS = ("otdr.ev_no", "otdr.ev_distance", "otdr.ev_type", "otdr.ev_loss",
                     "otdr.ev_refl", "otdr.ev_section", "otdr.ev_status")
    CMP_COLUMNS = ("otdr.cmp_item", "otdr.cmp_expected", "otdr.cmp_measured", "otdr.cmp_delta")

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.views: list[MeasurementView] = []
        self.current: MeasurementView | None = None
        self._traces: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self._overlay_boxes: dict[int, QCheckBox] = {}
        self._related: dict[int, MeasurementView] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        header = PageHeader(tr("otdr.title"), tr("otdr.subtitle"))
        self.project_filter = QComboBox()
        self.status_filter = QComboBox()
        self.status_filter.addItem(tr("otdr.filter_status"), "")
        for st in Status:
            self.status_filter.addItem(tr(f"status.{st.value}"), st.value)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("common.search"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.icon("search", "#93a8d2", 16),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(220)
        for w in (self.project_filter, self.status_filter, self.search):
            header.right.addWidget(w)
        lay.addWidget(header)

        main = QSplitter(Qt.Orientation.Horizontal)
        main.setChildrenCollapsible(False)
        main.setHandleWidth(14)

        list_card = Card(tr("otdr.measurements"))
        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")
        list_card.add_header_widget(self.count_label)
        self.list_table = make_table([tr(c) for c in self.LIST_COLUMNS], stretch_column=0)
        self.list_table.itemSelectionChanged.connect(self._selection_changed)
        list_card.body.addWidget(self.list_table)
        list_card.setMinimumWidth(360)

        right = QSplitter(Qt.Orientation.Vertical)
        right.setChildrenCollapsible(False)
        right.setHandleWidth(14)

        self.trace_card = Card()
        self.trace_title = ElidedLabel(tr("otdr.trace"))
        self.trace_title.setObjectName("CardTitle")
        self.trace_meta = ElidedLabel()
        self.trace_meta.setObjectName("Hint")
        self.trace_card.body.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(self.trace_title, 1)
        self.trace_card.body.addLayout(title_row)
        self.trace_card.body.addWidget(self.trace_meta)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        overlay_label = QLabel(tr("otdr.overlay"))
        overlay_label.setObjectName("Muted")
        toolbar.addWidget(overlay_label)
        self.overlay_row = QHBoxLayout()
        self.overlay_row.setSpacing(12)
        toolbar.addLayout(self.overlay_row)
        toolbar.addStretch(1)
        fit = QPushButton(tr("otdr.reset_zoom"))
        fit.setIcon(icons.icon("fit", "#ffffff", 16))
        fit.clicked.connect(lambda: self.plot.getPlotItem().autoRange())
        self.export_btn = QPushButton(tr("otdr.export"))
        self.export_btn.setObjectName("Primary")
        self.export_btn.setIcon(icons.icon("file", "#08321c", 16))
        self.export_btn.clicked.connect(self._export)
        title_row.addWidget(fit)
        title_row.addWidget(self.export_btn)
        self.trace_card.body.addLayout(toolbar)
        self.trace_card.body.addSpacing(4)
        self.plot = TracePlot()
        self.trace_card.body.addWidget(self.plot, 1)

        events_card = Card(tr("otdr.events"))
        self.event_table = make_table([tr(c) for c in self.EVENT_COLUMNS], stretch_column=2,
                                      sortable=False)
        self.event_table.itemSelectionChanged.connect(self._event_selected)
        events_card.body.addWidget(self.event_table)
        self.cmp_card = Card(tr("otdr.compare"))
        self.cmp_badge = StatusBadge(None)
        self.cmp_card.add_header_widget(self.cmp_badge)
        self.cmp_table = make_table([tr(c) for c in self.CMP_COLUMNS], stretch_column=0,
                                    sortable=False)
        self.cmp_table.setMinimumHeight(140)
        self.cmp_card.body.addWidget(self.cmp_table)

        # Left column: measurement list over the comparison; right: trace over events.
        left = QSplitter(Qt.Orientation.Vertical)
        left.setChildrenCollapsible(False)
        left.setHandleWidth(14)
        left.addWidget(list_card)
        left.addWidget(self.cmp_card)
        left.setStretchFactor(0, 1)
        left.setStretchFactor(1, 0)
        self._left = left
        self._sized = False

        right.addWidget(self.trace_card)
        right.addWidget(events_card)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        right.setSizes([470, 320])

        main.addWidget(left)
        main.addWidget(right)
        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([410, 1000])
        lay.addWidget(main, 1)

        self.project_filter.currentIndexChanged.connect(self._apply_filter)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        self.search.textChanged.connect(self._apply_filter)
        ctx.data_changed.connect(self.refresh)
        ctx.settings_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._sized:
            # Give the comparison its natural height and the list everything else.
            self._sized = True
            cmp_h = self.cmp_card.sizeHint().height()
            self._left.setSizes([max(200, self._left.height() - cmp_h), cmp_h])

    # --- list ----------------------------------------------------------------

    def on_show(self, payload: object = None) -> None:
        if not isinstance(payload, dict):
            return
        if "measurement" in payload:
            self._clear_filters()
            self._select_measurement(payload["measurement"])
        elif "line" in payload:
            self._clear_filters()
            view = next((v for v in self.views if v.line.id == payload["line"]), None)
            if view:
                self.search.setText(view.line.name)
                self._select_measurement(view.measurement.id)

    def _clear_filters(self) -> None:
        self.project_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.search.clear()

    def refresh(self) -> None:
        selected = self.current.measurement.id if self.current else None
        self.views = self.ctx.db.measurement_views(self.ctx.defaults)
        self._traces.clear()
        project = self.project_filter.currentData()
        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem(tr("otdr.filter_project"), None)
        for p in self.ctx.db.projects():
            self.project_filter.addItem(p.name, p.id)
        self.project_filter.setCurrentIndex(max(0, self.project_filter.findData(project)))
        self.project_filter.blockSignals(False)

        t = self.list_table
        t.blockSignals(True)
        t.setSortingEnabled(False)
        t.clearContents()
        t.setRowCount(len(self.views))
        for r, v in enumerate(self.views):
            m = v.measurement
            name = Item(v.line.name)
            name.setData(Qt.ItemDataRole.UserRole, m.id)
            name.setToolTip(f"{v.project.name}\n{v.device.serial} · {m.operator}")
            date = Item(m.measured_at[:10], m.measured_at)
            for c, item in enumerate((name, num_item(m.wavelength_nm, 0), date,
                                      status_item(v.status))):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)
        t.sortItems(2, Qt.SortOrder.DescendingOrder)
        fit_columns(t)
        t.blockSignals(False)
        self._apply_filter()
        if selected is not None and self._select_measurement(selected):
            return
        self._select_first_visible()

    def _apply_filter(self) -> None:
        project = self.project_filter.currentData()
        status = self.status_filter.currentData()
        text = self.search.text().strip().lower()
        by_id = {v.measurement.id: v for v in self.views}
        shown = 0
        for r in range(self.list_table.rowCount()):
            v = by_id[self.list_table.item(r, 0).data(Qt.ItemDataRole.UserRole)]
            hay = " ".join((v.line.name, v.project.name, v.device.serial, v.measurement.operator,
                            str(v.measurement.wavelength_nm))).lower()
            visible = (project is None or v.project.id == project) \
                and (not status or v.status.value == status) and (not text or text in hay)
            self.list_table.setRowHidden(r, not visible)
            shown += visible
        self.count_label.setText(f"{shown} / {len(self.views)}")
        if self.current and self._row_of(self.current.measurement.id) is not None \
                and not self.list_table.isRowHidden(self._row_of(self.current.measurement.id)):
            return
        self._select_first_visible()

    def _row_of(self, measurement_id: int) -> int | None:
        for r in range(self.list_table.rowCount()):
            if self.list_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == measurement_id:
                return r
        return None

    def _select_measurement(self, measurement_id: int) -> bool:
        r = self._row_of(measurement_id)
        if r is None or self.list_table.isRowHidden(r):
            return False
        self.list_table.selectRow(r)
        self.list_table.scrollToItem(self.list_table.item(r, 0))
        self._show(next(v for v in self.views if v.measurement.id == measurement_id))
        return True

    def _select_first_visible(self) -> None:
        for r in range(self.list_table.rowCount()):
            if not self.list_table.isRowHidden(r):
                self._select_measurement(self.list_table.item(r, 0).data(Qt.ItemDataRole.UserRole))
                return
        self._show(None)

    def _selection_changed(self) -> None:
        rows = self.list_table.selectionModel().selectedRows()
        if rows:
            mid = self.list_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            if not self.current or self.current.measurement.id != mid:
                self._show(next(v for v in self.views if v.measurement.id == mid))

    # --- detail --------------------------------------------------------------

    def _trace(self, view: MeasurementView) -> tuple[np.ndarray, np.ndarray]:
        key = view.measurement.id
        if key not in self._traces:
            self._traces[key] = trace_for(view, self.ctx.defaults)
        return self._traces[key]

    def _show(self, view: MeasurementView | None) -> None:
        self.current = view
        self.plot.clear_all()
        self.export_btn.setEnabled(view is not None)
        for box in self._overlay_boxes.values():
            self.overlay_row.removeWidget(box)
            box.deleteLater()
        self._overlay_boxes.clear()
        if view is None:
            self.trace_title.setText(tr("otdr.trace"))
            self.trace_meta.setText(tr("otdr.no_match"))
            self.event_table.setRowCount(0)
            self.cmp_table.setRowCount(0)
            self.cmp_badge.set_status(None)
            return
        m = view.measurement
        self.trace_title.setText(
            f"{view.line.name} · {view.line.a_end} → {view.line.b_end} · {m.wavelength_nm} nm")
        self.trace_meta.setText(
            f"{view.project.name} · {format_date(m.measured_at, with_time=True)} · "
            + tr("otdr.meta", device=view.device.profile.model, serial=view.device.serial,
                 pulse=m.pulse_ns, range=f"{m.range_km:g}", operator=m.operator)
            + (f" · {m.notes}" if m.notes else ""))

        self._related = related_views(view, self.views)
        for wl, rv in self._related.items():
            box = QCheckBox(f"{wl} nm")
            color = theme.WAVELENGTH_COLORS.get(wl, "#ffffff")
            box.setStyleSheet(f"QCheckBox {{ color: {color}; font-weight: 600; }}")
            box.setChecked(True)
            box.setEnabled(rv is not view)
            box.toggled.connect(lambda on, w=wl: self._toggle_overlay(w, on))
            self.overlay_row.addWidget(box)
            self._overlay_boxes[wl] = box
            x, y = self._trace(rv)
            self.plot.add_curve(wl, x, y, rv is view)

        self.event_table.setRowCount(len(view.events))
        for r, e in enumerate(view.events):
            status = evaluate_event(e, m.wavelength_nm, self.ctx.defaults)
            self.plot.add_marker(e.distance_km, e.number, status)
            kind = tr(f"event.{e.kind.value}")
            if e.kind is EventKind.SPLITTER and e.splitter_ratio:
                kind += f" 1:{e.splitter_ratio}"
            cells = (num_item(e.number, 0), num_item(e.distance_km, 3), Item(kind),
                     num_item(e.loss_db, 3), num_item(e.reflectance_db, 1),
                     num_item(e.section_db_km, 3),
                     status_item(status) if e.kind is not EventKind.END else Item("—"))
            for c, item in enumerate(cells):
                self.event_table.setItem(r, c, item)
        fit_columns(self.event_table, 56)
        self.plot.getPlotItem().autoRange()
        self._fill_comparison(view)

    def _fill_comparison(self, view: MeasurementView) -> None:
        wl = view.measurement.wavelength_nm
        expected = calculate_budget(view.line.budget_input(wl), self.ctx.defaults).loss_by_key
        cmp = compare_expected(expected, link_breakdown(view.events), self.ctx.defaults)
        self.cmp_card.title_label.setToolTip(tr("otdr.compare_hint", wl=wl))
        self.cmp_table.setToolTip(tr("otdr.compare_hint", wl=wl))
        self.cmp_badge.set_status(cmp.status, f"{cmp.status.value}  Δ {cmp.delta_db:+.2f} dB")
        rows = [(tr(f"loss.{r.key}"), r.expected_db, r.measured_db, r.delta_db) for r in cmp.rows]
        rows.append((tr("otdr.cmp_total"), cmp.expected_total_db, cmp.measured_total_db,
                     cmp.delta_db))
        self.cmp_table.setRowCount(len(rows))
        for r, (label, exp, meas, delta) in enumerate(rows):
            items = (Item(label), num_item(exp), num_item(meas), num_item(delta))
            if r == len(rows) - 1:
                for it in items:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
            if abs(delta) >= 0.005:
                color = theme.STATUS_COLORS[Status.FAIL if delta > self.ctx.defaults.compare_warn_db
                                            else Status.PASS] if delta > 0 else theme.TEXT_2
                items[3].setForeground(QColor(color))
            for c, it in enumerate(items):
                self.cmp_table.setItem(r, c, it)
        fit_columns(self.cmp_table)
        header_h = self.cmp_table.horizontalHeader().sizeHint().height()
        self.cmp_table.setMaximumHeight(header_h + sum(self.cmp_table.rowHeight(r)
                                                       for r in range(len(rows))) + 4)

    def _toggle_overlay(self, wavelength: int, on: bool) -> None:
        curve = self.plot.curves.get(wavelength)
        if curve is not None:
            curve.setVisible(on)

    def _event_selected(self) -> None:
        rows = self.event_table.selectionModel().selectedRows()
        if not rows or self.current is None:
            return
        event = self.current.events[rows[0].row()]
        x, y = self._trace(self.current)
        span = x[-1] - x[0]
        half = max(span * 0.04, 0.15)
        self.plot.setXRange(event.distance_km - half, event.distance_km + half, padding=0)
        window = (x > event.distance_km - half) & (x < event.distance_km + half)
        if window.any():
            self.plot.setYRange(float(y[window].min()) - 1.0, float(y[window].max()) + 1.0)
        for i, marker in enumerate(self.plot.markers):
            pen = marker.pen
            pen.setWidthF(2.2 if i == rows[0].row() else 1.0)
            marker.setPen(pen)

    def _export(self) -> None:
        if self.current is None:
            return
        from ..report import export_line_report

        default = f"{self.current.line.name}_{self.current.measurement.wavelength_nm}nm.pdf"
        path, _ = QFileDialog.getSaveFileName(self, tr("otdr.export_title"), default, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_line_report(path, self.current, list(self._related.values()), self.ctx.defaults)
        except OSError as exc:
            QMessageBox.warning(self, tr("otdr.export"), tr("otdr.export_failed", error=exc))
            return
        QMessageBox.information(self, tr("otdr.export"), tr("otdr.export_done", path=path))
