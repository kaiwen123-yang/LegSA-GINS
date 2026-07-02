"""Runnable Yang-style baseline-length constrained KF yaw contract."""
from .method_contracts import METHOD_CATALOG
CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA03_YANG_BASELINE_KF_STATUS")
