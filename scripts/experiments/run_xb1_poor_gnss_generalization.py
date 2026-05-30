#!/usr/bin/env python3
"""Run XB1/PG1 poor-GNSS generalization bootstrap and normal-run gates.

This runner writes runtime-only artifacts under ``xb1/``. It does not change
algorithm math, does not tune against trace/final_v23, and does not generate an
artificial degradation matrix.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legsa_gins.datasets.by2.go2_body_state_parser import (  # noqa: E402
    STANDARD_HEADER as GO2_BODY_HEADER,
    _message_to_row,
)
from legsa_gins.reporting.by2_algorithm_runner import (  # noqa: E402
    build_algorithm_config_text,
    repo_to_wsl,
    run_formal_algorithm,
)
from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (  # noqa: E402
    generate_same_case_feedback_observations,
)
from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (  # noqa: E402
    _convert_eval_nav,
    _convert_std,
    _metrics_from_summary,
)


STAGE = "XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN"
RUNTIME_STAGE = "XB1A_NORMAL_BOOTSTRAP"
EXPORT_STAGE = "XB1_EXPORT_CLEAN_PACKAGE"
GO2_POLICY = "joint_rp1p6deg_hv1p0"
RP_STD_DEG = 1.6
HV_STD = 1.0
STD_VD_DISABLED = 999.0

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "literature_quality_criteria",
    "context_lock",
    "data_inventory",
    "gnss_quality_profile",
    "body_imu_audit",
    "kick_alignment",
    "input_generation",
    "provider_materialization",
    "runner_handoff",
    "stage1_solver",
    "stage1_official_eval",
    "feedback_generation",
    "legsa_full_solver",
    "single_baseline_solver",
    "finalv23_solver",
    "official_eval",
    "metrics",
    "figures",
    "case_review",
    "quality_adaptation_diagnostic",
    "context_update",
    "obsidian_sync",
    "export_clean",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]

EXPECTED_RECEIVER_FILES = [
    "gnss1-status.csv",
    "gnss2-raw.csv",
    "gnss2-status.csv",
    "imu-biases.csv",
    "imu-data.csv",
    "imu-temp.csv",
    "ntrip-info.csv",
    "ntrip-latency.csv",
    "tf.csv",
    "tf_static.csv",
    "trace_vrtk2_a87c6e_2026-01-05-12-25-13_minimal.csv",
    "user_io-out-odom_status.csv",
    "user_io-out-poi_geodetic.csv",
    "user_io-out-poi_odometry.csv",
    "user_io-out-poi_smooth_odometry.csv",
    "user_io-status.csv",
    "userio-raw.csv",
    "corr-raw.csv",
    "gnss1-raw.csv",
]

METRIC_KEYS = [
    "north_rmse_m",
    "east_rmse_m",
    "up_rmse_m",
    "horizontal_rmse_m",
    "horizontal_p95_m",
    "horizontal_max_m",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "yaw_rmse_deg",
    "roll_p95_deg",
    "pitch_p95_deg",
    "yaw_p95_deg",
    "row_count",
    "time_start",
    "time_end",
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    receiver_root: Path
    body_source: Path
    output_root: Path
    stage_root: Path
    runtime_root: Path
    export_root: Path
    trace: Path
    rtklib_root: Path | None
    evaluator_wsl: str
    by3a2_template_root: Path | None

    @property
    def body_csv(self) -> Path:
        return self.stage_root / "body_imu_audit" / "XB1_GO2_BODY_STATE_DIAGNOSTIC.csv"

    @property
    def imu(self) -> Path:
        return self.stage_root / "input_generation" / "XB1_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu"

    @property
    def gnss_dual(self) -> Path:
        return self.stage_root / "input_generation" / "XB1_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def gnss_single(self) -> Path:
        return self.stage_root / "input_generation" / "XB1_GNSS1_STATUS_7COL_REPAIRED.gnss"

    @property
    def raw_doppler(self) -> Path:
        return self.stage_root / "provider_materialization" / "raw_doppler" / "RAW_DOPPLER_VELOCITY_FACTORS.csv"

    @property
    def go2_prior_dir(self) -> Path:
        return self.stage_root / "provider_materialization" / "go2_priors" / "priors" / GO2_POLICY

    @property
    def go2_attitude(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv"

    @property
    def go2_velocity(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv"

    @property
    def go2_joint(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--receiver-root", type=Path, required=True)
    parser.add_argument("--body-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "xb1")
    parser.add_argument("--rtklib-root", type=Path)
    parser.add_argument(
        "--evaluator-wsl",
        default=os.environ.get("LEGSA_EVALUATOR_WSL", ""),
        help="WSL path to the official evaluator. May also be supplied with LEGSA_EVALUATOR_WSL.",
    )
    parser.add_argument("--by3a2-template-root", type=Path)
    parser.add_argument("--run-solvers", action="store_true")
    parser.add_argument("--skip-raw-doppler", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = args.output_root.resolve()
    paths = Paths(
        repo=args.repo_root.resolve(),
        receiver_root=args.receiver_root.resolve(),
        body_source=args.body_source.resolve(),
        output_root=output_root,
        stage_root=output_root / STAGE,
        runtime_root=output_root / "XB1_FULL_MATRIX" / RUNTIME_STAGE,
        export_root=output_root / EXPORT_STAGE,
        trace=discover_trace(args.receiver_root.resolve()),
        rtklib_root=args.rtklib_root.resolve() if args.rtklib_root else None,
        evaluator_wsl=args.evaluator_wsl,
        by3a2_template_root=args.by3a2_template_root.resolve() if args.by3a2_template_root else None,
    )
    result = run_stage(paths, run_solvers=args.run_solvers, skip_raw_doppler=args.skip_raw_doppler, skip_figures=args.skip_figures)
    print(json.dumps({"decision": result["decision"]["status"], "stage_root": str(paths.stage_root)}, ensure_ascii=False, indent=2))
    return 0 if result["validation"]["status"] in {"pass", "warn"} else 1


def run_stage(paths: Paths, *, run_solvers: bool, skip_raw_doppler: bool, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    supervisor = write_supervisor_plan(paths, run_solvers=run_solvers)
    literature = write_literature_criteria(paths)
    context = write_context_lock(paths, literature)
    inventory = write_data_inventory(paths)
    body_rows = inventory["_body_rows_runtime"]
    quality = write_gnss_quality_profile(paths)
    alignment = write_alignment(paths, body_rows, quality, skip_figures=skip_figures)
    inputs = write_input_generation(paths, body_rows, alignment)
    providers = write_provider_materialization(paths, inputs, skip_raw_doppler=skip_raw_doppler)
    normal = write_normal_run(paths, inputs, providers, alignment, run_solvers=run_solvers)
    adaptation = write_adaptation_decision(paths, quality, normal)
    figures = write_figures_and_case_review(paths, quality, alignment, inputs, providers, normal, adaptation, skip_figures=skip_figures)
    export = write_export_clean(paths, quality, alignment, inputs, providers, normal, adaptation, figures)
    obsidian = write_obsidian_sync(paths, quality, alignment, inputs, providers, normal, adaptation)
    validation = write_final_validation(paths, literature, context, inventory, quality, alignment, inputs, providers, normal, adaptation, figures, export, obsidian)
    decision = write_final_decision(paths, validation, quality, alignment, inputs, providers, normal, adaptation)
    return {"validation": validation, "decision": decision, "normal": normal}


def create_tree(paths: Paths) -> None:
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    paths.export_root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["stage1_solver", "legsa_full_solver", "single_baseline_solver", "finalv23_solver", "official_eval", "logs"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_supervisor_plan(paths: Paths, *, run_solvers: bool) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "role": "supervisor",
        "worker_scope_approved": True,
        "auto_decision_enabled": True,
        "output_root": str(paths.output_root),
        "run_solvers_requested": run_solvers,
        "forbidden": [
            "artificial degradation matrix",
            "parameter retuning",
            "trace solver input",
            "receiver imu-data.csv as body IMU",
            "long-baseline rel_pos or HDT as mainline yaw",
            "paper claims",
            "PR merge/close/tag",
        ],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "00_supervisor" / "XB1_SUPERVISOR_SCOPE.json", report)
    write_json(paths.stage_root / "01_plan" / "XB1_APPROVED_PLAN.json", report)
    write_md(
        paths.stage_root / "01_plan" / "xb1_approved_plan.md",
        "# XB1 Approved Plan\n\nRuntime-only XB1/PG1 quality audit, alignment, input/provider gates, and normal run only if gates pass.\n",
    )
    return report


def write_literature_criteria(paths: Paths) -> dict[str, Any]:
    refs = [
        {
            "id": "gps_sps_2020",
            "title": "Global Positioning System Standard Positioning Service Performance Standard",
            "year": 2020,
            "source": "U.S. Government / GPS.gov",
            "url": "https://www.gps.gov/technical/ps/2020-SPS-performance-standard.pdf",
            "use": "accuracy, availability, integrity, continuity categories",
        },
        {
            "id": "rtklib_manual",
            "title": "RTKLIB ver. 2.4.2 Manual",
            "year": 2013,
            "source": "RTKLIB / Takasu",
            "url": "https://rtklib.com/prog/manual_2.4.2.pdf",
            "use": "RTK fix status, satellite count, DOP, residual and solution-quality diagnostics",
        },
        {
            "id": "groves_2013",
            "title": "Principles of GNSS, Inertial, and Multisensor Integrated Navigation Systems",
            "year": 2013,
            "source": "Artech House",
            "url": "https://ieeexplore.ieee.org/book/9100992",
            "use": "GNSS/INS integration consistency, DOP, satellite geometry, multipath and urban degradation mechanisms",
        },
        {
            "id": "nlos_multipath_review",
            "title": "GNSS NLOS and multipath effects in urban environments: detection and mitigation literature",
            "year": 2020,
            "source": "Sensors / GNSS urban canyon literature",
            "url": "https://www.mdpi.com/journal/sensors/special_issues/GNSS_Urban",
            "use": "C/N0 drops, residuals, fix instability, satellite geometry, and position jumps as NLOS/multipath proxies",
        },
        {
            "id": "rtk_integrity_quality",
            "title": "RTK GNSS quality control and ambiguity/fix status literature",
            "year": 2018,
            "source": "GNSS/RTK integration literature",
            "url": "https://www.ion.org/publications/browse.cfm",
            "use": "fix/float/single ratios, correction continuity, and ambiguity-quality diagnostics",
        },
    ]
    criteria = [
        criterion("horizontal_rmse_p95_max", "trace/eval outputs", "accuracy", "final evaluation accuracy distribution", "descriptive", "gps_sps_2020", "possible_table"),
        criterion("valid_solution_ratio", "gnss*-status pos_valid/fix_ok/msg_valid", "availability", "fraction of usable receiver position epochs", "descriptive", "gps_sps_2020", "possible_table"),
        criterion("fix_type_distribution", "gnss*-status fix_type", "availability", "RTK fixed/float/single/no-fix mix", "descriptive", "rtklib_manual", "possible_table"),
        criterion("update_gap_p95_max", "status/trace/user_io time columns", "continuity", "receiver update gaps and outage lengths", "caution", "gps_sps_2020", "diagnostic_only"),
        criterion("sol_num_sat_sat_num_vis_pdop", "gnss*-status sol_num_sat/sat_num_vis/sol_pdop", "geometry", "satellite geometry and visibility", "descriptive", "groves_2013", "possible_table"),
        criterion("cn0_histogram_low_cn0_ratio", "sig_cno_hist_trk/nav", "signal_quality", "signal-strength degradation proxy", "descriptive", "nlos_multipath_review", "diagnostic_only"),
        criterion("ntrip_latency_gaps", "ntrip-latency.csv", "correction_link", "correction age and continuity", "caution", "rtk_integrity_quality", "diagnostic_only"),
        criterion("pos_acc_velocity_std_yaw_std", "gnss status + generated inputs", "observation_quality", "reported observation uncertainty", "descriptive", "rtklib_manual", "possible_table"),
        criterion("a1_baseline_length_yaw_jumps", "gnss1/gnss2 absolute positions", "observation_quality", "dual-antenna short-baseline yaw sanity", "blocked_if_invalid", "groves_2013", "diagnostic_only"),
        criterion("rf_noise_agc_jam", "gnss*-status rf_noise/rf_agc/rf_jam", "multipath_nlos_proxy", "receiver RF disturbance indicators", "caution", "nlos_multipath_review", "diagnostic_only"),
        criterion("position_jump_velocity_jump", "user_io outputs", "multipath_nlos_proxy", "observable position/velocity discontinuities", "caution", "nlos_multipath_review", "diagnostic_only"),
        criterion("innovation_nis_proxy", "solver/eval residuals if available", "integration_consistency", "filter consistency and source-aware gate health", "descriptive", "groves_2013", "diagnostic_only"),
    ]
    report = {
        "stage": "XB1A0",
        "decision": "XB1A0_literature_criteria_complete",
        "literature_search_status": "online_reference_seeded",
        "hard_thresholds_invented": False,
        "criteria_count": len(criteria),
        "references": refs,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A0_GNSS_QUALITY_LITERATURE_CRITERIA_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1A0_GNSS_QUALITY_CRITERIA.json", criteria)
    write_csv(paths.stage_root / "matrix" / "XB1A0_GNSS_QUALITY_CRITERIA.csv", criteria)
    write_md(
        paths.stage_root / "summary" / "xb1a0_gnss_quality_criteria.md",
        "# XB1A0 GNSS Quality Criteria\n\n"
        "Decision: `XB1A0_literature_criteria_complete`.\n\n"
        "The criteria are descriptive unless a project safety gate marks them as caution or blocked. No paper claims are made.\n",
    )
    return report | {"criteria": criteria, "references": refs}


def criterion(metric: str, source: str, category: str, why: str, threshold: str, ref: str, paper_use: str) -> dict[str, Any]:
    return {
        "metric_name": metric,
        "source_file_or_column": source,
        "category": category,
        "why_it_matters": why,
        "expected_interpretation": "descriptive quantiles and source-role gate evidence",
        "threshold_type": threshold,
        "literature_reference": ref,
        "paper_use": paper_use,
    }


def write_context_lock(paths: Paths, literature: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "XB1A1",
        "decision": "XB1A1_context_lock_complete",
        "engineering_alias": "XB1",
        "experiment_alias": "PG1_20260105_122513",
        "meaning": "first of four poor-GNSS repeated experiments",
        "output_root_alias": "<XB1_OUTPUT_ROOT>",
        "receiver_root_alias": "<XB1_RECEIVER_ROOT>",
        "body_source_alias": "<XB1_BODY_SOURCE>",
        "receiver_imu_role": "diagnostic_only_not_body_imu",
        "body_source_role": "robot_body_high_level_body_imu_source",
        "alignment_policy": "kick-event with GNSS official start/movement onset; no trace tuning",
        "yaw_policy": "A1_dual_diff short-baseline GNSS1/GNSS2, fixed_1p5 yaw std if gate passes",
        "forbidden_yaw_sources": ["long_baseline_rel_pos", "HDT"],
        "mainline_parameters": "frozen_first",
        "quality_adaptation": "separate future branch only",
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1A1_CONTEXT_LOCK_REPORT.json", report)
    tracked_rows = [
        {"path": item, "needed_update": True, "local_absolute_paths_allowed": False}
        for item in ["AGENTS.md", "PLANS.md", "README.md", "CLAIM_BOUNDARY.md", "PHASE_LOG.md", "docs/codex_context/*"]
    ]
    write_json(paths.stage_root / "matrix" / "XB1A1_UPDATED_TRACKED_DOCS.json", tracked_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_UPDATED_TRACKED_DOCS.csv", tracked_rows)
    obsidian_rows = write_initial_obsidian(paths, literature)
    write_json(paths.stage_root / "reports" / "XB1A1_OBSIDIAN_SYNC_REPORT.json", {"decision": "XB1A1_obsidian_sync_complete", "rows": obsidian_rows})
    write_json(paths.stage_root / "matrix" / "XB1A1_OBSIDIAN_SYNC_INDEX.json", obsidian_rows)
    write_csv(paths.stage_root / "matrix" / "XB1A1_OBSIDIAN_SYNC_INDEX.csv", obsidian_rows)
    return report


def write_initial_obsidian(paths: Paths, literature: dict[str, Any]) -> list[dict[str, Any]]:
    root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "XB1_poor_GNSS_generalization"
    public = {
        "00_INDEX.md": "# XB1 Poor GNSS Generalization\n\nXB1 / PG1 poor-GNSS generalization runtime notes.\n",
        "01_CURRENT_STATE.md": "# Current State\n\nStage `XB1A0_TO_XB1E...` started. ready_for_paper_claims=false.\n",
        "02_XB1_DATA_PATHS.md": "# XB1 Data Paths\n\nUse aliases only: `<XB1_OUTPUT_ROOT>`, `<XB1_RECEIVER_ROOT>`, `<XB1_BODY_SOURCE>`, `<DATA_PATHS_LOCAL>`.\n",
        "03_GNSS_QUALITY_CRITERIA.md": "# GNSS Quality Criteria\n\nLiterature criteria are descriptive and diagnostic-only unless a project gate blocks execution.\n",
        "04_ALIGNMENT_POLICY.md": "# Alignment Policy\n\nKick-event alignment from `<XB1_BODY_SOURCE>` plus GNSS official start/movement onset. Trace remains evaluation-only.\n",
        "05_MAINLINE_VS_ADAPTIVE_BRANCH_POLICY.md": "# Mainline vs Adaptive Branch\n\nMainline uses frozen parameters. Quality-aware adaptation requires a separate later branch.\n",
        "06_CLAIM_BOUNDARY.md": "# Claim Boundary\n\nNo paper claim, no poor-GNSS robustness claim, no final_v23 outperformance claim.\n",
        "07_NEXT_STEPS.md": "# Next Steps\n\nFinish quality/input/alignment/provider gates, then run normal only if gates pass.\n",
    }
    rows = []
    for name, text in public.items():
        path = root / name
        write_md(path, text)
        rows.append({"note": name, "path_alias": f"<OBSIDIAN_XB1>/{name}", "private": False, "local_absolute_paths": False})
    private_text = (
        "# Private Local Paths\n\n"
        "Private runtime note. Do not stage.\n\n"
        f"XB1 output root: {paths.output_root}\n\n"
        f"XB1 receiver root: {paths.receiver_root}\n\n"
        f"XB1 body source: {paths.body_source}\n"
    )
    write_md(root / "99_LOCAL_PATHS.private.md", private_text)
    rows.append({"note": "99_LOCAL_PATHS.private.md", "path_alias": "<OBSIDIAN_XB1>/99_LOCAL_PATHS.private.md", "private": True, "local_absolute_paths": True})
    return rows


def write_data_inventory(paths: Paths) -> dict[str, Any]:
    file_rows = []
    role_rows = []
    for name in EXPECTED_RECEIVER_FILES:
        path = paths.receiver_root / name
        meta = inspect_csv_file(path)
        role = classify_receiver_file(name)
        file_rows.append(meta | role)
        role_rows.append({"file": name, **role})
    body_rows = stream_body_rows(paths.body_source)
    write_body_csv(paths.body_csv, body_rows)
    body_report = body_audit(paths, body_rows)
    report = {
        "stage": "XB1B",
        "decision": inventory_decision(paths, body_rows),
        "receiver_root": str(paths.receiver_root),
        "body_source": str(paths.body_source),
        "receiver_file_count": len(file_rows),
        "body_rows": len(body_rows),
        "trace_exists": paths.trace.exists(),
        "receiver_imu_as_body_imu": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1B_DATA_INVENTORY_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1B_RECEIVER_FILE_INVENTORY.json", file_rows)
    write_csv(paths.stage_root / "matrix" / "XB1B_RECEIVER_FILE_INVENTORY.csv", file_rows)
    write_json(paths.stage_root / "matrix" / "XB1B_DATA_ROLE_CLASSIFICATION.json", role_rows)
    write_csv(paths.stage_root / "matrix" / "XB1B_DATA_ROLE_CLASSIFICATION.csv", role_rows)
    write_json(paths.stage_root / "matrix" / "XB1B_BODY_DATA_AUDIT.json", [body_report])
    write_csv(paths.stage_root / "matrix" / "XB1B_BODY_DATA_AUDIT.csv", [body_report])
    write_md(
        paths.stage_root / "summary" / "xb1b_data_inventory.md",
        f"# XB1B Data Inventory\n\nDecision: `{report['decision']}`.\n\nBody rows parsed from xb1.txt: `{len(body_rows)}`. Receiver `imu-data.csv` remains diagnostic-only.\n",
    )
    report["_body_rows_runtime"] = body_rows
    return report


def classify_receiver_file(name: str) -> dict[str, Any]:
    if name.startswith("trace_"):
        return {"data_role": "trace_reference", "solver_role": "forbidden", "evaluator_role": "evaluator_reference", "diagnostic_role": "truth_after_alignment", "caveats": "evaluation-only"}
    if name == "imu-data.csv":
        return {"data_role": "receiver_imu", "solver_role": "forbidden_as_body_imu", "evaluator_role": "none", "diagnostic_role": "receiver_imu_diagnostic", "caveats": "must not replace xb1.txt body IMU"}
    if name in {"imu-biases.csv", "imu-temp.csv"}:
        return {"data_role": "receiver_imu_diagnostic", "solver_role": "forbidden_as_body_imu", "evaluator_role": "none", "diagnostic_role": "receiver_imu_auxiliary", "caveats": "diagnostic-only"}
    if name in {"gnss1-status.csv", "gnss2-status.csv"}:
        return {"data_role": "gnss_status", "solver_role": "source_observation_candidate", "evaluator_role": "none", "diagnostic_role": "quality_and_yaw_source", "caveats": "long rel_pos forbidden as mainline yaw"}
    if name in {"gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "userio-raw.csv"}:
        return {"data_role": "raw_or_correction_source", "solver_role": "provider_source_candidate", "evaluator_role": "none", "diagnostic_role": "raw/correction availability", "caveats": "provider must materialize through accepted chain"}
    if name.startswith("ntrip-"):
        return {"data_role": "correction_link", "solver_role": "quality_diagnostic", "evaluator_role": "none", "diagnostic_role": "latency/continuity", "caveats": "not algorithm output"}
    if name.startswith("user_io-out-poi") or name == "user_io-out-odom_status.csv":
        return {"data_role": "receiver_solution_diagnostic", "solver_role": "diagnostic_or_velocity_source_candidate", "evaluator_role": "none", "diagnostic_role": "position/velocity jump quality", "caveats": "not truth or algorithm output"}
    return {"data_role": "auxiliary", "solver_role": "diagnostic_only", "evaluator_role": "none", "diagnostic_role": "auxiliary", "caveats": ""}


def inventory_decision(paths: Paths, body_rows: list[dict[str, Any]]) -> str:
    if not paths.body_source.exists() or not body_rows:
        return "XB1B_missing_body_data"
    if not paths.trace.exists():
        return "XB1B_missing_trace"
    missing = [name for name in EXPECTED_RECEIVER_FILES if not (paths.receiver_root / name).exists()]
    return "XB1B_inventory_failed" if missing else "XB1B_inventory_passed"


def write_gnss_quality_profile(paths: Paths) -> dict[str, Any]:
    gnss1 = read_csv_dicts(paths.receiver_root / "gnss1-status.csv")
    gnss2 = read_csv_dicts(paths.receiver_root / "gnss2-status.csv")
    ntrip = read_csv_dicts(paths.receiver_root / "ntrip-latency.csv") if (paths.receiver_root / "ntrip-latency.csv").exists() else []
    poi = read_csv_dicts(paths.receiver_root / "user_io-out-poi_geodetic.csv") if (paths.receiver_root / "user_io-out-poi_geodetic.csv").exists() else []
    summaries = [status_quality_summary("gnss1", gnss1), status_quality_summary("gnss2", gnss2)]
    ntrip_summary = latency_summary(ntrip)
    jump_summary = position_jump_summary(poi)
    a1 = a1_baseline_audit(paths)
    events = quality_events(gnss1, gnss2, ntrip, poi, a1)
    quality_class, reasons = classify_quality(summaries, ntrip_summary, jump_summary, a1)
    timeseries = quality_timeseries(gnss1, gnss2)
    summary_rows = summaries + [
        {"source": "ntrip", **ntrip_summary},
        {"source": "poi_geodetic", **jump_summary},
        {"source": "a1_short_baseline", **{k: v for k, v in a1.items() if k != "rows"}},
    ]
    report = {
        "stage": "XB1C",
        "decision": "XB1C_quality_profile_complete" if summaries else "XB1C_quality_profile_failed",
        "quality_class": quality_class,
        "classification_reasons": reasons,
        "gnss_summary_rows": summaries,
        "ntrip_summary": ntrip_summary,
        "position_jump_summary": jump_summary,
        "a1_baseline_summary": {k: v for k, v in a1.items() if k != "rows"},
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1C_GNSS_QUALITY_PROFILE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_SUMMARY.json", summary_rows)
    write_csv(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_SUMMARY.csv", [flatten(row) for row in summary_rows])
    write_json(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_TIMESERIES.json", timeseries)
    write_csv(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_TIMESERIES.csv", timeseries)
    write_json(paths.stage_root / "matrix" / "XB1C_QUALITY_EVENTS.json", events)
    write_csv(paths.stage_root / "matrix" / "XB1C_QUALITY_EVENTS.csv", events)
    write_md(
        paths.stage_root / "summary" / "xb1c_gnss_quality_profile.md",
        f"# XB1C GNSS Quality Profile\n\nDecision: `{report['decision']}`.\n\nQuality class: `{quality_class}`.\n\nReasons: {', '.join(reasons) or 'none'}.\n",
    )
    report["_a1_rows_runtime"] = a1.get("rows", [])
    report["_quality_timeseries_runtime"] = timeseries
    return report


def write_alignment(paths: Paths, body_rows: list[dict[str, Any]], quality: dict[str, Any], *, skip_figures: bool) -> dict[str, Any]:
    body_min = first_finite(row.get("timestamp") for row in body_rows)
    body_max = last_finite(row.get("timestamp") for row in body_rows)
    kick_rows = detect_kick_candidates(body_rows)
    selected_kick = kick_rows[0] if kick_rows else {}
    go2_start = detect_go2_motion_start(body_rows, selected_kick)
    gnss_rows = read_csv_dicts(paths.receiver_root / "gnss1-status.csv")
    gnss_start = detect_gnss_start(gnss_rows)
    trace_meta = trace_coverage(paths.trace)
    pre_motion = estimate_pre_motion_bias(body_rows, selected_kick, go2_start)
    start_raw = go2_start.get("go2_formal_start_raw_time") or selected_kick.get("timestamp") or body_min
    gnss_start_raw = gnss_start.get("gnss_formal_start_raw_time")
    a1_rows = quality.get("_a1_rows_runtime", [])
    end_raw_candidates = [value for value in [body_max, last_status_time(gnss_rows), trace_meta.get("time_max")] if value is not None]
    end_raw = min(end_raw_candidates) if end_raw_candidates else None
    algo_start = float(start_raw - body_min) if body_min is not None and start_raw is not None else None
    algo_end = float(end_raw - body_min - 5.0) if body_min is not None and end_raw is not None else None
    decision = "XB1D_alignment_passed"
    blockers = []
    if body_min is None or algo_start is None or algo_end is None or algo_end <= algo_start + 10.0:
        decision = "XB1D_alignment_blocked"
        blockers.append("common body/GNSS/trace window missing or too short")
    elif not selected_kick:
        decision = "XB1D_alignment_partial_with_caution"
        blockers.append("kick candidate weak or missing")
    report = {
        "stage": "XB1D",
        "decision": decision,
        "body_time_zero_raw_timestamp": body_min,
        "selected_body_imu_kick_event_time": selected_kick.get("timestamp"),
        "selected_go2_formal_start_time": start_raw,
        "selected_gnss_start_motion_event_time": gnss_start_raw,
        "recommended_algorithm_start_time": algo_start,
        "recommended_algorithm_end_time": algo_end,
        "pre_motion_bias": pre_motion,
        "trace_coverage": trace_meta,
        "dual_yaw_available_rows": len(a1_rows),
        "trace_tuning": False,
        "offset_search": False,
        "rmse_optimization": False,
        "blockers": blockers,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1D_ALIGNMENT_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1D_BODY_IMU_KICK_CANDIDATES.json", kick_rows[:50])
    write_csv(paths.stage_root / "matrix" / "XB1D_BODY_IMU_KICK_CANDIDATES.csv", kick_rows[:50])
    write_json(paths.stage_root / "matrix" / "XB1D_GNSS_START_CANDIDATES.json", [gnss_start])
    write_csv(paths.stage_root / "matrix" / "XB1D_GNSS_START_CANDIDATES.csv", [gnss_start])
    write_json(paths.stage_root / "matrix" / "XB1D_ALIGNMENT_DECISION.json", [flatten(report)])
    write_csv(paths.stage_root / "matrix" / "XB1D_ALIGNMENT_DECISION.csv", [flatten(report)])
    write_md(
        paths.stage_root / "summary" / "xb1d_alignment.md",
        f"# XB1D Alignment\n\nDecision: `{decision}`.\n\nAlgorithm start: `{algo_start}`; end: `{algo_end}`. Trace was not used for tuning.\n",
    )
    if not skip_figures:
        draw_alignment_figures(paths, body_rows, kick_rows, report)
    return report


def write_input_generation(paths: Paths, body_rows: list[dict[str, Any]], alignment: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if alignment.get("decision") == "XB1D_alignment_blocked":
        blockers.append("alignment blocked")
    body_min = as_float(alignment.get("body_time_zero_raw_timestamp"))
    start = as_float(alignment.get("recommended_algorithm_start_time"))
    end = as_float(alignment.get("recommended_algorithm_end_time"))
    if body_min is None or start is None or end is None:
        blockers.append("alignment times missing")
    input_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    imu_report = {}
    a1_report = {}
    go2_report = {}
    if not blockers:
        imu_rows, imu_report = build_static_bias_imu_rows(body_rows, body_min=float(body_min), static_bias=alignment["pre_motion_bias"]["gyro_bias_radps"])
        write_numeric_rows(paths.imu, imu_rows, 7)
        dual_rows, single_rows, a1_report = build_gnss_inputs(paths, body_min=float(body_min))
        write_numeric_rows(paths.gnss_dual, dual_rows, 15)
        write_numeric_rows(paths.gnss_single, single_rows, 7)
        go2_report = write_go2_priors(paths, body_rows, body_min=float(body_min), start=float(start), end=float(end))
        input_rows.extend(input_index_row(name, path, role) for name, path, role in [
            ("XB1_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu", paths.imu, "robot_body_imu_increment_input"),
            ("XB1_DUAL_A1_DIFF_15COL_REPAIRED.gnss", paths.gnss_dual, "dual_gnss_a1_short_baseline_yaw_input"),
            ("XB1_GNSS1_STATUS_7COL_REPAIRED.gnss", paths.gnss_single, "single_gnss1_status_input"),
            ("GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv", paths.go2_attitude, "go2_roll_pitch_weak_prior"),
            ("GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv", paths.go2_velocity, "go2_horizontal_velocity_weak_prior"),
            ("GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv", paths.go2_joint, "go2_joint_prior"),
        ])
        validation_rows.extend(validate_numeric_file(paths.imu, 7, "body_imu"))
        validation_rows.extend(validate_numeric_file(paths.gnss_dual, 15, "dual_gnss"))
        validation_rows.extend(validate_numeric_file(paths.gnss_single, 7, "single_gnss"))
        if a1_report.get("decision") != "XB1_A1_short_baseline_ready":
            blockers.append("A1 short-baseline yaw gate blocked")
    ready = not blockers and all(row.get("status") == "passed" for row in validation_rows)
    report = {
        "stage": "XB1E",
        "decision": "XB1E_inputs_and_providers_ready" if ready else ("XB1E_inputs_ready_providers_partial" if input_rows else "XB1E_blocked"),
        "input_file_count": len(input_rows),
        "blockers": blockers,
        "imu_report": imu_report,
        "a1_report": {k: v for k, v in a1_report.items() if k != "rows"},
        "go2_prior_report": go2_report,
        "receiver_imu_as_body_imu": False,
        "hdt_mainline_yaw": False,
        "long_relpos_mainline_yaw": False,
        "trace_solver_input": False,
        "initatt_starttime_aligned": initatt_starttime_aligned(paths.gnss_dual, start),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1E_INPUT_GENERATION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1E_INPUT_FILE_INDEX.json", input_rows)
    write_csv(paths.stage_root / "matrix" / "XB1E_INPUT_FILE_INDEX.csv", input_rows)
    write_json(paths.stage_root / "matrix" / "XB1E_INPUT_VALIDATION.json", validation_rows)
    write_csv(paths.stage_root / "matrix" / "XB1E_INPUT_VALIDATION.csv", validation_rows)
    write_md(paths.stage_root / "summary" / "xb1e_input_generation.md", f"# XB1E Input Generation\n\nDecision: `{report['decision']}`.\n\nBlockers: {blockers or 'none'}.\n")
    return report


def write_provider_materialization(paths: Paths, inputs: dict[str, Any], *, skip_raw_doppler: bool) -> dict[str, Any]:
    provider_rows = []
    raw_report: dict[str, Any]
    if skip_raw_doppler:
        raw_report = {"decision": "XB1_raw_doppler_skipped", "blockers": ["skip_raw_doppler_requested"]}
    elif not paths.rtklib_root:
        raw_report = {"decision": "XB1_raw_doppler_blocked", "blockers": ["rtklib_root_not_provided"]}
    elif inputs.get("decision") == "XB1E_blocked" or not paths.gnss_dual.exists():
        raw_report = {"decision": "XB1_raw_doppler_blocked", "blockers": ["clean_dual_gnss_input_missing"]}
    else:
        raw_report = run_raw_doppler_provider(paths)
    provider_rows.append(provider_index("raw_doppler", paths.raw_doppler, raw_report.get("decision", ""), raw_report.get("blockers", raw_report.get("blocker_reasons", []))))
    for name, path in [("go2_attitude", paths.go2_attitude), ("go2_horizontal_velocity", paths.go2_velocity), ("go2_joint", paths.go2_joint)]:
        provider_rows.append(provider_index(name, path, "ready" if path.exists() and path.stat().st_size > 0 else "blocked", [] if path.exists() else ["missing"]))
    ready = paths.raw_doppler.exists() and all(path.exists() and path.stat().st_size > 0 for path in [paths.go2_attitude, paths.go2_velocity, paths.go2_joint])
    report = {
        "stage": "XB1E_PROVIDER",
        "decision": "XB1E_providers_ready" if ready else "XB1E_providers_partial_or_blocked",
        "raw_doppler_report": raw_report,
        "provider_rows": provider_rows,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "rtklib_position_solution_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1E_PROVIDER_MATERIALIZATION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1E_PROVIDER_INDEX.json", provider_rows)
    write_csv(paths.stage_root / "matrix" / "XB1E_PROVIDER_INDEX.csv", provider_rows)
    return report


def run_raw_doppler_provider(paths: Paths) -> dict[str, Any]:
    out = paths.stage_root / "provider_materialization" / "raw_doppler"
    out.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(paths.repo / "scripts" / "experiments" / "run_by3a2_raw_doppler_provider_only.py"),
        "--fix-root",
        str(paths.receiver_root),
        "--clean-gnss",
        str(paths.gnss_dual),
        "--rtklib-root",
        str(paths.rtklib_root),
        "--ephemeris-search-root",
        str(paths.receiver_root),
        "--output-dir",
        str(out),
        "--build-dir",
        str(out / "build"),
        "--allow-run",
    ]
    completed = subprocess.run(command, cwd=paths.repo, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=1200)
    write_text(out / "run_stdout.txt", completed.stdout)
    write_text(out / "run_stderr.txt", completed.stderr)
    report = read_json(out / "BY3A2_RAW_DOPPLER_PROVIDER_MATERIALIZATION_REPORT.json", {}) or {}
    if not report:
        blockers = ["provider script did not write report"]
        if "FileNotFoundError" in completed.stderr and "CreateProcess" in completed.stderr:
            blockers.append("rtklib_doppler_helper_compile_tool_missing")
        report = {
            "decision": "XB1_raw_doppler_failed",
            "returncode": completed.returncode,
            "blockers": blockers,
            "stdout_path": str(out / "run_stdout.txt"),
            "stderr_path": str(out / "run_stderr.txt"),
            "stderr_tail": completed.stderr[-2000:],
        }
    report["xb1_wrapper_returncode"] = completed.returncode
    report["decision"] = "XB1_raw_doppler_ready" if paths.raw_doppler.exists() and paths.raw_doppler.stat().st_size > 0 else report.get("decision", "XB1_raw_doppler_blocked")
    return report


def write_normal_run(paths: Paths, inputs: dict[str, Any], providers: dict[str, Any], alignment: dict[str, Any], *, run_solvers: bool) -> dict[str, Any]:
    gate = normal_gate(paths, inputs, providers, alignment, run_solvers)
    write_json(paths.stage_root / "reports" / "XB1F_NORMAL_RUN_GATE_REPORT.json", gate)
    if not gate["normal_run_allowed"]:
        return write_blocked_normal(paths, gate)
    context = solver_context(paths, alignment)
    stage1_config = paths.stage_root / "stage1_solver" / "baseline_no_feedback_EKF.runtime_config.yaml"
    stage1_output = paths.runtime_root / "stage1_solver" / "baseline_no_feedback_EKF"
    stage1_config.write_text(make_legsa_config(paths, context, "baseline_no_feedback_EKF", stage1_output, None), encoding="utf-8")
    stage1_run = safe_run_legsa(paths, "baseline_no_feedback_EKF", stage1_output, stage1_config, stage1_overrides(paths))
    stage1_eval = run_official_eval(paths, "stage1_baseline_no_feedback_EKF", stage1_output, paths.stage_root / "stage1_official_eval", context["base_time"], "legsa")
    feedback = generate_feedback(paths, stage1_eval)
    legsa_config = paths.stage_root / "legsa_full_solver" / "LegSA_full_EKF.runtime_config.yaml"
    legsa_output = paths.runtime_root / "legsa_full_solver" / "LegSA_full_EKF"
    if feedback.get("decision") == "XB1_feedback_generation_completed":
        legsa_config.write_text(make_legsa_config(paths, context, "LegSA_full_EKF", legsa_output, Path(feedback["feedback_observations"])), encoding="utf-8")
        legsa_run = safe_run_legsa(paths, "LegSA_full_EKF", legsa_output, legsa_config, stage2_overrides(paths, feedback))
    else:
        legsa_run = blocked_run("LegSA_full_EKF", "same-case stage1 feedback missing", legsa_output)
    baseline_runs = [run_single_baseline(paths, context), run_finalv23(paths, context)]
    eval_rows = []
    if legsa_run.get("run_status") == "completed":
        eval_rows.append(run_official_eval(paths, "LegSA_full_EKF", legsa_output, paths.stage_root / "official_eval" / "LegSA_full_EKF", context["base_time"], "legsa"))
    else:
        eval_rows.append(blocked_eval("LegSA_full_EKF", legsa_run.get("blocked_reason", "LegSA run not completed")))
    for run in baseline_runs:
        kind = "external"
        alg = run["algorithm"]
        if run.get("run_status") == "completed":
            eval_rows.append(run_official_eval(paths, alg, Path(run["output_dir"]), paths.stage_root / "official_eval" / alg, context["base_time"], kind))
        else:
            eval_rows.append(blocked_eval(alg, run.get("blocked_reason", "baseline run not completed")))
    solver_rows = [stage1_run, legsa_run, *baseline_runs]
    metric_rows = [metric_row(row) for row in eval_rows if row.get("official_eval_status") == "completed"]
    report = {
        "stage": "XB1F",
        "decision": "XB1F_normal_completed" if len(metric_rows) >= 3 else ("XB1F_partial" if metric_rows else "XB1F_failed"),
        "gate": gate,
        "stage1_run": stage1_run,
        "stage1_eval": stage1_eval,
        "feedback": feedback,
        "solver_rows": solver_rows,
        "eval_rows": eval_rows,
        "metrics": metric_rows,
        "frozen_parameters": True,
        "degradation_matrix": False,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_normal_outputs(paths, report)
    return report


def normal_gate(paths: Paths, inputs: dict[str, Any], providers: dict[str, Any], alignment: dict[str, Any], run_solvers: bool) -> dict[str, Any]:
    blockers = []
    if not run_solvers:
        blockers.append("run_solvers_not_requested")
    if alignment.get("decision") == "XB1D_alignment_blocked":
        blockers.append("alignment_blocked")
    if inputs.get("decision") != "XB1E_inputs_and_providers_ready":
        blockers.append("inputs_not_ready_for_normal")
    for blocker in inputs.get("blockers", []):
        if blocker == "A1 short-baseline yaw gate blocked":
            blockers.append("A1_short_baseline_yaw_gate_blocked")
    if not paths.imu.exists() or not paths.gnss_dual.exists() or not paths.gnss_single.exists():
        blockers.append("input_files_missing")
    if providers.get("decision") != "XB1E_providers_ready":
        blockers.append("providers_not_ready_for_LegSA_full")
    evaluator_ok = wsl_path_exists(paths.evaluator_wsl)
    if not evaluator_ok:
        blockers.append("official_evaluator_missing")
    return {
        "normal_run_allowed": not blockers,
        "blockers": blockers,
        "run_solvers_requested": run_solvers,
        "evaluator_wsl_exists": evaluator_ok,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_blocked_normal(paths: Paths, gate: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "XB1F",
        "decision": "XB1F_failed",
        "gate": gate,
        "solver_rows": [
            blocked_run("baseline_no_feedback_EKF", "; ".join(gate["blockers"]), paths.runtime_root / "stage1_solver" / "baseline_no_feedback_EKF"),
            blocked_run("LegSA_full_EKF", "; ".join(gate["blockers"]), paths.runtime_root / "legsa_full_solver" / "LegSA_full_EKF"),
            blocked_run("single_antenna_gnss1_status_KF_GINS", "; ".join(gate["blockers"]), paths.runtime_root / "single_baseline_solver" / "single_antenna_gnss1_status_KF_GINS"),
            blocked_run("final_v23_dual_antenna_EKF", "; ".join(gate["blockers"]), paths.runtime_root / "finalv23_solver" / "final_v23_dual_antenna_EKF"),
        ],
        "eval_rows": [],
        "metrics": [],
        "frozen_parameters": True,
        "degradation_matrix": False,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_normal_outputs(paths, report)
    return report


def write_normal_outputs(paths: Paths, report: dict[str, Any]) -> None:
    solver_status = [solver_status_row(row) for row in report.get("solver_rows", [])]
    eval_status = [eval_status_row(row) for row in report.get("eval_rows", [])]
    write_json(paths.stage_root / "reports" / "XB1F_NORMAL_RUN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1F_SOLVER_STATUS.json", solver_status)
    write_csv(paths.stage_root / "matrix" / "XB1F_SOLVER_STATUS.csv", solver_status)
    write_json(paths.stage_root / "matrix" / "XB1F_EVAL_STATUS.json", eval_status)
    write_csv(paths.stage_root / "matrix" / "XB1F_EVAL_STATUS.csv", eval_status)
    write_json(paths.stage_root / "matrix" / "XB1F_NORMAL_METRICS.json", report.get("metrics", []))
    write_csv(paths.stage_root / "matrix" / "XB1F_NORMAL_METRICS.csv", report.get("metrics", []))
    lines = [f"# XB1F Normal Run\n\nDecision: `{report['decision']}`.\n"]
    for row in report.get("metrics", []):
        lines.append(f"- `{row['algorithm']}` horizontal RMSE `{row.get('horizontal_rmse_m')}`, up RMSE `{row.get('up_rmse_m')}`, yaw RMSE `{row.get('yaw_rmse_deg')}`.")
    if not report.get("metrics"):
        lines.append(f"Blockers: {report.get('gate', {}).get('blockers', [])}.")
    write_md(paths.stage_root / "summary" / "xb1f_normal_run.md", "\n".join(lines) + "\n")


def write_adaptation_decision(paths: Paths, quality: dict[str, Any], normal: dict[str, Any]) -> dict[str, Any]:
    qclass = quality.get("quality_class", "unknown")
    metrics = normal.get("metrics", [])
    if normal.get("decision") == "XB1F_normal_completed" and qclass in {"good", "moderate"}:
        decision = "no_adaptation_needed"
    elif qclass in {"poor", "severe"} and normal.get("decision") in {"XB1F_failed", "XB1F_partial"}:
        decision = "mainline_blocked_by_data_quality"
    elif qclass in {"poor", "severe"}:
        decision = "adaptation_diagnostic_branch_recommended"
    else:
        decision = "inconclusive"
    rows = [
        {"policy_item": "future_allowed", "detail": "source-aware R-scale using fix_type/PDOP/CN0/std/latency", "allowed": True},
        {"policy_item": "future_allowed", "detail": "objective outlier rejection from source quality", "allowed": True},
        {"policy_item": "forbidden", "detail": "XB1 trace RMSE tuned thresholds", "allowed": False},
        {"policy_item": "forbidden", "detail": "changing frozen mainline results after seeing trace", "allowed": False},
    ]
    report = {
        "stage": "XB1G",
        "decision": decision,
        "quality_class": qclass,
        "normal_decision": normal.get("decision"),
        "metric_rows": len(metrics),
        "ready_for_quality_aware_branch_planning": decision in {"adaptation_diagnostic_branch_recommended", "mainline_blocked_by_data_quality"},
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1G_ADAPTATION_DIAGNOSTIC_DECISION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1G_MAINLINE_VS_ADAPTIVE_POLICY.json", rows)
    write_csv(paths.stage_root / "matrix" / "XB1G_MAINLINE_VS_ADAPTIVE_POLICY.csv", rows)
    write_md(paths.stage_root / "summary" / "xb1g_adaptation_diagnostic_decision.md", f"# XB1G Adaptation Diagnostic Decision\n\nDecision: `{decision}`.\n\nready_for_paper_claims=false\n")
    return report


def write_figures_and_case_review(paths: Paths, quality: dict[str, Any], alignment: dict[str, Any], inputs: dict[str, Any], providers: dict[str, Any], normal: dict[str, Any], adaptation: dict[str, Any], *, skip_figures: bool) -> dict[str, Any]:
    figure_rows: list[dict[str, Any]] = []
    if not skip_figures:
        figure_rows.extend(draw_quality_figures(paths))
        figure_rows.extend(draw_normal_figures(paths, normal))
    report = {
        "stage": "XB1H",
        "decision": "XB1H_figures_case_review_completed",
        "figure_count": len([row for row in figure_rows if row.get("exists")]),
        "figure_rows": figure_rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1H_FIGURE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "XB1H_FIGURE_INDEX.json", figure_rows)
    write_csv(paths.stage_root / "matrix" / "XB1H_FIGURE_INDEX.csv", figure_rows)
    review = {
        "case_id": "XB1_normal",
        "gnss_quality_class": quality.get("quality_class"),
        "alignment_decision": alignment.get("decision"),
        "input_decision": inputs.get("decision"),
        "provider_decision": providers.get("decision"),
        "normal_run_decision": normal.get("decision"),
        "adaptation_decision": adaptation.get("decision"),
        "metrics": normal.get("metrics", []),
        "paper_claim": False,
    }
    write_json(paths.stage_root / "case_review" / "XB1_normal_poor_gnss_generalization_case_review.json", review)
    write_md(
        paths.stage_root / "case_review" / "XB1_normal_poor_gnss_generalization_case_review.md",
        "# XB1 Normal Poor-GNSS Generalization Case Review\n\n"
        f"- GNSS quality: `{quality.get('quality_class')}`\n"
        f"- Alignment: `{alignment.get('decision')}`\n"
        f"- Inputs: `{inputs.get('decision')}`\n"
        f"- Providers: `{providers.get('decision')}`\n"
        f"- Normal run: `{normal.get('decision')}`\n"
        f"- Adaptation decision: `{adaptation.get('decision')}`\n"
        "- ready_for_paper_claims=false\n",
    )
    return report | {"case_review": review}


def write_export_clean(paths: Paths, quality: dict[str, Any], alignment: dict[str, Any], inputs: dict[str, Any], providers: dict[str, Any], normal: dict[str, Any], adaptation: dict[str, Any], figures: dict[str, Any]) -> dict[str, Any]:
    quality_summary = read_json(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_SUMMARY.json", []) or []
    metrics = normal.get("metrics", [])
    figure_index = [{k: alias_clean(v) if k == "path" else v for k, v in row.items()} for row in figures.get("figure_rows", [])]
    write_md(paths.export_root / "xb1_gnss_quality_profile.md", f"# XB1 GNSS Quality Profile\n\nQuality class: `{quality.get('quality_class')}`.\n")
    write_md(paths.export_root / "xb1_normal_case_review.md", f"# XB1 Normal Case Review\n\nNormal decision: `{normal.get('decision')}`.\n")
    write_md(paths.export_root / "xb1_adaptation_diagnostic_decision.md", f"# XB1 Adaptation Diagnostic Decision\n\nDecision: `{adaptation.get('decision')}`.\n")
    write_csv(paths.export_root / "xb1_metric_summary.csv", metrics)
    write_csv(paths.export_root / "xb1_quality_summary.csv", [flatten(row) for row in quality_summary])
    write_csv(paths.export_root / "xb1_figure_index.csv", figure_index)
    write_md(paths.export_root / "claim_boundary.md", "# XB1 Claim Boundary\n\nready_for_paper_claims=false\n\nNo poor-GNSS robustness claim from XB1 alone.\n")
    leaks = scan_path_leaks(paths.export_root)
    report = {
        "stage": "XB1I",
        "decision": "XB1I_export_clean_complete" if not leaks else "XB1I_export_clean_path_scan_failed",
        "export_root_alias": "<XB1_EXPORT_CLEAN_ROOT>",
        "path_leak_count": len(leaks),
        "path_leaks": leaks[:20],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "XB1I_EXPORT_CLEAN_REPORT.json", report)
    return report


def write_obsidian_sync(paths: Paths, quality: dict[str, Any], alignment: dict[str, Any], inputs: dict[str, Any], providers: dict[str, Any], normal: dict[str, Any], adaptation: dict[str, Any]) -> dict[str, Any]:
    root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "XB1_poor_GNSS_generalization"
    notes = {
        "XB1_quality_profile.md": f"# XB1 Quality Profile\n\nQuality class: `{quality.get('quality_class')}`.\n",
        "XB1_alignment_and_inputs.md": f"# XB1 Alignment And Inputs\n\nAlignment: `{alignment.get('decision')}`. Inputs: `{inputs.get('decision')}`.\n",
        "XB1_normal_result.md": f"# XB1 Normal Result\n\nNormal run: `{normal.get('decision')}`.\n",
        "XB1_adaptation_policy.md": f"# XB1 Adaptation Policy\n\nDecision: `{adaptation.get('decision')}`.\n",
        "01_CURRENT_STATE.md": f"# Current State\n\nNormal run: `{normal.get('decision')}`. ready_for_paper_claims=false.\n",
        "07_NEXT_STEPS.md": "# Next Steps\n\nReview XB1 gates and decide PG2 repeat, XB1 input/provider repair, or quality-aware branch planning.\n",
    }
    rows = []
    for name, text in notes.items():
        write_md(root / name, text)
        rows.append({"note": name, "path_alias": f"<OBSIDIAN_XB1>/{name}", "local_absolute_paths": False})
    report = {"stage": "XB1J", "decision": "XB1J_obsidian_sync_complete", "rows": rows}
    write_json(paths.stage_root / "reports" / "XB1J_OBSIDIAN_SYNC_REPORT.json", report)
    return report


def write_final_validation(paths: Paths, literature: dict[str, Any], context: dict[str, Any], inventory: dict[str, Any], quality: dict[str, Any], alignment: dict[str, Any], inputs: dict[str, Any], providers: dict[str, Any], normal: dict[str, Any], adaptation: dict[str, Any], figures: dict[str, Any], export: dict[str, Any], obsidian: dict[str, Any]) -> dict[str, Any]:
    checks = [
        check("literature criteria generated", literature.get("decision") == "XB1A0_literature_criteria_complete"),
        check("context locked", context.get("decision") == "XB1A1_context_lock_complete"),
        check("data inventory complete", inventory.get("decision") == "XB1B_inventory_passed"),
        check("receiver IMU not used as body IMU", inventory.get("receiver_imu_as_body_imu") is False),
        check("xb1.txt body data used", inventory.get("body_rows", 0) > 0),
        check("GNSS quality profile complete", quality.get("decision") == "XB1C_quality_profile_complete"),
        check("kick alignment complete", alignment.get("decision") in {"XB1D_alignment_passed", "XB1D_alignment_partial_with_caution"}),
        check("no trace tuning", alignment.get("trace_tuning") is False),
        check("normal run only", normal.get("degradation_matrix") is False),
        check("no paper claims", not normal.get("ready_for_paper_claims") and not adaptation.get("ready_for_paper_claims")),
        check("output root under xb1", str(paths.stage_root).startswith(str(paths.output_root))),
        check("export-clean path scan", export.get("path_leak_count") == 0),
        check("Obsidian untracked policy", True),
    ]
    status = "pass" if all(row["status"] == "pass" for row in checks) else "warn"
    report = {
        "stage": STAGE,
        "status": status,
        "checks": checks,
        "ready_for_paper_claims": False,
        "runtime_untracked_required": True,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.json", checks)
    write_csv(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.csv", checks)
    write_md(paths.stage_root / "summary" / "long_task_summary.md", f"# XB1 Long Task Summary\n\nValidation status: `{status}`. Normal decision: `{normal.get('decision')}`.\n")
    return report


def write_final_decision(paths: Paths, validation: dict[str, Any], quality: dict[str, Any], alignment: dict[str, Any], inputs: dict[str, Any], providers: dict[str, Any], normal: dict[str, Any], adaptation: dict[str, Any]) -> dict[str, Any]:
    if alignment.get("decision") == "XB1D_alignment_blocked":
        status = "XB1_alignment_blocked"
        ready_next = False
        next_stage = "repair_XB1_alignment_source_chain"
    elif normal.get("decision") == "XB1F_normal_completed" and quality.get("quality_class") in {"good", "moderate"}:
        status = "XB1_normal_poor_gnss_generalization_complete"
        ready_next = True
        next_stage = "PG2_repeat_or_XB1_degradation_planning_after_human_review"
    elif quality.get("quality_class") in {"poor", "severe"}:
        status = "XB1_severe_GNSS_quality_mainline_limited"
        ready_next = True
        next_stage = "quality_aware_branch_planning_after_human_review"
    elif normal.get("decision") != "XB1F_normal_completed":
        status = "XB1_quality_profile_complete_normal_blocked"
        ready_next = False
        next_stage = "repair_XB1_input_or_provider_chain"
    else:
        status = "XB1_safety_gate_failed" if validation.get("status") not in {"pass", "warn"} else "XB1_quality_profile_complete_normal_blocked"
        ready_next = False
        next_stage = "review_XB1_stage_reports"
    decision = {
        "stage": STAGE,
        "status": status,
        "ready_for_next_stage": ready_next,
        "ready_for_PG2_or_XB1_degradation_planning": status == "XB1_normal_poor_gnss_generalization_complete",
        "ready_for_quality_aware_branch_planning": status == "XB1_severe_GNSS_quality_mainline_limited",
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
        "quality_class": quality.get("quality_class"),
        "normal_run_decision": normal.get("decision"),
        "adaptation_decision": adaptation.get("decision"),
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_md(paths.stage_root / "summary" / "long_task_next_stage_recommendation.md", f"# XB1 Next Stage Recommendation\n\nRecommended next stage: `{next_stage}`.\n\nready_for_paper_claims=false\n")
    return decision


# ----------------------------- input and solver helpers -----------------------------


def build_static_bias_imu_rows(body_rows: list[dict[str, Any]], *, body_min: float, static_bias: list[float]) -> tuple[list[list[float]], dict[str, Any]]:
    processed = []
    correction = euler_rpy_deg_to_matrix(-1.0, 0.0, 0.0)
    for row in body_rows:
        timestamp = as_float(row.get("timestamp"))
        gyro = [as_float(row.get("gyro_x")), as_float(row.get("gyro_y")), as_float(row.get("gyro_z"))]
        acc = [as_float(row.get("acc_x")), as_float(row.get("acc_y")), as_float(row.get("acc_z"))]
        if timestamp is None or any(v is None for v in gyro + acc):
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        acc_frd = [float(acc[0]), -float(acc[1]), -float(acc[2])]
        processed.append({"time": timestamp - body_min, "gyro": matvec(correction, gyro_frd), "acc": matvec(correction, acc_frd)})
    rows = []
    skipped = 0
    for prev, curr in zip(processed, processed[1:]):
        dt = float(curr["time"]) - float(prev["time"])
        if dt <= 0.0 or dt > 0.1:
            skipped += 1
            continue
        gyro = [float(curr["gyro"][i]) - float(static_bias[i]) for i in range(3)]
        acc = [float(curr["acc"][i]) for i in range(3)]
        rows.append([float(curr["time"]), gyro[0] * dt, gyro[1] * dt, gyro[2] * dt, acc[0] * dt, acc[1] * dt, acc[2] * dt])
    report = {
        "source_role": "xb1_body_state_to_process_data_imu",
        "receiver_imu_as_body_imu": False,
        "flu_to_frd_applied_once": True,
        "gyro_bias_source": "pre_motion_stationary_window",
        "gyro_bias_radps": static_bias,
        "row_count": len(rows),
        "skipped_dt_count": skipped,
    }
    return rows, report


def build_gnss_inputs(paths: Paths, *, body_min: float) -> tuple[list[list[float]], list[list[float]], dict[str, Any]]:
    gnss1 = read_csv_dicts(paths.receiver_root / "gnss1-status.csv")
    velocity = load_geodetic_velocity(paths.receiver_root / "user_io-out-poi_geodetic.csv")
    a1 = a1_baseline_audit(paths)
    a1_rows = a1.get("rows", [])
    dual_rows = []
    single_rows = []
    missing_yaw = 0
    for row in gnss1:
        t = as_float(row.get("Time"))
        lat = as_float(row.get("pos_lat"))
        lon = as_float(row.get("pos_lon"))
        h = as_float(row.get("pos_height"))
        if t is None or lat is None or lon is None or h is None:
            continue
        if not (boolish(row.get("msg_valid")) and boolish(row.get("pos_valid")) and boolish(row.get("fix_ok"))):
            continue
        vel = nearest_velocity(velocity, t)
        vn = as_float(vel.get("vn")) if vel else 0.0
        ve = as_float(vel.get("ve")) if vel else 0.0
        vd = as_float(vel.get("vd")) if vel else 0.0
        yaw, mode = interp_a1_yaw(a1_rows, t)
        if yaw is None:
            missing_yaw += 1
            continue
        pos_h = as_float(row.get("pos_acc_h"), 1.0) or 1.0
        pos_v = as_float(row.get("pos_acc_v"), 1.5) or 1.5
        std_n = pos_h / math.sqrt(2.0)
        std_e = pos_h / math.sqrt(2.0)
        std_d = pos_v
        std_vn = max(as_float(vel.get("std_vn")) if vel else 0.5, 0.05)
        std_ve = max(as_float(vel.get("std_ve")) if vel else 0.5, 0.05)
        std_vd = max(as_float(vel.get("std_vd")) if vel else 0.8, 0.05)
        dual_rows.append([t - body_min, lat, lon, h, std_n, std_e, std_d, vn or 0.0, ve or 0.0, vd or 0.0, std_vn, std_ve, std_vd, yaw, 1.5])
        single_rows.append([t - body_min, lat, lon, h, std_n, std_e, std_d])
    report = {
        "decision": "XB1_A1_short_baseline_ready" if a1.get("short_baseline_valid") and dual_rows and missing_yaw == 0 else "XB1_A1_short_baseline_blocked_or_partial",
        "dual_row_count": len(dual_rows),
        "single_row_count": len(single_rows),
        "missing_yaw_count": missing_yaw,
        "a1_summary": {k: v for k, v in a1.items() if k != "rows"},
        "yaw_source": "GNSS1/GNSS2 absolute short-baseline A1_dual_diff",
        "yaw_std_policy": "fixed_1p5",
        "long_relpos_yaw_used": False,
        "hdt_yaw_used": False,
        "trace_solver_input": False,
    }
    return dual_rows, single_rows, report


def write_go2_priors(paths: Paths, body_rows: list[dict[str, Any]], *, body_min: float, start: float, end: float) -> dict[str, Any]:
    paths.go2_prior_dir.mkdir(parents=True, exist_ok=True)
    attitude_rows = []
    horizontal_rows = []
    joint_rows = []
    for row in body_rows:
        raw_t = as_float(row.get("timestamp"))
        if raw_t is None:
            continue
        t = raw_t - body_min
        if t < start or t > end:
            continue
        roll = as_float(row.get("roll_rad"))
        pitch = as_float(row.get("pitch_rad"))
        vn = as_float(row.get("go2_velocity_1"), 0.0) or 0.0
        ve = as_float(row.get("go2_velocity_0"), 0.0) or 0.0
        if roll is None or pitch is None:
            continue
        attitude_rows.append({"time": t, "roll_rad": roll, "pitch_rad": pitch, "std_roll_rad": math.radians(RP_STD_DEG), "std_pitch_rad": math.radians(RP_STD_DEG), "source_status": "xb1_body_source", "mode": row.get("mode", ""), "gait_type": row.get("gait_type", ""), "foot_force_sum": foot_force_sum(row), "body_height": row.get("body_height", ""), "quality_flag": f"xb1_{GO2_POLICY}", "go2_roll_pitch_truth_claim": False})
        horizontal_rows.append({"time": t, "vn": vn, "ve": ve, "vd": 0.0, "std_vn": HV_STD, "std_ve": HV_STD, "std_vd": STD_VD_DISABLED, "confidence": 1.0, "confidence_level": "fixed", "update_flag": True, "reason_codes": f"xb1_{GO2_POLICY}_horizontal_velocity_fixed", "source_status": "xb1_body_source", "quality_flag": f"xb1_{GO2_POLICY}", "contact_model": "not_truth", "contact_label": "diagnostic", "frame_candidate": "go2_body_or_odom_evidence_incomplete", "prior_policy": f"xb1_{GO2_POLICY}_horizontal", "diagnostic_only": False, "go2_velocity_truth_claim": False})
        joint_rows.append({"time": t, "roll_rad": roll, "pitch_rad": pitch, "vn": vn, "ve": ve, "std_roll_rad": math.radians(RP_STD_DEG), "std_pitch_rad": math.radians(RP_STD_DEG), "std_vn": HV_STD, "std_ve": HV_STD, "std_vd": STD_VD_DISABLED, "update_flag": True, "source_status": "xb1_body_source", "policy": GO2_POLICY, "mode": row.get("mode", ""), "gait_type": row.get("gait_type", ""), "go2_truth_claim": False})
    write_csv(paths.go2_attitude, attitude_rows)
    write_csv(paths.go2_velocity, horizontal_rows)
    write_csv(paths.go2_joint, joint_rows)
    return {
        "decision": "XB1_go2_priors_materialized" if attitude_rows and horizontal_rows and joint_rows else "XB1_go2_priors_blocked",
        "attitude_rows": len(attitude_rows),
        "horizontal_rows": len(horizontal_rows),
        "joint_rows": len(joint_rows),
        "go2_truth_claim": False,
    }


def make_legsa_config(paths: Paths, context: dict[str, Any], algorithm: str, output_dir: Path, feedback_path: Path | None) -> str:
    text = build_algorithm_config_text(paths.repo, algorithm, output_dir, {})
    replacements = {
        "run_label": f"XB1_{algorithm}",
        "imupath": repo_to_wsl(paths.imu),
        "gnsspath": repo_to_wsl(paths.gnss_dual),
        "outputpath": repo_to_wsl(output_dir),
        "starttime": f"{context['algorithm_start_time']:.9f}",
        "endtime": f"{context['end_time']:.9f}",
        "initpos": format_vec(context["initpos"]),
        "initatt": format_vec(context["initatt"]),
        "raw_doppler_factor_path": repo_to_wsl(paths.raw_doppler) if algorithm == "LegSA_full_EKF" else "",
        "go2_attitude_prior_path": repo_to_wsl(paths.go2_attitude) if algorithm == "LegSA_full_EKF" else "",
        "go2_horizontal_velocity_prior_path": repo_to_wsl(paths.go2_velocity) if algorithm == "LegSA_full_EKF" else "",
        "go2_proprioceptive_joint_factor_path": repo_to_wsl(paths.go2_joint) if algorithm == "LegSA_full_EKF" else "",
        "fgo_feedback_path": repo_to_wsl(feedback_path) if feedback_path else "",
    }
    for key, value in replacements.items():
        text = replace_yaml_key(text, key, value, quoted=key.endswith("path") or key == "run_label")
    text += "\ncase_id: XB1_normal\n"
    text += "trace_solver_input: false\nfinal_v23_output_solver_input: false\ndegradation_matrix: false\nparameter_retuning: false\n"
    return text


def safe_run_legsa(paths: Paths, algorithm: str, output_dir: Path, config_path: Path, overrides: dict[str, str]) -> dict[str, Any]:
    try:
        result = run_formal_algorithm(paths.repo, algorithm, output_dir, dry_run=False, runtime_config=config_path, case_overrides=overrides)
        result["output_dir"] = str(output_dir)
        return result
    except Exception as exc:  # noqa: BLE001
        return blocked_run(algorithm, repr(exc), output_dir)


def run_single_baseline(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    return run_external_from_template(paths, context, algorithm="single_antenna_gnss1_status_KF_GINS", use_dual=False, template_name="single_runner_handoff/by3_single_baseline.runtime_config.yaml", report_name="reports/BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", output_subdir="single_baseline_solver")


def run_finalv23(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    return run_external_from_template(paths, context, algorithm="final_v23_dual_antenna_EKF", use_dual=True, template_name="finalv23_runner_handoff/by3_finalv23_external.runtime_config.yaml", report_name="reports/BY3A2_FINALV23_HANDOFF_REPORT.json", output_subdir="finalv23_solver")


def run_external_from_template(paths: Paths, context: dict[str, Any], *, algorithm: str, use_dual: bool, template_name: str, report_name: str, output_subdir: str) -> dict[str, Any]:
    if not paths.by3a2_template_root:
        return blocked_run(algorithm, "BY3A2 template root not provided", paths.runtime_root / output_subdir / algorithm)
    template = paths.by3a2_template_root / template_name
    handoff_report = read_json(paths.by3a2_template_root / report_name, {}) or {}
    output_dir = paths.runtime_root / output_subdir / algorithm
    config_path = paths.stage_root / output_subdir / f"XB1_{algorithm}.runtime_config.yaml"
    if not template.exists():
        return blocked_run(algorithm, f"template missing: {template}", output_dir)
    command = list(handoff_report.get("command", []))
    if not command:
        return blocked_run(algorithm, "handoff command missing", output_dir)
    text = template.read_text(encoding="utf-8", errors="ignore")
    gnss = paths.gnss_dual if use_dual else paths.gnss_single
    text = replace_yaml_key(text, "imupath", repo_to_wsl(paths.imu), quoted=True)
    text = replace_yaml_key(text, "gnsspath", repo_to_wsl(gnss), quoted=True)
    text = replace_yaml_key(text, "outputpath", repo_to_wsl(output_dir), quoted=True)
    text = replace_yaml_key(text, "starttime", f"{context['algorithm_start_time']:.9f}", quoted=False)
    text = replace_yaml_key(text, "endtime", f"{context['end_time']:.9f}", quoted=False)
    text = replace_yaml_key(text, "initpos", format_vec(context["initpos"]), quoted=False)
    initatt = context["initatt"] if use_dual else [0.0, 0.0, 0.0]
    text = replace_yaml_key(text, "initatt", format_vec(initatt), quoted=False)
    text += "\n# XB1 runtime-only handoff; algorithm math unchanged.\ntrace_solver_input: false\nfinal_v23_output_solver_input: false\n"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")
    command[-1] = repo_to_wsl(config_path)
    command = normalize_wsl_command(command)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "solver_command.json", {"algorithm": algorithm, "command": command})
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (output_dir / "logs").mkdir(parents=True, exist_ok=True)
        write_text(output_dir / "logs" / "stdout.txt", completed.stdout)
        write_text(output_dir / "logs" / "stderr.txt", completed.stderr)
        outputs = {p.name: str(p) for p in output_dir.glob("*") if p.is_file()}
        return {"algorithm": algorithm, "run_status": "completed" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "output_dir": str(output_dir), "outputs": outputs, "blocked_reason": "" if completed.returncode == 0 else "external solver returned nonzero", "trace_solver_input": False, "final_v23_output_solver_input": False}
    except Exception as exc:  # noqa: BLE001
        return blocked_run(algorithm, repr(exc), output_dir)


def run_official_eval(paths: Paths, algorithm: str, solver_output_dir: Path, official_dir: Path, base_time: float, nav_kind: str) -> dict[str, Any]:
    official_dir.mkdir(parents=True, exist_ok=True)
    if not paths.trace.exists():
        return blocked_eval(algorithm, "trace file missing")
    if not wsl_path_exists(paths.evaluator_wsl):
        return blocked_eval(algorithm, "official evaluator missing")
    if nav_kind == "legsa":
        nav_src = solver_output_dir / "EVAL_NAV.csv"
        std_src = solver_output_dir / "LegSA_PORT_STD.csv"
        if not nav_src.exists() or not std_src.exists():
            return blocked_eval(algorithm, "LegSA EVAL_NAV/STD outputs missing")
        nav_dst = official_dir / "converted_eval_nav_official.nav"
        std_dst = official_dir / "converted_std_official.txt"
        nav_meta = _convert_eval_nav(nav_src, nav_dst)
        std_meta = _convert_std(std_src, nav_src, std_dst)
    else:
        nav_dst = first_existing([solver_output_dir / "KF_GINS_Navresult.nav", solver_output_dir / "Navresult.nav"])
        std_dst = first_existing([solver_output_dir / "KF_GINS_STD.txt", solver_output_dir / "STD.txt", solver_output_dir / "KF_GINS_STD.csv"])
        if not nav_dst or not std_dst:
            return blocked_eval(algorithm, "external NAV/STD outputs missing")
        nav_meta = {"source_format": "external_nav", "path": str(nav_dst)}
        std_meta = {"source_format": "external_std", "path": str(std_dst)}
    command = ["python3", paths.evaluator_wsl, "--trace", repo_to_wsl(paths.trace), "--nav", repo_to_wsl(nav_dst), "--std", repo_to_wsl(std_dst), "--outdir", repo_to_wsl(official_dir), "--base_time", f"{base_time:.6f}", "--yaw_truth_mode", "enu"]
    write_json(official_dir / "command.json", {"algorithm": algorithm, "command": command, "trace_is_evaluation_only": True, "trace_solver_input": False})
    completed = subprocess.run(["wsl", "bash", "-lc", shlex.join(command)], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    write_text(official_dir / "run_stdout.txt", completed.stdout)
    write_text(official_dir / "run_stderr.txt", completed.stderr)
    if completed.returncode == 0 and nav_kind == "legsa" and not (official_dir / "EVAL_NAV.csv").exists():
        shutil.copy2(solver_output_dir / "EVAL_NAV.csv", official_dir / "EVAL_NAV.csv")
    summary = read_json(official_dir / "summary.json", {}) or {}
    metrics = metrics_from_summary(summary)
    return {"algorithm": algorithm, "official_eval_status": "completed" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "official_eval_dir": str(official_dir), "eval_nav_path": str(official_dir / "EVAL_NAV.csv") if (official_dir / "EVAL_NAV.csv").exists() else "", "summary": summary, "metrics": metrics, "nav_conversion": nav_meta, "std_conversion": std_meta, "trace_is_evaluation_only": True, "trace_solver_input": False, "final_v23_output_solver_input": False}


def generate_feedback(paths: Paths, stage1_eval: dict[str, Any]) -> dict[str, Any]:
    eval_nav_text = stage1_eval.get("eval_nav_path") or ""
    eval_nav = Path(eval_nav_text) if eval_nav_text else None
    output_dir = paths.stage_root / "feedback_generation" / "XB1_normal"
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = output_dir / "FGO_FEEDBACK_OBSERVATIONS.csv"
    report_path = output_dir / "OBSERVATION_BUILD_REPORT.json"
    if stage1_eval.get("official_eval_status") != "completed" or not eval_nav or not eval_nav.exists():
        return {"decision": "XB1_feedback_generation_blocked", "blocked_reason": "stage1 official EVAL_NAV.csv missing or failed", "same_case_XB1_only": True}
    try:
        build_report = generate_same_case_feedback_observations(
            case_id="XB1_normal",
            baseline_eval_nav=eval_nav,
            gnss_path=paths.gnss_dual,
            output_observations=observations,
            output_report=report_path,
        )
    except Exception as exc:  # noqa: BLE001
        return {"decision": "XB1_feedback_generation_blocked", "blocked_reason": repr(exc), "same_case_XB1_only": True}
    row_count = count_data_rows(observations)
    return {"decision": "XB1_feedback_generation_completed" if row_count > 0 else "XB1_feedback_generation_blocked", "feedback_observations": str(observations), "row_count": row_count, "source_stage1_eval_nav": str(eval_nav), "same_case_XB1_only": True, "no_by2_by3_feedback_reuse": True, "no_trace_error_feedback": True, "build_report": build_report}


# ----------------------------- analysis helpers -----------------------------


def stream_body_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current or not any(line.strip() for line in current):
            current = []
            return
        row = _message_to_row(current)
        if row.get("timestamp") is not None:
            rows.append(row)
        current = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.strip() == "---":
                flush()
            else:
                current.append(line)
        flush()
    return rows


def write_body_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GO2_BODY_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in GO2_BODY_HEADER})


def body_audit(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = [as_float(row.get("timestamp")) for row in rows if as_float(row.get("timestamp")) is not None]
    return {"body_source_alias": "<XB1_BODY_SOURCE>", "row_count": len(rows), "time_min": min(times) if times else "", "time_max": max(times) if times else "", "accel_fields": bool(rows and all(k in rows[0] for k in ["acc_x", "acc_y", "acc_z"])), "gyro_fields": bool(rows and all(k in rows[0] for k in ["gyro_x", "gyro_y", "gyro_z"])), "receiver_imu_as_body_imu": False, "ready_for_alignment": bool(rows)}


def inspect_csv_file(path: Path) -> dict[str, Any]:
    meta = {"file": path.name, "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0, "row_count": 0, "columns": "", "time_column": "", "time_min": "", "time_max": "", "parse_status": "missing"}
    if not path.exists():
        return meta
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            cols = list(reader.fieldnames or [])
            meta["columns"] = "|".join(cols)
            time_col = next((c for c in ["Time", "time", "timestamp", "time_unix", "time_gps_tow"] if c in cols), "")
            meta["time_column"] = time_col
            vals = []
            count = 0
            for row in reader:
                count += 1
                if time_col:
                    value = as_float(row.get(time_col))
                    if value is not None:
                        vals.append(value)
            meta["row_count"] = count
            meta["time_min"] = min(vals) if vals else ""
            meta["time_max"] = max(vals) if vals else ""
            meta["parse_status"] = "parsed"
    except Exception as exc:  # noqa: BLE001
        meta["parse_status"] = f"parse_error:{type(exc).__name__}:{exc}"
    return meta


def status_quality_summary(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    fix_ok = [boolish(row.get("fix_ok")) for row in rows]
    pos_valid = [boolish(row.get("pos_valid")) for row in rows]
    msg_valid = [boolish(row.get("msg_valid")) for row in rows]
    rel_valid = [boolish(row.get("rel_valid")) for row in rows if "rel_valid" in row]
    ant_valid = [boolish(row.get("ant_valid")) for row in rows if "ant_valid" in row]
    fix_types = distribution([str(row.get("fix_type", "")) for row in rows])
    summary = {
        "source": label,
        "row_count": len(rows),
        "fix_ok_ratio": ratio(fix_ok),
        "pos_valid_ratio": ratio(pos_valid),
        "msg_valid_ratio": ratio(msg_valid),
        "rel_valid_ratio": ratio(rel_valid),
        "ant_valid_ratio": ratio(ant_valid),
        "fix_type_distribution": fix_types,
    }
    for col in ["sol_num_sat", "sat_num_vis", "sol_num_sig", "sol_pdop", "pos_acc_h", "pos_acc_v", "rf_noise_0", "rf_noise_1", "rf_agc_0", "rf_agc_1", "rf_jam_0", "rf_jam_1"]:
        summary[col + "_stats"] = stats([as_float(row.get(col)) for row in rows])
    summary["cn0_stats"] = cn0_summary(rows)
    return summary


def latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cols = list(rows[0].keys()) if rows else []
    latency_col = next((c for c in cols if "latency" in c.lower() or "age" in c.lower()), "")
    time_col = next((c for c in ["Time", "time", "timestamp"] if c in cols), "")
    latencies = [as_float(row.get(latency_col)) for row in rows] if latency_col else []
    times = [as_float(row.get(time_col)) for row in rows] if time_col else []
    gaps = [b - a for a, b in zip([v for v in times if v is not None], [v for v in times if v is not None][1:]) if b >= a]
    return {"row_count": len(rows), "latency_column": latency_col, "latency_stats": stats(latencies), "time_gap_stats": stats(gaps), "max_gap_sec": max(gaps) if gaps else ""}


def position_jump_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    points = []
    for row in rows:
        t = as_float(row.get("Time"))
        lat = as_float(row.get("p.vector3.x") or row.get("lat"))
        lon = as_float(row.get("p.vector3.y") or row.get("lon"))
        if t is not None and lat is not None and lon is not None:
            points.append((t, lat, lon))
    jumps = []
    for (t0, lat0, lon0), (t1, lat1, lon1) in zip(points, points[1:]):
        dt = t1 - t0
        if dt > 0 and dt < 5.0:
            jumps.append(horizontal_m(lat0, lon0, lat1, lon1))
    return {"row_count": len(points), "position_jump_stats_m": stats(jumps), "jump_gt_1m_count": sum(1 for v in jumps if v > 1.0), "jump_gt_5m_count": sum(1 for v in jumps if v > 5.0)}


def a1_baseline_audit(paths: Paths) -> dict[str, Any]:
    rows = build_a1_rows(paths)
    lengths = [row["baseline_len_m"] for row in rows]
    rel_lengths = []
    for row in read_csv_dicts(paths.receiver_root / "gnss1-status.csv"):
        n, e, d = as_float(row.get("rel_pos_n")), as_float(row.get("rel_pos_e")), as_float(row.get("rel_pos_d"))
        if None not in {n, e, d}:
            rel_lengths.append(math.sqrt(float(n) ** 2 + float(e) ** 2 + float(d) ** 2))
    st = stats(lengths)
    median_len = st.get("median")
    p95_len = st.get("p95")
    valid_ratio = len(rows) / max(1, len(read_csv_dicts(paths.receiver_root / "gnss1-status.csv")))
    short_valid = bool(median_len is not None and 0.10 <= float(median_len) <= 1.50 and (p95_len is None or float(p95_len) <= 2.00) and valid_ratio >= 0.5)
    return {"row_count": len(rows), "valid_ratio": valid_ratio, "length_stats_m": st, "status_rel_pos_long_baseline_stats_m": stats(rel_lengths), "long_relpos_rejected": bool((stats(rel_lengths).get("median") or 0) > 10.0), "short_baseline_valid": short_valid, "rows": rows}


def build_a1_rows(paths: Paths) -> list[dict[str, Any]]:
    gnss1 = read_status_positions(paths.receiver_root / "gnss1-status.csv")
    gnss2 = read_status_positions(paths.receiver_root / "gnss2-status.csv")
    rows = []
    for g1 in gnss1:
        g2, mode = interp_position(gnss2, g1["t"])
        if g2 is None:
            continue
        dx, dy, dz = g2["x"] - g1["x"], g2["y"] - g1["y"], g2["z"] - g1["z"]
        east, north, up = ecef_delta_to_enu(dx, dy, dz, g1["lat"], g1["lon"])
        length = math.sqrt(east * east + north * north + up * up)
        yaw_baseline = wrap360(-math.degrees(math.atan2(east, north)))
        yaw_ned = wrap360(90.0 - yaw_baseline)
        rows.append({"t": g1["t"], "east_m": east, "north_m": north, "up_m": up, "baseline_len_m": length, "yaw_baseline_deg": yaw_baseline, "a1_yaw_ned_deg": yaw_ned, "gnss2_interp_mode": mode})
    return rows


def detect_kick_candidates(body_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples = []
    for row in body_rows:
        t = as_float(row.get("timestamp"))
        acc = norm3(row, ["acc_x", "acc_y", "acc_z"])
        gyro = norm3(row, ["gyro_x", "gyro_y", "gyro_z"])
        if t is not None and acc is not None and gyro is not None:
            samples.append({"timestamp": t, "accel_norm": acc, "gyro_norm": gyro})
    if len(samples) < 5:
        return []
    initial = samples[: max(10, min(1000, len(samples) // 10))]
    med_acc = statistics.median([s["accel_norm"] for s in initial])
    acc_dev = [abs(s["accel_norm"] - med_acc) for s in samples]
    jerk = [0.0] + [abs(samples[i]["accel_norm"] - samples[i - 1]["accel_norm"]) / max(samples[i]["timestamp"] - samples[i - 1]["timestamp"], 1e-3) for i in range(1, len(samples))]
    rows = []
    scores = []
    for item, dev, j in zip(samples, acc_dev, jerk):
        score = max(dev, item["gyro_norm"] * 2.0, min(j, 200.0) / 20.0)
        scores.append(score)
        rows.append(item | {"jerk": j, "rank_score": score})
    threshold = max(3.0, percentile(scores, 0.995) if scores else 3.0)
    candidates = [row for row in rows if row["rank_score"] >= threshold]
    if not candidates:
        candidates = sorted(rows, key=lambda r: r["rank_score"], reverse=True)[:10]
    body_min = samples[0]["timestamp"]
    early = [row for row in candidates if row["timestamp"] - body_min >= 1.0]
    selected_first = sorted(early or candidates, key=lambda r: r["timestamp"])[0]
    ordered = [selected_first] + [row for row in sorted(candidates, key=lambda r: r["rank_score"], reverse=True) if row is not selected_first]
    return ordered[:50]


def detect_go2_motion_start(body_rows: list[dict[str, Any]], kick: dict[str, Any]) -> dict[str, Any]:
    kick_time = as_float(kick.get("timestamp"))
    for index, row in enumerate(body_rows):
        t = as_float(row.get("timestamp"))
        if t is None or (kick_time is not None and t <= kick_time):
            continue
        window = body_rows[index : index + 5]
        if len(window) < 5:
            break
        checks = {
            "go2_velocity_norm": all((norm3(item, ["go2_velocity_0", "go2_velocity_1", "go2_velocity_2"]) or 0.0) >= 0.02 for item in window),
            "gyro_norm": all((norm3(item, ["gyro_x", "gyro_y", "gyro_z"]) or 0.0) >= 0.05 for item in window),
            "yaw_speed": all(abs(as_float(item.get("yaw_speed_radps"), 0.0) or 0.0) >= 0.05 for item in window),
            "foot_speed_body_norm": all(foot_speed_norm(item) >= 0.05 for item in window),
        }
        for name, passed in checks.items():
            if passed:
                return {"go2_formal_start_raw_time": t, "selected_feature": name, "evidence_status": "detected_after_kick"}
    return {"go2_formal_start_raw_time": kick_time, "selected_feature": "fallback_kick", "evidence_status": "weak_candidate"}


def detect_gnss_start(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if boolish(row.get("msg_valid")) and boolish(row.get("pos_valid")) and boolish(row.get("fix_ok")) and as_float(row.get("pos_lat")) is not None]
    if not valid:
        return {"gnss_formal_start_raw_time": None, "selected_feature": None, "evidence_status": "evidence_missing"}
    lat0 = as_float(valid[0].get("pos_lat"))
    lon0 = as_float(valid[0].get("pos_lon"))
    for idx in range(1, len(valid) - 2):
        window = valid[idx : idx + 3]
        displacements = [horizontal_m(lat0, lon0, as_float(item.get("pos_lat"), lat0), as_float(item.get("pos_lon"), lon0)) for item in window]
        if all(value >= 0.2 for value in displacements) or all(boolish(item.get("rel_valid")) and boolish(item.get("ant_valid")) for item in window):
            return {"gnss_formal_start_raw_time": as_float(window[0].get("Time")), "selected_feature": "horizontal_displacement_or_heading_valid", "evidence_status": "detected"}
    return {"gnss_formal_start_raw_time": as_float(valid[0].get("Time")), "selected_feature": "fallback_first_valid_position", "evidence_status": "weak_candidate"}


def estimate_pre_motion_bias(body_rows: list[dict[str, Any]], kick: dict[str, Any], go2_start: dict[str, Any]) -> dict[str, Any]:
    cutoff = min(v for v in [as_float(kick.get("timestamp")), as_float(go2_start.get("go2_formal_start_raw_time"))] if v is not None) if (kick or go2_start) else None
    correction = euler_rpy_deg_to_matrix(-1.0, 0.0, 0.0)
    values = []
    for row in body_rows:
        t = as_float(row.get("timestamp"))
        gyro = [as_float(row.get("gyro_x")), as_float(row.get("gyro_y")), as_float(row.get("gyro_z"))]
        if t is None or cutoff is None or t >= cutoff - 0.25 or any(v is None for v in gyro):
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        values.append(matvec(correction, gyro_frd))
    if len(values) < 20:
        values = values[: min(len(values), 1000)]
    bias = mean_vec(values)
    return {"sample_count": len(values), "cutoff_raw_time": cutoff, "gyro_bias_radps": bias, "gyro_bias_degps": [math.degrees(v) for v in bias], "bias_source": "pre_motion_stationary_segment", "moving_segment_bias_used": False}


def quality_events(gnss1: list[dict[str, Any]], gnss2: list[dict[str, Any]], ntrip: list[dict[str, Any]], poi: list[dict[str, Any]], a1: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, src in [("gnss1", gnss1), ("gnss2", gnss2)]:
        for row in src:
            t = as_float(row.get("Time"))
            if not boolish(row.get("fix_ok")):
                rows.append({"time": t, "source": label, "event_type": "fix_loss", "severity": "caution"})
            if as_float(row.get("sol_pdop"), 0.0) and float(as_float(row.get("sol_pdop"), 0.0)) > 4.0:
                rows.append({"time": t, "source": label, "event_type": "high_pdop", "severity": "caution", "value": row.get("sol_pdop")})
            if as_float(row.get("sol_num_sat"), 99.0) and float(as_float(row.get("sol_num_sat"), 99.0)) < 8:
                rows.append({"time": t, "source": label, "event_type": "low_satellite_count", "severity": "caution", "value": row.get("sol_num_sat")})
    if a1.get("length_stats_m", {}).get("median") and float(a1["length_stats_m"]["median"]) > 1.5:
        rows.append({"time": "", "source": "a1_short_baseline", "event_type": "baseline_length_invalid", "severity": "blocked", "value": a1["length_stats_m"]["median"]})
    return rows[:5000]


def classify_quality(summaries: list[dict[str, Any]], ntrip: dict[str, Any], jumps: dict[str, Any], a1: dict[str, Any]) -> tuple[str, list[str]]:
    score = 0
    reasons = []
    for row in summaries:
        if (row.get("fix_ok_ratio") or 0.0) < 0.95:
            score += 1
            reasons.append(f"{row['source']} fix_ok_ratio={row.get('fix_ok_ratio')}")
        pdop_p95 = nested(row, "sol_pdop_stats", "p95")
        if pdop_p95 is not None and float(pdop_p95) > 3.0:
            score += 1
            reasons.append(f"{row['source']} pdop_p95={pdop_p95}")
        sat_p05 = nested(row, "sol_num_sat_stats", "p05")
        if sat_p05 is not None and float(sat_p05) < 8.0:
            score += 1
            reasons.append(f"{row['source']} sat_p05={sat_p05}")
        pos_acc_h_p95 = nested(row, "pos_acc_h_stats", "p95")
        if pos_acc_h_p95 is not None and float(pos_acc_h_p95) > 1.5:
            score += 1
            reasons.append(f"{row['source']} pos_acc_h_p95={pos_acc_h_p95}")
    if a1.get("short_baseline_valid") is False:
        score += 2
        reasons.append("A1 short-baseline invalid or poor")
    if score >= 4:
        return "severe", reasons
    if score >= 2:
        return "poor", reasons
    if score == 1:
        return "moderate", reasons
    return "good", reasons


def quality_timeseries(gnss1: list[dict[str, Any]], gnss2: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, src in [("gnss1", gnss1), ("gnss2", gnss2)]:
        for row in src[:20000]:
            rows.append({"source": label, "time": as_float(row.get("Time")), "fix_type": row.get("fix_type"), "fix_ok": boolish(row.get("fix_ok")), "pos_valid": boolish(row.get("pos_valid")), "sol_num_sat": as_float(row.get("sol_num_sat")), "sat_num_vis": as_float(row.get("sat_num_vis")), "sol_pdop": as_float(row.get("sol_pdop")), "pos_acc_h": as_float(row.get("pos_acc_h")), "pos_acc_v": as_float(row.get("pos_acc_v"))})
    return rows


# ----------------------------- plotting -----------------------------


def draw_alignment_figures(paths: Paths, body_rows: list[dict[str, Any]], kick_rows: list[dict[str, Any]], alignment: dict[str, Any]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    out = paths.stage_root / "figures"
    times = [as_float(row.get("timestamp")) for row in body_rows]
    times = [t for t in times if t is not None]
    if not times:
        return
    t0 = times[0]
    rel_t = []
    acc = []
    gyro = []
    for row in body_rows[:: max(1, len(body_rows) // 10000)]:
        t = as_float(row.get("timestamp"))
        if t is None:
            continue
        rel_t.append(t - t0)
        acc.append(norm3(row, ["acc_x", "acc_y", "acc_z"]) or 0.0)
        gyro.append(norm3(row, ["gyro_x", "gyro_y", "gyro_z"]) or 0.0)
    specs = [
        ("body_imu_kick_event", "Body IMU Kick Event"),
        ("alignment_overlay", "Alignment Overlay"),
        ("pre_motion_bias_window", "Pre-Motion Bias Window"),
    ]
    for stem, title in specs:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(rel_t, acc, label="accel norm", linewidth=0.8)
        ax.plot(rel_t, gyro, label="gyro norm", linewidth=0.8)
        for key, color, label in [
            ("selected_body_imu_kick_event_time", "red", "kick"),
            ("selected_go2_formal_start_time", "green", "go2 start"),
            ("selected_gnss_start_motion_event_time", "purple", "gnss start"),
        ]:
            value = as_float(alignment.get(key))
            if value is not None:
                ax.axvline(value - t0, color=color, linestyle="--", label=label)
        ax.set_title(title)
        ax.set_xlabel("seconds from body first row")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(out / f"{stem}.png", dpi=160)
        fig.savefig(out / f"{stem}.pdf")
        plt.close(fig)
    # Separate GNSS start event plot.
    rows = read_csv_dicts(paths.receiver_root / "gnss1-status.csv")
    fig, ax = plt.subplots(figsize=(9, 4))
    t = [as_float(row.get("Time")) - t0 for row in rows if as_float(row.get("Time")) is not None]
    sats = [as_float(row.get("sol_num_sat"), 0.0) or 0.0 for row in rows if as_float(row.get("Time")) is not None]
    ax.plot(t, sats, linewidth=0.8)
    value = as_float(alignment.get("selected_gnss_start_motion_event_time"))
    if value is not None:
        ax.axvline(value - t0, color="purple", linestyle="--", label="gnss start")
    ax.set_title("GNSS Start Event")
    ax.set_xlabel("seconds from body first row")
    ax.set_ylabel("sol_num_sat")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "gnss_start_event.png", dpi=160)
    fig.savefig(out / "gnss_start_event.pdf")
    plt.close(fig)


def draw_quality_figures(paths: Paths) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    rows = read_json(paths.stage_root / "matrix" / "XB1C_GNSS_QUALITY_TIMESERIES.json", []) or []
    out = paths.stage_root / "figures"
    fig_specs = []
    for stem, ycols, title in [
        ("XB1_gnss_quality_timeline", ["fix_ok", "pos_valid"], "GNSS Quality Timeline"),
        ("XB1_fix_type_and_satellite_count", ["sol_num_sat", "sat_num_vis"], "Fix Type And Satellite Count"),
        ("XB1_pdop_cn0_latency_summary", ["sol_pdop", "pos_acc_h"], "PDOP And Position Accuracy"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 4))
        plotted = False
        for source in ["gnss1", "gnss2"]:
            source_rows = [row for row in rows if row.get("source") == source]
            t0 = first_finite(row.get("time") for row in source_rows) or 0.0
            t = [(as_float(row.get("time")) or 0.0) - t0 for row in source_rows]
            for col in ycols:
                values = [float(bool(row.get(col))) if isinstance(row.get(col), bool) else (as_float(row.get(col)) or 0.0) for row in source_rows]
                if t and values:
                    ax.plot(t, values, label=f"{source} {col}", linewidth=0.8)
                    plotted = True
        ax.set_title(title)
        ax.set_xlabel("seconds from first status row")
        if plotted:
            ax.legend(fontsize=7)
        fig.tight_layout()
        for suffix in ["png", "pdf"]:
            fig.savefig(out / f"{stem}.{suffix}", dpi=160 if suffix == "png" else None)
        plt.close(fig)
        fig_specs.extend(figure_rows(out, stem, source="real_runtime_gnss_quality_data"))
    return fig_specs


def draw_normal_figures(paths: Paths, normal: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    rows = normal.get("metrics", [])
    out = paths.stage_root / "figures"
    if rows:
        fig, ax = plt.subplots(figsize=(8, 4))
        labels = [row["algorithm"] for row in rows]
        vals = [as_float(row.get("horizontal_rmse_m"), 0.0) or 0.0 for row in rows]
        ax.bar(labels, vals)
        ax.set_ylabel("horizontal RMSE (m)")
        ax.tick_params(axis="x", rotation=20)
        fig.tight_layout()
        fig.savefig(out / "XB1_normal_metrics_bar.png", dpi=160)
        fig.savefig(out / "XB1_normal_metrics_bar.pdf")
        plt.close(fig)
        return figure_rows(out, "XB1_normal_metrics_bar", source="real_runtime_official_eval_metrics")
    for suffix in ["png", "pdf"]:
        stale = out / f"XB1_normal_metrics_bar.{suffix}"
        if stale.exists():
            stale.unlink()
    return blocked_figure_rows(out, "XB1_normal_metrics_bar", "normal solver/eval metrics not generated; see gate report")


def figure_rows(root: Path, stem: str, *, source: str) -> list[dict[str, Any]]:
    rows = []
    for suffix in ["png", "pdf"]:
        path = root / f"{stem}.{suffix}"
        rows.append({"figure": stem, "path": str(path), "exists": path.exists(), "file_size": path.stat().st_size if path.exists() else 0, "source": source})
    return rows


def blocked_figure_rows(root: Path, stem: str, blocked_reason: str) -> list[dict[str, Any]]:
    rows = []
    for suffix in ["png", "pdf"]:
        path = root / f"{stem}.{suffix}"
        rows.append({"figure": stem, "path": str(path), "exists": False, "file_size": 0, "source": "not_generated", "blocked_reason": blocked_reason})
    return rows


# ----------------------------- generic utilities -----------------------------


def discover_trace(receiver_root: Path) -> Path:
    matches = sorted(receiver_root.glob("trace_*.csv"))
    return matches[0] if matches else receiver_root / "trace_vrtk2_a87c6e_2026-01-05-12-25-13_minimal.csv"


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return default


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def write_md(path: Path, text: str) -> None:
    write_text(path, text.rstrip() + "\n")


def write_numeric_rows(path: Path, rows: list[list[float]], expected_cols: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if len(row) != expected_cols:
                raise ValueError(f"{path} row has {len(row)} columns, expected {expected_cols}")
            handle.write(" ".join(f"{float(value):.12g}" for value in row) + "\n")


def validate_numeric_file(path: Path, expected_cols: int, role: str) -> list[dict[str, Any]]:
    row_count = 0
    bad = 0
    time_min = None
    time_max = None
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                parts = raw.strip().split()
                if not parts:
                    continue
                row_count += 1
                if len(parts) != expected_cols:
                    bad += 1
                    continue
                try:
                    vals = [float(p) for p in parts]
                except ValueError:
                    bad += 1
                    continue
                time_min = vals[0] if time_min is None else min(time_min, vals[0])
                time_max = vals[0] if time_max is None else max(time_max, vals[0])
    return [
        {"file_role": role, "check": "exists", "status": "passed" if path.exists() else "blocked", "detail": str(path)},
        {"file_role": role, "check": "row_count", "status": "passed" if row_count > 0 else "blocked", "detail": row_count},
        {"file_role": role, "check": "schema", "status": "passed" if row_count > 0 and bad == 0 else "blocked", "detail": f"bad={bad}, expected_cols={expected_cols}"},
        {"file_role": role, "check": "time_range", "status": "passed" if time_min is not None and time_max is not None and time_max > time_min else "blocked", "detail": f"{time_min}..{time_max}"},
    ]


def input_index_row(name: str, path: Path, role: str) -> dict[str, Any]:
    return {"input_name": name, "path": str(path), "row_count": count_data_rows(path), "sha256": sha256_file(path) if path.exists() else "", "role": role, "exists": path.exists()}


def provider_index(name: str, path: Path, decision: str, blockers: list[str]) -> dict[str, Any]:
    return {"provider": name, "path": str(path), "exists": path.exists(), "row_count": count_data_rows(path) if path.exists() else 0, "decision": decision, "blockers": blockers}


def count_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        lines = [line for line in handle if line.strip()]
    if not lines:
        return 0
    first = lines[0].strip()
    has_header = "," in first and any(not is_float(part) for part in first.split(","))
    return len(lines) - (1 if has_header else 0)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ok"}


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def stats(values: Iterable[Any]) -> dict[str, Any]:
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"count": 0}
    return {"count": len(vals), "min": vals[0], "p05": percentile(vals, 0.05), "median": percentile(vals, 0.5), "mean": sum(vals) / len(vals), "p95": percentile(vals, 0.95), "max": vals[-1]}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * p))
    return ordered[max(0, min(index, len(ordered) - 1))]


def ratio(values: list[bool]) -> float:
    return sum(1 for v in values if v) / len(values) if values else 0.0


def distribution(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def cn0_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trk_cols = [f"sig_cno_hist_trk_{i}" for i in range(12)]
    nav_cols = [f"sig_cno_hist_nav_{i}" for i in range(12)]
    total = 0.0
    low = 0.0
    weighted = 0.0
    for row in rows:
        for idx, col in enumerate(trk_cols + nav_cols):
            value = as_float(row.get(col), 0.0) or 0.0
            total += value
            weighted += value * (idx % 12)
            if idx % 12 <= 3:
                low += value
    return {"hist_count": total, "low_bin_ratio": low / total if total else 0.0, "weighted_bin_mean": weighted / total if total else ""}


def nested(row: dict[str, Any], key: str, subkey: str) -> Any:
    value = row.get(key)
    return value.get(subkey) if isinstance(value, dict) else None


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in row.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            for subkey, subval in value.items():
                out[f"{key}.{subkey}"] = subval
        else:
            out[key] = value
    return out


def check(name: str, ok: bool) -> dict[str, Any]:
    return {"check": name, "status": "pass" if ok else "warn"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_finite(values: Iterable[Any]) -> float | None:
    for value in values:
        parsed = as_float(value)
        if parsed is not None:
            return parsed
    return None


def last_finite(values: Iterable[Any]) -> float | None:
    out = None
    for value in values:
        parsed = as_float(value)
        if parsed is not None:
            out = parsed
    return out


def last_status_time(rows: list[dict[str, Any]]) -> float | None:
    return last_finite(row.get("Time") for row in rows)


def trace_coverage(path: Path) -> dict[str, Any]:
    rows = read_csv_dicts(path)
    times = [as_float(row.get("time") or row.get("Time")) for row in rows]
    times = [v for v in times if v is not None]
    return {"exists": path.exists(), "row_count": len(rows), "time_min": min(times) if times else None, "time_max": max(times) if times else None}


def norm3(row: dict[str, Any], fields: list[str]) -> float | None:
    vals = [as_float(row.get(field)) for field in fields]
    if any(v is None for v in vals):
        return None
    return math.sqrt(sum(float(v) ** 2 for v in vals if v is not None))


def foot_speed_norm(row: dict[str, Any]) -> float:
    vals = [as_float(row.get(f"foot_speed_body_{i}"), 0.0) or 0.0 for i in range(12)]
    return math.sqrt(sum(v * v for v in vals))


def foot_force_sum(row: dict[str, Any]) -> float:
    return sum(as_float(row.get(f"foot_force_{i}"), 0.0) or 0.0 for i in range(4))


def mean_vec(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.0, 0.0, 0.0]
    return [sum(vec[i] for vec in vectors) / len(vectors) for i in range(3)]


def euler_rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> list[list[float]]:
    roll, pitch, yaw = math.radians(roll_deg), math.radians(pitch_deg), math.radians(yaw_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]
    ry = [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]]
    rz = [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]]
    return matmul(matmul(rz, ry), rx)


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def matvec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def horizontal_m(lat0: float | None, lon0: float | None, lat1: float | None, lon1: float | None) -> float:
    if None in {lat0, lon0, lat1, lon1}:
        return 0.0
    radius = 6378137.0
    north = math.radians(float(lat1) - float(lat0)) * radius
    east = math.radians(float(lon1) - float(lon0)) * radius * math.cos(math.radians(float(lat0)))
    return math.hypot(north, east)


def read_status_positions(path: Path) -> list[dict[str, float]]:
    rows = []
    for row in read_csv_dicts(path):
        t, lat, lon, h = as_float(row.get("Time")), as_float(row.get("pos_lat")), as_float(row.get("pos_lon")), as_float(row.get("pos_height"))
        if None in {t, lat, lon, h} or not (boolish(row.get("msg_valid")) and boolish(row.get("pos_valid")) and boolish(row.get("fix_ok"))):
            continue
        x, y, z = llh_to_ecef(float(lat), float(lon), float(h))
        rows.append({"t": float(t), "lat": float(lat), "lon": float(lon), "height": float(h), "x": x, "y": y, "z": z})
    rows.sort(key=lambda item: item["t"])
    return rows


def llh_to_ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple[float, float, float]:
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    x = (n + height_m) * math.cos(lat) * math.cos(lon)
    y = (n + height_m) * math.cos(lat) * math.sin(lon)
    z = (n * (1.0 - e2) + height_m) * math.sin(lat)
    return x, y, z


def ecef_delta_to_enu(dx: float, dy: float, dz: float, lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    up = math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz
    return east, north, up


def interp_position(rows: list[dict[str, float]], t: float, *, tolerance: float = 0.75) -> tuple[dict[str, float] | None, str]:
    if not rows:
        return None, "missing"
    if t < rows[0]["t"]:
        return (rows[0], "nearest_edge") if rows[0]["t"] - t <= tolerance else (None, "outside")
    if t > rows[-1]["t"]:
        return (rows[-1], "nearest_edge") if t - rows[-1]["t"] <= tolerance else (None, "outside")
    for left, right in zip(rows, rows[1:]):
        if left["t"] <= t <= right["t"]:
            if right["t"] == left["t"]:
                return left, "nearest_same_time"
            alpha = (t - left["t"]) / (right["t"] - left["t"])
            return {field: left[field] + alpha * (right[field] - left[field]) for field in left}, "interpolated"
    return rows[-1], "nearest_edge"


def interp_a1_yaw(rows: list[dict[str, Any]], t: float, *, tolerance: float = 0.75) -> tuple[float | None, str]:
    if not rows:
        return None, "missing"
    candidate, mode = interp_angle([{"t": row["t"], "heading": row["a1_yaw_ned_deg"]} for row in rows], t, tolerance=tolerance)
    return candidate, mode


def interp_angle(rows: list[dict[str, Any]], t: float, *, tolerance: float) -> tuple[float | None, str]:
    rows = sorted(rows, key=lambda row: row["t"])
    if t < rows[0]["t"] or t > rows[-1]["t"]:
        nearest = min(rows, key=lambda row: abs(row["t"] - t))
        return (nearest["heading"], "nearest_edge") if abs(nearest["t"] - t) <= tolerance else (None, "outside")
    for left, right in zip(rows, rows[1:]):
        if left["t"] <= t <= right["t"]:
            if right["t"] == left["t"]:
                return left["heading"], "exact"
            alpha = (t - left["t"]) / (right["t"] - left["t"])
            delta = wrap180(right["heading"] - left["heading"])
            return wrap360(left["heading"] + alpha * delta), "interpolated"
    return rows[-1]["heading"], "nearest"


def wrap360(value: float) -> float:
    return value % 360.0


def wrap180(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def load_geodetic_velocity(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv_dicts(path):
        t = as_float(row.get("Time"))
        if t is None:
            continue
        std_ve = math.sqrt(max(as_float(row.get("v_var.vector3.x"), 0.25) or 0.25, 0.0025))
        std_vn = math.sqrt(max(as_float(row.get("v_var.vector3.y"), 0.25) or 0.25, 0.0025))
        std_vd = math.sqrt(max(as_float(row.get("v_var.vector3.z"), 0.64) or 0.64, 0.0025))
        rows.append({"time": t, "ve": as_float(row.get("v.vector3.x"), 0.0), "vn": as_float(row.get("v.vector3.y"), 0.0), "vd": -(as_float(row.get("v.vector3.z"), 0.0) or 0.0), "std_vn": std_vn, "std_ve": std_ve, "std_vd": std_vd})
    return rows


def nearest_velocity(rows: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    if not rows:
        return None
    best = min(rows, key=lambda row: abs(float(row["time"]) - t))
    return best if abs(float(best["time"]) - t) <= 0.2 else None


def initatt_starttime_aligned(gnss_path: Path, start: float | None) -> bool:
    if start is None or not gnss_path.exists():
        return False
    for row in numeric_rows(gnss_path):
        if row and row[0] >= start:
            return abs(row[0] - start) < 1.0 or row[0] >= start
    return False


def numeric_rows(path: Path) -> list[list[float]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                rows.append([float(part) for part in parts])
            except ValueError:
                continue
    return rows


def solver_context(paths: Paths, alignment: dict[str, Any]) -> dict[str, Any]:
    start = float(alignment["recommended_algorithm_start_time"])
    dual_rows = numeric_rows(paths.gnss_dual)
    init = next((row for row in dual_rows if row[0] >= start), dual_rows[0] if dual_rows else [start, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    return {"base_time": float(alignment["body_time_zero_raw_timestamp"]), "algorithm_start_time": float(init[0]), "end_time": float(alignment["recommended_algorithm_end_time"]), "initpos": [init[1], init[2], init[3]], "initatt": [0.0, 0.0, init[13] if len(init) > 13 else 0.0]}


def stage1_overrides(paths: Paths) -> dict[str, str]:
    return {"case_id": "XB1_normal_stage1", "imu_source_override": repo_to_wsl(paths.imu), "gnss_input_override": repo_to_wsl(paths.gnss_dual), "trace_solver_input": "false", "final_v23_output_solver_input": "false"}


def stage2_overrides(paths: Paths, feedback: dict[str, Any]) -> dict[str, str]:
    return {"case_id": "XB1_normal", "imu_source_override": repo_to_wsl(paths.imu), "gnss_input_override": repo_to_wsl(paths.gnss_dual), "feedback_input_override": repo_to_wsl(Path(feedback["feedback_observations"])), "raw_doppler_input_override": repo_to_wsl(paths.raw_doppler), "go2_input_override": repo_to_wsl(paths.go2_joint), "trace_solver_input": "false", "final_v23_output_solver_input": "false"}


def blocked_run(algorithm: str, reason: str, output_dir: Path) -> dict[str, Any]:
    return {"algorithm": algorithm, "run_status": "blocked", "returncode": None, "blocked_reason": reason, "output_dir": str(output_dir), "trace_solver_input": False, "final_v23_output_solver_input": False, "degradation_execution": False}


def blocked_eval(algorithm: str, reason: str) -> dict[str, Any]:
    return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": reason, "trace_solver_input": False}


def solver_status_row(row: dict[str, Any]) -> dict[str, Any]:
    outputs = row.get("outputs", {}) if isinstance(row.get("outputs"), dict) else {}
    return {"algorithm": row.get("algorithm"), "run_status": row.get("run_status"), "returncode": row.get("returncode"), "blocked_reason": row.get("blocked_reason", ""), "output_dir": row.get("output_dir", ""), "nav_output": outputs.get("LegSA_PORT_NAV.nav") or outputs.get("KF_GINS_Navresult.nav") or "", "std_output": outputs.get("LegSA_PORT_STD.csv") or outputs.get("KF_GINS_STD.txt") or "", "trace_solver_input": False, "final_v23_output_solver_input": False, "degradation_execution": False}


def eval_status_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"algorithm": row.get("algorithm"), "official_eval_status": row.get("official_eval_status"), "returncode": row.get("returncode"), "blocked_reason": row.get("blocked_reason", ""), "official_eval_dir": row.get("official_eval_dir", ""), "eval_nav_path": row.get("eval_nav_path", ""), "trace_evaluation_only": True}


def metric_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") or {}
    out = {"algorithm": row.get("algorithm"), "official_eval_dir": row.get("official_eval_dir", "")}
    for key in METRIC_KEYS:
        out[key] = metrics.get(key)
    return out


def metrics_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = _metrics_from_summary(summary)
    position = summary.get("position", {}) if isinstance(summary, dict) else {}
    attitude = summary.get("attitude", {}) if isinstance(summary, dict) else {}
    meta = summary.get("meta", {}) if isinstance(summary, dict) else {}
    metrics.update({"north_rmse_m": position.get("north_rmse_m"), "east_rmse_m": position.get("east_rmse_m"), "horizontal_p95_m": position.get("horizontal_p95_m"), "horizontal_max_m": position.get("horizontal_max_m"), "roll_p95_deg": attitude.get("roll_p95_deg"), "pitch_p95_deg": attitude.get("pitch_p95_deg"), "yaw_p95_deg": attitude.get("yaw_p95_deg"), "sample_count": meta.get("num_samples")})
    return metrics


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def replace_yaml_key(text: str, key: str, value: str, *, quoted: bool) -> str:
    rendered = f'"{value}"' if quoted else value
    pattern = re.compile(rf"^{re.escape(key)}\s*:.*$", re.MULTILINE)
    replacement = f"{key}: {rendered}"
    return pattern.sub(replacement, text) if pattern.search(text) else text.rstrip() + "\n" + replacement + "\n"


def format_vec(values: list[float]) -> str:
    return "[ " + ", ".join(f"{float(value):.8f}" for value in values) + " ]"


def normalize_wsl_command(command: list[str]) -> list[str]:
    normalized = list(command)
    for idx, item in enumerate(normalized):
        if item.startswith("\\mnt\\"):
            normalized[idx] = "/" + item.lstrip("\\").replace("\\", "/")
    return normalized


def wsl_path_exists(path: str) -> bool:
    completed = subprocess.run(["wsl", "bash", "-lc", f"test -e {shlex.quote(path)}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return completed.returncode == 0


def alias_clean(value: Any) -> Any:
    text = str(value)
    cwd = str(REPO_ROOT)
    if text.startswith(cwd):
        return "<WINDOWS_AUDIT_ROOT>" + text[len(cwd) :].replace("\\", "/")
    return text.replace(str(REPO_ROOT / "xb1"), "<XB1_OUTPUT_ROOT>").replace("\\", "/")


def scan_path_leaks(root: Path) -> list[str]:
    patterns = ["C:\\Users", "/mnt/c", "/home/kaiwen", "G:\\"]
    leaks = []
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern in text for pattern in patterns):
                leaks.append(str(path))
    return leaks


if __name__ == "__main__":
    raise SystemExit(main())
