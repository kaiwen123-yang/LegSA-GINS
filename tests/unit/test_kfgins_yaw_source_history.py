"""中文说明：KF-GINS source history 单元测试使用 toy git repo。"""

from pathlib import Path
import subprocess

from legsa_gins.source_audit.kfgins_yaw_source_history import (
    audit_current_yaw_update_source,
    search_yaw_update_history,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "toy@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Toy"], cwd=root, check=True)
    source = root / "src" / "kf-gins" / "gi_engine.cpp"
    _write(source, "auto yaw = gnssdata.yaw; auto r = wrap(euler[2] - yaw); // scheme_C\n")
    subprocess.run(["git", "add", "src/kf-gins/gi_engine.cpp"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "direct yaw"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _write(source, "auto yaw = 90 - gnssdata.yaw; auto r = wrap(euler[2] - yaw); // scheme_C\n")
    subprocess.run(["git", "add", "src/kf-gins/gi_engine.cpp"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "transform yaw"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_current_yaw_update_detection(tmp_path) -> None:
    _init_repo(tmp_path)
    report = audit_current_yaw_update_source(tmp_path)
    assert report["current_yaw_measurement_loaded"] is True
    assert report["no_source_modification"] is True
    assert report["trace_solver_input"] is False


def test_source_history_candidate_detection(tmp_path) -> None:
    _init_repo(tmp_path)
    report = search_yaw_update_history(tmp_path)
    assert report["candidate_commit_count"] >= 2
    assert report["evidence_of_yaw_transform_variants"] is True
    assert report["no_source_modification"] is True
