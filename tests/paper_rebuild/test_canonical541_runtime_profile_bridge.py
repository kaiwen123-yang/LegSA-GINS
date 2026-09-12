from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import legsa_gins.paper_rebuild.canonical541.runner as runner_module
from legsa_gins.paper_rebuild.canonical541.ablation_registry import ABLATION_METHODS
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS, MethodProfile
from legsa_gins.paper_rebuild.clean2r2a_runner import method_features as parent_method_features
from legsa_gins.paper_rebuild.canonical541.runner import (
    CanonicalRunnerError,
    build_runtime_config,
    clean2r2a_template_profile_id,
    runtime_profile_id,
    scientific_runtime_config_hash,
)


ALL_LOGICAL_PROFILES = (*FULL_METHODS, *ABLATION_METHODS)

EXPECTED_PARENT_TEMPLATES = {
    "F01": "single_antenna_EKF",
    "F02": "basic_dual_yaw_EKF",
    "F03": "AB0000",
    "F04": "AB1111",
    "A01": "AB1111",
    "A02": "AB0000",
    "A03": "AB0111",
    "A04": "AB1011",
    "A05": "AB1101",
    "A06": "AB1110",
    "A07": "AB1100",
    "A08": "AB1000",
    "A09": "AB0100",
}

EXPECTED_CANONICAL_IDENTITIES = {
    "F01": "single_antenna_EKF",
    "F02": "basic_dual_yaw_EKF",
    "F03": "strong_dual_yaw_EKF",
    "F04": "LegSA_Paper_V1",
    "A01": "LegSA_Paper_V1",
    "A02": "strong_dual_yaw_EKF",
    "A03": "AB0111",
    "A04": "AB1011",
    "A05": "AB1101",
    "A06": "AB1110",
    "A07": "AB1100",
    "A08": "AB1000",
    "A09": "AB0100",
}


def _method_bound_manifest() -> dict[str, dict[str, str]]:
    return {
        "actual_solver_inputs": {
            "imu": "/provider/imu.txt",
            "gnss": "/provider/gnss.txt",
            "raw_doppler": "/provider/raw_doppler.csv",
            "go2_rp": "/provider/go2_rp.csv",
            "go2_hv": "/provider/go2_hv.csv",
        }
    }


def test_all_13_logical_profiles_have_separate_parent_and_canonical_selectors() -> None:
    assert len(ALL_LOGICAL_PROFILES) == 13
    assert {profile.method_id for profile in ALL_LOGICAL_PROFILES} == set(EXPECTED_PARENT_TEMPLATES)
    assert {
        profile.method_id: clean2r2a_template_profile_id(profile)
        for profile in ALL_LOGICAL_PROFILES
    } == EXPECTED_PARENT_TEMPLATES
    assert {
        profile.method_id: runtime_profile_id(profile)
        for profile in ALL_LOGICAL_PROFILES
    } == EXPECTED_CANONICAL_IDENTITIES


def test_parent_template_selector_fails_closed_outside_frozen_profiles() -> None:
    invalid = MethodProfile(
        "X01", "single_antenna_EKF", "strong_dual_yaw_EKF",
        dict(FULL_METHODS[2].flags),
    )
    with pytest.raises(CanonicalRunnerError, match="cannot bridge"):
        clean2r2a_template_profile_id(invalid)


def test_all_parent_template_ids_are_accepted_by_real_parent_with_exact_flags() -> None:
    for profile in ALL_LOGICAL_PROFILES:
        selected = clean2r2a_template_profile_id(profile)
        assert parent_method_features(selected) == {
            "dual": profile.flags["dual_yaw"],
            "receiver": profile.flags["receiver_velocity"],
            "raw": profile.flags["raw_doppler"],
            "source_aware": profile.flags["source_aware"],
            "go2_roll_pitch": profile.flags["go2_rp"],
            "go2_horizontal": profile.flags["go2_hv"],
        }


def test_runtime_builder_passes_only_parent_supported_ids_and_preserves_alias_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    parent_calls: list[str] = []

    def fake_parent_builder(*, method_id: str, **_: object) -> str:
        parent_calls.append(method_id)
        return yaml.safe_dump(
            {"parent_template_method_id": method_id},
            allow_unicode=True,
            sort_keys=False,
        )

    monkeypatch.setattr(runner_module, "build_clean_runtime_config", fake_parent_builder)

    rendered: dict[str, str] = {}
    for profile in ALL_LOGICAL_PROFILES:
        rendered[profile.method_id] = build_runtime_config(
            profile=profile,
            clean_input_manifest="/manifest/clean.json",
            auxiliary_manifest="/manifest/aux.json",
            provider_protocol="/contract/provider.yaml",
            method_bound_manifest=_method_bound_manifest(),
            output_dir=tmp_path / "shared-output",
            case_id="C00_clean_normal",
            run_id="shared-run",
        )
        payload = yaml.safe_load(rendered[profile.method_id])
        assert parent_calls[-1] == EXPECTED_PARENT_TEMPLATES[profile.method_id]
        assert payload["parent_template_method_id"] == EXPECTED_PARENT_TEMPLATES[profile.method_id]
        assert payload["algorithm_id"] == EXPECTED_CANONICAL_IDENTITIES[profile.method_id]

    assert len(parent_calls) == 13
    assert not ({"strong_dual_yaw_EKF", "LegSA_Paper_V1"} & set(parent_calls))

    for full_id, ablation_id in (("F04", "A01"), ("F03", "A02")):
        assert rendered[full_id] == rendered[ablation_id]
        assert scientific_runtime_config_hash(rendered[full_id]) == scientific_runtime_config_hash(
            rendered[ablation_id]
        )
