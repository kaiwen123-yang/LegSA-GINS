"""Manifest writer for the N4H2E dual replay visual bundle.

中文说明：manifest 只记录图像包证据与边界布尔值，不承载 solver 输出修改或
formal performance claim。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLOT_FOLDERS = [
    "01_trajectory",
    "02_position_errors",
    "03_velocity",
    "04_attitude",
    "05_consistency",
    "06_observation_quality",
    "08_summary_panels",
    "09_case_review",
]


def count_figures_by_folder(output_dir: str | Path) -> dict[str, int]:
    root = Path(output_dir)
    counts: dict[str, int] = {}
    for folder in PLOT_FOLDERS:
        directory = root / folder
        counts[folder] = len(list(directory.glob("*.png"))) if directory.exists() else 0
    return counts


def list_required_figures() -> list[str]:
    return [
        "01_trajectory/dual_replay_traj_truth_est.png",
        "01_trajectory/dual_replay_height_time.png",
        "02_position_errors/dual_replay_pos_horizontal.png",
        "04_attitude/dual_replay_yaw_error_deg.png",
        "08_summary_panels/dual_replay_summary_panel.png",
        "09_case_review/visual_case_review.md",
        "09_case_review/visual_case_review.json",
    ]


def build_figure_manifest(
    output_dir: str | Path,
    *,
    metrics_snapshot: dict[str, Any],
    gates_snapshot: dict[str, Any],
    visual_sanity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    required = list_required_figures()
    missing = [figure for figure in required if not (root / figure).exists()]
    counts = count_figures_by_folder(root)
    return {
        "phase": "N4H2E",
        "plot_bundle_role": "dual_final_v23_only_visual_validation",
        "algorithm_role": "baseline_replay_diagnostic",
        "source_artifacts_role_aliases": [
            "DUAL_FINAL_V23_ARTIFACT_ROOT",
            "N4H2_ARTIFACTS_ROOT",
            "N4H2D_FRESH_EVALUATION_OUTPUT",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "figure_counts_by_folder": counts,
        "figure_count_total": sum(counts.values()),
        "required_figures": required,
        "missing_figures": missing,
        "required_figures_generated": not missing,
        "metrics_snapshot": metrics_snapshot,
        "gates_snapshot": gates_snapshot,
        "visual_sanity": visual_sanity or {},
        "old_summary_invalidated": True,
        "solver_output_changed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "manual_visual_review_required": True,
    }


def write_figure_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
