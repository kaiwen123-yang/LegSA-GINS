"""Teunissen affine MILS fallback contract module for Q2R2."""

from .method_contracts import METHOD_CATALOG

CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA05_TEUNISSEN_AFFINE_MILS")
