"""TIA-598 fiber and buffer-tube colour code."""

from __future__ import annotations

from dataclasses import dataclass

# (name, hex) in TIA-598 order.
TIA598_COLORS: tuple[tuple[str, str], ...] = (
    ("Blue", "#1f6fd1"),
    ("Orange", "#f28c28"),
    ("Green", "#2e9e4f"),
    ("Brown", "#8b5a2b"),
    ("Slate", "#7d8b99"),
    ("White", "#f4f4f4"),
    ("Red", "#d7322f"),
    ("Black", "#1a1a1a"),
    ("Yellow", "#f2d42b"),
    ("Violet", "#8a4fc9"),
    ("Rose", "#f19bb5"),
    ("Aqua", "#33c7d1"),
)

CABLE_SIZES: tuple[int, ...] = (12, 24, 48, 96, 144)


@dataclass(frozen=True)
class ColorSpec:
    position: int  # 1-based position within its group
    name: str
    hex: str
    tracer: str | None = None  # stripe colour name for positions 13–24, else None

    @property
    def label(self) -> str:
        return f"{self.name} / {self.tracer} tracer" if self.tracer else self.name


@dataclass(frozen=True)
class FiberAddress:
    fiber: int
    tube: ColorSpec
    color: ColorSpec


def color_for_position(position: int) -> ColorSpec:
    """Colour of a 1-based position. 13–24 repeat the sequence with a black tracer
    (black itself gets a yellow tracer); beyond 24 the double cycle repeats."""
    if position < 1:
        raise ValueError("Position must be 1 or greater")
    index = (position - 1) % 24
    name, hex_ = TIA598_COLORS[index % 12]
    tracer = None
    if index >= 12:
        tracer = "Yellow" if name == "Black" else "Black"
    return ColorSpec(position, name, hex_, tracer)


def tracer_hex(spec: ColorSpec) -> str | None:
    if spec.tracer is None:
        return None
    return dict(TIA598_COLORS)[spec.tracer]


def locate_fiber(fiber: int, cable_size: int, fibers_per_tube: int = 12) -> FiberAddress:
    if fibers_per_tube < 1:
        raise ValueError("Fibers per tube must be positive")
    if not 1 <= fiber <= cable_size:
        raise ValueError(f"Fiber {fiber} is outside a {cable_size}-fiber cable")
    tube = (fiber - 1) // fibers_per_tube + 1
    within = (fiber - 1) % fibers_per_tube + 1
    return FiberAddress(fiber, color_for_position(tube), color_for_position(within))


def cable_grid(cable_size: int, fibers_per_tube: int = 12) -> list[list[FiberAddress]]:
    """All fibers of a cable grouped by tube (one inner list per tube)."""
    if cable_size < 1:
        raise ValueError("Cable size must be positive")
    rows: list[list[FiberAddress]] = []
    for n in range(1, cable_size + 1):
        addr = locate_fiber(n, cable_size, fibers_per_tube)
        if addr.color.position == 1:
            rows.append([])
        rows[-1].append(addr)
    return rows
