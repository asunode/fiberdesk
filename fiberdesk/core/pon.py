"""Cascaded PON splitter budget against GPON B+ / C+ classes."""

from __future__ import annotations

from dataclasses import dataclass

from .defaults import Defaults
from .status import Status, grade_margin


@dataclass(frozen=True)
class PonInput:
    olt_power_dbm: float
    stages: tuple[int, ...]  # splitter ratios in order, e.g. (4, 8)
    length_km: float
    wavelength_nm: int = 1490
    connectors: int = 2
    splices: int = 0


@dataclass(frozen=True)
class PowerStep:
    label: str
    loss_db: float
    power_dbm: float  # power after this element


@dataclass(frozen=True)
class ClassVerdict:
    name: str
    budget_db: float
    remaining_db: float
    status: Status


@dataclass(frozen=True)
class PonResult:
    steps: tuple[PowerStep, ...]
    split_ratio: int
    splitter_loss_db: float
    total_loss_db: float
    onu_power_dbm: float
    classes: tuple[ClassVerdict, ...]


def calculate_pon(inp: PonInput, defaults: Defaults | None = None) -> PonResult:
    defaults = defaults or Defaults()
    if inp.length_km < 0:
        raise ValueError("Length cannot be negative")
    power = inp.olt_power_dbm
    steps: list[PowerStep] = [PowerStep("OLT", 0.0, power)]

    def add(label: str, loss: float) -> None:
        nonlocal power
        power -= loss
        steps.append(PowerStep(label, loss, power))

    # Connector loss is split around the passive path: half at the OLT side, half at the ONU side.
    half_conn = inp.connectors * defaults.connector_loss_db / 2
    if inp.connectors:
        add("connectors_olt", half_conn)
    split_loss = 0.0
    split_ratio = 1
    for ratio in inp.stages:
        loss = defaults.splitter(ratio)
        split_loss += loss
        split_ratio *= ratio
        add(f"1:{ratio}", loss)
    fiber = inp.length_km * defaults.attenuation(inp.wavelength_nm)
    add("fiber", fiber)
    if inp.splices:
        add("splices", inp.splices * defaults.splice_loss_db)
    if inp.connectors:
        add("connectors_onu", half_conn)

    total = inp.olt_power_dbm - power
    classes = tuple(
        ClassVerdict(name, budget, budget - total, grade_margin(budget - total, defaults.warn_band_db))
        for name, budget in (("B+", defaults.gpon_b_plus_db), ("C+", defaults.gpon_c_plus_db))
    )
    return PonResult(
        steps=tuple(steps),
        split_ratio=split_ratio,
        splitter_loss_db=split_loss,
        total_loss_db=total,
        onu_power_dbm=power,
        classes=classes,
    )
