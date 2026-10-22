"""Device profiles and inventory."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.devices import PROFILES, DeviceProfile
from ...i18n import format_date, tr
from .. import theme
from ..context import AppContext
from ..widgets import Card, FlowGrid, PageHeader, Pill, icon_label, scrollable


def wavelength_pills(profile: DeviceProfile) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    for wl in profile.wavelengths:
        row.addWidget(Pill(f"{wl} nm · {profile.dynamic_range_db[wl]:g} dB",
                           theme.WAVELENGTH_COLORS.get(wl, "#8fb4ff")))
    row.addStretch(1)
    return row


class ProfileCard(Card):
    def __init__(self, profile: DeviceProfile):
        super().__init__(profile.model, profile.category, margins=16)
        self.add_header_widget(icon_label("devices", 26, theme.TEXT_2))
        cap = QLabel(tr("dev.range"))
        cap.setObjectName("Muted")
        self.body.addWidget(cap)
        self.body.addLayout(wavelength_pills(profile))
        usage = QLabel(f"{tr('dev.usage')}: {profile.usage}")
        usage.setObjectName("StatLabel")
        usage.setWordWrap(True)
        self.body.addWidget(usage)


class DeviceCard(Card):
    def __init__(self, device, measurements: int):
        profile = device.profile
        super().__init__(device.serial, profile.model, margins=16)
        count = QLabel(str(measurements))
        count.setObjectName("MidValue")
        count.setToolTip(tr("dev.measurements"))
        self.add_header_widget(count)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        rows = ((tr("dev.team"), device.team),
                (tr("dev.calibration"), format_date(device.calibration_date)),
                (tr("dev.measurements"), str(measurements)))
        for r, (k, v) in enumerate(rows):
            key = QLabel(k)
            key.setObjectName("Muted")
            grid.addWidget(key, r, 0)
            grid.addWidget(QLabel(v), r, 1)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)
        self.body.addLayout(wavelength_pills(profile))


class DevicesPage(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("dev.title"), tr("dev.subtitle")))
        notice = QLabel(tr("app.demo_note"))
        notice.setObjectName("Notice")
        lay.addWidget(notice)

        title = QLabel(tr("dev.profiles"))
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        profiles = FlowGrid(340)
        profiles.set_widgets([ProfileCard(p) for p in PROFILES.values()])
        lay.addWidget(profiles)

        title = QLabel(tr("dev.inventory"))
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        self.inventory = FlowGrid(300)
        lay.addWidget(self.inventory)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))
        ctx.data_changed.connect(self.refresh)
        self.refresh()

    def on_show(self, payload: object = None) -> None:
        self.refresh()

    def refresh(self) -> None:
        counts = self.ctx.db.measurement_counts_by_device()
        self.inventory.set_widgets([DeviceCard(d, counts.get(d.id, 0))
                                    for d in self.ctx.db.devices()])
