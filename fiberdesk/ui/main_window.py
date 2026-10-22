"""Main window: top bar, sidebar navigation and the page stack."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..i18n import tr
from . import icons, theme
from .context import AppContext
from .pages.budget import BudgetPage
from .pages.colorcode import ColorCodePage
from .pages.dashboard import DashboardPage
from .pages.devices import DevicesPage
from .pages.otdr import OtdrPage
from .pages.pon import PonPage
from .pages.projects import ProjectsPage
from .pages.settings import SettingsPage
from .widgets import GradientBackground, Pill

PAGES = (
    ("dashboard", "dashboard", DashboardPage),
    ("projects", "projects", ProjectsPage),
    ("budget", "budget", BudgetPage),
    ("otdr", "otdr", OtdrPage),
    ("colorcode", "colorcode", ColorCodePage),
    ("pon", "pon", PonPage),
    ("devices", "devices", DevicesPage),
    ("settings", "settings", SettingsPage),
)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{tr('app.name')} {__version__}")
        self.setWindowIcon(icons.icon("logo", theme.ACCENT, 64))
        self.setMinimumSize(1100, 680)
        self.resize(1440, 900)

        root = GradientBackground()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(14)
        outer.addWidget(self._top_bar())

        body = QHBoxLayout()
        body.setSpacing(14)
        outer.addLayout(body, 1)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 16, 12, 14)
        side.setSpacing(4)
        for key, icon_name, cls in PAGES:
            page = cls(ctx)
            self.pages[key] = page
            self.stack.addWidget(page)
            btn = QPushButton(tr(f"nav.{key}").replace("&", "&&"))
            btn.setObjectName("NavButton")
            btn.setIcon(icons.icon(icon_name))
            btn.setIconSize(QSize(20, 20))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            group.addButton(btn)
            self.buttons[key] = btn
            if key == "settings":
                side.addStretch(1)
            side.addWidget(btn)
        note = QLabel(tr("app.demo_note"))
        note.setObjectName("Hint")
        note.setWordWrap(True)
        note.setContentsMargins(10, 10, 6, 0)
        side.addWidget(note)

        body.addWidget(sidebar)
        body.addWidget(self.stack, 1)

        ctx.navigate.connect(self._on_navigate)
        self.show_page("dashboard")

    def _top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", 30, theme.ACCENT, 1.8))
        title = QLabel(tr("app.name"))
        title.setObjectName("AppTitle")
        tagline = QLabel(tr("app.tagline"))
        tagline.setObjectName("AppTagline")
        lay.addWidget(logo)
        lay.addWidget(title)
        lay.addSpacing(6)
        lay.addWidget(tagline, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)
        lay.addWidget(Pill(tr("app.demo_badge"), theme.ACCENT))
        version = QLabel(f"v{__version__}")
        version.setObjectName("Muted")
        lay.addWidget(version)
        return bar

    def show_page(self, key: str, payload: object = None) -> None:
        page = self.pages[key]
        self.buttons[key].setChecked(True)
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_show"):
            page.on_show(payload)

    def _on_navigate(self, key: str, payload: object) -> None:
        self.show_page(key, payload)
