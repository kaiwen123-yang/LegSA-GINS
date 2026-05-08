"""中文说明：N4H4B propagation toy 只验证预测传播输出契约。"""

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path("/tmp/legsa_n4h4b_propagation_toy")


def _run(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_n4h4b_propagation_toy_generates_outputs_and_boundary_manifest():
    _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
    _run(["cmake", "--build", "build/cpp"])
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    _run([
        str(REPO_ROOT / "build/cpp/legsa_v23_core_demo"),
        "--dry-run-propagation-toy",
        "--output-dir",
        str(OUTPUT_DIR),
    ])

    for name in ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        assert (OUTPUT_DIR / name).is_file()

    manifest = json.loads((OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "N4H4B"
    assert manifest["solver_role"] == "legsa_v23_core_propagation_foundation"
    assert manifest["mechanization_predict_implemented"] is True
    assert manifest["measurement_update_implemented"] is False
    assert manifest["state_feedback_implemented"] is False
    for flag in [
        "trace_solver_input",
        "raw_doppler",
        "go2_prior",
        "lsim_oim",
        "fgo",
        "fgo_feedback",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "numerical_performance_claim",
        "final_v23_output_substitution",
    ]:
        assert manifest[flag] is False
