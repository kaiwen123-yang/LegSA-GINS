from pathlib import Path

import jsonschema

from legsa_gins.paper_rebuild.clean2r2a_runner import method_features, validate_formal_wrapper


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "configs/paper_rebuild/clean2r2a_formal_manifest_schema.yaml"
SHA = "a" * 64


def _wrapper() -> dict:
    counters = {
        "position_update_count": 1, "receiver_velocity_update_count": 1,
        "dual_yaw_attempt_count": 1, "dual_yaw_normal_count": 1,
        "dual_yaw_downweight_count": 0, "dual_yaw_reject_count": 0,
        "dual_yaw_accepted_count": 1, "raw_doppler_update_count": 0,
        "source_aware_evaluation_count": 0, "source_aware_weight_changed_count": 0,
        "go2_roll_pitch_update_count": 0, "go2_horizontal_velocity_update_count": 0,
        "fgo_count": 0, "qm_count": 0, "qa_count": 0, "contact_fk_count": 0,
    }
    return {
        "schema_version": "paper_rebuild.clean2r2a1_formal_run.v1",
        "stage_id": "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME",
        "protocol_id": "CLEAN2R2A1_BY2_CLEAN_MODULE_ABLATION_RESUME",
        "solver_parent_stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
        "solver_parent_protocol_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION",
        "provider_stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
        "provider_protocol_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION",
        "provider_code_freeze_commit": "91793894a43c8ba83c25d8da698b7ee16e31b80e",
        "execution_code_freeze_commit": "b" * 40,
        "case_id": "CLEAN1_BY2_CLEAN_NORMAL", "data_mode": "real_clean",
        "run_id": "03_AB0000", "algorithm_id": "AB0000",
        "method_features": method_features("AB0000"), "code_commit": "b" * 40,
        "code_worktree_dirty_at_run": False, "executable_hash": SHA,
        "runtime_config_hash": SHA, "local_config_hash": SHA,
        "provider_protocol_hash": SHA, "formal_schema_hash": SHA,
        "base_provider_parity_sha256": SHA,
        "provider_hashes": {f"p{i}": SHA for i in range(8)},
        "raw_source_hashes": {f"r{i}": SHA for i in range(22)},
        "provider_generation": {f"g{i}": SHA for i in range(6)},
        "solver_manifest_sha256": SHA,
        "actual_solver_inputs": {
            "imu": {"path": "/provider/imu", "role": "source", "sha256": SHA, "open_count": 1},
            "gnss": {"path": "/provider/gnss", "role": "source", "sha256": SHA, "open_count": 1},
        },
        "solver_read_ledger": {"trace_open_count": 0, "raw_root_open_count": 0,
                               "legacy_open_count": 0, "passed": True},
        "solver_read_ledger_sha256": SHA,
        "output_hashes": {f"o{i}": SHA for i in range(8)},
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "trace_used_online": False, "trace_open_count": 0,
        "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0, "legacy_aggregate_input_count": 0,
        "module_counters": counters,
        "mechanism_evidence": {"scheme_c": {}, "source_aware": {}},
        "structure": {"nav_rows": 56642, "std_rows": 56642,
                      "time_start": 66.005054, "time_end": 339.997056, "finite": True},
        "runtime_seconds": 1.0, "solver_returncode": 0,
        "metric_driven_rerun": False, "terminal_status": "PASS",
    }


def test_formal_schema_is_executed_and_rejects_trace_online() -> None:
    wrapper = _wrapper()
    validate_formal_wrapper(wrapper, SCHEMA)
    wrapper["trace_used_online"] = True
    try:
        validate_formal_wrapper(wrapper, SCHEMA)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError("formal schema accepted online trace")
