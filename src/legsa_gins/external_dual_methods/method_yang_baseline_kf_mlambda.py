"""Yang baseline KF/MLAMBDA contract module for Q2R2."""

from .method_contracts import METHOD_CATALOG

CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA03_YANG_BASELINE_KF_MLAMBDA")
