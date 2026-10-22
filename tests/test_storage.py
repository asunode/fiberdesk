from collections import Counter

import pytest

from fiberdesk.core.budget import calculate_budget
from fiberdesk.core.defaults import Defaults
from fiberdesk.core.devices import PROFILES
from fiberdesk.core.otdr import EventKind
from fiberdesk.core.status import Status
from fiberdesk.storage.db import Database, open_database
from fiberdesk.storage.models import Line, Project
from fiberdesk.storage.seed import populate, rebuild


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    db = open_database(tmp_path_factory.mktemp("db") / "demo.db")
    yield db
    db.close()


def test_demo_counts(demo):
    counts = demo.counts()
    assert counts["projects"] == 5
    assert 28 <= counts["lines"] <= 32
    assert 50 <= counts["measurements"] <= 70
    assert counts["devices"] == 7


def test_demo_is_mostly_pass_with_some_warn_and_fail(demo):
    statuses = Counter(v.status for v in demo.measurement_views())
    assert statuses[Status.PASS] > statuses[Status.WARN] > 0
    assert statuses[Status.FAIL] > 0
    assert statuses[Status.PASS] > len(demo.measurement_views()) / 2


def test_measurements_respect_device_wavelengths(demo):
    for view in demo.measurement_views():
        assert view.measurement.wavelength_nm in view.device.profile.wavelengths


def test_event_layout_matches_line(demo):
    for view in demo.measurement_views():
        kinds = Counter(e.kind for e in view.events)
        assert kinds[EventKind.CONNECTOR] == view.line.connectors
        assert kinds[EventKind.SPLICE] == view.line.splices
        assert kinds[EventKind.SPLITTER] == len(view.line.splitter_ratios)
        assert kinds[EventKind.END] == 1
        assert view.events[0].distance_km == 0.0
        assert [e.number for e in view.events] == list(range(1, len(view.events) + 1))


def test_seed_is_reproducible(tmp_path):
    a = Database(tmp_path / "a.db")
    b = Database(tmp_path / "b.db")
    populate(a)
    populate(b)
    rows = lambda db: [(v.measurement.measured_at, v.line.name, v.measurement.trace_seed,
                        round(v.total_loss_db, 6)) for v in db.measurement_views()]
    assert rows(a) == rows(b)


def test_rebuild_replaces_data(tmp_path):
    path = tmp_path / "r.db"
    db = rebuild(path)
    db.save_project(Project(None, "Extra"))
    db.close()
    db = rebuild(path)
    assert "Extra" not in [p.name for p in db.projects()]
    db.close()


def test_project_and_line_crud(tmp_path):
    db = Database(tmp_path / "crud.db")
    pid = db.save_project(Project(None, "Test Project", "FTTH"))
    line = Line(None, pid, "L-1", "A", "B", 2.5, "G.657.A1", 4, 2, "1:8", 1490, 3.0, -28.0)
    lid = db.save_line(line)
    line.length_km = 3.0
    db.save_line(line)
    assert db.line(lid).length_km == 3.0
    result = calculate_budget(line.budget_input())
    db.save_line_budget(lid, result)
    stored = db.line(lid)
    assert stored.budget_status is result.status
    assert stored.budget_remaining_db == pytest.approx(result.remaining_db, abs=1e-3)
    db.delete_project(pid)  # cascades to lines
    assert db.lines() == []


def test_settings_round_trip(tmp_path):
    db = Database(tmp_path / "s.db")
    assert db.load_defaults() == Defaults()
    custom = Defaults.from_dict({"safety_margin_db": 4.5, "splitter_loss_db": {"32": 17.5}})
    db.save_defaults(custom)
    loaded = db.load_defaults()
    assert loaded.safety_margin_db == 4.5
    assert loaded.splitter(32) == 17.5
    assert loaded.splitter(8) == 10.5
    db.reset_defaults()
    assert db.load_defaults() == Defaults()


def test_device_profiles():
    assert set(PROFILES) == {"maxtester-730d", "maxtester-730c", "maxtester-715d"}
    assert PROFILES["maxtester-730d"].wavelengths == (1310, 1550, 1625)
    assert PROFILES["maxtester-715d"].dynamic_range_db[1550] == 30.0
