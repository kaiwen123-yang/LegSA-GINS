"""No-feedback FGO foundation modules.

中文说明：N8A FGO 只做离线诊断 smoother，不反馈 EKF，不替换 EKF NAV。
"""

from legsa_gins.fgo.fgo_backend_discovery import discover_fgo_backend
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry

__all__ = ["discover_fgo_backend", "build_default_factor_registry"]
