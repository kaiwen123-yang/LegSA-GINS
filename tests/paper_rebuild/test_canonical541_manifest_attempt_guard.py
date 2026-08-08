from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.canonical541.authorization import STAGE_ID


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/build_canonical541_manifest.py"
SPEC = importlib.util.spec_from_file_location("canonical_manifest_builder", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)


def _local_config(path: Path, runtime_root: Path) -> Path:
    path.write_text(yaml.safe_dump({"paths": {"runtime_root": str(runtime_root)}}), encoding="utf-8")
    return path


def test_manifest_builder_rejects_bare_stage_before_any_write(monkeypatch, tmp_path):
    bare = tmp_path / STAGE_ID; bare.mkdir()
    local = _local_config(tmp_path / "local.yaml", bare)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--local-config", str(local),
                        "--code-freeze-commit", "a" * 40, "--executable", str(local)])
    with pytest.raises(Exception, match="runtime_root must be exactly"):
        builder.main()
    assert list(bare.iterdir()) == []


def test_manifest_builder_rejects_nonmatching_output_override_before_write(monkeypatch, tmp_path):
    stage = tmp_path / STAGE_ID; configured = stage / ".attempt_configured"
    override = stage / ".attempt_override"; configured.mkdir(parents=True); override.mkdir()
    local = _local_config(tmp_path / "local.yaml", configured)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--local-config", str(local),
                        "--output-root", str(override), "--code-freeze-commit", "a" * 40,
                        "--executable", str(local)])
    with pytest.raises(SystemExit, match="exactly equal"):
        builder.main()
    assert list(configured.iterdir()) == [] and list(override.iterdir()) == []
