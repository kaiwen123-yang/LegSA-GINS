"""Wu robust dual-antenna EQKF contract module for Q2R2."""

from .method_contracts import METHOD_CATALOG

CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA04_WU_ROBUST_DA_EQKF")
