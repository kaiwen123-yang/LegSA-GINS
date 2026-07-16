import csv
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_evidence import (
    FINAL_ZIP_PREFIX,
    TERMINAL_ARTIFACT_RELATIVE_PATHS,
    Clean2EvidenceError,
    EvidenceMember,
    _required_terminal_audit_export_members,
    _validate_c00_structural_alias_rows,
    _validate_terminal_offline_chain_identity,
    _validate_terminal_attempt_audit,
    _validate_terminal_invariants,
    assert_position_velocity_case_isolation,
    build_clean2_final_zip,
    select_clean2_export_members,
    validate_clean2_terminal_gate,
    validate_export_members,
)
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.clean2_runner import ATTEMPT_FIELDS, validate_attempt_rows


def _member(tmp_path: Path, name: str, content: bytes = b"safe\n") -> EvidenceMember:
    source = tmp_path / name
    source.write_bytes(content)
    return EvidenceMember(source=source, archive_path=f"14_FINAL_EVIDENCE/{name}", category="test")


def test_export_rejects_unsafe_root_recursion(tmp_path: Path) -> None:
    # 只有精确 CLEAN2 stage root 可进入显式 allowlist；不能把 clean_root 当作递归源。
    with pytest.raises(Clean2EvidenceError, match="root-recursive"):
        select_clean2_export_members(tmp_path)


def test_export_rejects_absolute_private_path_text(tmp_path: Path) -> None:
    member = _member(tmp_path, "CLEAN2_FULL_REPORT.json", b'{"path":"/mnt/g/private/raw.csv"}\n')
    with pytest.raises(Clean2EvidenceError, match="privacy scan"):
        validate_export_members([member])


def test_export_rejects_extra_nav_payload(tmp_path: Path) -> None:
    member = _member(tmp_path, "EXTRA_OUTPUT.nav", b"1 2 3\n")
    with pytest.raises(Clean2EvidenceError, match="NAV/STD"):
        validate_export_members([member])


def test_export_rejects_second_final_zip_before_selection(tmp_path: Path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / f"{FINAL_ZIP_PREFIX}20260716T120000P0800.zip").write_bytes(b"existing")
    with pytest.raises(Clean2EvidenceError, match="second ZIP"):
        build_clean2_final_zip(stage_root=tmp_path / "missing", export_root=export)


def test_export_rejects_missing_terminal_gate_before_member_selection(tmp_path: Path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    with pytest.raises(Clean2EvidenceError, match="terminal PASS gate"):
        build_clean2_final_zip(stage_root=tmp_path / "missing", export_root=export)


def test_placeholder_terminal_gate_cannot_authorize_export(tmp_path: Path) -> None:
    stage = tmp_path / "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
    gate = stage / "14_FINAL_EVIDENCE/CLEAN2_TERMINAL_GATE.json"
    gate.parent.mkdir(parents=True)
    gate.write_text(
        json.dumps({
            "schema_version": "paper_rebuild.clean2_terminal_gate.v1",
            "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
            "terminal_decision": "PASS_CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW",
            "artifacts": {},
            "checks": {"passed": True},
            "passed": True,
        }),
        encoding="utf-8",
    )
    with pytest.raises(Clean2EvidenceError, match="artifact role set"):
        validate_clean2_terminal_gate(gate, stage_root=stage)


def test_export_rejects_oversized_explicit_set(tmp_path: Path) -> None:
    member = _member(tmp_path, "CLEAN2_FULL_REPORT.md", b"1234567890")
    with pytest.raises(Clean2EvidenceError, match="preflight"):
        validate_export_members([member], max_uncompressed_bytes=9)


def test_export_rejects_symlink_member(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("safe\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)
    member = EvidenceMember(link, "14_FINAL_EVIDENCE/CLEAN2_FULL_REPORT.md", "test")
    with pytest.raises(Clean2EvidenceError, match="symlink"):
        validate_export_members([member])


@pytest.mark.parametrize("validity_column", [15, 16])
def test_case_isolation_rejects_position_or_velocity_validity_mutation(
    tmp_path: Path, validity_column: int
) -> None:
    fields = [
        "1", "39", "116", "42", "0.1", "0.1", "0.2",
        "1", "2", "3", "0.05", "0.05", "0.05", "90", "1.5",
        "1", "1", "1",
    ]
    inputs = {}
    for index in range(18):
        case_id = f"C{index:02d}_case"
        path = tmp_path / f"{case_id}.extended"
        current = list(fields)
        if index == 7:
            current[validity_column] = "0"
        path.write_text(" ".join(current) + "\n", encoding="utf-8")
        inputs[case_id] = path
    with pytest.raises(Clean2EvidenceError, match="POSITION_VELOCITY_SOURCE_ISOLATION"):
        assert_position_velocity_case_isolation(inputs)


def test_terminal_dependency_map_requires_c00_structural_gate() -> None:
    assert TERMINAL_ARTIFACT_RELATIVE_PATHS["c00_structural_gate"] == (
        "13_AUDITS/CLEAN2_C00_STRUCTURAL_GATE.json"
    )
    assert TERMINAL_ARTIFACT_RELATIVE_PATHS["attempts_audit"] == (
        "13_AUDITS/CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    )


def _real_c00_structural_rows() -> list[dict]:
    common = {
        "case_id": "C00_clean_normal",
        "feature_RD": False,
        "feature_SA": False,
        "feature_RP": False,
        "feature_HV": False,
        "formal": True,
    }
    return [
        {
            **common,
            "structural_method": "single_antenna_EKF",
            "ablation_id": "",
            "alias_roles": "canonical_single_antenna_EKF;C00_structural_gate",
        },
        {
            **common,
            "structural_method": "basic_dual_yaw_EKF",
            "ablation_id": "",
            "alias_roles": "canonical_basic_dual_yaw_EKF;C00_structural_gate",
        },
        {
            **common,
            "structural_method": "strong_dual_yaw_EKF",
            "ablation_id": "AB0000",
            "alias_roles": "canonical_strong;C00_structural_gate;ablation_configuration",
        },
        {
            **common,
            "structural_method": "strong_dual_yaw_EKF",
            "ablation_id": "AB1111",
            "feature_RD": True,
            "feature_SA": True,
            "feature_RP": True,
            "feature_HV": True,
            "alias_roles": "canonical_LegSA;C00_structural_gate;ablation_configuration",
        },
    ]


def test_real_four_row_c00_structural_alias_identity_passes() -> None:
    assert _validate_c00_structural_alias_rows(_real_c00_structural_rows()) == (
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "LegSA_Paper_V1",
    )


@pytest.mark.parametrize(
    ("row_index", "field", "value"),
    (
        (3, "structural_method", "LegSA_Paper_V1"),
        (3, "feature_HV", False),
        (3, "alias_roles", "C00_structural_gate;ablation_configuration"),
        (2, "feature_RD", True),
    ),
)
def test_real_four_row_c00_structural_alias_identity_rejects_drift(
    row_index: int, field: str, value
) -> None:
    rows = _real_c00_structural_rows()
    rows[row_index][field] = value
    with pytest.raises(Clean2EvidenceError, match="alias/feature identity drifted"):
        _validate_c00_structural_alias_rows(rows)


def test_terminal_gate_rejects_missing_or_tampered_structural_gate(
    tmp_path: Path, monkeypatch
) -> None:
    stage = tmp_path / "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
    rows = {}
    for role, relative in TERMINAL_ARTIFACT_RELATIVE_PATHS.items():
        artifact = stage / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"{role}\n", encoding="utf-8")
        rows[role] = {
            "relative_path": relative,
            "sha256": sha256_file(artifact),
            "size_bytes": artifact.stat().st_size,
        }
    checks = {"passed": True}
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_evidence._terminal_semantic_checks",
        lambda **_kwargs: checks,
    )
    gate = stage / "14_FINAL_EVIDENCE/CLEAN2_TERMINAL_GATE.json"

    def write_gate(artifacts):
        gate.write_text(
            json.dumps(
                {
                    "schema_version": "paper_rebuild.clean2_terminal_gate.v1",
                    "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
                    "terminal_decision": (
                        "PASS_CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18_"
                        "FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW"
                    ),
                    "artifacts": artifacts,
                    "checks": checks,
                    "passed": True,
                }
            ),
            encoding="utf-8",
        )

    missing = dict(rows)
    missing.pop("c00_structural_gate")
    write_gate(missing)
    with pytest.raises(Clean2EvidenceError, match="artifact role set"):
        validate_clean2_terminal_gate(gate, stage_root=stage)

    missing_audit = dict(rows)
    missing_audit.pop("attempts_audit")
    write_gate(missing_audit)
    with pytest.raises(Clean2EvidenceError, match="artifact role set"):
        validate_clean2_terminal_gate(gate, stage_root=stage)

    write_gate(rows)
    structural = stage / TERMINAL_ARTIFACT_RELATIVE_PATHS["c00_structural_gate"]
    structural.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(Clean2EvidenceError, match="artifact changed"):
        validate_clean2_terminal_gate(gate, stage_root=stage)


def test_terminal_invariants_reject_stale_hash_binding(tmp_path: Path, monkeypatch) -> None:
    artifacts = {}
    for role in (
        "registry", "complete_output_seal", "solver_artifact_index",
        "offline_evaluation_index", "case_provider_index",
    ):
        path = tmp_path / f"{role}.json"
        path.write_text("{}\n", encoding="utf-8")
        artifacts[role] = path
    persisted = {
        "schema_version": "paper_rebuild.clean2_formal_invariants.v2",
        "run_registry_sha256": "a" * 64,
        "passed": True,
    }
    invariant_path = tmp_path / "CLEAN2_FORMAL_INVARIANTS.json"
    invariant_path.write_text(json.dumps(persisted), encoding="utf-8")
    artifacts["invariants"] = invariant_path
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.clean2_evidence.audit_clean2_formal_invariants",
        lambda **_kwargs: {**persisted, "run_registry_sha256": "b" * 64},
    )
    with pytest.raises(Clean2EvidenceError, match="invariants are not terminal PASS"):
        _validate_terminal_invariants(artifacts=artifacts, runtime_root=tmp_path)


def test_terminal_attempt_audit_mutation_is_rejected(tmp_path: Path) -> None:
    registry = tmp_path / "CLEAN2_RUN_REGISTRY.csv"
    registry.write_text("frozen registry\n", encoding="utf-8")
    registry_rows = [
        {"run_id": f"R{order:03d}", "run_order": order}
        for order in range(1, 111)
    ]
    attempt_rows = [
        {
            "run_id": row["run_id"],
            "run_order": row["run_order"],
            "attempt_number": 1,
            "technical_retry": False,
            "retry_reason": "",
            "metric_driven_rerun": False,
            "returncode": 0,
            "runtime_seconds": 1.0,
            "terminal_status": "PASS",
        }
        for row in registry_rows
    ]
    attempts = tmp_path / "CLEAN2_RUN_ATTEMPTS.csv"
    with attempts.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ATTEMPT_FIELDS))
        writer.writeheader()
        writer.writerows(attempt_rows)
    computed = validate_attempt_rows(
        attempt_rows,
        registry_rows=registry_rows,
        required_run_ids={str(row["run_id"]) for row in registry_rows},
    )
    audit = tmp_path / "CLEAN2_RUN_ATTEMPTS_AUDIT.json"
    payload = {
        "schema_version": "paper_rebuild.clean2_terminal_attempt_audit.v1",
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "registry_sha256": sha256_file(registry),
        "attempts_sha256": sha256_file(attempts),
        **computed,
    }
    audit.write_text(json.dumps(payload), encoding="utf-8")
    _validate_terminal_attempt_audit(
        registry_path=registry,
        attempts_path=attempts,
        audit_path=audit,
        registry_rows=registry_rows,
    )
    payload["technical_retry_run_count"] = 1
    audit.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Clean2EvidenceError, match="three-way binding failed"):
        _validate_terminal_attempt_audit(
            registry_path=registry,
            attempts_path=attempts,
            audit_path=audit,
            registry_rows=registry_rows,
        )


def test_exact_terminal_audit_export_members_include_invariants_once(tmp_path: Path) -> None:
    stage = tmp_path / "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
    for role in ("attempts_audit", "c00_structural_gate", "invariants"):
        path = stage / TERMINAL_ARTIFACT_RELATIVE_PATHS[role]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}\n", encoding="utf-8")
    members = _required_terminal_audit_export_members(stage)
    paths = [member.archive_path for member in members]
    assert len(paths) == len(set(paths)) == 3
    assert paths.count("13_AUDITS/CLEAN2_FORMAL_INVARIANTS.json") == 1
    assert "13_AUDITS/CLEAN2_RUN_ATTEMPTS_AUDIT.json" in paths


def test_offline_index_attempt_audit_hash_mutation_is_rejected(tmp_path: Path) -> None:
    artifacts = {}
    for role in (
        "solver_artifact_index", "complete_output_seal", "registry",
        "attempts", "attempts_audit",
    ):
        path = tmp_path / role
        path.write_text(f"{role}\n", encoding="utf-8")
        artifacts[role] = path
    offline = {
        "schema_version": "paper_rebuild.clean2_offline_evaluation_index.v2",
        "run_count": 110,
        "passed": True,
        "all_110_outputs_validated_before_trace": True,
        "all_outputs_sealed_before_trace": True,
        "all_110_attempt_histories_validated_before_trace": True,
        "terminal_attempt_audit_validated_before_trace": True,
        "trace_used_online": False,
        "exact_evaluator_sha256": (
            "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
        ),
        "trace_sha256": (
            "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
        ),
        "solver_artifact_index_sha256": sha256_file(artifacts["solver_artifact_index"]),
        "complete_output_seal_sha256": sha256_file(artifacts["complete_output_seal"]),
        "registry_sha256": sha256_file(artifacts["registry"]),
        "run_attempts_sha256": sha256_file(artifacts["attempts"]),
        "run_attempts_audit_sha256": sha256_file(artifacts["attempts_audit"]),
        "results": [{"run_id": f"R{order:03d}"} for order in range(1, 111)],
    }
    assert len(_validate_terminal_offline_chain_identity(offline, artifacts=artifacts)) == 110
    offline["run_attempts_audit_sha256"] = "0" * 64
    with pytest.raises(Clean2EvidenceError, match="offline evaluation index is stale"):
        _validate_terminal_offline_chain_identity(offline, artifacts=artifacts)
