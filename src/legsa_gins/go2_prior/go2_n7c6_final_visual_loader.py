"""Load N7C6 runtime outputs for the N7C6A final review.

中文说明：本模块只读取 N7C6 runtime evidence，生成输入清单；不改 solver，
不调权重，也不把 Go2 或 final_v23 当作 solver truth。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_N7C6_REPORTS = [
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_VARIANT_SUMMARIES.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_COMPARISON_REPORT.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json",
    "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json",
]

OPTIONAL_N7C6_REPORTS = [
    "N7C6_FIGURE_MANIFEST.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_JACOBIAN_REPORT.json",
]


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json(path: str | Path, data: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _variant_dirs(root: Path) -> list[Path]:
    variants = root / "variants"
    if not variants.exists():
        return []
    return sorted(path for path in variants.iterdir() if path.is_dir())


def build_n7c6a_visual_input_manifest(n7c6_root: str | Path) -> dict[str, Any]:
    root = Path(n7c6_root)
    found_reports = {name: (root / name).exists() for name in REQUIRED_N7C6_REPORTS}
    optional_reports = {name: (root / name).exists() for name in OPTIONAL_N7C6_REPORTS}
    variants = _variant_dirs(root)
    clean_series = [path.name for path in variants if (path / "EVAL_NAV.csv").exists()]
    stress_series = [
        path.name
        for path in variants
        if "stress" in path.name and ((path / "EVAL_NAV.csv").exists() or (path / "RUN_MANIFEST.json").exists())
    ]
    figure_manifest = read_json(root / "N7C6_FIGURE_MANIFEST.json")
    figures = figure_manifest.get("generated_figures", [])
    if not isinstance(figures, list):
        figures = []
    return {
        "stage": "N7C6A_go2_proprioceptive_joint_final_review",
        "n7c6_root_role_alias": "N7C6_REPORT_OUTPUT_DIR",
        "n7c6_reports_found": found_reports,
        "n7c6_reports_all_found": all(found_reports.values()),
        "n7c6_optional_reports_found": optional_reports,
        "n7c6_figures_found": bool(figures) or bool(figure_manifest.get("required_figures_generated", False)),
        "n7c6_figure_count": int(figure_manifest.get("figure_count_total", len(figures)) or 0),
        "clean_timeseries_found": bool(clean_series),
        "clean_timeseries_variants": clean_series,
        "stress_timeseries_found": bool(stress_series),
        "stress_timeseries_variants": stress_series,
        "nis_report_found": found_reports["N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json"],
        "decision_report_found": found_reports["N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json"],
        "variant_count": len(variants),
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "fgo": False,
    }


def write_n7c6a_visual_input_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    return write_json(path, manifest)
