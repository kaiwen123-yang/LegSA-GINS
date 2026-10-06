from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/run_canonical541_repaired_pipeline.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("canonical_pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pipeline)


def test_live_lock_rejected_and_dead_lock_requires_matching_explicit_resume(monkeypatch, tmp_path):
    stage = tmp_path / pipeline.STAGE_ID / ".attempt_20260808T000000"; stage.mkdir(parents=True)
    stage = stage.resolve(); freeze = "a" * 40
    lock = stage / "runner.lock"
    lock.write_text(json.dumps({"pid": 42, "stage_id": pipeline.STAGE_ID,
                                "stage_root": str(stage), "code_freeze_commit": freeze}))
    monkeypatch.setattr(pipeline, "_pid_alive", lambda pid: True)
    with pytest.raises(SystemExit, match="live process"):
        pipeline._acquire_runner_lock(stage, freeze, resume=True)
    monkeypatch.setattr(pipeline, "_pid_alive", lambda pid: False)
    with pytest.raises(SystemExit, match="explicit --resume"):
        pipeline._acquire_runner_lock(stage, freeze, resume=False)
    with pytest.raises(SystemExit, match="freeze mismatch"):
        pipeline._acquire_runner_lock(stage, "b" * 40, resume=True)
    acquired = pipeline._acquire_runner_lock(stage, freeze, resume=True)
    payload = json.loads(acquired.read_text())
    assert payload["pid"] == pipeline.os.getpid() and payload["stage_id"] == pipeline.STAGE_ID
    pipeline._release_owned_lock(acquired)
    assert not acquired.exists()


def test_bare_stage_root_is_rejected_for_lock(tmp_path):
    stage = tmp_path / pipeline.STAGE_ID; stage.mkdir()
    with pytest.raises(Exception, match="runtime_root must be exactly"):
        pipeline._acquire_runner_lock(stage, "a" * 40, resume=False)
