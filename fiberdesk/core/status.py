"""PASS / WARN / FAIL verdicts shared by every calculation."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @classmethod
    def worst(cls, statuses: Iterable["Status"]) -> "Status":
        """Return the most severe status; an empty iterable counts as PASS."""
        result = cls.PASS
        for status in statuses:
            if status.rank > result.rank:
                result = status
        return result


_RANK = {Status.PASS: 0, Status.WARN: 1, Status.FAIL: 2}


def grade_margin(margin_db: float, safety_margin_db: float) -> Status:
    """Grade a remaining margin: below zero fails, below the safety margin warns."""
    if margin_db < 0:
        return Status.FAIL
    if margin_db < safety_margin_db:
        return Status.WARN
    return Status.PASS


def grade_above(value: float, warn_above: float, fail_above: float) -> Status:
    """Grade a value where larger is worse (losses, reflectance)."""
    if value > fail_above:
        return Status.FAIL
    if value > warn_above:
        return Status.WARN
    return Status.PASS
