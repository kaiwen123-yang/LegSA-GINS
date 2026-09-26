"""BY2 canonical 541-case controlled-degradation experiment.

This package deliberately contains only clean-rebuild code.  It does not import
legacy runners and never treats controlled perturbations as real scenarios.
"""

from .matrix_spec import (
    CLEAN_CASE_ID,
    CASE_COUNT,
    DEGRADED_CASE_COUNT,
    DEGRADATION_TYPE_COUNT,
    SEED_COUNT,
)

__all__ = [
    "CLEAN_CASE_ID",
    "CASE_COUNT",
    "DEGRADED_CASE_COUNT",
    "DEGRADATION_TYPE_COUNT",
    "SEED_COUNT",
]
