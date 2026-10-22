import pytest

from fiberdesk.core.defaults import Defaults
from fiberdesk.core.pon import PonInput, calculate_pon
from fiberdesk.core.status import Status


def test_cascade_1x4_1x8():
    result = calculate_pon(PonInput(olt_power_dbm=3.0, stages=(4, 8), length_km=5.0,
                                    wavelength_nm=1490, connectors=2, splices=2))
    assert result.split_ratio == 32
    assert result.splitter_loss_db == pytest.approx(7.3 + 10.5)
    # 17.8 splitters + 5 × 0.24 fibre + 2 × 0.5 connectors + 2 × 0.1 splices
    assert result.total_loss_db == pytest.approx(17.8 + 1.2 + 1.0 + 0.2)
    assert result.onu_power_dbm == pytest.approx(3.0 - 20.2)
    b_plus, c_plus = result.classes
    assert (b_plus.name, b_plus.budget_db) == ("B+", 28.0)
    assert b_plus.remaining_db == pytest.approx(7.8)
    assert b_plus.status is Status.PASS
    assert c_plus.remaining_db == pytest.approx(11.8)


def test_steps_accumulate_to_onu_power():
    result = calculate_pon(PonInput(5.0, (2, 16), 3.0, 1310, connectors=4))
    assert result.steps[0].label == "OLT"
    assert result.steps[-1].power_dbm == pytest.approx(result.onu_power_dbm)
    assert sum(s.loss_db for s in result.steps) == pytest.approx(result.total_loss_db)
    labels = [s.label for s in result.steps]
    assert labels.index("1:2") < labels.index("1:16") < labels.index("fiber")


def test_class_verdicts_differ_on_large_split():
    # 1:64 (20.5) + 1:2 (3.7) + 20 km × 0.24 = 29.0 dB plus 1 dB connectors = 30.0 dB
    result = calculate_pon(PonInput(3.0, (64, 2), 20.0, 1490, connectors=2))
    b_plus, c_plus = result.classes
    assert result.total_loss_db == pytest.approx(30.0)
    assert b_plus.status is Status.FAIL
    assert c_plus.status is Status.WARN  # 2 dB left, inside the 3 dB warn band


def test_no_stages_and_custom_budget():
    defaults = Defaults.from_dict({"gpon_b_plus_db": 10.0})
    result = calculate_pon(PonInput(0.0, (), 10.0, 1310, connectors=0), defaults)
    assert result.split_ratio == 1
    assert result.total_loss_db == pytest.approx(3.5)
    assert result.classes[0].remaining_db == pytest.approx(6.5)


def test_rejects_unknown_ratio_and_negative_length():
    with pytest.raises(ValueError):
        calculate_pon(PonInput(3.0, (3,), 1.0))
    with pytest.raises(ValueError):
        calculate_pon(PonInput(3.0, (4,), -1.0))
