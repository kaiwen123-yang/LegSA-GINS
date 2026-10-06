"""Synthetic C-03 configuration fixtures; no real providers or solver execution."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_sequence import runtime_config as rc


@pytest.fixture
def joint_inputs(tmp_path, monkeypatch):
    profiles = {}
    for method, algorithm in rc.METHODS.items():
        flags = {
            "enable_dual_yaw": method != "F01",
            "enable_receiver_velocity": method in {"F03", "A04", "F04"},
            "enable_raw_doppler": method in {"A04", "F04"},
            "enable_source_aware": method == "F04",
            "enable_go2_roll_pitch_prior": method in {"A04", "F04"},
            "enable_go2_horizontal_velocity_prior": method in {"A04", "F04"},
        }
        extras = {**rc.NATIVE_IDENTITY, **flags, "algorithm_id": algorithm,
                  "raw_doppler_backend_source_files": ["by2/gnss1-raw.csv", "by2/gnss1-status.csv"],
                  "raw_doppler_backend_source_hashes": {"by2/gnss1-raw.csv": "a" * 64},
                  "raw_doppler_backend_id": "synthetic_fixture_backend", "covariance_policy": "frozen_fixture_policy",
                  **{key: "a" * 64 for key in ("helper_executable_hash", "obs_source_hash",
                                               "nav_source_hash", "conversion_config_hash")}}
        text = rc.active_runtime_config(
            Path("/fixture/imu"), Path("/fixture/gnss"), Path("/fixture/output"),
            method_id="LegSA_Paper_V1", auxiliary_paths={"raw_doppler": "/fixture/raw",
                "go2_roll_pitch": "/fixture/rp", "go2_horizontal_velocity": "/fixture/hv"},
            run_id="fixture_BY2_" + method,
            extra_config={key: rc._literal(value) for key, value in extras.items()})
        profiles[method] = {"text": text, "sha256": rc._sha(text.encode()), "path": "/fixture/" + method,
                            "values": yaml.safe_load(text)}
    monkeypatch.setattr(rc, "SEALED_CONFIG_SHA256", {m: p["sha256"] for m, p in profiles.items()})
    monkeypatch.setattr(rc, "load_sealed_profiles", lambda _: {"profiles": profiles})
    contracts, manifests, outputs = {}, {}, {}
    for i, dataset in enumerate(("BY2H", "BY2O"), 1):
        prefix = "fixture_" + dataset.lower()
        source_paths = [prefix + "/gnss1-raw.csv", prefix + "/gnss1-status.csv"]
        raw_hashes = {p: str(i) * 64 for p in source_paths}
        identity = {"dataset_id": dataset, "data_mode": "real_" + dataset.lower() + "_raw",
                    "stage_id": "CLEAN5_" + dataset + "_FIXTURE", "fix_prefix": prefix,
                    "raw_files_sha256": raw_hashes}
        contracts[dataset] = {"identity": identity,
            "method_set": {"methods": rc.METHODS, "execution_order": list(rc.METHODS)},
            "window_contract": {"t_start": 100 * i, "t_end": 100 * i + 50},
            "initialization_contract": {"initpos": [39 + i, 116, 42], "initatt": [0, 0, i],
                "rule_source": "synthetic_fixture_only", "position_epoch_R1": 100 * i, "yaw_epoch_R1": 100 * i}}
        stage = tmp_path / dataset
        stage.mkdir()
        artifacts = {}
        for role in rc.PATH_ROLES.values():
            path = stage / (role + ".csv")
            path.write_text("synthetic_test_fixture_only\n" + dataset + "\n")
            artifacts[role] = {"path": str(path), "sha256": rc._sha(path.read_bytes())}
        manifests[dataset] = {**identity, "artifacts": artifacts,
            "code_freeze_commit": "f" * 40, "code_commit": "f" * 40,
            "code_worktree_dirty_at_generation": False,
            "execution_worktree": str(Path(__file__).resolve().parents[2]),
            "execution_worktree_head": "f" * 40, "execution_worktree_git_status": "",
            "execution_worktree_untracked_files": "all", "execution_worktree_detached": True,
            "origin_stage_clean3_math_repair_head": "f" * 40,
            "config_hash": rc._sha(json.dumps(contracts[dataset], sort_keys=True,
                                               separators=(",", ":")).encode()),
            "raw_doppler_backend": {
            "raw_doppler_backend_source_files": source_paths, "raw_doppler_backend_source_hashes": raw_hashes,
            "raw_doppler_backend_id": "synthetic_fixture_backend", "covariance_policy": "frozen_fixture_policy",
            **{key: str(i) * 64 for key in ("helper_executable_hash", "obs_source_hash",
                                           "nav_source_hash", "conversion_config_hash")}},
            "frozen_executable": {"path": "/fixture/frozen_executable_not_invoked",
                "sha256": "9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f"}}
        outputs[dataset] = stage / "03_RUNTIME_CONFIGS"
    return {"contracts": contracts, "provider_manifests": manifests, "output_dirs": outputs,
            "base_provider_gate": tmp_path / "synthetic_gate.json",
            "code_root": Path(__file__).resolve().parents[2]}, profiles


def test_joint_five_profile_gate_writes_true_provenance(joint_inputs):
    inputs, profiles = joint_inputs
    report = rc.render_joint_runtime_configs(**inputs)
    gate = report["joint_frozen_parameter_gate"]
    assert gate["passed"] and gate["profile_count"] == 5
    assert gate["scientific_runtime_config_hash_is_cross_sequence_gate"] is False
    for dataset, out in inputs["output_dirs"].items():
        audit = json.loads((out / "RUNTIME_CONFIG_AUDIT.json").read_text())
        assert audit["dataset_id"] == dataset
        assert audit["execution_worktree_head"] == "f" * 40
        assert audit["execution_worktree_git_status"] == ""
        assert audit["source_contract_config_hash"] == inputs["provider_manifests"][dataset]["config_hash"]
        assert audit["backend_provenance_source_audit"]["globally_manifest_only"] is False
        assert "integrity/lineage" in (out / "RUNTIME_CONFIG_DIFF_VS_CLEAN2R2A1.md").read_text()
        for profile in audit["profiles"]:
            method = profile["method_id"]
            text = (out / rc.CONFIG_FILENAMES[method]).read_text()
            actual = yaml.safe_load(text)
            backend = inputs["provider_manifests"][dataset]["raw_doppler_backend"]
            assert profile["frozen_parameter_hash"] == rc.frozen_parameter_hash(profiles[method]["text"])
            assert profile["scientific_runtime_config_hash"] != profile["sealed_scientific_runtime_config_sha256"]
            for key in rc.BACKEND_PROVENANCE_KEYS:
                expected = backend[key]
                if key.startswith("raw_doppler_backend_source_"):
                    assert actual[key] == expected
                    line = next(line for line in text.splitlines() if line.startswith(key + ":"))
                    # Exact frozen native loader: unquoted JSON collections are retained.
                    native = line.split(":", 1)[1].strip()
                    assert json.loads(native) == expected
                else:
                    assert actual[key] == expected
            assert profile["profile_flags"] == {k: profiles[method]["values"][k] for k in rc.PROFILE_FLAGS}
            assert {d["category"] for d in profile["parameter_differences"]} == set(rc.OVERRIDE_CATEGORIES)
        assert len(list(out.glob("*.yaml"))) == 5


@pytest.mark.parametrize("key", ["antlever", "initvel", "enable_raw_doppler", "raw_doppler_backend_id", "covariance_policy"])
def test_nonwhitelisted_override_rejected_even_if_unchanged(key):
    with pytest.raises(rc.RuntimeConfigError, match="whitelist"):
        rc.apply_runtime_overrides({key: 1}, {key: 1})


def test_frozen_hash_omits_exact_categories_but_keeps_profile_parameters():
    base = {key: "original" for key in rc.ALLOWED_OVERRIDES}
    base.update({"enable_raw_doppler": True, "raw_doppler_R_scale": 1.0})
    changed = {key: "replacement" for key in rc.ALLOWED_OVERRIDES}
    changed.update({"enable_raw_doppler": True, "raw_doppler_R_scale": 1.0})
    assert rc.frozen_parameter_hash(yaml.safe_dump(base)) == rc.frozen_parameter_hash(yaml.safe_dump(changed))
    assert rc.scientific_runtime_config_hash(yaml.safe_dump(base)) != rc.scientific_runtime_config_hash(yaml.safe_dump(changed))
    changed["enable_raw_doppler"] = False
    assert rc.frozen_parameter_hash(yaml.safe_dump(base)) != rc.frozen_parameter_hash(yaml.safe_dump(changed))


def test_joint_cross_profile_mismatch_writes_neither_directory(joint_inputs, monkeypatch):
    inputs, _ = joint_inputs
    original = rc.build_runtime_config
    def altered(**kwargs):
        text, audit = original(**kwargs)
        if kwargs["method_id"] == "F04" and kwargs["contract"]["identity"]["dataset_id"] == "BY2O":
            text = text.replace("enable_source_aware: true", "enable_source_aware: false")
        return text, audit
    monkeypatch.setattr(rc, "build_runtime_config", altered)
    with pytest.raises(rc.RuntimeConfigError, match="frozen_parameter_hash mismatch"):
        rc.render_joint_runtime_configs(**inputs)
    assert not any(path.exists() for path in inputs["output_dirs"].values())


@pytest.mark.parametrize("key", ["raw_doppler_backend_id", "covariance_policy"])
def test_backend_scientific_values_remain_frozen(joint_inputs, key):
    inputs, _ = joint_inputs
    inputs["provider_manifests"]["BY2O"]["raw_doppler_backend"][key] = "changed"
    with pytest.raises(rc.RuntimeConfigError, match="frozen scientific field"):
        rc.render_joint_runtime_configs(**inputs)
    assert not any(path.exists() for path in inputs["output_dirs"].values())


def test_changed_provider_payload_blocks_all_rendering(joint_inputs):
    inputs, _ = joint_inputs
    path = inputs["provider_manifests"]["BY2O"]["artifacts"]["raw_doppler_provider"]["path"]
    Path(path).write_text("changed synthetic fixture\n")
    with pytest.raises(rc.RuntimeConfigError, match="artifact hash mismatch"):
        rc.render_joint_runtime_configs(**inputs)
    assert not any(path.exists() for path in inputs["output_dirs"].values())


def test_mismatched_execution_snapshot_blocks_all_rendering(joint_inputs):
    inputs, _ = joint_inputs
    inputs["provider_manifests"]["BY2O"]["execution_worktree_head"] = "e" * 40
    with pytest.raises(rc.RuntimeConfigError, match="execution snapshot fields"):
        rc.render_joint_runtime_configs(**inputs)
    assert not any(path.exists() for path in inputs["output_dirs"].values())


def test_wrong_source_contract_hash_blocks_all_rendering(joint_inputs):
    inputs, _ = joint_inputs
    inputs["provider_manifests"]["BY2O"]["config_hash"] = "e" * 64
    with pytest.raises(rc.RuntimeConfigError, match="contract config_hash mismatch"):
        rc.render_joint_runtime_configs(**inputs)
    assert not any(path.exists() for path in inputs["output_dirs"].values())


def test_single_sequence_renderer_cannot_bypass_joint_gate():
    with pytest.raises(rc.RuntimeConfigError, match="required BY2/BY2H/BY2O gate"):
        rc.render_runtime_configs()


def test_source_audit_rejects_changed_source_identity(tmp_path, monkeypatch):
    path = tmp_path / "fixture.cpp"
    path.write_text("changed")
    monkeypatch.setattr(rc, "BACKEND_SOURCE_AUDIT", ({"source": "fixture.cpp", "sha256": "0" * 64},))
    with pytest.raises(rc.RuntimeConfigError, match="source audit identity changed"):
        rc.audit_backend_provenance_sources(tmp_path)
