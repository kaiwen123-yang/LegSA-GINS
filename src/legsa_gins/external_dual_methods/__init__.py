"""Q2R2 external dual-antenna method contracts.

This package is intentionally separate from the LegSA main algorithm.  It
contains method contracts, frame adapters, and preflight helpers for targeted
external dual-antenna reproduction work.
"""

from .method_contracts import METHOD_CATALOG, MethodContract, ReproductionType

__all__ = ["METHOD_CATALOG", "MethodContract", "ReproductionType"]
