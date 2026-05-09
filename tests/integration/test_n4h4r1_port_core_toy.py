"""中文说明：集成测试构建并运行 N4H4R1 port-core toy，不代表性能。"""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n4h4r1_port_core_toy_runtime(tmp_path):
    for command in [
        ["cmake", "-S", "cpp", "-B", "build/cpp"],
        ["cmake", "--build", "build/cpp"],
        [
            "./build/cpp/legsa_v23_port_core_demo",
            "--dry-run-toy",
            "--output-dir",
            str(tmp_path),
        ],
    ]:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        assert (tmp_path / name).exists()
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["parity_attempted"] is False
    assert manifest["final_v23_output_solver_input"] is False
    assert manifest["trace_solver_input"] is False
    assert manifest["raw_doppler"] is False
    assert manifest["go2_prior"] is False
    assert manifest["lsim_oim"] is False
    assert manifest["fgo"] is False
    assert manifest["performance_claim"] is False

