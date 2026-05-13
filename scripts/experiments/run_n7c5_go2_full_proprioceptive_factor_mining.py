#!/usr/bin/env python3
"""Run N7C5 Go2 full proprioceptive factor mining.

中文说明：N7C5 系统挖掘 Go2 本体字段并排序候选因子；本阶段不正式激活
新增联合因子，不使用 trace/final_v23 输出调参，不提交 runtime 图表。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_probability_factor_review import (
    build_go2_contact_probability_factor_review,
    write_go2_contact_probability_factor_review,
)
from legsa_gins.go2_prior.go2_foot_kinematic_velocity_candidate import (
    build_go2_foot_kinematic_velocity_candidate,
    write_go2_foot_kinematic_velocity_outputs,
)
from legsa_gins.go2_prior.go2_full_field_inventory import (
    build_go2_full_field_inventory,
    read_csv_rows,
    write_go2_full_field_inventory,
)
from legsa_gins.go2_prior.go2_mode_gait_phase_model import (
    build_go2_mode_gait_phase_model,
    write_go2_mode_gait_phase_outputs,
)
from legsa_gins.go2_prior.go2_n7c5_decision import make_n7c5_decision, write_n7c5_decision
from legsa_gins.go2_prior.go2_n7c5_visual_plots import generate_n7c5_visual_plots
from legsa_gins.go2_prior.go2_proprioceptive_factor_ranking import (
    build_go2_proprioceptive_factor_ranking,
    write_go2_proprioceptive_factor_ranking,
)
from legsa_gins.go2_prior.go2_relative_odometry_candidate import (
    build_go2_relative_odometry_candidate,
    write_go2_relative_odometry_candidate,
)
from legsa_gins.go2_prior.go2_yawrate_consistency_candidate import (
    build_go2_yawrate_consistency_candidate,
    write_go2_yawrate_consistency_candidate,
)
from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    find_clean_gnss,
    find_factor_csv,
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7b4-root", required=True)
    parser.add_argument("--n7b5-root", required=True)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7c4-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _selected_contact_rows(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    selected = str(report.get("selected_contact_probability_model") or "")
    if selected:
        filtered = [row for row in rows if str(row.get("model_id") or "") == selected]
        if filtered:
            return filtered
    for preferred in ["force_speed_fused_probability", "ensemble_probability", "force_probability"]:
        filtered = [row for row in rows if str(row.get("model_id") or "") == preferred]
        if filtered:
            return filtered
    return rows


def _write_case_review(path: str | Path, *, inventory: dict[str, Any], contact: dict[str, Any], foot: dict[str, Any], phase: dict[str, Any], yaw: dict[str, Any], relative: dict[str, Any], ranking: dict[str, Any], decision: dict[str, Any], figures: dict[str, Any]) -> None:
    lines = [
        "# N7C5 Go2 full proprioceptive factor mining",
        "",
        f"- field row_count: {inventory.get('row_count')}",
        f"- all required groups available: {inventory.get('all_required_groups_available')}",
        f"- contact recommendation: {contact.get('recommendation')}",
        f"- foot activation candidate: {foot.get('activation_candidate')}",
        f"- foot rmse receiver/raw/go2: {foot.get('rmse_to_receiver')} / {foot.get('rmse_to_raw')} / {foot.get('rmse_to_go2_velocity')}",
        f"- phase counts: {phase.get('phase_counts')}",
        f"- yawrate status: {yaw.get('stability_status')}",
        f"- relative odometry status: {relative.get('relative_odometry_stability')}",
        f"- recommended EKF next factor: {ranking.get('recommended_EKF_next_factor')}",
        f"- decision: {decision.get('status')}",
        f"- next stage: {decision.get('recommended_next_stage')}",
        f"- figures: {figures.get('figure_count_total')}",
        "- Go2 fields are not truth.",
        "- No trace/final_v23 tuning, no output-only correction, no FGO activation, no paper performance claim.",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7C5 runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    go2_rows = read_csv_rows(Path(args.n7a_root) / "GO2_BODY_STATE_STANDARDIZED.csv")
    contact_all = read_csv_rows(Path(args.n7b4_root) / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    contact_report_source = _read_json(Path(args.n7b4_root) / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json")
    contact_rows = _selected_contact_rows(contact_all, contact_report_source)
    go2_velocity_rows = read_csv_rows(Path(args.n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    clean_gnss = find_clean_gnss(args.clean_root)
    receiver_rows = load_receiver_velocity_rows(clean_gnss)
    raw_rows = load_raw_doppler_factor_rows(find_factor_csv(args.n5b_root))
    n7c4_decision = _read_json(Path(args.n7c4_root) / "N7C4_STRENGTH_CALIBRATION_DECISION_REPORT.json")

    inventory = build_go2_full_field_inventory(go2_rows)
    write_go2_full_field_inventory(out / "GO2_FULL_FIELD_INVENTORY_REPORT.json", inventory)
    contact = build_go2_contact_probability_factor_review(contact_rows)
    write_go2_contact_probability_factor_review(out / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json", contact)
    phase_rows, phase = build_go2_mode_gait_phase_model(go2_rows, contact_rows)
    write_go2_mode_gait_phase_outputs(out, phase_rows, phase)
    foot_rows, foot = build_go2_foot_kinematic_velocity_candidate(
        go2_rows=go2_rows,
        contact_rows=contact_rows,
        go2_velocity_rows=go2_velocity_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
    )
    write_go2_foot_kinematic_velocity_outputs(out, foot_rows, foot)
    yaw = build_go2_yawrate_consistency_candidate(go2_rows, phase_rows)
    write_go2_yawrate_consistency_candidate(out / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json", yaw)
    relative = build_go2_relative_odometry_candidate(
        go2_rows,
        eval_nav_path=Path(args.n7c4_root) / "variants" / "fixed_1p0" / "EVAL_NAV.csv",
    )
    write_go2_relative_odometry_candidate(out / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json", relative)
    ranking = build_go2_proprioceptive_factor_ranking(
        inventory_report=inventory,
        contact_report=contact,
        foot_report=foot,
        phase_report=phase,
        yawrate_report=yaw,
        relative_report=relative,
        n7c4_decision=n7c4_decision,
    )
    write_go2_proprioceptive_factor_ranking(out / "GO2_PROPRIOCEPTIVE_FACTOR_RANKING_REPORT.json", ranking)
    preliminary = make_n7c5_decision(
        foot_report=foot,
        yawrate_report=yaw,
        relative_report=relative,
        ranking_report=ranking,
        n7c4_decision=n7c4_decision,
        figure_manifest={},
    )
    figures = generate_n7c5_visual_plots(
        figure_output_dir=figs,
        inventory_report=inventory,
        contact_rows=contact_rows,
        foot_rows=foot_rows,
        phase_rows=phase_rows,
        yawrate_report=yaw,
        relative_report=relative,
        ranking_report=ranking,
        decision=preliminary,
    )
    _write_json(out / "N7C5_FIGURE_MANIFEST.json", figures)
    decision = make_n7c5_decision(
        foot_report=foot,
        yawrate_report=yaw,
        relative_report=relative,
        ranking_report=ranking,
        n7c4_decision=n7c4_decision,
        figure_manifest=figures,
    )
    write_n7c5_decision(out / "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n7c5_go2_full_proprioceptive_factor_case_review.md",
        inventory=inventory,
        contact=contact,
        foot=foot,
        phase=phase,
        yaw=yaw,
        relative=relative,
        ranking=ranking,
        decision=decision,
        figures=figures,
    )
    run_report = {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "input_roles": {
            "n7a_root": "N7A_runtime_report_root",
            "n7b4_root": "N7B4_runtime_report_root",
            "n7b5_root": "N7B5_runtime_report_root",
            "n7c_root": "N7C_runtime_report_root",
            "n7c4_root": "N7C4_runtime_report_root",
            "n5b_root": "N5B_runtime_report_root",
            "n6b_root": "N6B_runtime_report_root",
            "clean_root": "clean_runtime_root",
            "dual_root": "dual_reference_runtime_root",
            "output_dir": "N7C5_runtime_output_root",
            "figure_output_dir": "N7C5_runtime_figure_root",
        },
        "inventory": inventory,
        "contact_probability_review": contact,
        "foot_kinematic_velocity_candidate": foot,
        "mode_gait_phase": phase,
        "yawrate_candidate": yaw,
        "relative_odometry_candidate": relative,
        "factor_ranking": ranking,
        "decision": decision,
        "figure_manifest": figures,
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "fgo": False,
    }
    _write_json(out / "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_RUN_REPORT.json", run_report)
    print(json.dumps({"inventory": inventory, "contact": contact, "foot": foot, "phase": phase, "yawrate": yaw, "relative": relative, "ranking": ranking, "decision": decision, "figures": figures}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
