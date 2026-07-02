"""Runnable Liu constrained wrapped-WLS yaw implementation contract."""
from .method_contracts import METHOD_CATALOG
CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA02_LIU_CONSTRAINED_WRAPPED_WLS")
