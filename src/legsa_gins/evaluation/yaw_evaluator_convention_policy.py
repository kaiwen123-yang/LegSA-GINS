"""Yaw evaluator convention policy profiles for N4R2.

中文说明：本模块只改变 evaluator 里的 yaw error 解释方式；不修改 solver input、
solver output，不做 output-only correction，也不把 trace/reference 放入求解器。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.trajectory_metrics import summary_metrics, write_error_series, write_summary
from legsa_gins.evaluation.yaw_convention_transforms import compute_yaw_error
from legsa_gins.evaluation.yaw_evaluator_parity import compute_errors_for_transforms


@dataclass(frozen=True)
class YawConventionProfile:
    """A diagnostic evaluator yaw convention profile."""

    name: str
    est_transform: str
    ref_transform: str
    source: str
    evidence_status: str
    formal_allowed: bool
    notes: str = ""

    @classmethod
    def from_mapping(cls, value: "YawConventionProfile | dict[str, Any]") -> "YawConventionProfile":
        if isinstance(value, cls):
            return value
        return cls(
            name=str(value["name"]),
            est_transform=str(value["est_transform"]),
            ref_transform=str(value["ref_transform"]),
            source=str(value.get("source", "diagnostic")),
            evidence_status=str(value.get("evidence_status", "diagnostic_only")),
            formal_allowed=bool(value.get("formal_allowed", False)),
            notes=str(value.get("notes", "")),
        )


def _profile_dict(profile: YawConventionProfile) -> dict[str, Any]:
    return asdict(profile)


def default_yaw_convention_profiles() -> list[dict[str, Any]]:
    """Return controlled evaluator yaw profiles.

    The official candidate remains formal_allowed=false until dual_final_v23
    artifact parity confirms it.
    """

    profiles = [
        YawConventionProfile(
            name="direct_identity",
            est_transform="identity",
            ref_transform="identity",
            source="baseline_direct",
            evidence_status="baseline_direct_profile",
            formal_allowed=True,
            notes="default evaluator convention",
        ),
        YawConventionProfile(
            name="official_candidate_ref_heading_to_math",
            est_transform="identity",
            ref_transform="heading_to_math_yaw",
            source="N4R_single_antenna_official_candidate",
            evidence_status="requires_dual_final_v23_verification",
            formal_allowed=False,
            notes="requires_dual_final_v23_verification",
        ),
        YawConventionProfile(
            name="diagnostic_ref_neg",
            est_transform="identity",
            ref_transform="neg",
            source="diagnostic_grid",
            evidence_status="diagnostic_only",
            formal_allowed=False,
            notes="yaw evaluator diagnostic only",
        ),
        YawConventionProfile(
            name="diagnostic_ref_plus90",
            est_transform="identity",
            ref_transform="plus90",
            source="diagnostic_grid",
            evidence_status="diagnostic_only",
            formal_allowed=False,
            notes="yaw evaluator diagnostic only",
        ),
    ]
    return [_profile_dict(profile) for profile in profiles]


def get_profile(profile_name: str) -> dict[str, Any]:
    for profile in default_yaw_convention_profiles():
        if profile["name"] == profile_name:
            return profile
    raise ValueError(f"unknown yaw convention profile: {profile_name}")


def apply_yaw_profile(
    est_yaw_deg: float,
    ref_yaw_deg: float,
    profile: YawConventionProfile | dict[str, Any],
) -> float:
    """Compute yaw error under one evaluator-only profile."""

    resolved = YawConventionProfile.from_mapping(profile)
    return compute_yaw_error(
        est_yaw_deg,
        ref_yaw_deg,
        est_transform=resolved.est_transform,
        ref_transform=resolved.ref_transform,
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evaluate_with_yaw_profile(
    eval_nav: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    profile: YawConventionProfile | dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate a trajectory with a controlled yaw convention profile."""

    resolved = YawConventionProfile.from_mapping(profile)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    errors = compute_errors_for_transforms(
        eval_nav,
        reference,
        est_transform=resolved.est_transform,
        ref_transform=resolved.ref_transform,
    )
    summary = summary_metrics(errors)
    summary.update(
        {
            "yaw_profile_name": resolved.name,
            "est_transform": resolved.est_transform,
            "ref_transform": resolved.ref_transform,
            "profile_formal_allowed": resolved.formal_allowed,
            "solver_input_modified": False,
            "solver_output_changed": False,
            "evaluator_only": True,
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    )
    report = {
        "phase": "N4R2",
        "profile": _profile_dict(resolved),
        "summary": summary,
        "error_series_count": len(errors),
        "summary_path": "summary.json",
        "error_series_path": "error_series.csv",
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_summary(summary, out / "summary.json")
    write_error_series(errors, out / "error_series.csv")
    _write_json(out / "profile_report.json", report)
    return report


def write_yaw_convention_policy_report(output_dir: str | Path) -> dict[str, Any]:
    """Write the default policy report used by N4R2 runners."""

    report = {
        "phase": "N4R2",
        "profiles": default_yaw_convention_profiles(),
        "default_profile_name": "direct_identity",
        "candidate_profile_name": "official_candidate_ref_heading_to_math",
        "formal_profile_patch_allowed": False,
        "formal_blocker": "dual_final_v23_artifact_parity_not_confirmed",
        "solver_input_modified": False,
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }
    _write_json(Path(output_dir) / "YAW_EVALUATOR_CONVENTION_POLICY_REPORT.json", report)
    return report
