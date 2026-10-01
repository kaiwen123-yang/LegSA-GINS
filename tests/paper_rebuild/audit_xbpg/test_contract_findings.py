"""Real project contract functions, synthetic inputs only; defects stay xfail."""
from pathlib import Path
import sys

import pytest

from legsa_gins.paper_rebuild import manifest, methods, paths
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group


@pytest.mark.xfail(strict=True, reason="P-CON-01 fallback splits a quoted # as comment")
def test_fallback_preserves_quoted_hash_in_path():
    value = paths._fallback_yaml_mapping('paths:\n  raw_root: "<SCRATCH>/原始#1"\n')
    assert value["paths"]["raw_root"] == "<SCRATCH>/原始#1"


@pytest.mark.xfail(strict=True, reason="P-CON-02 legacy denylist only checks link spelling")
def test_guard_rechecks_legacy_after_resolving_symlink(tmp_path):
    target = tmp_path / "experiments" / "old.txt"
    target.parent.mkdir()
    target.write_text("synthetic fixture")
    link = tmp_path / "new.txt"
    link.symlink_to(target)
    with pytest.raises(paths.PathContractError, match="legacy"):
        paths.guard_path(link, role="fixture", allowed_root=tmp_path, regular_file=True)


def clean_manifest(digest):
    value = dict(schema_version="paper-rebuild-run-manifest-v1", run_id="fixture",
                 algorithm_id="single_antenna_EKF", case_id="fixture", data_mode="real_by2_raw",
                 raw_source_hashes={"source": digest}, provider_hashes={"input": digest},
                 old_runtime_input_count=0, code_commit="a" * 40, code_worktree_dirty_at_run=False,
                 config_hash=digest, provider_generator_commit="a" * 40,
                 provider_generation_config_hash=digest, local_path_config_hash=digest,
                 terminal_status="PASS")
    value.update({name: False for name in manifest.FORBIDDEN_TRUE_FIELDS})
    return value


@pytest.mark.xfail(strict=True, reason="P-CON-03 SHA syntax check accepts nonhex 64 characters")
def test_manifest_sha256_has_hex_domain():
    assert manifest.validate_run_manifest(clean_manifest("z" * 64), require_pass=True)


def effective_configs(catalog):
    configs = {}
    for name in methods.FORMAL_METHOD_ORDER:
        value = {field: "same-fixture-value" for field in methods.REQUIRED_COMMON_RUNTIME_FIELDS}
        value.update(catalog.features(name))
        value.update({field: False for field in methods.FORBIDDEN_DEFAULT_FIELDS})
        value.update(algorithm_id=name, method_role=catalog.method(name)["role"],
                     enable_basic_dual_yaw_baseline=name == "basic_dual_yaw_EKF",
                     basic_dual_yaw_fixed_std_deg=1.5 if name == "basic_dual_yaw_EKF" else "NOT_METHOD_SPECIFIC")
        configs[name] = value
    return configs


def method_catalog():
    return methods.load_method_catalog(Path(__file__).resolve().parents[3] / "configs/paper_rebuild/methods.yaml")


@pytest.mark.xfail(strict=True, reason="P-CON-04 effective method label is not bound to mapping key")
def test_effective_algorithm_label_cannot_change_behind_flags():
    catalog = method_catalog()
    configs = effective_configs(catalog)
    configs["single_antenna_EKF"]["algorithm_id"] = "LegSA_Paper_V1"
    assert not methods.audit_effective_config_differences(catalog, configs)["passed"]


def test_valid_manifest_and_method_flags_have_positive_controls():
    assert manifest.validate_run_manifest(clean_manifest("a" * 64), require_pass=True) == []
    catalog = method_catalog()
    configs = effective_configs(catalog)
    assert methods.audit_effective_config_differences(catalog, configs)["passed"]
    configs["single_antenna_EKF"]["enable_dual_yaw"] = True
    assert not methods.audit_effective_config_differences(catalog, configs)["passed"]


def test_raw_hash_change_and_outside_symlink_rejected(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    source = raw / "source"
    source.write_text("before")
    lock = {"source": {"size_bytes": "6", "sha256": manifest.sha256_file(source)}}
    source.write_text("after!")
    with pytest.raises(manifest.ManifestContractError, match="hash changed"):
        manifest.verify_raw_sources(raw, ["source"], lock)
    link = raw / "escape"
    link.symlink_to(tmp_path)
    with pytest.raises(paths.PathContractError, match="outside"):
        paths.guard_path(link, role="fixture", allowed_root=raw)


def test_original_subprocess_guard_preserves_exit_and_stderr(tmp_path):
    result = run_process_group([sys.executable, "-c", "import sys;sys.stderr.write('fixture error');sys.exit(7)"],
                               cwd=tmp_path, timeout_seconds=2, timeout_message="timed out",
                               launch_failure_message="launch failed")
    assert result.returncode == 7 and result.stderr == "fixture error"


def test_original_subprocess_guard_launch_and_timeout(tmp_path):
    arguments = dict(cwd=tmp_path, timeout_seconds=.1, timeout_message="fixture timeout",
                     launch_failure_message="fixture launch", termination_grace_seconds=.1)
    missing = run_process_group([str(tmp_path / "missing")], **arguments)
    assert missing.returncode == 127 and "fixture launch" in missing.stderr
    timeout = run_process_group([sys.executable, "-c", "import time;time.sleep(30)"], **arguments)
    assert timeout.returncode == 124 and "fixture timeout" in timeout.stderr
