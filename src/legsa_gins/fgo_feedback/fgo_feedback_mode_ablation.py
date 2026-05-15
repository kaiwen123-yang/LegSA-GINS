"""N8I feedback mode ablation report.

中文说明：mode 消融对比 baseline、primary、PVA、velocity-only、attitude-only
和 reject-all sanity，保持 FGO feedback 为 EKF update。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle, build_mode_ablation_reports
from .fgo_feedback_visual_loader import write_json


def build_feedback_mode_ablation(bundle: N8IPolicyRunBundle) -> tuple[dict[str, Any], dict[str, Any]]:
    summaries, comparison = build_mode_ablation_reports(bundle)
    summaries["mode_review_status"] = "mode_ablation_reviewed"
    comparison["mode_review_status"] = "mode_ablation_reviewed"
    return summaries, comparison


def write_feedback_mode_ablation_reports(
    output_root: str | Path,
    summaries: dict[str, Any],
    comparison: dict[str, Any],
) -> None:
    root = Path(output_root)
    write_json(root / "N8I_FEEDBACK_MODE_ABLATION_SUMMARIES.json", summaries)
    write_json(root / "N8I_FEEDBACK_MODE_COMPARISON_REPORT.json", comparison)
