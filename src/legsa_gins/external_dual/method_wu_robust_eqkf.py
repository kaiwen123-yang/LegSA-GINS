"""Runnable Wu-style robust dual-antenna EQKF yaw contract."""
from .method_contracts import METHOD_CATALOG
CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA04_WU_ROBUST_EQKF_GO2")
