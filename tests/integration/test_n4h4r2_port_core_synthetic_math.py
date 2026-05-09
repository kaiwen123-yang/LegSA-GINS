"""中文说明：构建并运行 R2 synthetic math smoke，不代表 clean parity。"""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n4h4r2_port_core_synthetic_math(tmp_path):
    for command in [
        ["cmake", "-S", "cpp", "-B", "build/cpp"],
        ["cmake", "--build", "build/cpp"],
        [
            "./build/cpp/legsa_v23_port_core_demo",
            "--dry-run-synthetic-math",
            "--output-dir",
            str(tmp_path),
        ],
    ]:
        completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        assert (tmp_path / name).exists()
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "N4H4R2"
    assert manifest["parity_attempted"] is False
    assert manifest["real_clean_replay_attempted"] is False
    assert manifest["performance_claim"] is False
