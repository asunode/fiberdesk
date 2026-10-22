"""Capture every page of a running window to PNG files (used for the README)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ..core.status import Status


def _pick_payloads(window) -> dict[str, object]:
    """Choose content that shows each screen at its most informative."""
    ctx = window.ctx
    views = ctx.db.measurement_views(ctx.defaults)
    lines_with_three = {v.line.id for v in views
                        if len({x.measurement.wavelength_nm for x in views
                                if x.line.id == v.line.id}) >= 3}
    otdr = next((v for v in views if v.line.id in lines_with_three and v.status is not Status.PASS
                 and v.line.splitters), None) or next(iter(views), None)
    pon_project = next((p for p in ctx.db.projects() if "FTTH" in p.kind), None)
    budget_line = next((ln for ln in ctx.db.lines() if ln.splitters), None)
    return {
        "otdr": {"measurement": otdr.measurement.id} if otdr else None,
        "projects": {"project": pon_project.id} if pon_project else None,
        "budget": {"line": budget_line.id} if budget_line else None,
    }


def capture_all(window, directory: str, delay_ms: int = 450) -> None:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    payloads = _pick_payloads(window)
    keys = list(window.pages)
    order = iter(enumerate(keys, start=1))

    def step() -> None:
        try:
            index, key = next(order)
        except StopIteration:
            QApplication.quit()
            return
        window.show_page(key, payloads.get(key))
        QTimer.singleShot(delay_ms, lambda: (window.grab().save(str(out / f"{index:02d}-{key}.png")),
                                             step()))

    QTimer.singleShot(delay_ms, step)
