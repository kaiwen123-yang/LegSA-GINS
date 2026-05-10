import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


# 中文说明：N5B real-style toy 复用 C++ raw Doppler EKF update，验证 manifest 新字段。


def test_n5b_raw_doppler_activation_toy_manifest(tmp_path: Path):
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        pytest.skip("C++ demo is not built")
    subprocess.run([str(exe), "--dry-run-raw-doppler-toy", "--output-dir", str(tmp_path)], cwd=ROOT, check=True)
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["raw_doppler_update_count"] > 0
    assert manifest["raw_doppler_factor_valid_epoch_count"] > 0
    assert manifest["raw_doppler_velocity_not_nav_pvt"] is True
    assert manifest["raw_doppler_velocity_not_gnss_15col"] is True
    assert manifest["paper_performance_claim"] is False
