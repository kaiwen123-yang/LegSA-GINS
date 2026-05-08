"""中文说明：N4H4A toy runtime 测试只验证 dry-run 输出契约，不验证导航精度。"""

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path("/tmp/legsa_n4h4a_toy")

FORBIDDEN_FLAGS = [
    "final_v23_reference_used_as_solver_input",
    "proposed_reads_final_v23_output",
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
]


def _run(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_legsa_v23_core_demo_dry_run_toy_outputs_manifest_and_streams():
    _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
    _run(["cmake", "--build", "build/cpp"])

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    _run([
        str(REPO_ROOT / "build/cpp/legsa_v23_core_demo"),
        "--dry-run-toy",
        "--output-dir",
        str(OUTPUT_DIR),
    ])

    for name in ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        assert (OUTPUT_DIR / name).is_file()

    manifest = json.loads((OUTPUT_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "N4H4A"
    assert manifest["solver_role"] == "legsa_v23_core_skeleton"
    for flag in FORBIDDEN_FLAGS:
        assert manifest[flag] is False
