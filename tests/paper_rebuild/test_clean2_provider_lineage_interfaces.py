from __future__ import annotations

import json

import pytest

from legsa_gins.paper_rebuild.clean2_case_provider import (
    RAW_AUDIT_PHASES,
    RAW_POST_PHASE,
    RAW_PRE_PHASE,
    Clean2CaseProviderError,
    _validate_fresh_dual_yaw_binding,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


def test_raw_checkpoint_cli_and_case_validator_share_exact_phases():
    assert RAW_AUDIT_PHASES == (RAW_PRE_PHASE, RAW_POST_PHASE, "post_run")
    assert RAW_PRE_PHASE == "pre_provider"
    assert RAW_POST_PHASE == "post_provider"


def test_same_yaw_modified_vector_cannot_escape_fresh_helper_hash_binding(tmp_path):
    providers = tmp_path / "providers"
    providers.mkdir()
    dual_source = providers / "dual_yaw_provider.csv"
    dual_source.write_text(
        "time,baseline_e,baseline_n,baseline_u,baseline_length,yaw_deg,yaw_std_deg,valid\n"
        "28801,0.35,0,0,0.35,90,1.5,1\n",
        encoding="utf-8",
    )
    dual = tmp_path / "clean_final_v23_time_basis/DUAL_YAW_PROVIDER.csv"
    dual.parent.mkdir()
    dual.write_text(
        "time,baseline_e,baseline_n,baseline_u,baseline_length,yaw_deg,yaw_std_deg,valid\n"
        "1,0.35,0,0,0.35,90,1.5,1\n",
        encoding="utf-8",
    )
    commit = "a" * 40
    raw_hashes = {f"raw/{index}": "b" * 64 for index in range(22)}
    helper = {
        "schema_version": "paper-rebuild-clean1-input-v1",
        "stage_id": "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        "protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V1",
        "generator_code_commit": commit,
        "generator_worktree_dirty": False,
        "generator_config_hash": "c" * 64,
        "provider_bundle_hash": "d" * 64,
        "data_mode": "real_by2_raw",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "raw_source_hashes": raw_hashes,
        "artifacts": {
            "dual_yaw_provider": {
                "relative_path": "providers/dual_yaw_provider.csv",
                "solver_input": False,
                "artifact_role": "audit_only_lineage",
            }
        },
        "provider_hashes": {"dual_yaw_provider": sha256_file(dual_source)},
    }
    helper_path = tmp_path / "CLEAN_INPUT_MANIFEST.json"
    helper_path.write_text(json.dumps(helper), encoding="utf-8")
    auxiliary_path = tmp_path / "CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    auxiliary_path.write_text("{}", encoding="utf-8")
    auxiliary = {
        "raw_source_hashes": raw_hashes,
        "classic18_dual_yaw_provider": {
            "path": str(dual),
            "sha256": sha256_file(dual),
            "helper_source_path": str(dual_source),
            "helper_source_sha256": sha256_file(dual_source),
            "helper_manifest_path": str(helper_path),
            "helper_manifest_sha256": sha256_file(helper_path),
            "helper_provider_bundle_hash": helper["provider_bundle_hash"],
            "generator_config_hash": helper["generator_config_hash"],
            "time_basis_audit": {
                "passed": True,
                "source_path": str(dual_source),
                "active_path": str(dual),
                "time_column_only_transformed": True,
                "source_time_column_preserved": True,
                "offset_subtracted_seconds": 28800.0,
            },
        },
    }
    assert _validate_fresh_dual_yaw_binding(
        auxiliary,
        auxiliary_manifest_path=auxiliary_path,
        provided_dual_yaw_path=dual,
        expected_code_commit=commit,
    ) == dual.resolve()
    # Keep yaw identical but alter the baseline vector; the fresh hash binding must fail.
    dual.write_text(
        "time,baseline_e,baseline_n,baseline_u,baseline_length,yaw_deg,yaw_std_deg,valid\n"
        "1,0.70,0,0,0.70,90,1.5,1\n",
        encoding="utf-8",
    )
    with pytest.raises(Clean2CaseProviderError, match="differs from fresh helper binding"):
        _validate_fresh_dual_yaw_binding(
            auxiliary,
            auxiliary_manifest_path=auxiliary_path,
            provided_dual_yaw_path=dual,
            expected_code_commit=commit,
        )
