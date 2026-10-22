"""OTDR device profiles.

Demo profiles modelled on the EXFO MaxTester series. Values are illustrative,
not manufacturer specifications.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    key: str
    model: str
    category: str
    dynamic_range_db: dict[int, float]  # wavelength nm → dB
    usage: str

    @property
    def wavelengths(self) -> tuple[int, ...]:
        return tuple(sorted(self.dynamic_range_db))


PROFILES: dict[str, DeviceProfile] = {
    p.key: p
    for p in (
        DeviceProfile(
            "maxtester-730d",
            "EXFO MaxTester 730D (SM3)",
            "PON / metro OTDR",
            {1310: 39.0, 1550: 38.0, 1625: 39.0},
            "Backbone, metro and splitter-based PON",
        ),
        DeviceProfile(
            "maxtester-730c",
            "EXFO MaxTester 730C",
            "PON / metro OTDR (previous generation)",
            {1310: 36.0, 1550: 35.0},
            "Legacy inventory unit",
        ),
        DeviceProfile(
            "maxtester-715d",
            "EXFO MaxTester 715D (SM1)",
            "Last-mile OTDR",
            {1310: 32.0, 1550: 30.0},
            "Subscriber drops and short links",
        ),
    )
}


def get_profile(key: str) -> DeviceProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError(f"Unknown device profile: {key}") from None
