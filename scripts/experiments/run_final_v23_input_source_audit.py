#!/usr/bin/env python3
"""Run N4H1 final_v23 input source-chain and yaw-generation audit.

中文说明：本脚本只做 read-only source-chain audit；不复制 KF-GINS 源码，不运行
proposed solver，不使用 trace 作为 solver input，不做 numerical performance claim。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.final_v23_input_audit import (  # noqa: E402
    audit_position_source,
    audit_position_std_source,
    audit_velocity_source,
    load_status_rows,
    make_final_v23_input_source_report,
    parse_final_v23_gnss_file,
    write_json,
)
from legsa_gins.evaluation.final_v23_yaw_chain_audit import (  # noqa: E402
    compare_final_v23_yaw_column,
    compute_a1_dual_diff_yaw,
)
from legsa_gins.experiments.by2_filter_trial import write_toy_standardized_inputs  # noqa: E402


PROCESS_KEYWORDS = [
    "process_data.py",
    "final_status_fixed",
    "final_status_fixed1p5",
    "A1_dual_diff",
    "rel_pos_n",
    "rel_pos_e",
    "yaw_std",
    "UBX-NAV-PVT",
    "pos_lat",
    "pos_lon",
    "pos_height",
    "pos_acc_h",
    "pos_acc_v",
]


def _standardize_inputs(args: argparse.Namespace, inputs_dir: Path) -> None:
    if args.toy:
        write_toy_standardized_inputs(inputs_dir, row_count=160)
        _rewrite_toy_heading_status(inputs_dir)
        return
    from scripts.datasets.standardize_by2_inputs import standardize_by2_inputs

    standardize_by2_inputs(
        fix_root=args.fix_root,
        body_imu=args.body_imu,
        output_dir=inputs_dir,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_body_messages=None,
    )


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _rewrite_toy_heading_status(inputs_dir: Path) -> None:
    for source_name in ["GNSS1", "GNSS2"]:
        path = inputs_dir / f"BY2_{source_name}_STATUS_STANDARD.csv"
        rows = _read_csv(path)
        if not rows:
            continue
        fieldnames = list(rows[0].keys())
        for row in rows:
            if source_name == "GNSS1":
                row["rel_pos_n_m"] = "0.0"
                row["rel_pos_e_m"] = "0.0"
            else:
                row["rel_pos_n_m"] = "1.0"
                row["rel_pos_e_m"] = "1.0"
            row["rel_pos_d_m"] = "0.0"
            row["rel_acc_n_m"] = "0.01"
            row["rel_acc_e_m"] = "0.01"
            row["rel_acc_d_m"] = "0.01"
            row["rel_valid"] = "true"
            row["ant_valid"] = "true"
            row["heading_valid"] = "true"
        _write_csv(path, rows, fieldnames)


def _write_toy_final_gnss(inputs_dir: Path, output_path: Path) -> Path:
    gnss1 = _read_csv(inputs_dir / "BY2_GNSS1_STATUS_STANDARD.csv")
    gnss2 = _read_csv(inputs_dir / "BY2_GNSS2_STATUS_STANDARD.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row1, row2 in zip(gnss1[:120], gnss2[:120]):
            yaw = compute_a1_dual_diff_yaw(row1, row2)["yaw_deg"]
            values = [
                row1["time_unix"],
                row1["lat_deg"],
                row1["lon_deg"],
                row1["height_m"],
                row1["pos_acc_h_m"],
                row1["pos_acc_h_m"],
                row1["pos_acc_v_m"],
                "0.1",
                "0.2",
                "-0.1",
                "0.05",
                "0.05",
                "0.05",
                f"{float(yaw):.6f}",
                "1.5",
            ]
            handle.write(" ".join(str(value) for value in values) + "\n")
    return output_path


def _write_toy_process_data(root: Path) -> Path:
    path = root / "bin/process_data.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# toy process_data.py for N4H1 audit",
                "def parse_ubx_pvt(data):",
                "    # UBX-NAV-PVT -> vn ve vd sAcc",
                "    return {'vn': 0.1, 've': 0.2, 'vd': -0.1, 'sAcc': 0.05}",
                "def build_status_baseline_yaw_df(g1, g2):",
                "    # A1_dual_diff uses rel_pos_n / rel_pos_e from gnss2 - gnss1",
                "    pass",
                "def write_final_status_fixed1p5_case():",
                "    # pos_lat pos_lon pos_height pos_acc_h pos_acc_v yaw_std final_status_fixed1p5",
                "    pass",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _source_summary_for_keyword(keyword: str) -> str:
    mapping = {
        "pos_lat": "position latitude upstream field",
        "pos_lon": "position longitude upstream field",
        "pos_height": "position height upstream field",
        "pos_acc_h": "horizontal position std upstream field",
        "pos_acc_v": "vertical position std upstream field",
        "UBX-NAV-PVT": "gnss1 raw velocity evidence keyword",
        "A1_dual_diff": "dual status rel_pos yaw scheme keyword",
        "rel_pos_n": "north baseline component keyword",
        "rel_pos_e": "east baseline component keyword",
        "yaw_std": "yaw std generation keyword",
        "final_status_fixed": "final status output keyword",
        "final_status_fixed1p5": "fixed 1.5 deg final status output keyword",
    }
    return mapping.get(keyword, "source-chain keyword")


def _search_process_data_source_map(source_root: Path) -> dict[str, Any]:
    candidates = list(source_root.rglob("process_data.py")) if source_root.exists() else []
    process_path = candidates[0] if candidates else None
    evidence: list[dict[str, Any]] = []
    found_keywords: dict[str, bool] = {keyword: False for keyword in PROCESS_KEYWORDS if keyword != "process_data.py"}
    if process_path and process_path.exists():
        for line_number, line in enumerate(process_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for keyword in found_keywords:
                if keyword in line:
                    found_keywords[keyword] = True
                    evidence.append(
                        {
                            "path": str(process_path),
                            "line": line_number,
                            "keyword": keyword,
                            "summary": _source_summary_for_keyword(keyword),
                        }
                    )
    if source_root.exists():
        for path in source_root.rglob("*"):
            if not path.is_file() or any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".md", ".txt", ".yaml", ".yml", ".json"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                for keyword in ["final_status_fixed", "final_status_fixed1p5"]:
                    if keyword in line:
                        found_keywords[keyword] = True
                        evidence.append(
                            {
                                "path": str(path),
                                "line": line_number,
                                "keyword": keyword,
                                "summary": _source_summary_for_keyword(keyword),
                            }
                        )
    found_position = all(found_keywords.get(keyword) for keyword in ["pos_lat", "pos_lon", "pos_height", "pos_acc_h", "pos_acc_v"])
    found_velocity = bool(found_keywords.get("UBX-NAV-PVT"))
    found_yaw = all(found_keywords.get(keyword) for keyword in ["A1_dual_diff", "rel_pos_n", "rel_pos_e", "yaw_std"])
    found_output = bool(found_keywords.get("final_status_fixed") or found_keywords.get("final_status_fixed1p5"))
    return {
        "phase": "N4H1",
        "process_data_path": str(process_path) if process_path else None,
        "found_position_mapping": found_position,
        "found_velocity_mapping": found_velocity,
        "found_yaw_mapping": found_yaw,
        "found_final_status_output": found_output,
        "keyword_hits": evidence,
        "evidence_missing": not bool(process_path),
        "copied_external_source": False,
        "external_source_read_only": True,
    }


def _make_review(path: Path, input_report: dict[str, Any], yaw_report: dict[str, Any], source_map: dict[str, Any]) -> None:
    lines = [
        "# final_v23 input source-chain review",
        "",
        "case_name: final_v23_input_source_chain_audit",
        "report_style_case_review: yes",
        "numerical_performance_claim: false",
        "final_v23_is_proposed: false",
        "",
        "## runtime actual input",
        "- final_v23 reads a 15-column `.gnss` file through gnsspath.",
        "- runtime columns: time, lat, lon, height, std_n, std_e, std_d, vn, ve, vd, std_vn, std_ve, std_vd, yaw, yaw_std.",
        f"- final_v23_gnss_file_status: {input_report.get('final_v23_gnss_file_status')}",
        "",
        "## upstream generation fields",
        "- position: gnss1-status pos_lat / pos_lon / pos_height.",
        "- position std: gnss1-status pos_acc_h / pos_acc_v.",
        "- velocity: gnss1-raw UBX-NAV-PVT vn / ve / vd / sAcc.",
        "- yaw: gnss1-status + gnss2-status rel_pos_n/e/d A1_dual_diff.",
        "- trace: evaluation-only and sanity checking; not final_v23 main positioning observation input.",
        "",
        "## Source Status",
        f"- position_source_status: {input_report.get('position_source_status')}",
        f"- position_std_source_status: {input_report.get('position_std_source_status')}",
        f"- velocity_source_status: {input_report.get('velocity_source_status')}",
        f"- yaw_source_status: {input_report.get('yaw_source_status')}",
        "",
        "## Yaw Chain",
        "- A1_dual_diff formula: b_n = rel_pos_n(gnss2) - rel_pos_n(gnss1); b_e = rel_pos_e(gnss2) - rel_pos_e(gnss1); yaw = -atan2(b_e,b_n).",
        f"- best_matching_candidate_to_final_gnss_yaw: {yaw_report.get('best_matching_candidate_to_final_gnss_yaw')}",
        f"- a1_dual_diff_matches_final_gnss_yaw: {str(yaw_report.get('a1_dual_diff_matches_final_gnss_yaw')).lower()}",
        "- formal_selection_allowed: false",
        "",
        "## process_data.py Source Map",
        f"- process_data_path: {source_map.get('process_data_path')}",
        f"- found_position_mapping: {str(source_map.get('found_position_mapping')).lower()}",
        f"- found_velocity_mapping: {str(source_map.get('found_velocity_mapping')).lower()}",
        f"- found_yaw_mapping: {str(source_map.get('found_yaw_mapping')).lower()}",
        f"- found_final_status_output: {str(source_map.get('found_final_status_output')).lower()}",
        "",
        "## Claim Boundary",
        "- trace_solver_input: false",
        "- final_v23_is_proposed: false",
        "- proposed_solver_output: false",
        "- output_only_correction: false",
        "- raw_doppler_claim: false",
        "- go2_prior_claim: false",
        "- source_aware_weighting_claim: false",
        "- fgo_smoother_claim: false",
        "- performance claim: false",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    inputs_dir = output_dir / "inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    _standardize_inputs(args, inputs_dir)
    process_root = output_dir / "toy_kf_gins" if args.toy else Path(args.process_data_root)
    if args.toy:
        _write_toy_process_data(process_root)
        final_v23_gnss = _write_toy_final_gnss(inputs_dir, output_dir / "toy_final_status_fixed1p5_case.gnss")
    else:
        final_v23_gnss = Path(args.final_v23_gnss) if args.final_v23_gnss else None

    source_map = _search_process_data_source_map(process_root)
    write_json(output_dir / "PROCESS_DATA_SOURCE_MAP.json", source_map)

    gnss1_rows = load_status_rows(inputs_dir / "BY2_GNSS1_STATUS_STANDARD.csv")
    gnss2_rows = load_status_rows(inputs_dir / "BY2_GNSS2_STATUS_STANDARD.csv")
    final_rows: list[dict[str, Any]] = []
    final_status = "evidence_missing"
    if final_v23_gnss is not None and final_v23_gnss.exists():
        final_rows = parse_final_v23_gnss_file(final_v23_gnss)
        final_status = "parsed_15_column_gnss"

    if final_rows:
        position_report = audit_position_source(final_rows, gnss1_rows)
        position_std_report = audit_position_std_source(final_rows, gnss1_rows)
        yaw_report = compare_final_v23_yaw_column(final_rows, gnss1_rows, gnss2_rows)
    else:
        position_report = {"position_source_status": "evidence_missing", "trace_solver_input": False}
        position_std_report = {"position_std_source_status": "evidence_missing", "trace_solver_input": False}
        yaw_report = {
            "yaw_column_source_status": "evidence_missing",
            "best_matching_candidate_to_final_gnss_yaw": None,
            "a1_dual_diff_matches_final_gnss_yaw": False,
            "formal_selection_allowed": False,
            "trace_solver_input": False,
            "final_v23_is_proposed": False,
        }

    velocity_report = audit_velocity_source(final_rows, [])
    if source_map.get("found_velocity_mapping"):
        velocity_report["velocity_source_status"] = "found_process_data_velocity_source"
        velocity_report["process_data_keyword_evidence"] = True

    input_report = make_final_v23_input_source_report(
        final_gnss_file_status=final_status,
        position_report=position_report,
        position_std_report=position_std_report,
        velocity_report=velocity_report,
        yaw_report=yaw_report,
        process_data_source_map=source_map,
    )
    input_report["final_v23_gnss_row_count"] = len(final_rows)
    input_report["raw_gnss_observation_input_claim"] = False
    write_json(output_dir / "FINAL_V23_INPUT_SOURCE_REPORT.json", input_report)
    yaw_report_for_write = dict(yaw_report)
    yaw_report_for_write.pop("candidate_rows", None)
    write_json(output_dir / "FINAL_V23_YAW_CHAIN_REPORT.json", yaw_report_for_write)
    _make_review(output_dir / "final_v23_input_source_chain_review.md", input_report, yaw_report_for_write, source_map)
    return {
        "output_dir": str(output_dir),
        "process_data_source_map": source_map,
        "input_report": input_report,
        "yaw_report": yaw_report_for_write,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", help="Local BY2 Fixposition root.")
    parser.add_argument("--body-imu", help="Local BY2 Go2 body-state text file.")
    parser.add_argument("--final-v23-gnss", help="Optional local final_v23 15-column .gnss input.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-status-rows", type=int, default=None)
    parser.add_argument("--max-raw-rows", type=int, default=None)
    parser.add_argument("--process-data-root", default="/home/kaiwen/KF-GINS")
    parser.add_argument("--toy", action="store_true", help="Use toy standardized inputs and toy process_data evidence.")
    args = parser.parse_args()
    if not args.toy and (not args.fix_root or not args.body_imu):
        parser.error("--fix-root and --body-imu are required unless --toy is used.")
    return args


def main() -> int:
    result = run_audit(_parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
