"""Official final_v23 case-review reproduction utilities for N4R.

中文说明：本模块只读取 official artifacts 和 evaluation-only trace/reference；
不复制外部源码，不把 trace 作为 solver input，不做 output-only correction。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import (
    compare_error_series,
    compare_summary_metrics,
    load_official_error_series,
    load_official_summary,
)
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M, summary_metrics, write_error_series
from legsa_gins.evaluation.yaw_evaluator_parity import (
    compute_errors_for_transforms,
    evaluate_yaw_transform_grid,
)
from legsa_gins.evaluation.yaw_convention_transforms import wrap_deg360
from legsa_gins.source_audit.final_v23_artifact_recovery import recover_final_v23_artifacts


ARTIFACT_NAMES = [
    "input.gnss",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "summary.json",
    "error_series.csv",
    "case_review.md",
]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _path(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    candidate = Path(path_text)
    return candidate if candidate.exists() else None


def _artifact_paths(group: dict[str, Any]) -> dict[str, Path]:
    artifacts = group.get("artifacts", {})
    return {name: path for name in ARTIFACT_NAMES if (path := _path(artifacts.get(name)))}


def _role_alias(group: dict[str, Any], name: str) -> str:
    group_id = group.get("group_id", group.get("role_alias", "ACTUAL_FINAL_V23_ARTIFACT_GROUP"))
    return f"{group_id}/{name}"


def _read_recovery_report(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size > 10_000_000:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _group_from_recovery_report(path: Path) -> dict[str, Any] | None:
    report = _read_recovery_report(path)
    if not report:
        return None
    group = report.get("best_final_v23_candidate_group") or report.get("best_actual_final_v23_candidate_group")
    if not isinstance(group, dict):
        return None
    if _artifact_paths(group):
        group.setdefault("role_alias", group.get("group_id", "ACTUAL_FINAL_V23_ARTIFACT_GROUP"))
        group["locate_source"] = "recovery_report"
        return group
    return None


def locate_actual_final_v23_artifact_group(
    recovery_report_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Locate the runtime-only actual final_v23 artifact group."""

    if recovery_report_path:
        group = _group_from_recovery_report(Path(recovery_report_path))
        if group:
            return group

    root = Path(artifact_root) if artifact_root else Path.home() / "KF-GINS"
    if all((root / name).exists() for name in ["KF_GINS_Navresult.nav", "summary.json"]):
        artifacts = {name: str(root / name) for name in ARTIFACT_NAMES if (root / name).exists()}
        return {
            "group_id": "ACTUAL_FINAL_V23_ARTIFACT_GROUP",
            "role_alias": "ACTUAL_FINAL_V23_ARTIFACT_GROUP",
            "root_role": "ACTUAL_FINAL_V23_ARTIFACT_GROUP",
            "artifacts": artifacts,
            "evidence_status": "candidate_final_v23_artifact_group",
            "locate_source": "direct_artifact_root",
        }

    report = recover_final_v23_artifacts({"EXTERNAL_KFGINS_ROOT": root}, max_depth=6)
    group = report.get("best_final_v23_candidate_group")
    if isinstance(group, dict):
        group.setdefault("role_alias", group.get("group_id", "ACTUAL_FINAL_V23_ARTIFACT_GROUP"))
        group["locate_source"] = "read_only_artifact_search"
        return group

    if artifact_root is None:
        for candidate_report in [
            Path("/tmp") / "legsa_n4h2c_deep_parity_audit_v2" / "FINAL_V23_ARTIFACT_RECOVERY_REPORT.json",
            Path("/tmp") / "legsa_n4h2c_deep_parity_audit" / "FINAL_V23_ARTIFACT_RECOVERY_REPORT.json",
        ]:
            group = _group_from_recovery_report(candidate_report)
            if group:
                return group

    return {
        "group_id": "ACTUAL_FINAL_V23_ARTIFACT_GROUP",
        "role_alias": "ACTUAL_FINAL_V23_ARTIFACT_GROUP",
        "artifacts": {},
        "evidence_status": "evidence_missing",
        "locate_source": "evidence_missing",
    }


def parse_kfgins_nav(path: str | Path) -> list[dict[str, float]]:
    """Parse KF_GINS_Navresult.nav without correcting or deleting epochs."""

    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        previous_time: float | None = None
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            fields = stripped.replace(",", " ").split()
            if len(fields) != 11:
                raise ValueError(f"{path}:{line_number} expected 11 columns, got {len(fields)}")
            week, time, lat, lon, height, vn, ve, vd, roll, pitch, yaw = [float(value) for value in fields]
            if previous_time is not None and time < previous_time:
                raise ValueError(f"{path}:{line_number} time must be monotonic non-decreasing")
            previous_time = time
            rows.append(
                {
                    "week": week,
                    "time": time,
                    "timestamp": time,
                    "lat": lat,
                    "lon": lon,
                    "height": height,
                    "lat_deg": lat,
                    "lon_deg": lon,
                    "height_m": height,
                    "vn": vn,
                    "ve": ve,
                    "vd": vd,
                    "roll": roll,
                    "pitch": pitch,
                    "yaw": yaw,
                    "roll_deg": roll,
                    "pitch_deg": pitch,
                    "yaw_deg": yaw,
                }
            )
    return rows


def load_eval_nav_csv(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            timestamp = float(raw.get("timestamp") or raw.get("tow") or raw.get("time"))
            rows.append(
                {
                    "timestamp": timestamp,
                    "time": timestamp,
                    "lat_deg": float(raw["lat_deg"]),
                    "lon_deg": float(raw["lon_deg"]),
                    "height_m": float(raw["height_m"]),
                    "roll_deg": float(raw["roll_deg"]),
                    "pitch_deg": float(raw["pitch_deg"]),
                    "yaw_deg": float(raw["yaw_deg"]),
                }
            )
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def _nearest_by_time(rows: list[dict[str, Any]], timestamp: float, start_index: int, tolerance: float) -> tuple[dict[str, Any] | None, int]:
    if not rows:
        return None, start_index
    index = min(max(start_index, 0), len(rows) - 1)
    while index + 1 < len(rows) and abs(float(rows[index + 1]["timestamp"]) - timestamp) <= abs(
        float(rows[index]["timestamp"]) - timestamp
    ):
        index += 1
    row = rows[index]
    return (row if abs(float(row["timestamp"]) - timestamp) <= tolerance else None), index


def reconstruct_reference_from_error_series(
    est_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> list[dict[str, float]]:
    """Recover evaluator reference rows from an estimate stream and error_series."""

    est_sorted = sorted(est_rows, key=lambda row: float(row["timestamp"]))
    err_sorted = sorted(
        [row for row in error_rows if "timestamp" in row],
        key=lambda row: float(row["timestamp"]),
    )
    ref_rows: list[dict[str, float]] = []
    est_index = 0
    for err in err_sorted:
        est, est_index = _nearest_by_time(est_sorted, float(err["timestamp"]), est_index, tolerance)
        if est is None:
            continue
        north = float(err.get("north_error_m", 0.0))
        east = float(err.get("east_error_m", 0.0))
        up = float(err.get("up_error_m", 0.0))
        ref_lat = float(est["lat_deg"]) - math.degrees(north / EARTH_RADIUS_M)
        cos_lat = math.cos(math.radians(ref_lat))
        if abs(cos_lat) < 1.0e-12:
            ref_lon = float(est["lon_deg"])
        else:
            ref_lon = float(est["lon_deg"]) - math.degrees(east / (EARTH_RADIUS_M * cos_lat))
        ref_rows.append(
            {
                "timestamp": float(err["timestamp"]),
                "time": float(err["timestamp"]),
                "lat_deg": ref_lat,
                "lon_deg": ref_lon,
                "height_m": float(est["height_m"]) - up,
                "roll_deg": float(est["roll_deg"]) - float(err.get("roll_error_deg", 0.0)),
                "pitch_deg": float(est["pitch_deg"]) - float(err.get("pitch_error_deg", 0.0)),
                "yaw_deg": wrap_deg360(float(est["yaw_deg"]) - float(err.get("yaw_error_deg", 0.0))),
            }
        )
    return ref_rows


def _reference_from_official_error_fields(error_rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    aliases = {
        "timestamp": ["reference_timestamp", "ref_timestamp", "truth_time", "time"],
        "lat_deg": ["reference_lat_deg", "ref_lat_deg", "truth_lat_deg", "lat_ref"],
        "lon_deg": ["reference_lon_deg", "ref_lon_deg", "truth_lon_deg", "lon_ref"],
        "height_m": ["reference_height_m", "ref_height_m", "truth_height_m", "height_ref"],
        "roll_deg": ["reference_roll_deg", "ref_roll_deg", "truth_roll_deg", "roll_ref"],
        "pitch_deg": ["reference_pitch_deg", "ref_pitch_deg", "truth_pitch_deg", "pitch_ref"],
        "yaw_deg": ["reference_yaw_deg", "ref_yaw_deg", "truth_yaw_deg", "yaw_ref"],
    }
    rows: list[dict[str, float]] = []
    for error in error_rows:
        out: dict[str, float] = {}
        for field, names in aliases.items():
            for name in names:
                if name in error:
                    out[field] = float(error[name])
                    break
        if all(field in out for field in aliases):
            out["time"] = out["timestamp"]
            rows.append(out)
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def _find_n4h2_reference_root(artifact_group: dict[str, Any]) -> Path:
    configured = artifact_group.get("n4h2_artifacts_root")
    return Path(configured) if configured else Path.home() / "legsa_n4h2_artifacts"


def load_trace_reference_for_case(
    artifact_group: dict[str, Any],
    external_source_root: str | Path,
) -> dict[str, Any]:
    """Load evaluation-only reference rows for official/replay parity."""

    artifacts = _artifact_paths(artifact_group)
    official_error_rows = (
        load_official_error_series(artifacts["error_series.csv"])
        if "error_series.csv" in artifacts
        else []
    )
    official_ref = _reference_from_official_error_fields(official_error_rows)
    if official_ref:
        return {
            "reference_rows": official_ref,
            "reference_source": "official_error_series_reference_fields",
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "evidence_status": "reference_loaded",
        }

    n4h2_root = _find_n4h2_reference_root(artifact_group)
    replay_nav = n4h2_root / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv"
    replay_errors = n4h2_root / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv"
    if replay_nav.exists() and replay_errors.exists():
        nav_rows = load_eval_nav_csv(replay_nav)
        error_rows = load_official_error_series(replay_errors)
        reference_rows = reconstruct_reference_from_error_series(nav_rows, error_rows)
        return {
            "reference_rows": reference_rows,
            "reference_source": "evidence_missing_or_by2_trace_fallback",
            "fallback_role": "N4H2_ARTIFACTS_ROOT/replay/evaluation",
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "evidence_status": "reference_loaded" if reference_rows else "evidence_missing",
        }

    _ = external_source_root
    return {
        "reference_rows": [],
        "reference_source": "evidence_missing",
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "evidence_status": "evidence_missing",
    }


def recompute_case_metrics(
    nav_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    yaw_transform_candidate: dict[str, str] | None = None,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    """Recompute metrics with optional yaw transform candidate."""

    candidate = yaw_transform_candidate or {"est_transform": "identity", "ref_transform": "identity"}
    errors = compute_errors_for_transforms(
        nav_rows,
        reference_rows,
        est_transform=candidate["est_transform"],
        ref_transform=candidate["ref_transform"],
    )
    summary = summary_metrics(errors)
    summary.update(
        {
            "est_transform": candidate["est_transform"],
            "ref_transform": candidate["ref_transform"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    )
    return errors, summary


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    official = report.get("official_summary", {})
    direct = report.get("direct_recompute_summary", {})
    best = report.get("best_transform_summary", {})
    best_candidate = report.get("best_yaw_transform_candidate") or {}
    lines = [
        "# N4R official final_v23 case-review reproduction",
        "",
        "This runtime report is evaluator-parity diagnostic only.",
        "",
        "## Scope",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- bad_epoch_deletion_for_metric=false",
        "- numerical_performance_claim=false",
        "- yaw transform candidates are evaluator diagnostics, not solver tuning",
        "",
        "## Metrics",
        "",
        f"- official horizontal_rmse_m: {official.get('horizontal_rmse_m')}",
        f"- official up_rmse_m: {official.get('up_rmse_m')}",
        f"- official yaw_rmse_deg: {official.get('yaw_rmse_deg')}",
        f"- direct horizontal_rmse_m: {direct.get('horizontal_rmse_m')}",
        f"- direct up_rmse_m: {direct.get('up_rmse_m')}",
        f"- direct yaw_rmse_deg: {direct.get('yaw_rmse_deg')}",
        f"- best candidate: {best_candidate.get('candidate_id')}",
        f"- best yaw_rmse_deg: {best.get('yaw_rmse_deg')}",
        f"- reference_source: {report.get('reference_source')}",
        f"- recommended_next_stage: {report.get('recommended_next_stage')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def reproduce_official_case_review(
    actual_artifact_group: dict[str, Any],
    *,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Reproduce official summary/error_series parity from actual artifacts."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = _artifact_paths(actual_artifact_group)
    missing = [name for name in ["KF_GINS_Navresult.nav", "summary.json", "error_series.csv"] if name not in artifacts]
    if missing:
        report = {
            "phase": "N4R",
            "artifact_group_id": actual_artifact_group.get("group_id"),
            "artifact_located": False,
            "evidence_status": "evidence_missing",
            "evidence_missing": missing,
            "recommended_next_stage": "N4R_artifact_recovery_fix",
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "OFFICIAL_CASE_REPRODUCTION_REPORT.json", report)
        return report

    official_summary = load_official_summary(artifacts["summary.json"])
    official_error_rows = load_official_error_series(artifacts["error_series.csv"])
    nav_rows = parse_kfgins_nav(artifacts["KF_GINS_Navresult.nav"])
    reference_bundle = load_trace_reference_for_case(
        actual_artifact_group,
        actual_artifact_group.get("external_source_root", Path.home() / "KF-GINS"),
    )
    reference_rows = reference_bundle.get("reference_rows", [])
    if not reference_rows:
        report = {
            "phase": "N4R",
            "artifact_group_id": actual_artifact_group.get("group_id"),
            "artifact_located": True,
            "evidence_status": "evidence_missing",
            "evidence_missing": ["reference_rows"],
            "official_summary": official_summary,
            "recommended_next_stage": "N4R_artifact_recovery_fix",
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "OFFICIAL_CASE_REPRODUCTION_REPORT.json", report)
        return report

    direct_errors, direct_summary = recompute_case_metrics(nav_rows, reference_rows)
    direct_summary_parity = compare_summary_metrics(official_summary, direct_summary)
    yaw_report = evaluate_yaw_transform_grid(
        nav_rows,
        reference_rows,
        official_summary=official_summary,
        official_error_rows=official_error_rows,
    )
    best_candidate = yaw_report.get("best_yaw_transform_candidate") or {}
    best_errors, best_summary = recompute_case_metrics(nav_rows, reference_rows, best_candidate)
    best_summary_parity = compare_summary_metrics(official_summary, best_summary)
    error_series_parity = compare_error_series(official_error_rows, best_errors)

    direct_yaw_diff = direct_summary_parity.get("metric_diff", {}).get("yaw_rmse_deg")
    best_yaw_diff = best_summary_parity.get("metric_diff", {}).get("yaw_rmse_deg")
    direct_passed = direct_yaw_diff is not None and abs(float(direct_yaw_diff)) < 0.1
    transform_needed = bool(
        not direct_passed
        and best_yaw_diff is not None
        and abs(float(best_yaw_diff)) < 0.1
    )
    recommended = (
        "N4R_fix_yaw_evaluator_convention"
        if transform_needed
        else "N4H2C_runtime_yaw_update_config_audit"
        if direct_passed
        else "N4R_artifact_recovery_fix"
    )
    report = {
        "phase": "N4R",
        "artifact_group_id": actual_artifact_group.get("group_id"),
        "artifact_role_aliases": {name: _role_alias(actual_artifact_group, name) for name in artifacts},
        "artifact_located": True,
        "evidence_status": "official_case_review_recomputed",
        "reference_source": reference_bundle.get("reference_source"),
        "official_summary": official_summary,
        "direct_recompute_summary": direct_summary,
        "best_transform_summary": best_summary,
        "direct_summary_parity": direct_summary_parity,
        "best_summary_parity": best_summary_parity,
        "official_error_series_parity": error_series_parity,
        "best_yaw_transform_candidate": {
            "candidate_id": best_candidate.get("candidate_id"),
            "est_transform": best_candidate.get("est_transform"),
            "ref_transform": best_candidate.get("ref_transform"),
        },
        "evaluator_direct_parity_passed": direct_passed,
        "evaluator_yaw_transform_needed": transform_needed,
        "evaluator_reference_source_mismatch": bool(not direct_passed and not transform_needed),
        "official_yaw_error_definition_identified": bool(
            error_series_parity.get("yaw_error_series_parity_status") == "passed"
        ),
        "recommended_next_stage": recommended,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

    _write_json(out / "OFFICIAL_CASE_REPRODUCTION_REPORT.json", report)
    _write_json(out / "OFFICIAL_YAW_EVALUATOR_PARITY_REPORT.json", yaw_report)
    _write_json(out / "OFFICIAL_ERROR_SERIES_PARITY_REPORT.json", error_series_parity)
    write_error_series(best_errors, out / "OFFICIAL_RECOMPUTED_BEST_ERROR_SERIES.csv")
    _write_markdown(out / "official_case_review_reproduction.md", report)
    return report
