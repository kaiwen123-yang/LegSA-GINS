"""中文说明：N4H4C toy update runtime 集成测试。"""

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path("/tmp/legsa_n4h4c_pytest_update_toy")


def test_update_toy_runtime_generates_outputs_and_manifest_flags():
    for command in [["cmake", "-S", "cpp", "-B", "build/cpp"], ["cmake", "--build", "build/cpp"]]:
        result = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    result = subprocess.run(
        [
            str(REPO_ROOT / "build/cpp/legsa_v23_core_demo"),
            "--dry-run-update-toy",
            "--output-dir",
            str(OUTPUT_DIR),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    for filename in ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        assert (OUTPUT_DIR / filename).is_file()

    manifest = json.loads((OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "N4H4C"
    assert manifest["measurement_update_implemented"] is True
    assert manifest["state_feedback_implemented"] is True
    assert manifest["position_update_implemented"] is True
    assert manifest["velocity_update_implemented"] is True
    assert manifest["yaw_update_implemented"] is True
    assert manifest["yaw_normal_count"] == 1
    assert manifest["yaw_downweight_count"] == 1
    assert manifest["yaw_reject_count"] == 1
    for key in [
        "raw_doppler",
        "go2_prior",
        "lsim_oim",
        "fgo",
        "trace_solver_input",
        "final_v23_output_substitution",
        "numerical_performance_claim",
    ]:
        assert manifest[key] is False
