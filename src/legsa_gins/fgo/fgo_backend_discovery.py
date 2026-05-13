"""Backend discovery for N8A no-feedback FGO."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


BACKEND_ORDER = ["gtsam", "ceres", "scipy", "numpy"]


def _available(module: str) -> bool:
    if module == "ceres":
        return importlib.util.find_spec("ceres") is not None or importlib.util.find_spec("pyceres") is not None
    return importlib.util.find_spec(module) is not None


def discover_fgo_backend() -> dict[str, Any]:
    """中文说明：优先发现专业 FGO 后端；没有时使用 numpy/scipy fallback。"""
    availability = {name: _available(name) for name in BACKEND_ORDER}
    selected = next((name for name in BACKEND_ORDER if availability[name]), "python_fallback")
    return {
        "stage": "N8A_no_feedback_fgo_foundation",
        "backend_order": BACKEND_ORDER,
        "backend_available": availability,
        "selected_backend": selected,
        "fallback_runs_without_advanced_backend": selected in {"numpy", "scipy", "python_fallback"},
        "no_feedback": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_backend_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
