"""Drive the real window offscreen: every page renders and the main flows work."""

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from fiberdesk.core.status import Status  # noqa: E402
from fiberdesk.i18n import EN  # noqa: E402
from fiberdesk.storage.db import open_database  # noqa: E402
from fiberdesk.storage.models import Line, Project  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from fiberdesk.ui import theme

    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    instance.setStyleSheet(theme.STYLE_SHEET)
    return instance


@pytest.fixture
def window(app, tmp_path):
    from fiberdesk.ui.context import AppContext
    from fiberdesk.ui.main_window import MainWindow

    db = open_database(tmp_path / "ui.db")
    win = MainWindow(AppContext(db))
    win.resize(1280, 800)
    win.show()
    app.processEvents()
    yield win
    win.close()
    db.close()


def test_every_page_renders(window, app):
    for key in window.pages:
        window.show_page(key)
        app.processEvents()
        image = window.grab()
        assert not image.isNull() and image.width() == 1280


def test_window_survives_resizing(window, app):
    for size in ((1100, 680), (1920, 1080), (1280, 800)):
        window.resize(*size)
        for key in window.pages:
            window.show_page(key)
            app.processEvents()
    assert window.width() >= window.minimumWidth()


def test_dashboard_counts(window):
    page = window.pages["dashboard"]
    assert page.stats["lines"].value.text() == str(len(window.ctx.db.lines()))


def test_project_and_line_crud_refresh_pages(window, app):
    ctx = window.ctx
    pid = ctx.db.save_project(Project(None, "Smoke Test Area", "FTTH"))
    line = Line(None, pid, "SMK-01", "CO", "Cabinet", 2.0, "G.657.A1", 4, 2, "1:32", 1490, 3.0, -28.0)
    ctx.db.save_line(line)
    ctx.data_changed.emit()
    window.show_page("projects", {"project": pid})
    app.processEvents()
    page = window.pages["projects"]
    assert page.table.rowCount() == 1
    page.search.setText("nothing-matches")
    assert page.table.isRowHidden(0)
    page.search.clear()
    page.table.selectRow(0)
    assert page.budget_btn.isEnabled()
    ctx.db.delete_line(line.id)
    ctx.data_changed.emit()
    assert page.table.rowCount() == 0


def test_budget_page_saves_to_line(window, app):
    line = window.ctx.db.lines()[0]
    window.show_page("budget", {"line": line.id})
    page = window.pages["budget"]
    assert page.length.value() == pytest.approx(line.length_km)
    page.rx.setValue(-10.0)  # far too little budget for a PON split
    app.processEvents()
    assert page._result.status is Status.FAIL
    page._save()
    assert window.ctx.db.line(line.id).budget_status is Status.FAIL
    page.splitters.setEditText("1:3")
    app.processEvents()
    assert page.error.isVisibleTo(page) and not page.save_btn.isEnabled()


def test_otdr_page_shows_trace_overlay_and_comparison(window, app):
    views = window.ctx.db.measurement_views()
    target = next(v for v in views
                  if len({x.measurement.wavelength_nm for x in views if x.line.id == v.line.id}) > 1)
    window.show_page("otdr", {"measurement": target.measurement.id})
    app.processEvents()
    page = window.pages["otdr"]
    assert page.current.measurement.id == target.measurement.id
    assert len(page.plot.curves) > 1
    assert len(page.plot.markers) == len(target.events)
    assert page.event_table.rowCount() == len(target.events)
    assert page.cmp_table.rowCount() == 6
    page.event_table.selectRow(1)
    app.processEvents()
    page.status_filter.setCurrentIndex(page.status_filter.findData("FAIL"))
    visible = [r for r in range(page.list_table.rowCount()) if not page.list_table.isRowHidden(r)]
    assert visible and all(page.list_table.item(r, 3).text() == "FAIL" for r in visible)


def test_pdf_report(window, tmp_path):
    from fiberdesk.ui.pages.otdr import related_views
    from fiberdesk.ui.report import export_line_report

    views = window.ctx.db.measurement_views()
    view = views[0]
    out = tmp_path / "report.pdf"
    export_line_report(str(out), view, list(related_views(view, views).values()),
                       window.ctx.defaults)
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 20_000
    assert len(re.findall(rb"/Type\s*/Page[^s]", data)) == 1  # one page


def test_settings_change_regrades(window, app):
    page = window.pages["settings"]
    page.scalar_boxes["splice_warn_db"].setValue(0.01)
    page.scalar_boxes["splice_fail_db"].setValue(0.02)
    page._save()
    app.processEvents()
    fails = sum(v.status is Status.FAIL for v in window.ctx.db.measurement_views(window.ctx.defaults))
    assert window.ctx.defaults.splice_fail_db == pytest.approx(0.02)
    assert fails > 20
    page._reset()
    assert window.ctx.defaults.splice_fail_db == pytest.approx(0.50)


def test_color_and_pon_pages(window, app):
    color = window.pages["colorcode"]
    color.size.setCurrentIndex(color.size.findData(144))
    color.fiber.setValue(144)
    assert "Aqua" in color.summary.text()
    pon = window.pages["pon"]
    pon._set_stages((64, 2))
    pon.length.setValue(20.0)
    assert pon.class_cards[0].badge.text() == "FAIL"


def test_all_ui_strings_exist():
    """Every tr("...") key used in the package is defined in the English table."""
    root = Path(__file__).resolve().parents[1] / "fiberdesk"
    used = set()
    for path in root.rglob("*.py"):
        used |= set(re.findall(r'tr\(\s*"([a-z_]+\.[A-Za-z_.+]+)"', path.read_text()))
    missing = sorted(k for k in used if k not in EN)
    assert not missing, missing


def test_line_dialog_validates_and_fills_line(window, monkeypatch):
    from fiberdesk.ui.pages.projects import LineDialog

    projects = window.ctx.db.projects()
    line = Line(None, projects[0].id, "")
    dlg = LineDialog(line, projects, window.ctx.defaults, window)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: None)  # no popups
    dlg._accept()  # empty name is rejected
    assert dlg.result() == 0 and line.name == ""
    dlg.name.setText("NEW-01")
    dlg.length.setValue(3.5)
    dlg.splitters.setText("1:4+1:8")
    dlg._accept()
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert (line.name, line.length_km, line.splitters) == ("NEW-01", 3.5, "1:4 + 1:8")
