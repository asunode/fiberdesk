"""Optical link budget."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .defaults import Defaults
from .status import Status, grade_margin

_RATIO_RE = re.compile(r"^\s*1\s*[:x/]\s*(\d+)\s*$")


def parse_splitters(text: str | None) -> list[int]:
    """Parse a cascade such as ``"1:4 + 1:8"`` into ``[4, 8]``; blank means none."""
    if not text or not text.strip():
        return []
    ratios: list[int] = []
    for part in text.split("+"):
        match = _RATIO_RE.match(part)
        if not match:
            raise ValueError(f"Invalid splitter ratio: {part.strip()!r}")
        ratios.append(int(match.group(1)))
    return ratios


def format_splitters(ratios: list[int]) -> str:
    return " + ".join(f"1:{r}" for r in ratios)


@dataclass(frozen=True)
class BudgetInput:
    tx_power_dbm: float
    rx_sensitivity_dbm: float
    length_km: float
    wavelength_nm: int
    splices: int = 0
    connectors: int = 2
    splitters: tuple[int, ...] = ()
    safety_margin_db: float | None = None  # required headroom; None → Defaults.safety_margin_db

    def __post_init__(self) -> None:
        if self.length_km < 0:
            raise ValueError("Length cannot be negative")
        if self.splices < 0 or self.connectors < 0:
            raise ValueError("Splice and connector counts cannot be negative")


@dataclass(frozen=True)
class LossItem:
    key: str  # "fiber", "splices", "connectors", "splitters"
    loss_db: float
    detail: str


@dataclass(frozen=True)
class BudgetResult:
    items: tuple[LossItem, ...]
    available_db: float
    total_loss_db: float
    safety_margin_db: float
    remaining_db: float
    status: Status
    loss_by_key: dict[str, float] = field(default_factory=dict)


def passive_losses(
    length_km: float,
    wavelength_nm: int,
    splices: int,
    connectors: int,
    splitters: tuple[int, ...] | list[int],
    defaults: Defaults,
) -> tuple[LossItem, ...]:
    """Loss contributions of the passive path, in a fixed order."""
    att = defaults.attenuation(wavelength_nm)
    split_total = sum(defaults.splitter(r) for r in splitters)
    return (
        LossItem("fiber", length_km * att, f"{length_km:.2f} km × {att:.2f} dB/km"),
        LossItem("splices", splices * defaults.splice_loss_db,
                 f"{splices} × {defaults.splice_loss_db:.2f} dB"),
        LossItem("connectors", connectors * defaults.connector_loss_db,
                 f"{connectors} × {defaults.connector_loss_db:.2f} dB"),
        LossItem("splitters", split_total,
                 format_splitters(list(splitters)) if splitters else "—"),
    )


def calculate_budget(inp: BudgetInput, defaults: Defaults | None = None) -> BudgetResult:
    defaults = defaults or Defaults()
    items = passive_losses(inp.length_km, inp.wavelength_nm, inp.splices,
                           inp.connectors, inp.splitters, defaults)
    total = sum(i.loss_db for i in items)
    available = inp.tx_power_dbm - inp.rx_sensitivity_dbm
    safety = defaults.safety_margin_db if inp.safety_margin_db is None else inp.safety_margin_db
    remaining = available - total
    return BudgetResult(
        items=items,
        available_db=available,
        total_loss_db=total,
        safety_margin_db=safety,
        remaining_db=remaining,
        status=grade_margin(remaining, safety),
        loss_by_key={i.key: i.loss_db for i in items},
    )
