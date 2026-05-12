"""中文说明：C++ toy 验证 Go2 roll/pitch weak prior 真实进入 EKF。"""

import json
import subprocess
from pathlib import Path


def test_n7a_go2_weak_prior_toy_updates_ekf(tmp_path):
    root = Path(__file__).resolve().parents[2]
    exe = root / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        subprocess.run(["cmake", "-S", "cpp", "-B", "build/cpp"], cwd=root, check=True)
        subprocess.run(["cmake", "--build", "build/cpp"], cwd=root, check=True)
    proc = subprocess.run(
        [str(exe), "--dry-run-go2-weak-prior-toy", "--output-dir", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["go2_attitude_weak_prior_enabled"] is True
    assert manifest["go2_attitude_weak_prior_update_count"] > 0
    assert manifest["go2_position_prior_enabled"] is False
    assert manifest["go2_velocity_prior_enabled"] is False
    assert manifest["go2_yaw_prior_enabled"] is False
    assert manifest["paper_performance_claim"] is False
