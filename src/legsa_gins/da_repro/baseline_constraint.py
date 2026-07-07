"""Baseline-length constraints for C-LAMBDA candidate checks."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineConstraint:
    nominal_length_m: float
    tolerance_m: float

    def residual(self, vector_m: tuple[float, float, float]) -> float:
        length = math.sqrt(sum(float(v) * float(v) for v in vector_m))
        return length - self.nominal_length_m

    def passes(self, vector_m: tuple[float, float, float]) -> bool:
        return abs(self.residual(vector_m)) <= self.tolerance_m
