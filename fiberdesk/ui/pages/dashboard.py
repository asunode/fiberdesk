"""Overview: counters, verdict distribution, recent measurements and project health."""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.status import Status
from ...i18n import format_date, tr
from .. import theme
from ..context import AppContext
from ..widgets import (Card, FlowGrid, PageHeader, Pill, RowList, RowWidget, SegmentBar, StatCard,
                       StatusBadge, scrollable)

RECENT_LIMIT = 8


class VerdictCard(Card):
    """Three counters (PASS / WARN / FAIL) over a proportion bar."""

    def __init__(self, title: str, hint: str):
        super().__init__(title, hint)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.values: dict[Status, QLabel] = {}
        for status in Status:
            box = QVBoxLayout()
            box.setSpacing(2)
            value = QLabel("0")
            value.setObjectName("MidValue")
            value.setStyleSheet(f"color: {theme.STATUS_COLORS[status]};")
            box.addWidget(value)
            box.addWidget(StatusBadge(status), 0, Qt.AlignmentFlag.AlignLeft)
            row.addLayout(box, 1)
            self.values[status] = value
        self.extra = QLabel()
        self.extra.setObjectName("Muted")
        self.body.addLayout(row)
        self.bar = SegmentBar(height=10)
        self.body.addWidget(self.bar)
        self.body.addWidget(self.extra)

    def set_counts(self, counts: Counter, extra: str = "") -> None:
        for status, label in self.values.items():
            label.setText(str(counts.get(status, 0)))
        self.bar.set_segments((counts.get(s, 0), theme.STATUS_COLORS[s]) for s in Status)
        self.extra.setText(extra)
        self.extra.setVisible(bool(extra))


class DashboardPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("dash.title"), tr("dash.subtitle")))

        stats = QGridLayout()
        stats.setSpacing(14)
        self.stats = {
            "projects": StatCard("projects", tr("dash.projects")),
            "lines": StatCard("fiber", tr("dash.lines")),
            "measurements": StatCard("otdr", tr("dash.measurements")),
            "devices": StatCard("devices", tr("dash.devices")),
        }
        for i, card in enumerate(self.stats.values()):
            stats.addWidget(card, 0, i)
        lay.addLayout(stats)

        verdicts = QHBoxLayout()
        verdicts.setSpacing(14)
        self.results = VerdictCard(tr("dash.results"), tr("dash.results_hint"))
        self.budgets = VerdictCard(tr("dash.budgets"), tr("dash.budgets_hint"))
        verdicts.addWidget(self.results, 1)
        verdicts.addWidget(self.budgets, 1)
        lay.addLayout(verdicts)

        recent_card = Card(tr("dash.recent"))
        self.recent = RowList()
        self.recent.activated.connect(
            lambda mid: self.ctx.navigate.emit("otdr", {"measurement": mid}))
        recent_card.body.addWidget(self.recent)
        health_card = Card(tr("dash.health"))
        self.health = RowList()
        self.health.activated.connect(
            lambda pid: self.ctx.navigate.emit("projects", {"project": pid}))
        health_card.body.addWidget(self.health)
        lists = FlowGrid(470)  # side by side when wide, stacked when narrow
        lists.set_widgets([recent_card, health_card])
        lay.addWidget(lists)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        ctx.data_changed.connect(self.refresh)
        ctx.settings_changed.connect(self.refresh)
        self.refresh()

    def on_show(self, payload: object = None) -> None:
        self.refresh()

    def refresh(self) -> None:
        db = self.ctx.db
        for key, value in db.counts().items():
            self.stats[key].set_value(value)
        views = db.measurement_views(self.ctx.defaults)
        self.results.set_counts(Counter(v.status for v in views))
        lines = db.lines()
        missing = sum(1 for ln in lines if ln.budget_status is None)
        self.budgets.set_counts(Counter(ln.budget_status for ln in lines if ln.budget_status),
                                f"{tr('dash.not_saved')}: {missing}" if missing else "")

        self.recent.clear()
        for v in views[:RECENT_LIMIT]:
            wl = v.measurement.wavelength_nm
            row = RowWidget(
                "otdr", f"{v.line.name} · {v.project.name}",
                f"{format_date(v.measurement.measured_at)} · {v.device.serial} · "
                f"{v.measurement.operator}",
                right=[Pill(f"{wl} nm", theme.WAVELENGTH_COLORS.get(wl, "#8fb4ff")),
                       StatusBadge(v.status)])
            self.recent.add_row(row, v.measurement.id)

        self.health.clear()
        by_project: dict[int, Counter] = {}
        for v in views:
            by_project.setdefault(v.project.id, Counter())[v.status] += 1
        line_counts = Counter(ln.project_id for ln in lines)
        for project in db.projects():
            counts = by_project.get(project.id, Counter())
            worst = Status.worst(counts) if counts else None
            bar = SegmentBar(height=8)
            bar.setFixedWidth(90)
            bar.set_segments((counts.get(s, 0), theme.STATUS_COLORS[s]) for s in Status)
            row = RowWidget(
                "projects", project.name,
                f"{tr('dash.lines_count', n=line_counts.get(project.id, 0))} · "
                f"{tr('dash.meas_count', n=sum(counts.values()))}",
                right=[bar, StatusBadge(worst)])
            self.health.add_row(row, project.id)
