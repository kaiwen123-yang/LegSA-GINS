import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：集成测试 C++ toy 确实产生 raw_doppler_update_count。

def test_n5a_cpp_raw_doppler_toy_applies_factor(tmp_path: Path):
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        pytest.skip("C++ demo is not built")
    subprocess.run([str(exe), "--dry-run-raw-doppler-toy", "--output-dir", str(tmp_path)], cwd=ROOT, check=True)
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["raw_doppler_factor_code_present"] is True
    assert manifest["raw_doppler_toy_factor_applied"] is True
    assert manifest["raw_doppler_update_count"] > 0
    assert manifest["final_v23_output_solver_input"] is False
    assert manifest["trace_solver_input"] is False
