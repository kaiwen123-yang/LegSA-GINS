"""N8G manifest helpers.

中文说明：manifest 检查 feedback update 计数和禁用 output substitution 边界。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .feedback_state_types import manifest_false_flags


def read_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_feedback_manifest(manifest: dict[str, Any]) -> bool:
    required = [
        "fgo_feedback_enabled",
        "fgo_feedback_mode",
        "feedback_update_count",
        "feedback_accept_count",
        "feedback_reject_count",
        "feedback_position_enabled",
        "feedback_velocity_enabled",
        "feedback_attitude_enabled",
        "fgo_feedback_output_substitution",
        "fgo_feedback_direct_nav_override",
        "fgo_feedback_no_future_data",
        "trace_solver_input",
        "final_v23_output_solver_input",
        "paper_performance_claim",
    ]
    return all(key in manifest for key in required) and manifest_false_flags(manifest)


def summarize_variant_manifest(variant_id: str, run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    manifest_path = root / "RUN_MANIFEST.json"
    manifest = read_manifest(manifest_path) if manifest_path.exists() else {}
    return {
        "variant_id": variant_id,
        "run_dir_role": "runtime_variant_dir",
        "manifest_present": bool(manifest),
        "nav_generated": (root / "LegSA_PORT_NAV.nav").exists(),
        "std_generated": (root / "LegSA_PORT_STD.csv").exists(),
        "eval_nav_generated": (root / "EVAL_NAV.csv").exists(),
        "run_manifest_generated": manifest_path.exists(),
        "feedback_update_count": int(manifest.get("feedback_update_count", 0) or 0),
        "feedback_accept_count": int(manifest.get("feedback_accept_count", 0) or 0),
        "feedback_reject_count": int(manifest.get("feedback_reject_count", 0) or 0),
        "fgo_feedback_enabled": bool(manifest.get("fgo_feedback_enabled", False)),
        "no_output_substitution": manifest.get("fgo_feedback_output_substitution") is False,
        "no_direct_nav_override": manifest.get("fgo_feedback_direct_nav_override") is False,
        "no_future_data": manifest.get("fgo_feedback_no_future_data") is not False,
        "trace_solver_input": manifest.get("trace_solver_input", False),
        "final_v23_output_solver_input": manifest.get("final_v23_output_solver_input", False),
        "paper_performance_claim": manifest.get("paper_performance_claim", False),
    }
