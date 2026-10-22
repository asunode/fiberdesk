"""SQLite persistence."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..core.budget import BudgetResult
from ..core.defaults import Defaults
from ..core.otdr import Event, EventKind, evaluate_measurement, link_loss
from ..core.status import Status
from .models import Device, Line, Measurement, Project

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    a_end TEXT NOT NULL DEFAULT '',
    b_end TEXT NOT NULL DEFAULT '',
    length_km REAL NOT NULL,
    fiber_type TEXT NOT NULL,
    connectors INTEGER NOT NULL,
    splices INTEGER NOT NULL,
    splitters TEXT NOT NULL DEFAULT '',
    wavelength_nm INTEGER NOT NULL,
    tx_power_dbm REAL NOT NULL,
    rx_sensitivity_dbm REAL NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    budget_status TEXT,
    budget_remaining_db REAL,
    budget_saved_at TEXT
);
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    profile_key TEXT NOT NULL,
    serial TEXT NOT NULL,
    calibration_date TEXT NOT NULL,
    team TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY,
    line_id INTEGER NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    wavelength_nm INTEGER NOT NULL,
    measured_at TEXT NOT NULL,
    operator TEXT NOT NULL,
    pulse_ns INTEGER NOT NULL,
    range_km REAL NOT NULL,
    trace_seed INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    measurement_id INTEGER NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    distance_km REAL NOT NULL,
    kind TEXT NOT NULL,
    loss_db REAL,
    reflectance_db REAL,
    section_db_km REAL,
    splitter_ratio INTEGER
);
CREATE INDEX IF NOT EXISTS idx_lines_project ON lines(project_id);
CREATE INDEX IF NOT EXISTS idx_meas_line ON measurements(line_id);
CREATE INDEX IF NOT EXISTS idx_events_meas ON events(measurement_id);
"""


def default_db_path() -> Path:
    """``$FIBERDESK_DB`` if set; ``data/fiberdesk.db`` in a source checkout; otherwise
    (an installed package) ``$XDG_DATA_HOME/fiberdesk/fiberdesk.db``."""
    env = os.environ.get("FIBERDESK_DB")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[2]
    if (root / "pyproject.toml").exists():
        return root / "data" / "fiberdesk.db"
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "fiberdesk" / "fiberdesk.db"


@dataclass
class MeasurementView:
    """A measurement joined with everything a list row needs."""
    measurement: Measurement
    line: Line
    project: Project
    device: Device
    events: list[Event]
    status: Status
    total_loss_db: float


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)",
                          (str(SCHEMA_VERSION),))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0

    def clear(self) -> None:
        with self.conn:
            for table in ("events", "measurements", "lines", "devices", "projects", "settings"):
                self.conn.execute(f"DELETE FROM {table}")

    def set_meta(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    # --- Settings ------------------------------------------------------------

    def load_defaults(self) -> Defaults:
        row = self.conn.execute("SELECT value FROM settings WHERE key = 'defaults'").fetchone()
        return Defaults.from_dict(json.loads(row[0]) if row else None)

    def save_defaults(self, defaults: Defaults) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO settings VALUES ('defaults', ?)",
                              (json.dumps(defaults.to_dict()),))

    def reset_defaults(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE key = 'defaults'")

    # --- Projects ------------------------------------------------------------

    def projects(self) -> list[Project]:
        rows = self.conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
        return [Project(**dict(r)) for r in rows]

    def project(self, project_id: int) -> Project:
        row = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return Project(**dict(row))

    def save_project(self, project: Project) -> int:
        values = (project.name, project.kind, project.region, project.description)
        with self.conn:
            if project.id is None:
                cur = self.conn.execute(
                    "INSERT INTO projects (name, kind, region, description) VALUES (?, ?, ?, ?)",
                    values)
                project.id = cur.lastrowid
            else:
                self.conn.execute(
                    "UPDATE projects SET name=?, kind=?, region=?, description=? WHERE id=?",
                    (*values, project.id))
        return project.id

    def delete_project(self, project_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # --- Lines ---------------------------------------------------------------

    _LINE_COLUMNS = ("project_id", "name", "a_end", "b_end", "length_km", "fiber_type",
                     "connectors", "splices", "splitters", "wavelength_nm", "tx_power_dbm",
                     "rx_sensitivity_dbm", "notes")

    @staticmethod
    def _line(row: sqlite3.Row) -> Line:
        data = dict(row)
        status = data.pop("budget_status")
        return Line(**data, budget_status=Status(status) if status else None)

    def lines(self, project_id: int | None = None) -> list[Line]:
        if project_id is None:
            rows = self.conn.execute("SELECT * FROM lines ORDER BY project_id, id").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM lines WHERE project_id = ? ORDER BY id",
                                     (project_id,)).fetchall()
        return [self._line(r) for r in rows]

    def line(self, line_id: int) -> Line:
        row = self.conn.execute("SELECT * FROM lines WHERE id = ?", (line_id,)).fetchone()
        if row is None:
            raise KeyError(line_id)
        return self._line(row)

    def save_line(self, line: Line) -> int:
        values = tuple(getattr(line, c) for c in self._LINE_COLUMNS)
        with self.conn:
            if line.id is None:
                cols = ", ".join(self._LINE_COLUMNS)
                marks = ", ".join("?" for _ in self._LINE_COLUMNS)
                cur = self.conn.execute(f"INSERT INTO lines ({cols}) VALUES ({marks})", values)
                line.id = cur.lastrowid
            else:
                sets = ", ".join(f"{c}=?" for c in self._LINE_COLUMNS)
                self.conn.execute(f"UPDATE lines SET {sets} WHERE id=?", (*values, line.id))
        return line.id

    def save_line_budget(self, line_id: int, result: BudgetResult,
                         when: datetime | None = None) -> None:
        stamp = (when or datetime.now()).isoformat(timespec="minutes")
        with self.conn:
            self.conn.execute(
                "UPDATE lines SET budget_status=?, budget_remaining_db=?, budget_saved_at=? "
                "WHERE id=?",
                (result.status.value, round(result.remaining_db, 3), stamp, line_id))

    def delete_line(self, line_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM lines WHERE id = ?", (line_id,))

    # --- Devices -------------------------------------------------------------

    def devices(self) -> list[Device]:
        rows = self.conn.execute("SELECT * FROM devices ORDER BY id").fetchall()
        return [Device(**dict(r)) for r in rows]

    def save_device(self, device: Device) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO devices (profile_key, serial, calibration_date, team) "
                "VALUES (?, ?, ?, ?)",
                (device.profile_key, device.serial, device.calibration_date, device.team))
        device.id = cur.lastrowid
        return device.id

    def measurement_counts_by_device(self) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT device_id, COUNT(*) FROM measurements GROUP BY device_id").fetchall()
        return {r[0]: r[1] for r in rows}

    # --- Measurements --------------------------------------------------------

    def save_measurement(self, m: Measurement, events: list[Event]) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO measurements (line_id, device_id, wavelength_nm, measured_at, "
                "operator, pulse_ns, range_km, trace_seed, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                (m.line_id, m.device_id, m.wavelength_nm, m.measured_at, m.operator,
                 m.pulse_ns, m.range_km, m.trace_seed, m.notes))
            m.id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO events (measurement_id, number, distance_km, kind, loss_db, "
                "reflectance_db, section_db_km, splitter_ratio) VALUES (?,?,?,?,?,?,?,?)",
                [(m.id, e.number, e.distance_km, e.kind.value, e.loss_db, e.reflectance_db,
                  e.section_db_km, e.splitter_ratio) for e in events])
        return m.id

    def _events_by_measurement(self) -> dict[int, list[Event]]:
        result: dict[int, list[Event]] = {}
        for r in self.conn.execute("SELECT * FROM events ORDER BY measurement_id, number"):
            result.setdefault(r["measurement_id"], []).append(Event(
                number=r["number"], distance_km=r["distance_km"], kind=EventKind(r["kind"]),
                loss_db=r["loss_db"], reflectance_db=r["reflectance_db"],
                section_db_km=r["section_db_km"], splitter_ratio=r["splitter_ratio"]))
        return result

    def measurement_views(self, defaults: Defaults | None = None) -> list[MeasurementView]:
        """All measurements, newest first, graded with ``defaults``."""
        defaults = defaults or self.load_defaults()
        projects = {p.id: p for p in self.projects()}
        lines = {ln.id: ln for ln in self.lines()}
        devices = {d.id: d for d in self.devices()}
        events = self._events_by_measurement()
        views = []
        rows = self.conn.execute("SELECT * FROM measurements ORDER BY measured_at DESC, id DESC")
        for r in rows:
            m = Measurement(**dict(r))
            line = lines[m.line_id]
            evs = events.get(m.id, [])
            views.append(MeasurementView(
                measurement=m, line=line, project=projects[line.project_id],
                device=devices[m.device_id], events=evs,
                status=evaluate_measurement(evs, m.wavelength_nm, defaults),
                total_loss_db=link_loss(evs)))
        return views

    def counts(self) -> dict[str, int]:
        q = self.conn.execute
        return {
            "projects": q("SELECT COUNT(*) FROM projects").fetchone()[0],
            "lines": q("SELECT COUNT(*) FROM lines").fetchone()[0],
            "measurements": q("SELECT COUNT(*) FROM measurements").fetchone()[0],
            "devices": q("SELECT COUNT(*) FROM devices").fetchone()[0],
        }


def open_database(path: str | Path | None = None, seed_if_empty: bool = True) -> Database:
    db = Database(path or default_db_path())
    if seed_if_empty and db.is_empty():
        from .seed import populate

        populate(db)
    return db
