import pytest

from fiberdesk.core.budget import (BudgetInput, calculate_budget, format_splitters,
                                   parse_splitters)
from fiberdesk.core.defaults import Defaults
from fiberdesk.core.status import Status


def test_loss_items_use_default_table():
    result = calculate_budget(BudgetInput(
        tx_power_dbm=3.0, rx_sensitivity_dbm=-28.0, length_km=10.0, wavelength_nm=1310,
        splices=4, connectors=2, splitters=(32,)))
    losses = result.loss_by_key
    assert losses["fiber"] == pytest.approx(3.5)
    assert losses["splices"] == pytest.approx(0.4)
    assert losses["connectors"] == pytest.approx(1.0)
    assert losses["splitters"] == pytest.approx(17.1)
    assert result.total_loss_db == pytest.approx(22.0)
    assert result.available_db == pytest.approx(31.0)
    # 31 - 22 - 3 (safety) = 6 dB left → PASS
    assert result.remaining_db == pytest.approx(6.0)
    assert result.status is Status.PASS


@pytest.mark.parametrize("wavelength, expected", [(1310, 0.35), (1550, 0.22), (1625, 0.25)])
def test_fiber_attenuation_per_wavelength(wavelength, expected):
    result = calculate_budget(BudgetInput(0, -30, 1.0, wavelength, splices=0, connectors=0))
    assert result.loss_by_key["fiber"] == pytest.approx(expected)


@pytest.mark.parametrize("rx, status", [
    (-13.0, Status.FAIL),  # 13 - 10.5 - 3 = -0.5
    (-15.0, Status.WARN),  # 1.5
    (-17.0, Status.PASS),  # 3.5
])
def test_status_bands(rx, status):
    # Loss is exactly 10.5 dB (one 1:8 splitter), safety 3 dB.
    inp = BudgetInput(0.0, rx, 0.0, 1310, splices=0, connectors=0, splitters=(8,))
    result = calculate_budget(inp)
    assert result.total_loss_db == pytest.approx(10.5)
    assert result.status is status


def test_warn_band_edges():
    base = dict(length_km=0.0, wavelength_nm=1310, splices=0, connectors=0)
    # remaining exactly 0 → WARN, exactly 3 → PASS
    assert calculate_budget(BudgetInput(0.0, -3.0, **base)).status is Status.WARN
    assert calculate_budget(BudgetInput(0.0, -6.0, **base)).status is Status.PASS
    assert calculate_budget(BudgetInput(0.0, -2.99, **base)).status is Status.FAIL


def test_explicit_safety_margin_and_custom_defaults():
    defaults = Defaults.from_dict({"connector_loss_db": 0.3, "attenuation_db_km": {"1550": 0.2}})
    result = calculate_budget(
        BudgetInput(0.0, -10.0, 5.0, 1550, splices=0, connectors=2, safety_margin_db=0.0),
        defaults)
    assert result.total_loss_db == pytest.approx(1.6)
    assert result.remaining_db == pytest.approx(8.4)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        BudgetInput(0, -20, -1.0, 1310)
    with pytest.raises(ValueError):
        BudgetInput(0, -20, 1.0, 1310, splices=-1)
    with pytest.raises(ValueError):
        calculate_budget(BudgetInput(0, -20, 1.0, 1300))
    with pytest.raises(ValueError):
        calculate_budget(BudgetInput(0, -20, 1.0, 1310, splitters=(3,)))


@pytest.mark.parametrize("text, ratios", [
    ("", []), ("  ", []), (None, []), ("1:32", [32]), ("1:4 + 1:8", [4, 8]), ("1x2+1/16", [2, 16]),
])
def test_parse_splitters(text, ratios):
    assert parse_splitters(text) == ratios


def test_parse_splitters_rejects_garbage():
    with pytest.raises(ValueError):
        parse_splitters("32")


def test_format_round_trip():
    assert format_splitters(parse_splitters("1:4+1:8")) == "1:4 + 1:8"
