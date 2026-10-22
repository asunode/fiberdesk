"""Editable default values and thresholds."""

from __future__ import annotations

from PySide6.QtWidgets import (QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ...core.defaults import SPLITTER_RATIOS, WAVELENGTHS_NM, Defaults
from ...i18n import tr
from ...storage.seed import populate
from ..context import AppContext
from ..widgets import Card, FlowGrid, PageHeader, dspin, scrollable

# (field, label key, minimum, maximum, step, decimals)
SCALARS = {
    "set.components": (("splice_loss_db", "set.splice", 0, 2, 0.01, 2),
                       ("connector_loss_db", "set.connector", 0, 3, 0.05, 2)),
    "set.verdicts": (("safety_margin_db", "set.safety", 0, 20, 0.5, 1),),
    "set.gpon": (("gpon_b_plus_db", "set.gpon_b", 10, 50, 0.5, 1),
                 ("gpon_c_plus_db", "set.gpon_c", 10, 50, 0.5, 1)),
    "set.events": (("splice_warn_db", "set.splice_warn", 0, 5, 0.01, 2),
                   ("splice_fail_db", "set.splice_fail", 0, 5, 0.01, 2),
                   ("connector_warn_db", "set.conn_warn", 0, 5, 0.05, 2),
                   ("connector_fail_db", "set.conn_fail", 0, 5, 0.05, 2),
                   ("bend_fail_db", "set.bend_fail", 0, 5, 0.05, 2),
                   ("splitter_tolerance_db", "set.split_tol", 0, 5, 0.1, 1),
                   ("reflectance_warn_db", "set.refl_warn", -80, 0, 1, 1),
                   ("reflectance_fail_db", "set.refl_fail", -80, 0, 1, 1),
                   ("section_tolerance_db_km", "set.section_tol", 0, 1, 0.01, 2)),
    "set.compare": (("compare_warn_db", "set.cmp_warn", 0, 10, 0.1, 1),
                    ("compare_fail_db", "set.cmp_fail", 0, 10, 0.1, 1)),
}


def _form() -> QFormLayout:
    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    form.setSpacing(8)
    return form


class SettingsPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.scalar_boxes: dict[str, QDoubleSpinBox] = {}
        self.att_boxes: dict[int, QDoubleSpinBox] = {}
        self.split_boxes: dict[int, QDoubleSpinBox] = {}

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(14)
        header = PageHeader(tr("set.title"), tr("set.subtitle"))
        reset = QPushButton(tr("set.reset"))
        reset.clicked.connect(self._reset)
        save = QPushButton(tr("set.save"))
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        header.right.addWidget(reset)
        header.right.addWidget(save)
        lay.addWidget(header)

        cards = []
        att = Card(tr("set.attenuation"))
        form = _form()
        for wl in WAVELENGTHS_NM:
            box = dspin(0.0, 2.0, 0.0, 0.01, 3)
            box.setMinimumWidth(110)
            self.att_boxes[wl] = box
            form.addRow(f"{wl} nm", box)
        att.body.addLayout(form)
        cards.append(att)
        split = Card(tr("set.splitters"))
        form = _form()
        for r in SPLITTER_RATIOS:
            box = dspin(0.0, 30.0, 0.0, 0.1, 1)
            box.setMinimumWidth(110)
            self.split_boxes[r] = box
            form.addRow(f"1:{r}", box)
        split.body.addLayout(form)
        cards.append(split)
        for title, fields_ in SCALARS.items():
            card = Card(tr(title))
            form = _form()
            for name, label, lo, hi, step, dec in fields_:
                box = dspin(lo, hi, 0.0, step, dec)
                box.setMinimumWidth(110)
                self.scalar_boxes[name] = box
                form.addRow(tr(label), box)
            card.body.addLayout(form)
            cards.append(card)

        demo = Card(tr("set.demo"), tr("set.demo_hint"))
        rebuild = QPushButton(tr("set.rebuild"))
        rebuild.setObjectName("Danger")
        rebuild.clicked.connect(self._rebuild)
        row = QHBoxLayout()
        row.addWidget(rebuild)
        row.addStretch(1)
        demo.body.addLayout(row)
        cards.append(demo)

        grid = FlowGrid(420)
        grid.set_widgets(cards)
        lay.addWidget(grid)
        self.status = QLabel()
        self.status.setObjectName("Hint")
        lay.addWidget(self.status)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))
        self.load(ctx.defaults)

    def on_show(self, payload: object = None) -> None:
        self.load(self.ctx.defaults)
        self.status.clear()

    def load(self, d: Defaults) -> None:
        for wl, box in self.att_boxes.items():
            box.setValue(d.attenuation_db_km.get(wl, 0.0))
        for r, box in self.split_boxes.items():
            box.setValue(d.splitter_loss_db.get(r, 0.0))
        for name, box in self.scalar_boxes.items():
            box.setValue(getattr(d, name))

    def collect(self) -> Defaults:
        return Defaults.from_dict({
            "attenuation_db_km": {wl: b.value() for wl, b in self.att_boxes.items()},
            "splitter_loss_db": {r: b.value() for r, b in self.split_boxes.items()},
            **{name: b.value() for name, b in self.scalar_boxes.items()},
        })

    def _save(self) -> None:
        self.ctx.save_defaults(self.collect())
        self.status.setText(tr("set.saved"))

    def _reset(self) -> None:
        self.ctx.save_defaults(None)
        self.load(self.ctx.defaults)
        self.status.setText(tr("set.reset_done"))

    def _rebuild(self) -> None:
        if QMessageBox.question(self, tr("set.rebuild"), tr("set.rebuild_confirm")) \
                != QMessageBox.StandardButton.Yes:
            return
        self.ctx.db.clear()
        populate(self.ctx.db)
        self.ctx.defaults = self.ctx.db.load_defaults()
        self.load(self.ctx.defaults)
        self.ctx.settings_changed.emit()
        self.ctx.data_changed.emit()
        self.status.setText(tr("set.rebuilt"))
