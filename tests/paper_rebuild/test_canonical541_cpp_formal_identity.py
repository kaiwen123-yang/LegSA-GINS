from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541.runner import (
    CanonicalRunnerError,
    canonical_data_mode,
    runtime_profile_id,
)
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS
from legsa_gins.paper_rebuild.canonical541.ablation_registry import ABLATION_METHODS


def test_exact_canonical_case_and_data_mode_contract():
    assert canonical_data_mode("C00_clean_normal") == "real_clean"
    for degradation in range(1, 61):
        for seed in range(9):
            case_id = f"D{degradation:02d}_seed_{seed:02d}"
            assert canonical_data_mode(case_id) == "real_base_controlled_degradation"
    for bad in ("D00_seed_00", "D61_seed_00", "D01_seed_09", "D1_seed_00", "C00"):
        with pytest.raises(CanonicalRunnerError):
            canonical_data_mode(bad)


def test_shared_full_ablation_execution_profiles():
    full = {row.method_id: runtime_profile_id(row) for row in FULL_METHODS}
    ablation = {row.method_id: runtime_profile_id(row) for row in ABLATION_METHODS}
    assert full == {
        "F01": "single_antenna_EKF", "F02": "basic_dual_yaw_EKF",
        "F03": "strong_dual_yaw_EKF", "F04": "LegSA_Paper_V1",
    }
    assert ablation["A01"] == full["F04"]
    assert ablation["A02"] == full["F03"]
    assert tuple(ablation[f"A{index:02d}"] for index in range(3, 10)) == (
        "AB0111", "AB1011", "AB1101", "AB1110", "AB1100", "AB1000", "AB0100",
    )


def test_cpp_loader_contains_narrow_canonical_identity_only():
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text(encoding="utf-8")
    assert 'options.stage_id == "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"' in source
    assert 'options.protocol_id == "CANONICAL541_BY2_CONTROLLED_DEGRADATION"' in source
    assert 'options.data_mode == "real_base_controlled_degradation"' in source
    assert 'options.data_mode == "real_clean"' in source
    assert "isCanonical541CaseId(options.case_id)" in source
    assert "degradation >= 1 && degradation <= 60 && seed >= 0 && seed <= 8" in source
    assert "canonical541_matrix_identity && isCanonical541AblationId(options.algorithm_id)" in source
    assert "isCanonical541CompactReadinessIdentity" in source
    for allowed in ("AB0111", "AB1011", "AB1101", "AB1110", "AB1100", "AB1000", "AB0100"):
        assert f'"{allowed}"' in source
