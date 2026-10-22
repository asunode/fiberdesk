"""Colours, fonts and the application style sheet."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase

from ..core.status import Status

BG_START = "#0a1a6e"   # deep navy, top-left
BG_MID = "#163a9c"
BG_END = "#2f8aa6"     # muted turquoise, bottom-right

TEXT = "#ffffff"
TEXT_2 = "#cfdcf5"
TEXT_MUTED = "#93a8d2"
ACCENT = "#6cc58e"      # soft green: primary action and PASS
ACCENT_HOVER = "#7fd39f"

GLASS = "rgba(255, 255, 255, 0.10)"
GLASS_STRONG = "rgba(255, 255, 255, 0.16)"
GLASS_BORDER = "rgba(255, 255, 255, 0.24)"
TABLE_BG = "rgba(6, 16, 56, 0.62)"
PLOT_BG = "#0b1645"

STATUS_COLORS = {
    Status.PASS: "#6cc58e",
    Status.WARN: "#f2b84b",
    Status.FAIL: "#ff7a6b",
}
NEUTRAL = "#8ea2c9"

WAVELENGTH_COLORS = {1310: "#5ec8ff", 1490: "#6cc58e", 1550: "#c39bff", 1625: "#ffb86b"}

LOSS_COLORS = {
    "fiber": "#5ec8ff",
    "splices": "#c39bff",
    "connectors": "#ffb86b",
    "splitters": "#f78fb3",
    "bends": "#ff7a6b",
    "safety": "#93a8d2",
    "remaining": "#6cc58e",
}

ASSETS = (Path(__file__).parent / "assets").as_posix()

FONT_FAMILIES = ("Ubuntu Sans", "Inter", "Noto Sans", "DejaVu Sans")


def status_color(status: Status | None) -> QColor:
    return QColor(STATUS_COLORS.get(status, NEUTRAL))


def app_font(point_size: float = 10.0) -> QFont:
    available = set(QFontDatabase.families())
    family = next((f for f in FONT_FAMILIES if f in available), "")
    font = QFont(family, point_size) if family else QFont()
    font.setPointSizeF(point_size)
    tabular(font)
    return font


def tabular(font: QFont) -> QFont:
    """Tabular figures so numbers line up in tables and charts."""
    font.setFeature(QFont.Tag.fromString("tnum"), 1)
    return font


STYLE_SHEET = f"""
* {{ color: {TEXT}; outline: none; }}
QWidget {{ background: transparent; }}
QToolTip {{ background: #11245e; color: {TEXT}; border: 1px solid {GLASS_BORDER};
            border-radius: 6px; padding: 4px 8px; }}

#TopBar, #Sidebar, #Card {{
    background: {GLASS};
    border: 1px solid {GLASS_BORDER};
    border-radius: 18px;
}}
#Card[strong="true"] {{ background: {GLASS_STRONG}; }}
#Notice {{
    background: rgba(242, 184, 75, 0.14); border: 1px solid rgba(242, 184, 75, 0.45);
    border-radius: 12px; color: #ffe2a8; padding: 8px 12px;
}}

#AppTitle {{ font-size: 17pt; font-weight: 700; }}
#AppTagline {{ color: {TEXT_MUTED}; }}
#PageTitle {{ font-size: 19pt; font-weight: 700; }}
#PageSubtitle {{ color: {TEXT_2}; }}
#CardTitle {{ font-size: 12pt; font-weight: 600; }}
#Hint, #Muted {{ color: {TEXT_MUTED}; }}
#BigValue {{ font-size: 26pt; font-weight: 700; }}
#MidValue {{ font-size: 17pt; font-weight: 700; }}
#StatLabel {{ color: {TEXT_2}; }}

#NavButton {{
    text-align: left; padding: 10px 14px; border-radius: 12px; border: 1px solid transparent;
    font-size: 10.5pt; color: {TEXT_2};
}}
#NavButton:hover {{ background: rgba(255, 255, 255, 0.07); color: {TEXT}; }}
#NavButton:checked {{
    background: rgba(255, 255, 255, 0.18); border: 1px solid rgba(255, 255, 255, 0.28);
    color: {TEXT}; font-weight: 600;
}}

QPushButton {{
    background: rgba(255, 255, 255, 0.12); border: 1px solid {GLASS_BORDER};
    border-radius: 16px; padding: 6px 16px; min-height: 20px;
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.20); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 0.26); }}
QPushButton:disabled {{ color: rgba(255, 255, 255, 0.35); background: rgba(255, 255, 255, 0.05); }}
QPushButton#Primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: #08321c; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: rgba(108, 197, 142, 0.35); color: rgba(8, 50, 28, 0.6); }}
QPushButton#Danger:hover {{ background: rgba(255, 122, 107, 0.35); border-color: #ff7a6b; }}
QPushButton#Chip {{ border-radius: 12px; padding: 3px 12px; }}
QPushButton#Chip:checked {{ background: rgba(255, 255, 255, 0.28); border-color: rgba(255,255,255,0.55); }}
QToolButton#IconButton {{ border: none; border-radius: 16px; padding: 6px; }}
QToolButton#IconButton:hover {{ background: rgba(255, 255, 255, 0.14); }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: rgba(5, 14, 50, 0.45); border: 1px solid {GLASS_BORDER};
    border-radius: 10px; padding: 5px 9px; selection-background-color: #3a6fd8;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid #8fd3ff;
}}
QAbstractSpinBox {{ padding: 5px 22px 5px 9px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; margin-top: 3px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 3px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: rgba(255, 255, 255, 0.12); border-radius: 5px;
}}
QAbstractSpinBox::up-arrow {{ image: url({ASSETS}/chevron-up.svg); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url({ASSETS}/chevron-down.svg); width: 10px; height: 10px; }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 24px; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url({ASSETS}/chevron-down.svg); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: #12276a; border: 1px solid {GLASS_BORDER}; selection-background-color: #2f5cc4;
    padding: 4px; outline: none;
}}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 5px; border: 1px solid {GLASS_BORDER};
    background: rgba(5, 14, 50, 0.45);
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QTableView, QListView, QTreeView {{
    background: {TABLE_BG}; alternate-background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 12px;
    gridline-color: rgba(255, 255, 255, 0.07);
    selection-background-color: rgba(120, 170, 255, 0.30); selection-color: {TEXT};
}}
QTableView::item {{ padding: 4px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); }}
QTableView::item:selected {{ background: rgba(120, 170, 255, 0.30); }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: rgba(255, 255, 255, 0.07); color: {TEXT_2}; border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.14); padding: 6px 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QListWidget#StageList::item {{ padding: 6px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }}
#RowItem {{ border-bottom: 1px solid rgba(255, 255, 255, 0.10); border-radius: 0; }}
#RowItem:hover {{ background: rgba(255, 255, 255, 0.08); border-radius: 10px; }}
QListWidget#RowList {{ background: transparent; border: none; }}
QListWidget#RowList::item {{
    border-bottom: 1px solid rgba(255, 255, 255, 0.10); padding: 2px 4px; border-radius: 0;
}}
QListWidget#RowList::item:selected {{
    background: rgba(255, 255, 255, 0.16); border-radius: 10px; border-bottom-color: transparent;
}}
QListWidget#RowList::item:hover:!selected {{ background: rgba(255, 255, 255, 0.06); border-radius: 10px; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: rgba(255, 255, 255, 0.22); border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: rgba(255, 255, 255, 0.35); }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; width: 0; height: 0;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: rgba(255, 255, 255, 0.10); border-radius: 3px; }}

QDialog, QMessageBox {{ background: #10226a; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QMenu {{ background: #12276a; border: 1px solid {GLASS_BORDER}; padding: 4px; }}
QMenu::item:selected {{ background: #2f5cc4; border-radius: 6px; }}
"""
