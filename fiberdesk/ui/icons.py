"""Thin line icons drawn as inline SVG (24 × 24 view box, stroked)."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "logo": '<circle cx="12" cy="12" r="9"/><path d="M3 12h4l2-5 3 10 2-5h7"/>',
    "dashboard": '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/>'
                 '<rect x="13.5" y="3.5" width="7" height="4.5" rx="2"/>'
                 '<rect x="13.5" y="11" width="7" height="9.5" rx="2"/>'
                 '<rect x="3.5" y="13.5" width="7" height="7" rx="2"/>',
    "projects": '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13'
                'a2 2 0 0 1-2-2z"/>',
    "budget": '<rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M8.5 7h7"/>'
              '<path d="M8.5 11.5h1M12 11.5h1M15.5 11.5h0M8.5 15h1M12 15h1M8.5 18h1M12 18h1"/>'
              '<path d="M15.5 14.5v4"/>',
    "otdr": '<path d="M3 18h18"/><path d="M3 6l3 1 2 4 2-1.5 3 2.5 3 1 2 3h3"/>'
            '<path d="M8 4v14" stroke-dasharray="1.5 2"/>',
    "colorcode": '<circle cx="8" cy="8" r="3.5"/><circle cx="16" cy="8" r="3.5"/>'
                 '<circle cx="8" cy="16" r="3.5"/><circle cx="16" cy="16" r="3.5"/>',
    "pon": '<circle cx="4.5" cy="12" r="2"/><path d="M6.5 12h4"/><path d="M10.5 12l4-6h5"/>'
           '<path d="M10.5 12h9"/><path d="M10.5 12l4 6h5"/>',
    "devices": '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/>'
               '<rect x="6.5" y="7.5" width="11" height="6" rx="1"/>'
               '<circle cx="8" cy="16.8" r="0.8"/><path d="M12 16.8h5"/>',
    "settings": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/>'
                '<circle cx="10" cy="17" r="2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "chevron": '<path d="M9 6l6 6-6 6"/>',
    "fit": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "file": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
    "fiber": '<path d="M3 12c3-6 6 6 9 0s6 6 9 0"/>',
    "folder": '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13'
              'a2 2 0 0 1-2-2z"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v4h-4"/>',
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{_PATHS[name]}</svg>'
    ).encode()


@lru_cache(maxsize=None)
def pixmap(name: str, size: int = 20, color: str = "#ffffff", stroke: float = 1.6,
           ratio: float = 2.0) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(_svg(name, color, stroke)))
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pm.width(), pm.height()))
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name: str, color: str = "#ffffff", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, size, color))
