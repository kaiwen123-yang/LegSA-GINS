"""Build N7B5 horizontal-only diagnostic Go2 velocity priors.

中文说明：N7B5 仅构造 runtime-only horizontal Go2 velocity diagnostic CSV；
vertical velocity 通过 std_vd=999 关闭，Go2 velocity 不是 truth，不启用正式 prior。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_probability_weighted_prior_builder import (
    PRIOR_FIELDS,
    _base_std,
    _confidence_bucket,
    _contact_label,
    _selected_probability_rows,
    _std_for_bucket,
)
from .go2_velocity_frame_internal_external_score import _candidate_velocity
from .go2_velocity_quality import _nearest_from_index
from .go2_horizontal_velocity_prior_policy import (
    POLICY_FRAME,
    POLICY_NAME,
    STD_VD_DISABLED,
    build_n7c_policy,
    confidence_bucket_from_quality,
    validate_n7c_policy,
)


HORIZONTAL_STD_VD_DISABLED = 999.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in PRIOR_FIELDS} for row in rows])


def _frame_for_policy(frame_equivalence_report: dict[str, Any], frame_score_report: dict[str, Any]) -> str:
    policy = str(frame_equivalence_report.get("recommended_horizontal_policy") or "")
    primary = str(frame_equivalence_report.get("primary_frame") or frame_score_report.get("best_candidate") or "")
    secondary = str(frame_equivalence_report.get("secondary_frame") or frame_score_report.get("second_best") or "")
    if policy == "use_yaw_only_horizontal_only" and secondary:
        return secondary
    return primary


def _support_rows(probability_timeseries: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    rows = _selected_probability_rows(probability_timeseries, model_id)
    return rows if rows else sorted(probability_timeseries, key=lambda row: _f(row.get("time"), 0.0))


def _build_rows(
    *,
    go2_rows: list[dict[str, Any]],
    probability_rows: list[dict[str, Any]],
    frame_name: str,
    contact_model: str,
    base_std: float,
    policy: str,
    include_buckets: set[str],
    horizontal_only: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prob_index = 0
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        prob, prob_index = _nearest_from_index(probability_rows, time_value, prob_index, tolerance=0.10)
        if not prob:
            continue
        support = _f(prob.get("support_probability"))
        confidence = _f(prob.get("confidence_score"))
        bucket = _confidence_bucket(support, confidence)
        if bucket not in include_buckets:
            continue
        velocity = _candidate_velocity(row, frame_name)
        if not all(math.isfinite(value) for value in velocity):
            continue
        std = _std_for_bucket(base_std, bucket)
        rows.append(
            {
                "time": time_value,
                "vn": velocity[0],
                "ve": velocity[1],
                "vd": 0.0 if horizontal_only else velocity[2],
                "std_vn": std,
                "std_ve": std,
                "std_vd": HORIZONTAL_STD_VD_DISABLED if horizontal_only else std,
                "source_status": "active",
                "quality_flag": f"diagnostic_horizontal_{bucket}_confidence" if horizontal_only else f"diagnostic_full3d_{bucket}_confidence",
                "contact_model": contact_model,
                "contact_label": _contact_label(bucket, support),
                "frame_candidate": frame_name,
                "prior_policy": policy,
                "diagnostic_only": True,
                "go2_velocity_truth_claim": False,
            }
        )
    return rows


def _bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for row in rows:
        quality = str(row.get("quality_flag") or "")
        if "_high_" in quality:
            counts["high"] += 1
        elif "_medium_" in quality:
            counts["medium"] += 1
        else:
            counts["low"] += 1
    return counts


def build_horizontal_velocity_diagnostic_priors(
    *,
    go2_rows: list[dict[str, Any]],
    frame_equivalence_report: dict[str, Any],
    frame_score_report: dict[str, Any],
    probability_model_report: dict[str, Any],
    probability_timeseries: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Write N7B5 runtime-only prior CSVs for full-3D and horizontal variants."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    selected_model = str(probability_model_report.get("selected_contact_probability_model") or "")
    probability_rows = _support_rows(probability_timeseries, selected_model)
    primary_frame = str(frame_equivalence_report.get("primary_frame") or frame_score_report.get("best_candidate") or "")
    secondary_frame = str(frame_equivalence_report.get("secondary_frame") or frame_score_report.get("second_best") or "")
    selected_frame = _frame_for_policy(frame_equivalence_report, frame_score_report)
    horizontal_policy = str(frame_equivalence_report.get("recommended_horizontal_policy") or "do_not_use_go2_velocity")
    model_ready = bool(probability_model_report.get("contact_probability_model_ready", bool(probability_rows)))
    allowed = bool(go2_rows and probability_rows and selected_frame and horizontal_policy != "do_not_use_go2_velocity" and model_ready)
    base_std = max(
        2.0,
        _base_std(frame_score_report),
        _f(frame_equivalence_report.get("top_candidate_difference", {}).get("horizontal_rmse_mps"), 0.0),
    )
    rows: dict[str, list[dict[str, Any]]] = {
        "best_frame_full_3d": [],
        "yaw_only_full_3d": [],
        "best_frame_horizontal_only": [],
        "yaw_only_horizontal_only": [],
        "probability_weighted_horizontal_only": [],
        "contact_weighted_horizontal_only": [],
    }
    if allowed:
        rows["best_frame_full_3d"] = _build_rows(
            go2_rows=go2_rows,
            probability_rows=probability_rows,
            frame_name=primary_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="best_frame_full_3d_diagnostic",
            include_buckets={"high", "medium", "low"},
            horizontal_only=False,
        )
        if secondary_frame:
            rows["yaw_only_full_3d"] = _build_rows(
                go2_rows=go2_rows,
                probability_rows=probability_rows,
                frame_name=secondary_frame,
                contact_model=selected_model,
                base_std=base_std,
                policy="yaw_only_full_3d_diagnostic",
                include_buckets={"high", "medium", "low"},
                horizontal_only=False,
            )
        rows["best_frame_horizontal_only"] = _build_rows(
            go2_rows=go2_rows,
            probability_rows=probability_rows,
            frame_name=primary_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="best_frame_horizontal_only_diagnostic",
            include_buckets={"high", "medium", "low"},
            horizontal_only=True,
        )
        if secondary_frame:
            rows["yaw_only_horizontal_only"] = _build_rows(
                go2_rows=go2_rows,
                probability_rows=probability_rows,
                frame_name=secondary_frame,
                contact_model=selected_model,
                base_std=base_std,
                policy="yaw_only_horizontal_only_diagnostic",
                include_buckets={"high", "medium", "low"},
                horizontal_only=True,
            )
        rows["probability_weighted_horizontal_only"] = _build_rows(
            go2_rows=go2_rows,
            probability_rows=probability_rows,
            frame_name=selected_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="probability_weighted_horizontal_only_diagnostic",
            include_buckets={"high", "medium", "low"},
            horizontal_only=True,
        )
        rows["contact_weighted_horizontal_only"] = _build_rows(
            go2_rows=go2_rows,
            probability_rows=probability_rows,
            frame_name=selected_frame,
            contact_model=selected_model,
            base_std=base_std,
            policy="contact_weighted_horizontal_only_diagnostic",
            include_buckets={"high", "medium"},
            horizontal_only=True,
        )
    paths = {
        "best_frame_full_3d": out / "GO2_BEST_FRAME_FULL_3D_PRIORS_DIAGNOSTIC.csv",
        "yaw_only_full_3d": out / "GO2_YAW_ONLY_FULL_3D_PRIORS_DIAGNOSTIC.csv",
        "best_frame_horizontal_only": out / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv",
        "yaw_only_horizontal_only": out / "GO2_HORIZONTAL_VELOCITY_YAW_ONLY_PRIORS_DIAGNOSTIC.csv",
        "probability_weighted_horizontal_only": out / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
        "contact_weighted_horizontal_only": out / "GO2_HORIZONTAL_VELOCITY_CONTACT_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
    }
    for key, path in paths.items():
        _write_csv(path, rows[key])
    main_counts = _bucket_counts(rows["probability_weighted_horizontal_only"])
    report = {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "csv_generated": bool(rows["probability_weighted_horizontal_only"]),
        "epoch_count": len(rows["probability_weighted_horizontal_only"]),
        "contact_weighted_csv_generated": bool(rows["contact_weighted_horizontal_only"]),
        "contact_weighted_epoch_count": len(rows["contact_weighted_horizontal_only"]),
        "high_confidence_count": main_counts["high"],
        "medium_confidence_count": main_counts["medium"],
        "low_confidence_count": main_counts["low"],
        "variant_epoch_counts": {key: len(value) for key, value in rows.items()},
        "std_policy": {
            "base_std_mps": base_std,
            "base_rule": "max(2.0, N7B4 cross-source RMSE, N7B5 top-frame horizontal RMSE)",
            "high_confidence": "base_std",
            "medium_confidence": "base_std*2",
            "low_confidence": "base_std*5",
            "vertical_component": f"disabled_with_std_vd_{HORIZONTAL_STD_VD_DISABLED}",
        },
        "selected_frame": selected_frame,
        "primary_frame": primary_frame,
        "secondary_frame": secondary_frame,
        "selected_contact_probability_model": selected_model,
        "recommended_horizontal_policy": horizontal_policy,
        "vertical_velocity_disabled": True,
        "std_vd_disabled_threshold": HORIZONTAL_STD_VD_DISABLED,
        "activation_allowed_for_diagnostic": allowed,
        "formal_activation_allowed": False,
        "formal_go2_velocity_prior": False,
        "prior_csv_paths": {key: path.name for key, path in paths.items()},
        "diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_frame_tuning": False,
        "final_v23_frame_tuning": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    (out / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths, report


N7C_PRIOR_FIELDS = PRIOR_FIELDS


def _read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _n7c_source_rows(n7b5_root: str | Path, name: str) -> list[dict[str, Any]]:
    root = Path(n7b5_root)
    return _read_csv_rows(root / name)


def _coerce_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _convert_n7c_rows(
    rows: list[dict[str, Any]],
    *,
    prior_policy: str,
    include_buckets: set[str],
    diagnostic_variant: bool,
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in rows:
        bucket = confidence_bucket_from_quality(str(row.get("quality_flag") or ""))
        if bucket not in include_buckets:
            continue
        std_vn = max(2.0, _coerce_float(row.get("std_vn"), 2.0))
        std_ve = max(2.0, _coerce_float(row.get("std_ve"), 2.0))
        converted.append(
            {
                "time": _coerce_float(row.get("time")),
                "vn": _coerce_float(row.get("vn")),
                "ve": _coerce_float(row.get("ve")),
                "vd": 0.0,
                "std_vn": std_vn,
                "std_ve": std_ve,
                "std_vd": STD_VD_DISABLED,
                "source_status": "active",
                "quality_flag": f"n7c_horizontal_{bucket}_confidence",
                "contact_model": row.get("contact_model", ""),
                "contact_label": row.get("contact_label", ""),
                "frame_candidate": row.get("frame_candidate") or POLICY_FRAME,
                "prior_policy": prior_policy,
                "diagnostic_only": bool(diagnostic_variant),
                "go2_velocity_truth_claim": False,
            }
        )
    return converted


def _n7c_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for row in rows:
        counts[confidence_bucket_from_quality(str(row.get("quality_flag") or ""))] += 1
    return counts


def build_n7c_horizontal_velocity_weak_priors(
    *,
    n7b5_root: str | Path,
    output_dir: str | Path,
    policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Write N7C runtime-only horizontal velocity weak-prior CSV variants.

    N7C consumes N7B5 diagnostic priors as upstream evidence, but writes a new
    runtime CSV set. Only vn/ve are effective; vd is zeroed and disabled with
    std_vd=999 for any internal 3D fallback.
    """

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    n7b5_report_path = Path(n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json"
    n7b5_report = json.loads(n7b5_report_path.read_text(encoding="utf-8")) if n7b5_report_path.exists() else {}
    policy_data = policy or build_n7c_policy(n7b5_report)
    policy_ok, policy_blockers = validate_n7c_policy(policy_data)
    main_source = _n7c_source_rows(n7b5_root, "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    probability_source = _n7c_source_rows(n7b5_root, "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv")
    contact_source = _n7c_source_rows(n7b5_root, "GO2_HORIZONTAL_VELOCITY_CONTACT_WEIGHTED_PRIORS_DIAGNOSTIC.csv")
    if not main_source:
        main_source = probability_source or contact_source
    if not probability_source:
        probability_source = main_source
    if not contact_source:
        contact_source = [row for row in probability_source if confidence_bucket_from_quality(str(row.get("quality_flag") or "")) in {"high", "medium"}]

    rows = {
        "main": _convert_n7c_rows(
            main_source,
            prior_policy=POLICY_NAME,
            include_buckets={"high", "medium", "low"},
            diagnostic_variant=False,
        ),
        "probability_weighted": _convert_n7c_rows(
            probability_source,
            prior_policy="n7c_go2_horizontal_velocity_probability_weighted_diagnostic",
            include_buckets={"high", "medium", "low"},
            diagnostic_variant=True,
        ),
        "contact_weighted": _convert_n7c_rows(
            contact_source,
            prior_policy="n7c_go2_horizontal_velocity_contact_weighted_diagnostic",
            include_buckets={"high", "medium"},
            diagnostic_variant=True,
        ),
        "high_confidence_only": _convert_n7c_rows(
            probability_source,
            prior_policy="n7c_go2_horizontal_velocity_high_confidence_only_diagnostic",
            include_buckets={"high"},
            diagnostic_variant=True,
        ),
    }
    paths = {
        "main": out / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
        "probability_weighted": out / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_N7C.csv",
        "contact_weighted": out / "GO2_HORIZONTAL_VELOCITY_CONTACT_WEIGHTED_PRIORS_N7C.csv",
        "high_confidence_only": out / "GO2_HORIZONTAL_VELOCITY_HIGH_CONFIDENCE_PRIORS_N7C.csv",
    }
    for key, path in paths.items():
        _write_csv(path, rows[key])
    counts = _n7c_counts(rows["main"])
    report = {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "csv_generated": bool(rows["main"]),
        "epoch_count": len(rows["main"]),
        "variant_epoch_counts": {key: len(value) for key, value in rows.items()},
        "high_confidence_count": counts["high"],
        "medium_confidence_count": counts["medium"],
        "low_confidence_count": counts["low"],
        "std_policy": {
            "base_std_mps": float(policy_data.get("base_horizontal_std_mps", 2.0)),
            "main_rule": "N7B5 horizontal rows with conservative std; no R shrink",
            "source_aware_inflation_allowed": True,
            "trace_tuning": False,
            "final_v23_tuning": False,
            "vertical_component": f"disabled_with_std_vd_{STD_VD_DISABLED}",
        },
        "policy": policy_data,
        "policy_valid": policy_ok,
        "policy_blockers": policy_blockers,
        "selected_frame": POLICY_FRAME,
        "measurement_components": ["vn", "ve"],
        "vertical_velocity_disabled": True,
        "std_vd_disabled_threshold": STD_VD_DISABLED,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_velocity_truth_claim": False,
        "controlled_activation_allowed": policy_ok and bool(rows["main"]),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
        "prior_csv_paths": {key: path.name for key, path in paths.items()},
    }
    (out / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths, report
