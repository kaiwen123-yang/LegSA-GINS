"""RUN_MANIFEST helpers with N2 forbidden-claim guards."""

import json
from pathlib import Path


RUN_MANIFEST_REQUIRED_FIELDS = [
    "phase",
    "algorithm_role",
    "algorithm_name",
    "dataset_name",
    "output_dir",
    "final_v23_is_proposed",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "raw_data_committed",
    "rtk_fixed_claim",
    "carrier_ambiguity_fixed_claim",
    "self_raw_heading_claim",
    "full_raw_gnss_tight_coupling_claim",
    "neural_gate_formal_claim",
    "fgo_feedback_claim",
    "full_pose_fgo_claim",
    "full_leg_odometry_claim",
    "evidence_status",
]

ALGORITHM_ROLES = {"baseline", "proposed", "diagnostic", "infrastructure"}

FORBIDDEN_FALSE_FIELDS = [
    "final_v23_is_proposed",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "raw_data_committed",
    "rtk_fixed_claim",
    "carrier_ambiguity_fixed_claim",
    "self_raw_heading_claim",
    "full_raw_gnss_tight_coupling_claim",
    "neural_gate_formal_claim",
    "fgo_feedback_claim",
    "full_pose_fgo_claim",
    "full_leg_odometry_claim",
]


def default_run_manifest(
    phase: str,
    algorithm_role: str,
    algorithm_name: str,
    dataset_name: str,
    output_dir: str | Path,
) -> dict:
    manifest = {
        "phase": phase,
        "algorithm_role": algorithm_role,
        "algorithm_name": algorithm_name,
        "dataset_name": dataset_name,
        "output_dir": str(output_dir),
        "evidence_status": "evidence_missing",
    }
    for field in FORBIDDEN_FALSE_FIELDS:
        manifest[field] = False
    return manifest


def write_run_manifest(manifest: dict, output_path: str | Path) -> None:
    validate_run_manifest(manifest)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_run_manifest(manifest: dict) -> bool:
    missing = [field for field in RUN_MANIFEST_REQUIRED_FIELDS if field not in manifest]
    if missing:
        raise ValueError(f"RUN_MANIFEST missing required fields: {missing}")

    role = manifest["algorithm_role"]
    if role not in ALGORITHM_ROLES:
        raise ValueError(
            f"RUN_MANIFEST algorithm_role must be one of {sorted(ALGORITHM_ROLES)}."
        )

    forbidden_true = [
        field for field in FORBIDDEN_FALSE_FIELDS if manifest.get(field) is not False
    ]
    if forbidden_true:
        raise ValueError(f"RUN_MANIFEST forbidden flags must be false: {forbidden_true}")

    return True
