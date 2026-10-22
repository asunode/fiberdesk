"""OTDR events: evaluation, link totals, expected-vs-measured and trace synthesis.

The event list is the single source of truth: the event table is shown from it
directly and the trace is synthesised from it, so the two always agree.

Layout convention: distance 0 is the A-end connector (after a launch fibre),
the last non-end event is the B-end connector, and the ``end`` event marks the
end of the receive fibre. Link loss is measured between A and B inclusive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .defaults import Defaults
from .status import Status, grade_above


class EventKind(str, Enum):
    CONNECTOR = "connector"
    SPLICE = "splice"
    BEND = "bend"
    SPLITTER = "splitter"
    END = "end"


@dataclass(frozen=True)
class Event:
    number: int
    distance_km: float
    kind: EventKind
    loss_db: float | None = None
    reflectance_db: float | None = None
    section_db_km: float | None = None  # attenuation of the fibre section ending here
    splitter_ratio: int | None = None


def evaluate_event(event: Event, wavelength_nm: int, defaults: Defaults) -> Status:
    checks: list[Status] = []
    loss = event.loss_db
    if event.kind is EventKind.CONNECTOR and loss is not None:
        checks.append(grade_above(loss, defaults.connector_warn_db, defaults.connector_fail_db))
    elif event.kind is EventKind.SPLICE and loss is not None:
        checks.append(grade_above(loss, defaults.splice_warn_db, defaults.splice_fail_db))
    elif event.kind is EventKind.BEND and loss is not None:
        # A detected macrobend is never clean: it warns at least.
        checks.append(Status.FAIL if loss > defaults.bend_fail_db else Status.WARN)
    elif event.kind is EventKind.SPLITTER and loss is not None and event.splitter_ratio:
        nominal = defaults.splitter(event.splitter_ratio)
        tol = defaults.splitter_tolerance_db
        checks.append(grade_above(loss, nominal + tol, nominal + 2 * tol))

    if event.reflectance_db is not None and event.kind is EventKind.CONNECTOR:
        checks.append(grade_above(event.reflectance_db, defaults.reflectance_warn_db,
                                  defaults.reflectance_fail_db))
    if event.section_db_km is not None and event.kind is not EventKind.END:
        limit = defaults.attenuation(wavelength_nm) + defaults.section_tolerance_db_km
        if event.section_db_km > limit:
            checks.append(Status.WARN)
    return Status.worst(checks)


def evaluate_measurement(events: list[Event], wavelength_nm: int, defaults: Defaults) -> Status:
    return Status.worst(evaluate_event(e, wavelength_nm, defaults) for e in events)


def _link_events(events: list[Event]) -> list[Event]:
    """Events from the A connector up to the last event before the end marker."""
    ordered = sorted(events, key=lambda e: e.distance_km)
    return [e for e in ordered if e.kind is not EventKind.END]


def link_breakdown(events: list[Event]) -> dict[str, float]:
    """Measured loss by category, matching the keys of the budget breakdown."""
    result = {"fiber": 0.0, "splices": 0.0, "connectors": 0.0, "splitters": 0.0, "bends": 0.0}
    key_for = {
        EventKind.CONNECTOR: "connectors",
        EventKind.SPLICE: "splices",
        EventKind.SPLITTER: "splitters",
        EventKind.BEND: "bends",
    }
    link = _link_events(events)
    prev = None
    for event in link:
        if prev is not None and event.section_db_km is not None:
            result["fiber"] += event.section_db_km * (event.distance_km - prev.distance_km)
        if event.loss_db is not None:
            result[key_for[event.kind]] += event.loss_db
        prev = event
    return result


def link_loss(events: list[Event]) -> float:
    return sum(link_breakdown(events).values())


def link_length(events: list[Event]) -> float:
    link = _link_events(events)
    return link[-1].distance_km - link[0].distance_km if link else 0.0


@dataclass(frozen=True)
class ComparisonRow:
    key: str
    expected_db: float
    measured_db: float

    @property
    def delta_db(self) -> float:
        return self.measured_db - self.expected_db


@dataclass(frozen=True)
class Comparison:
    rows: tuple[ComparisonRow, ...]
    expected_total_db: float
    measured_total_db: float
    status: Status

    @property
    def delta_db(self) -> float:
        return self.measured_total_db - self.expected_total_db


def compare_expected(expected: dict[str, float], measured: dict[str, float],
                     defaults: Defaults) -> Comparison:
    """Compare a budget breakdown with an OTDR breakdown.

    A measurement above the expected total by more than ``compare_warn_db``
    warns, by more than ``compare_fail_db`` fails.
    """
    keys = ["fiber", "splices", "connectors", "splitters", "bends"]
    rows = tuple(ComparisonRow(k, expected.get(k, 0.0), measured.get(k, 0.0)) for k in keys)
    exp_total = sum(r.expected_db for r in rows)
    meas_total = sum(r.measured_db for r in rows)
    status = grade_above(meas_total - exp_total, defaults.compare_warn_db, defaults.compare_fail_db)
    return Comparison(rows, exp_total, meas_total, status)


# --- Trace synthesis --------------------------------------------------------

LAUNCH_FIBER_KM = 0.15
NOISE_FLOOR_DB = 0.0
# Shorter wavelengths backscatter more strongly, so their traces start higher.
BACKSCATTER_OFFSET_DB = {1310: 1.5, 1490: 0.5, 1550: 0.0, 1625: -0.5}


def _peak_height(reflectance_db: float) -> float:
    return float(np.clip((reflectance_db + 75.0) * 0.32, 1.0, 20.0))


def synthesize_trace(
    events: list[Event],
    wavelength_nm: int,
    dynamic_range_db: float,
    seed: int,
    defaults: Defaults | None = None,
    points: int = 5000,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(distance_km, level_db)`` arrays for a plausible OTDR trace."""
    defaults = defaults or Defaults()
    rng = np.random.default_rng(seed)
    ordered = sorted(events, key=lambda e: e.distance_km)
    if not ordered:
        raise ValueError("A trace needs at least one event")
    end_km = ordered[-1].distance_km
    span = end_km + LAUNCH_FIBER_KM
    x = np.linspace(-LAUNCH_FIBER_KM, end_km + max(0.12 * span, 0.3), points)
    nominal = defaults.attenuation(wavelength_nm)

    # Baseline: start level minus fibre loss and step losses of passed events.
    start_level = dynamic_range_db - 4.0 + BACKSCATTER_OFFSET_DB.get(int(wavelength_nm), 0.0)
    level = np.full_like(x, start_level)
    level -= np.clip(x + LAUNCH_FIBER_KM, 0, LAUNCH_FIBER_KM) * nominal
    prev_d = 0.0
    for event in ordered:
        att = event.section_db_km if event.section_db_km is not None else nominal
        seg = np.clip(x - prev_d, 0, event.distance_km - prev_d)
        level -= seg * att
        if event.loss_db:
            level -= np.where(x > event.distance_km, event.loss_db, 0.0)
        prev_d = event.distance_km

    # Past the end the signal collapses into the noise floor.
    after_end = x > end_km
    fall = np.exp(-(x - end_km) / max(span * 0.002, 0.004))
    level = np.where(after_end, NOISE_FLOOR_DB + (level - NOISE_FLOOR_DB) * fall, level)
    level = np.maximum(level, NOISE_FLOOR_DB)

    # Reflective peaks: front panel, reflective events and the fibre end.
    width = float(np.clip(span * 0.0025, 0.006, 0.08))
    above_floor = level > NOISE_FLOOR_DB + 0.5  # peaks are buried once the signal is gone
    peaks = [(-LAUNCH_FIBER_KM, 16.0, False)]
    peaks += [(e.distance_km, _peak_height(e.reflectance_db), e.kind is EventKind.END)
              for e in ordered if e.reflectance_db is not None]
    for d, height, is_end in peaks:
        rel = x - d
        shape = np.where(rel >= 0, np.exp(-np.maximum(rel, 0) / width),
                         np.exp(np.minimum(rel, 0) / (width * 0.15)))
        level = level + height * shape * (True if is_end else above_floor)

    # Noise grows as the signal approaches the floor.
    sigma = 0.006 + 0.9 * np.exp(-(level - NOISE_FLOOR_DB) / 2.2)
    noisy = level + rng.normal(0.0, 1.0, x.size) * sigma
    return x, np.maximum(noisy, NOISE_FLOOR_DB - 2.0)
