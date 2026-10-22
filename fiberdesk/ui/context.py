"""Shared application state passed to every page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..core.defaults import Defaults
from ..storage.db import Database


class AppContext(QObject):
    data_changed = Signal()      # projects, lines or measurements changed
    settings_changed = Signal()  # default values / thresholds changed
    navigate = Signal(str, object)  # page key, optional payload (e.g. a line or measurement id)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.defaults: Defaults = db.load_defaults()

    def save_defaults(self, defaults: Defaults | None) -> None:
        if defaults is None:
            self.db.reset_defaults()
        else:
            self.db.save_defaults(defaults)
        self.defaults = self.db.load_defaults()
        self.settings_changed.emit()
