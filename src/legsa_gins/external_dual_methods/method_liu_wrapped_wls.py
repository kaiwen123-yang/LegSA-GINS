"""Liu constrained wrapped-WLS contract module for Q2R2."""

from .method_contracts import METHOD_CATALOG

CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA02_LIU_CONSTRAINED_WRAPPED_WLS")
