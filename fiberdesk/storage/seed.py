"""Demo data generator.

Everything here is fictional: project names, sites, operators, serial numbers
and measurements. A fixed seed and a fixed reference date make the data set
identical on every run.

    python -m fiberdesk.storage.seed          # rebuild data/fiberdesk.db
    python -m fiberdesk.storage.seed --db x.db
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.budget import calculate_budget, format_splitters
from ..core.defaults import Defaults
from ..core.devices import get_profile
from ..core.otdr import LAUNCH_FIBER_KM, Event, EventKind
from .db import Database, default_db_path, open_database
from .models import Device, Line, Measurement, Project

DEFAULT_SEED = 598
REFERENCE_DATE = datetime(2026, 10, 15, 17, 0)  # demo "today"; measurements fall in the 6 months before
RECEIVE_FIBER_KM = 0.15

# Role labels rather than personal names, so no real person can be implied.
OPERATORS = tuple(f"Technician {c}" for c in "ABCDEF")

DEVICES = (
    ("maxtester-730d", "FD7D-24-0117", "2026-03-11", "PON Field Team"),
    ("maxtester-730d", "FD7D-24-0242", "2026-05-02", "Backbone Crew"),
    ("maxtester-730d", "FD7D-25-0031", "2026-08-19", "Ring Maintenance"),
    ("maxtester-730c", "FD7C-21-0880", "2025-12-04", "Ring Maintenance"),
    ("maxtester-730c", "FD7C-21-0913", "2026-01-22", "Backbone Crew"),
    ("maxtester-715d", "FD15-23-1406", "2026-04-27", "Campus Ops"),
    ("maxtester-715d", "FD15-24-0058", "2026-07-08", "Mobile Backhaul Team"),
)


@dataclass(frozen=True)
class ProjectPlan:
    name: str
    kind: str
    region: str
    description: str
    style: str
    line_count: int
    device_indexes: tuple[int, ...]


PROJECTS = (
    ProjectPlan("Moda FTTH Phase 2", "FTTH / GPON", "Moda",
                "Splitter-based GPON distribution, short feeder and drop runs.",
                "pon", 8, (0,)),
    ProjectPlan("Organized Industrial Zone Backbone", "Backbone", "Industrial Zone",
                "Long-haul backbone between zone substations, 12–40 km spans.",
                "backbone", 5, (1, 4)),
    ProjectPlan("Coastal City Ring", "Metro ring", "Coastal District",
                "Metro ring with 6–15 km sections between aggregation sites.",
                "ring", 6, (2, 3)),
    ProjectPlan("Campus Interconnect", "Campus", "University Campus",
                "Very short inter-building links with many patch panels.",
                "campus", 6, (5,)),
    ProjectPlan("Base Station Links", "Mobile backhaul", "Northern Hills",
                "Fronthaul and backhaul links to base station sites, 2–8 km.",
                "bts", 6, (6, 3)),
)

SITES = {
    "pon": ("Moda CO", ["Cabinet M-%02d" % i for i in range(1, 20)]),
    "backbone": ("Substation North", ["Substation %s" % c for c in "ABCDEFGH"]),
    "ring": ("Harbor Agg.", ["Lighthouse Agg.", "Marina Agg.", "Old Town Agg.", "Pier Agg.",
                             "Cliff Agg.", "Bay Agg.", "Harbor Agg."]),
    "campus": ("Main Library", ["Engineering B%d" % i for i in range(1, 10)]),
    "bts": ("Hilltop MSC", ["BTS-%03d" % i for i in range(101, 120)]),
}


@dataclass
class Anomaly:
    kind: str  # "connector", "splice", "bend"
    severity: str  # "warn" or "fail"
    index: int = 0  # which connector/splice is affected
    position_km: float = 0.0
    magnitude: float = 0.0


@dataclass
class Layout:
    """The physical line: element positions and their intrinsic quality."""
    connectors: list[tuple[float, float, float]] = field(default_factory=list)  # (km, loss, refl)
    splices: list[tuple[float, float]] = field(default_factory=list)  # (km, loss)
    splitters: list[tuple[float, int, float]] = field(default_factory=list)  # (km, ratio, excess)
    anomaly: Anomaly | None = None


# Transmitter power / receiver sensitivity pairs (dBm) per style. The first entry is
# the usual optic; the others are weaker parts that leave some links tight on budget.
OPTICS = {
    "pon": ((3.0, -28.0), (3.0, -28.0), (0.5, -25.0)),
    "backbone": ((2.0, -24.0), (2.0, -24.0), (0.0, -20.0)),
    "ring": ((-1.0, -18.0), (-1.0, -18.0), (-5.0, -14.0)),
    "campus": ((-1.0, -14.4), (-1.0, -14.4), (-8.2, -12.6)),
    "bts": ((-1.0, -14.4), (-1.0, -14.4), (-8.2, -14.4)),
}


def _line_spec(style: str, rng: random.Random) -> dict:
    tx, rx = rng.choice(OPTICS[style])
    if style == "pon":
        length = rng.uniform(1.2, 4.6)
        spec = dict(length_km=length, fiber_type="G.657.A1",
                    connectors=rng.choice((4, 4, 6)), splices=rng.randint(2, 5),
                    splitters=rng.choice(("1:32", "1:4 + 1:8", "1:8 + 1:4", "1:2 + 1:16", "1:64")),
                    wavelength_nm=1490)
    elif style == "backbone":
        length = rng.uniform(12.0, 40.0)
        spec = dict(length_km=length, fiber_type="G.652.D", connectors=2,
                    splices=max(2, math.ceil(length / 4.0) - 1), splitters="", wavelength_nm=1550)
    elif style == "ring":
        length = rng.uniform(6.0, 15.0)
        spec = dict(length_km=length, fiber_type="G.652.D", connectors=rng.choice((2, 4)),
                    splices=max(1, math.ceil(length / 3.0) - 1), splitters="", wavelength_nm=1310)
    elif style == "campus":
        length = rng.uniform(0.15, 1.5)
        spec = dict(length_km=length, fiber_type="G.657.A1", connectors=rng.choice((4, 6, 8)),
                    splices=rng.randint(0, 2), splitters="", wavelength_nm=1310)
    else:
        length = rng.uniform(2.0, 8.0)
        spec = dict(length_km=length, fiber_type="G.652.D", connectors=4,
                    splices=rng.randint(1, 3), splitters="", wavelength_nm=1310)
    return dict(spec, tx_power_dbm=tx, rx_sensitivity_dbm=rx)


def _spread(rng: random.Random, count: int, lo: float, hi: float, taken: list[float],
            gap: float) -> list[float]:
    """``count`` positions in ``(lo, hi)``, roughly evenly spaced, at least ``gap`` from others."""
    positions: list[float] = []
    for i in range(count):
        base = lo + (hi - lo) * (i + 1) / (count + 1)
        for _ in range(50):
            pos = base + rng.uniform(-0.3, 0.3) * (hi - lo) / (count + 1)
            if all(abs(pos - t) >= gap for t in taken + positions) and lo < pos < hi:
                break
        positions.append(round(pos, 3))
    return positions


def _layout(line: Line, rng: random.Random) -> Layout:
    length = line.length_km
    gap = max(0.02, length * 0.02)
    lay = Layout()
    taken = [0.0, length]

    for i, ratio in enumerate(line.splitter_ratios):
        frac = (0.35, 0.82)[min(i, 1)] if len(line.splitter_ratios) > 1 else 0.55
        pos = round(length * (frac + rng.uniform(-0.06, 0.06)), 3)
        lay.splitters.append((pos, ratio, rng.uniform(-0.35, 0.55)))
        taken.append(pos)

    intermediate = line.connectors - 2
    conn_pos = [0.0]
    # Splitters are connectorised: put intermediate connectors at the splitter cabinets first.
    for pos, _, _ in lay.splitters:
        if len(conn_pos) - 1 >= intermediate:
            break
        conn_pos.append(round(pos - min(0.01, gap / 2), 3))
    extra = intermediate - (len(conn_pos) - 1)
    new = _spread(rng, extra, 0.0, length, taken, gap)
    taken += new
    conn_pos += new
    conn_pos.append(length)
    conn_pos.sort()
    for pos in conn_pos:
        lay.connectors.append((pos, rng.uniform(0.12, 0.42), rng.uniform(-58.0, -49.0)))

    for pos in _spread(rng, line.splices, 0.0, length, taken + conn_pos, gap):
        lay.splices.append((pos, rng.choice((0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.12))))
    lay.splices.sort()

    roll = rng.random()
    if roll < 0.78:
        return lay
    severity = "warn" if roll < 0.93 else "fail"
    kinds = ["connector", "bend"] + (["splice"] if lay.splices else [])
    kind = rng.choice(kinds)
    if kind == "connector":
        mag = rng.uniform(0.56, 0.70) if severity == "warn" else rng.uniform(0.9, 1.5)
        lay.anomaly = Anomaly(kind, severity, rng.randrange(len(lay.connectors)), magnitude=mag)
    elif kind == "splice":
        mag = rng.uniform(0.33, 0.46) if severity == "warn" else rng.uniform(0.6, 0.95)
        lay.anomaly = Anomaly(kind, severity, rng.randrange(len(lay.splices)), magnitude=mag)
    else:
        # Loss at 1310 nm; longer wavelengths scale up (see BEND_SCALE).
        mag = rng.uniform(0.04, 0.10) if severity == "warn" else rng.uniform(0.16, 0.30)
        pos = _spread(rng, 1, length * 0.15, length * 0.9, taken + conn_pos, gap)[0]
        lay.anomaly = Anomaly(kind, severity, position_km=pos, magnitude=mag)
    return lay


BEND_SCALE = {1310: 1.0, 1550: 3.2, 1625: 5.0}
BEND_VISIBLE_DB = 0.05  # smaller bends disappear into the trace


def _events(lay: Layout, line: Line, wavelength: int, defaults: Defaults,
            rng: random.Random, repaired: bool) -> list[Event]:
    """One OTDR acquisition of a physical layout at ``wavelength``."""
    anomaly = None if repaired else lay.anomaly
    raw: list[tuple[float, EventKind, float | None, float | None, int | None]] = []
    for i, (pos, loss, refl) in enumerate(lay.connectors):
        if anomaly and anomaly.kind == "connector" and anomaly.index == i:
            loss = anomaly.magnitude
            refl = rng.uniform(-44.0, -39.0) if anomaly.severity == "warn" else rng.uniform(-37.0, -31.0)
        raw.append((pos, EventKind.CONNECTOR, loss * rng.uniform(0.93, 1.07),
                    refl + rng.uniform(-1.0, 1.0), None))
    for i, (pos, loss) in enumerate(lay.splices):
        if anomaly and anomaly.kind == "splice" and anomaly.index == i:
            loss = anomaly.magnitude
        jitter = rng.uniform(-0.015, 0.015) if wavelength != 1310 else 0.0
        raw.append((pos, EventKind.SPLICE, max(0.01, loss + jitter), None, None))
    for pos, ratio, excess in lay.splitters:
        loss = defaults.splitter(ratio) + excess + rng.uniform(-0.1, 0.1)
        raw.append((pos, EventKind.SPLITTER, loss, rng.uniform(-60.0, -55.0), ratio))
    if anomaly and anomaly.kind == "bend":
        loss = anomaly.magnitude * BEND_SCALE[wavelength] * rng.uniform(0.92, 1.08)
        if loss >= BEND_VISIBLE_DB:
            raw.append((anomaly.position_km, EventKind.BEND, loss, None, None))
    raw.append((round(line.length_km + RECEIVE_FIBER_KM, 3), EventKind.END, None,
                rng.uniform(-16.0, -14.0), None))
    raw.sort(key=lambda r: r[0])

    nominal = defaults.attenuation(wavelength)
    events: list[Event] = []
    for n, (pos, kind, loss, refl, ratio) in enumerate(raw, start=1):
        section = None if n == 1 else round(nominal + rng.uniform(-0.015, 0.025), 3)
        events.append(Event(
            number=n, distance_km=round(pos, 3), kind=kind,
            loss_db=None if loss is None else round(loss, 3),
            reflectance_db=None if refl is None else round(refl, 1),
            section_db_km=section, splitter_ratio=ratio))
    return events


def _pulse_and_range(length_km: float) -> tuple[int, float]:
    pulse = next(p for limit, p in ((1.0, 10), (5.0, 30), (15.0, 100), (30.0, 275),
                                    (math.inf, 1000)) if length_km <= limit)
    span = length_km + LAUNCH_FIBER_KM + RECEIVE_FIBER_KM
    rng_km = next(r for r in (1.25, 2.5, 5.0, 10.0, 20.0, 40.0, 80.0) if r >= span * 1.25)
    return pulse, rng_km


def populate(db: Database, seed: int = DEFAULT_SEED) -> None:
    """Fill an empty database with the demo data set."""
    rng = random.Random(seed)
    defaults = db.load_defaults()
    device_ids = [db.save_device(Device(None, *spec)) for spec in DEVICES]

    for plan in PROJECTS:
        project = Project(None, plan.name, plan.kind, plan.region, plan.description)
        db.save_project(project)
        hub, remotes = SITES[plan.style]
        remotes = list(remotes)
        rng.shuffle(remotes)
        for i in range(plan.line_count):
            spec = _line_spec(plan.style, rng)
            spec["length_km"] = round(spec["length_km"], 2)
            b_end = remotes[i % len(remotes)]
            a_end = hub
            if plan.style == "ring":
                a_end, b_end = SITES["ring"][1][i], SITES["ring"][1][i + 1]
            code = "".join(w[0] for w in plan.name.split()[:3]).upper()
            line = Line(None, project.id, f"{code}-{i + 1:02d}", a_end, b_end, **spec)
            line.splitters = format_splitters(list(line.splitter_ratios))
            db.save_line(line)
            when = REFERENCE_DATE - timedelta(days=rng.randint(0, 182), hours=rng.randint(0, 8))
            db.save_line_budget(line.id, calculate_budget(line.budget_input(), defaults),
                                when - timedelta(days=rng.randint(7, 30)))
            _measure_line(db, line, plan, device_ids, defaults, rng, when)

    db.set_meta("demo_seed", str(seed))


def _measure_line(db: Database, line: Line, plan: ProjectPlan, device_ids: list[int],
                  defaults: Defaults, rng: random.Random, when: datetime) -> None:
    lay = _layout(line, rng)
    device_index = rng.choice(plan.device_indexes)
    device_id = device_ids[device_index]
    profile = get_profile(DEVICES[device_index][0])
    wavelengths = list(profile.wavelengths)
    count = rng.choice((1, 2, 2, 3)) if len(wavelengths) > 2 else rng.choice((1, 2, 2))
    chosen = wavelengths[:count]
    operator = rng.choice(OPERATORS)
    pulse, range_km = _pulse_and_range(line.length_km)

    sessions: list[tuple[datetime, int, bool, str]] = [
        (when + timedelta(minutes=12 * k), wl, False, "") for k, wl in enumerate(chosen)]
    # A dirty connector found on an earlier visit gets cleaned and re-tested.
    fixable = lay.anomaly and lay.anomaly.kind == "connector"
    if fixable and len(sessions) < 3 and rng.random() < 0.7:
        retest = when + timedelta(days=rng.randint(3, 20))
        if retest <= REFERENCE_DATE:
            sessions.append((retest, chosen[-1], True, "Re-test after connector cleaning"))

    for stamp, wl, repaired, note in sessions:
        events = _events(lay, line, wl, defaults, rng, repaired)
        m = Measurement(None, line.id, device_id, wl, stamp.isoformat(timespec="minutes"),
                        operator, pulse, range_km, rng.randrange(1, 2**31), note)
        db.save_measurement(m, events)


def rebuild(path=None, seed: int = DEFAULT_SEED) -> Database:
    db = open_database(path, seed_if_empty=False)
    db.clear()
    populate(db, seed)
    return db


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rebuild the FiberDesk demo database.")
    parser.add_argument("--db", help=f"database path (default: {default_db_path()})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    db = rebuild(args.db, args.seed)
    counts = db.counts()
    print(f"Demo data written to {db.path}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    db.close()


if __name__ == "__main__":
    main()
