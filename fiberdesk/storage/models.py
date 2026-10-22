"""Plain records loaded from and saved to the database."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.budget import BudgetInput, parse_splitters
from ..core.devices import DeviceProfile, get_profile
from ..core.status import Status


@dataclass
class Project:
    id: int | None
    name: str
    kind: str = ""
    region: str = ""
    description: str = ""


@dataclass
class Line:
    id: int | None
    project_id: int
    name: str
    a_end: str = ""
    b_end: str = ""
    length_km: float = 1.0
    fiber_type: str = "G.652.D"
    connectors: int = 2
    splices: int = 0
    splitters: str = ""
    wavelength_nm: int = 1310
    tx_power_dbm: float = 0.0
    rx_sensitivity_dbm: float = -20.0
    notes: str = ""
    budget_status: Status | None = None
    budget_remaining_db: float | None = None
    budget_saved_at: str | None = None

    @property
    def splitter_ratios(self) -> tuple[int, ...]:
        return tuple(parse_splitters(self.splitters))

    def budget_input(self, wavelength_nm: int | None = None) -> BudgetInput:
        return BudgetInput(
            tx_power_dbm=self.tx_power_dbm,
            rx_sensitivity_dbm=self.rx_sensitivity_dbm,
            length_km=self.length_km,
            wavelength_nm=wavelength_nm or self.wavelength_nm,
            splices=self.splices,
            connectors=self.connectors,
            splitters=self.splitter_ratios,
        )


@dataclass
class Device:
    id: int | None
    profile_key: str
    serial: str
    calibration_date: str
    team: str

    @property
    def profile(self) -> DeviceProfile:
        return get_profile(self.profile_key)


@dataclass
class Measurement:
    id: int | None
    line_id: int
    device_id: int
    wavelength_nm: int
    measured_at: str  # ISO date-time
    operator: str
    pulse_ns: int
    range_km: float
    trace_seed: int
    notes: str = ""
