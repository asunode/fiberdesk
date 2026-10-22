import numpy as np
import pytest

from fiberdesk.core.defaults import Defaults
from fiberdesk.core.otdr import (Event, EventKind, compare_expected, evaluate_event,
                                 evaluate_measurement, link_breakdown, link_length, link_loss,
                                 synthesize_trace)
from fiberdesk.core.status import Status

D = Defaults()


def make_events(splice_loss=0.05, conn_loss=0.3, conn_refl=-52.0):
    return [
        Event(1, 0.0, EventKind.CONNECTOR, 0.25, -55.0),
        Event(2, 2.0, EventKind.SPLICE, splice_loss, None, 0.35),
        Event(3, 4.0, EventKind.CONNECTOR, conn_loss, conn_refl, 0.35),
        Event(4, 6.0, EventKind.CONNECTOR, 0.30, -54.0, 0.35),
        Event(5, 6.15, EventKind.END, None, -14.5, 0.35),
    ]


@pytest.mark.parametrize("loss, status", [(0.05, Status.PASS), (0.31, Status.WARN),
                                          (0.6, Status.FAIL)])
def test_splice_thresholds(loss, status):
    assert evaluate_event(Event(1, 1.0, EventKind.SPLICE, loss), 1310, D) is status


@pytest.mark.parametrize("loss, refl, status", [
    (0.3, -55.0, Status.PASS),
    (0.6, -55.0, Status.WARN),
    (0.8, -55.0, Status.FAIL),  # connector > 0.75 dB fails
    (0.3, -40.0, Status.WARN),  # reflectance above -45 dB
    (0.3, -30.0, Status.FAIL),  # reflectance above -35 dB
])
def test_connector_thresholds(loss, refl, status):
    assert evaluate_event(Event(1, 1.0, EventKind.CONNECTOR, loss, refl), 1310, D) is status


def test_bend_always_flags():
    assert evaluate_event(Event(1, 1.0, EventKind.BEND, 0.1), 1550, D) is Status.WARN
    assert evaluate_event(Event(1, 1.0, EventKind.BEND, 0.9), 1550, D) is Status.FAIL


def test_splitter_tolerance():
    ok = Event(1, 1.0, EventKind.SPLITTER, 10.9, splitter_ratio=8)
    warn = Event(1, 1.0, EventKind.SPLITTER, 11.8, splitter_ratio=8)
    fail = Event(1, 1.0, EventKind.SPLITTER, 12.8, splitter_ratio=8)
    assert [evaluate_event(e, 1310, D) for e in (ok, warn, fail)] == [
        Status.PASS, Status.WARN, Status.FAIL]


def test_high_section_attenuation_warns():
    event = Event(2, 3.0, EventKind.SPLICE, 0.05, None, section_db_km=0.35)
    assert evaluate_event(event, 1310, D) is Status.PASS
    assert evaluate_event(event, 1550, D) is Status.WARN  # 0.35 > 0.22 + 0.10


def test_measurement_status_is_worst_event():
    assert evaluate_measurement(make_events(), 1310, D) is Status.PASS
    assert evaluate_measurement(make_events(splice_loss=0.4), 1310, D) is Status.WARN
    assert evaluate_measurement(make_events(conn_loss=1.0), 1310, D) is Status.FAIL


def test_link_totals_exclude_receive_fiber():
    events = make_events()
    breakdown = link_breakdown(events)
    assert breakdown["fiber"] == pytest.approx(6.0 * 0.35)
    assert breakdown["connectors"] == pytest.approx(0.85)
    assert breakdown["splices"] == pytest.approx(0.05)
    assert link_loss(events) == pytest.approx(2.1 + 0.85 + 0.05)
    assert link_length(events) == pytest.approx(6.0)


def test_compare_expected():
    expected = {"fiber": 2.1, "splices": 0.1, "connectors": 1.5, "splitters": 0.0}
    measured = link_breakdown(make_events())
    cmp = compare_expected(expected, measured, D)
    assert cmp.expected_total_db == pytest.approx(3.7)
    assert cmp.delta_db == pytest.approx(3.0 - 3.7)
    assert cmp.status is Status.PASS
    worse = compare_expected(expected, {**measured, "bends": 2.5}, D)
    assert worse.status is Status.FAIL
    assert [r.key for r in cmp.rows] == ["fiber", "splices", "connectors", "splitters", "bends"]


def test_trace_is_deterministic_and_follows_events():
    events = make_events()
    x1, y1 = synthesize_trace(events, 1310, 39.0, seed=7)
    x2, y2 = synthesize_trace(events, 1310, 39.0, seed=7)
    _, y3 = synthesize_trace(events, 1310, 39.0, seed=8)
    assert np.array_equal(y1, y2)
    assert not np.array_equal(y1, y3)
    assert x1[0] < 0 < events[-1].distance_km < x1[-1]

    def level_at(km):
        window = (x1 > km - 0.05) & (x1 < km + 0.05)
        return float(np.median(y1[window]))

    # Between 1 and 3 km the trace drops by 2 km of fibre plus the 0.05 dB splice.
    drop = level_at(1.0) - level_at(3.0)
    assert drop == pytest.approx(2 * 0.35 + 0.05, abs=0.08)
    # After the end the level sits near the noise floor.
    assert level_at(6.7) < 3.0
    # A reflective connector produces a peak above the surrounding fibre.
    peak = y1[(x1 > 3.99) & (x1 < 4.05)].max()
    assert peak > level_at(3.8) + 3.0


def test_trace_needs_events():
    with pytest.raises(ValueError):
        synthesize_trace([], 1310, 30.0, seed=1)
