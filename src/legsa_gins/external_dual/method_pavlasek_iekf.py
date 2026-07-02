"""Diagnostic Pavlasek IEKF contract for A1 method selection evidence."""
from .method_contracts import METHOD_CATALOG
CONTRACT = next(method for method in METHOD_CATALOG if method.method_id == "DA06_PAVLASEK_TWO_RECEIVER_IEKF")
