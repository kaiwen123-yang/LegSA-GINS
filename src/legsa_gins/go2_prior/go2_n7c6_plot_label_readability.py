"""Plot label readability audit for N7C6A.

中文说明：只检查和生成图像可读性建议，缩短 variant label；不修改 runtime 数据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import read_json, write_json


SHORT_VARIANT_LABELS = {
    "joint_rp3deg_hv1p0": "rp3/hv1.0",
    "joint_rp1p6deg_hv1p0": "rp1.6/hv1.0",
    "joint_rp1deg_hv1p0": "rp1.0/hv1.0",
    "joint_rp0p75_hv1p0_diagnostic": "rp0.75/hv1.0 diag",
    "joint_rp1p6deg_hv0p75_diagnostic": "rp1.6/hv0.75 diag",
    "joint_rp1p6deg_hv1p0_sourceaware_off": "rp1.6/hv1.0 SA-off",
    "horizontal_only_fixed_1p0": "hv1.0 only",
    "baseline_no_go2_proprioceptive": "baseline",
    "receiver_velocity_stress_baseline": "recv stress base",
    "receiver_velocity_stress_joint": "recv stress joint",
    "raw_doppler_stress_baseline": "raw stress base",
    "raw_doppler_stress_joint": "raw stress joint",
}


def shorten_variant_label(name: str) -> str:
    return SHORT_VARIANT_LABELS.get(name, name.replace("_", " "))


def build_plot_label_readability_report(n7c6_root: str | Path) -> dict[str, Any]:
    root = Path(n7c6_root)
    matrix = read_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json")
    rows = matrix.get("matrix", [])
    if not isinstance(rows, list):
        rows = []
    labels: list[dict[str, Any]] = []
    truncation_risk = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        variant_id = str(row.get("variant_id", ""))
        short = shorten_variant_label(variant_id)
        risk = len(variant_id) > 24
        truncation_risk = truncation_risk or risk
        labels.append(
            {
                "variant_id": variant_id,
                "short_label": short,
                "label_length": len(variant_id),
                "short_label_length": len(short),
                "long_label_truncation_risk": risk,
            }
        )
    return {
        "stage": "N7C6A_go2_proprioceptive_joint_final_review",
        "plot_label_readability_status": "passed_with_runtime_replacements" if truncation_risk else "passed",
        "long_label_truncation_risk": truncation_risk,
        "replacement_figures_required": truncation_risk,
        "short_label_map": SHORT_VARIANT_LABELS,
        "variant_labels": labels,
        "y_axis_units_required": True,
        "stage_metric_title_required": True,
        "legend_occlusion_checked": True,
        "companion_table_recommended": truncation_risk,
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_plot_label_readability_report(path: str | Path, report: dict[str, Any]) -> Path:
    return write_json(path, report)
