"""Default engineering values.

Every figure here can be overridden from the Settings screen; the stored
overrides are merged on top of these defaults with :meth:`Defaults.from_dict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

WAVELENGTHS_NM: tuple[int, ...] = (1310, 1490, 1550, 1625)
OTDR_WAVELENGTHS_NM: tuple[int, ...] = (1310, 1550, 1625)
SPLITTER_RATIOS: tuple[int, ...] = (2, 4, 8, 16, 32, 64)
FIBER_TYPES: tuple[str, ...] = ("G.652.D", "G.657.A1")


def _attenuation() -> dict[int, float]:
    return {1310: 0.35, 1490: 0.24, 1550: 0.22, 1625: 0.25}


def _splitter_loss() -> dict[int, float]:
    return {2: 3.7, 4: 7.3, 8: 10.5, 16: 13.7, 32: 17.1, 64: 20.5}


@dataclass
class Defaults:
    # Loss model
    attenuation_db_km: dict[int, float] = field(default_factory=_attenuation)
    splice_loss_db: float = 0.10
    connector_loss_db: float = 0.50
    splitter_loss_db: dict[int, float] = field(default_factory=_splitter_loss)
    # Budget verdicts: a remaining margin below this warns, below zero fails
    safety_margin_db: float = 3.0
    # GPON optical budget classes (ITU-T G.984.2)
    gpon_b_plus_db: float = 28.0
    gpon_c_plus_db: float = 32.0
    # OTDR event thresholds
    splice_warn_db: float = 0.30
    splice_fail_db: float = 0.50
    connector_warn_db: float = 0.50
    connector_fail_db: float = 0.75
    bend_fail_db: float = 0.50
    splitter_tolerance_db: float = 1.0
    reflectance_warn_db: float = -45.0
    reflectance_fail_db: float = -35.0
    section_tolerance_db_km: float = 0.10
    # Expected-vs-measured comparison
    compare_warn_db: float = 0.5
    compare_fail_db: float = 1.5

    def attenuation(self, wavelength_nm: int) -> float:
        try:
            return self.attenuation_db_km[int(wavelength_nm)]
        except KeyError:
            raise ValueError(f"No attenuation defined for {wavelength_nm} nm") from None

    def splitter(self, ratio: int) -> float:
        try:
            return self.splitter_loss_db[int(ratio)]
        except KeyError:
            raise ValueError(f"Unsupported splitter ratio 1:{ratio}") from None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # JSON object keys must be strings.
        data["attenuation_db_km"] = {str(k): v for k, v in self.attenuation_db_km.items()}
        data["splitter_loss_db"] = {str(k): v for k, v in self.splitter_loss_db.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Defaults":
        """Build defaults, applying any known keys from ``data``; unknown keys are ignored."""
        result = cls()
        if not data:
            return result
        names = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key not in names:
                continue
            if key in ("attenuation_db_km", "splitter_loss_db"):
                merged = dict(getattr(result, key))
                merged.update({int(k): float(v) for k, v in value.items()})
                setattr(result, key, merged)
            else:
                setattr(result, key, float(value))
        return result
