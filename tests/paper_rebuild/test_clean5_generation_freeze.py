"""Synthetic C-03 snapshot, execution identity and no-retry ordering checks."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean5_sequence import generate as gen
from legsa_gins.paper_rebuild.clean5_sequence import generation_audit as audit
from legsa_gins.paper_rebuild.clean5_sequence.registry import BundleRegistry


COMMIT = "a" * 40


def fake_git(monkeypatch, root, *, head=COMMIT, remote=COMMIT, status="", detached=True):
    calls = []

    def output(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == root
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return str(root) + "\n"
        if command[1:] == ["rev-parse", "HEAD"]:
            return head + "\n"
        if command[1:] == ["rev-parse", "refs/remotes/origin/stage/clean3-math-repair"]:
            return remote + "\n"
        assert command[1:] == ["status", "--porcelain=v1", "--untracked-files=all"]
        return status

    monkeypatch.setattr(audit.subprocess, "check_output", output)
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=1 if detached else 0))
    return calls


def test_freeze_records_detached_head_and_complete_status(monkeypatch, tmp_path):
    calls = fake_git(monkeypatch, tmp_path)
    state = audit.code_freeze_state(tmp_path, COMMIT)
    assert state["execution_worktree"] == str(tmp_path)
    assert state["execution_worktree_head"] == COMMIT
    assert state["execution_worktree_git_status"] == ""
    assert state["execution_worktree_detached"] is True
    assert state["origin_stage_clean3_math_repair_head"] == COMMIT
    assert calls[-1][-1] == "--untracked-files=all"


@pytest.mark.parametrize("options, message", [
    ({"head": "b" * 40}, "Execution HEAD"),
    ({"remote": "b" * 40}, "Execution HEAD"),
    ({"detached": False}, "detached"),
    ({"status": "?? retained_lc02.py\n"}, "untracked"),
    ({"status": " M tracked.py\n"}, "clean committed"),
])
def test_freeze_rejects_unpushed_attached_or_dirty_snapshot(monkeypatch, tmp_path, options, message):
    fake_git(monkeypatch, tmp_path, **options)
    with pytest.raises(RuntimeError, match=message):
        audit.code_freeze_state(tmp_path, COMMIT)


def test_freeze_requires_full_sha_before_git(monkeypatch, tmp_path):
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *args, **kwargs: pytest.fail("must reject before Git"))
    with pytest.raises(RuntimeError, match="full lowercase"):
        audit.code_freeze_state(tmp_path, COMMIT[:12])


def snapshot_fixture(monkeypatch, tmp_path):
    active = tmp_path / "clean3-math-repair"
    snapshot = tmp_path / ("clean5-freeze-" + COMMIT[:12])
    snapshot.mkdir()
    binary = active / gen.FROZEN_EXECUTABLE_RELATIVE
    binary.parent.mkdir(parents=True)
    binary.write_text("synthetic frozen executable identity fixture\n")
    local_yaml = active / "local.yaml"
    local_yaml.write_text("paths:\n  code_root: original\n")
    script = snapshot / "scripts/paper_rebuild/clean5_generate_providers.py"
    script.parent.mkdir(parents=True)
    script.write_text("# synthetic script location fixture\n")
    module = snapshot / "src/legsa_gins/paper_rebuild/clean5_sequence/generate.py"
    monkeypatch.setattr(gen, "__file__", str(module))
    monkeypatch.setattr(gen, "sys", SimpleNamespace(modules={"legsa_gins.synthetic": SimpleNamespace(__file__=str(module))}))
    monkeypatch.setattr(gen, "code_freeze_state", lambda root, commit: {"code_freeze_commit": commit})
    monkeypatch.setattr(gen, "sha256_file", lambda path: gen.FROZEN_EXECUTABLE_SHA256)
    registry = BundleRegistry(tmp_path / "raw", tmp_path / "clean", active, {})
    return registry, snapshot, script, binary, local_yaml


def test_registry_override_keeps_local_yaml_and_original_binary(monkeypatch, tmp_path):
    registry, snapshot, script, binary, local_yaml = snapshot_fixture(monkeypatch, tmp_path)
    before = local_yaml.read_bytes()
    updated, state, executable = gen.execution_registry(
        registry, code_root=snapshot, code_freeze_commit=COMMIT, execution_script=script)
    assert updated is not registry
    assert updated.code_root == snapshot
    assert registry.code_root.name == "clean3-math-repair"
    assert local_yaml.read_bytes() == before
    assert executable["path"] == str(binary)
    assert executable["sha256"] == gen.FROZEN_EXECUTABLE_SHA256
    assert executable["executed_during_c03"] is executable["rebuilt_during_c03"] is False
    assert state["code_freeze_commit"] == COMMIT


@pytest.mark.parametrize("origin", ["script", "module", "dependency"])
def test_execution_rejects_actual_code_from_another_worktree(monkeypatch, tmp_path, origin):
    registry, snapshot, script, _, _ = snapshot_fixture(monkeypatch, tmp_path)
    if origin == "script":
        script = registry.code_root / "other.py"
        script.write_text("# wrong script\n")
    elif origin == "module":
        monkeypatch.setattr(gen, "__file__", str(registry.code_root / "src/legsa_gins/paper_rebuild/clean5_sequence/generate.py"))
    else:
        gen.sys.modules["legsa_gins.other"] = SimpleNamespace(__file__=str(registry.code_root / "src/other.py"))
    with pytest.raises(RuntimeError, match="code-root"):
        gen.execution_registry(registry, code_root=snapshot, code_freeze_commit=COMMIT, execution_script=script)


def test_execution_rejects_changed_solver_without_build(monkeypatch, tmp_path):
    registry, snapshot, script, _, _ = snapshot_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(gen, "sha256_file", lambda path: "0" * 64)
    with pytest.raises(RuntimeError, match="rebuilding is forbidden"):
        gen.execution_registry(registry, code_root=snapshot, code_freeze_commit=COMMIT, execution_script=script)


def ordering_fixture(tmp_path):
    sequences = {name: SimpleNamespace(dataset_id=name, stage_id="stage_" + name)
                 for name in ("BY2", "BY2H", "BY2O")}
    return SimpleNamespace(clean_root=tmp_path, sequences=sequences), {"code_freeze_commit": COMMIT}


def write_pass(registry, dataset, state):
    root = gen.stage_root(registry, registry.sequences[dataset]) / "02_PROVIDER_FREEZE"
    root.mkdir(parents=True)
    manifest = {"dataset_id": dataset, "status": "PASS_PROVIDER_FREEZE", **state}
    if dataset == "BY2":
        gate = {"passed": True}
        (root / "BY2_PROVIDER_PARITY_GATE.json").write_text(json.dumps(gate))
        manifest["by2_provider_parity_gate"] = gate
    (root / "PROVIDER_MANIFEST.json").write_text(json.dumps(manifest))
    return manifest


def test_by2o_cannot_start_before_by2h_pass(tmp_path):
    registry, state = ordering_fixture(tmp_path)
    write_pass(registry, "BY2", state)
    with pytest.raises(FileNotFoundError):
        gen.require_generation_order(registry, registry.sequences["BY2O"], state)
    write_pass(registry, "BY2H", state)
    gen.require_generation_order(registry, registry.sequences["BY2O"], state)


def test_prior_provider_requires_exact_freeze_and_by2_gate(tmp_path):
    registry, state = ordering_fixture(tmp_path)
    write_pass(registry, "BY2", {"code_freeze_commit": "b" * 40})
    with pytest.raises(RuntimeError, match="exact execution snapshot"):
        gen.require_provider_freeze(registry, "BY2", state)
    wrong = {"code_freeze_commit": "b" * 40}
    root = gen.stage_root(registry, registry.sequences["BY2"]) / "02_PROVIDER_FREEZE"
    (root / "BY2_PROVIDER_PARITY_GATE.json").write_text(json.dumps({"passed": False}))
    with pytest.raises(RuntimeError, match="BY2 provider parity"):
        gen.require_provider_freeze(registry, "BY2", wrong)


def test_attempt_in_later_sequence_blocks_out_of_order_restart(tmp_path):
    registry, state = ordering_fixture(tmp_path)
    later = gen.stage_root(registry, registry.sequences["BY2H"]) / "01_PROVIDER_GENERATION_AUDIT"
    later.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="no-retry boundary"):
        gen.require_generation_order(registry, registry.sequences["BY2"], state)


def test_render_requires_all_three_providers_before_renderer(monkeypatch, tmp_path):
    from legsa_gins.paper_rebuild.clean5_sequence import runtime_config

    registry, state = ordering_fixture(tmp_path)
    registry.code_root = tmp_path
    write_pass(registry, "BY2", state)
    write_pass(registry, "BY2H", state)
    monkeypatch.setattr(gen, "code_freeze_state", lambda *args: state)
    monkeypatch.setattr(runtime_config, "render_joint_runtime_configs", lambda **kwargs:
                        pytest.fail("missing BY2O must prevent rendering"), raising=False)
    with pytest.raises(FileNotFoundError):
        gen.render_only(SimpleNamespace(code_freeze_commit=COMMIT), registry)
