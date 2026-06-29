from pathlib import Path

from legsa_gins.degradation.m1r2b2_provider_regen import B2Paths, build_queue_drafts


def test_next_queue_builder_locks_run_allowed_now(tmp_path: Path) -> None:
    paths = B2Paths(tmp_path, tmp_path, tmp_path, tmp_path, tmp_path, tmp_path, tmp_path, tmp_path, tmp_path)
    ready = [
        {
            "case_id": "case",
            "case_index": "0",
            "degradation_type_id": "CLEAN",
            "seed_index": "none",
            "provider_ready": "true",
            "provider_root": "<DEGRADED_PROVIDER_ROOT>/case",
            "yaw_lineage_validation_status": "PASS",
        }
    ]
    full, ablation = build_queue_drafts(paths, ready)
    assert len(full) == 4
    assert len(ablation) == 9
    assert all(row["run_allowed_now"] == "false" for row in full + ablation)
    assert all(row["solver_allowed_now"] == "false" for row in full + ablation)

