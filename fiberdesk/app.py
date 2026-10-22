"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fiberdesk", description="FiberDesk desktop app")
    parser.add_argument("--db", help="SQLite database path (default: data/fiberdesk.db)")
    parser.add_argument("--reseed", action="store_true",
                        help="rebuild the demo data before starting")
    parser.add_argument("--screenshots", metavar="DIR",
                        help="save a PNG of every page into DIR and exit")
    parser.add_argument("--size", default="1440x900", help="window size, e.g. 1280x800")
    parser.add_argument("--version", action="version", version=f"FiberDesk {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    from .storage.db import open_database
    from .storage.seed import rebuild
    from .ui import theme
    from .ui.context import AppContext
    from .ui.main_window import MainWindow

    # English UI: keep number formats (decimal point) consistent with it.
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    app = QApplication(sys.argv[:1])
    app.setApplicationName("FiberDesk")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("fiberdesk")
    app.setStyle("Fusion")
    app.setFont(theme.app_font(10))
    app.setStyleSheet(theme.STYLE_SHEET)

    db = rebuild(args.db) if args.reseed else open_database(args.db)
    window = MainWindow(AppContext(db))
    width, height = (int(v) for v in args.size.lower().split("x"))
    window.resize(width, height)
    window.show()

    if args.screenshots:
        from .ui.screenshots import capture_all

        capture_all(window, args.screenshots)
    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
