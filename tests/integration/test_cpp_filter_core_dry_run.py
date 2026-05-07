"""中文说明：integration 测试验证 N4 toy filter dry-run 输出合同，不做数值性能结论。"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_FALSE_FLAGS = [
    "final_v23_is_proposed",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "raw_data_committed",
    "raw_doppler_claim",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
    "numerical_performance_claim",
]


def test_cpp_filter_core_dry_run_outputs_contract_files(tmp_path):
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not available on this machine")

    build_dir = tmp_path / "build" / "cpp"
    output_dir = tmp_path / "n4_filter_output"

    subprocess.run(
        ["cmake", "-S", str(REPO_ROOT / "cpp"), "-B", str(build_dir)],
        check=True,
        cwd=REPO_ROOT,
    )
    subprocess.run(["cmake", "--build", str(build_dir)], check=True, cwd=REPO_ROOT)
    subprocess.run(
        [
            str(build_dir / "legsa_gins"),
            "--dry-filter-demo",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    nav_path = output_dir / "LegSA_NAV.nav"
    std_path = output_dir / "LegSA_STD.csv"
    eval_nav_path = output_dir / "EVAL_NAV.csv"
    manifest_path = output_dir / "RUN_MANIFEST.json"

    assert nav_path.exists()
    assert std_path.exists()
    assert eval_nav_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["algorithm_role"] == "proposed"
    assert manifest["evidence_status"] == "filter_core_toy_only_no_performance_claim"
    for flag in FORBIDDEN_FALSE_FLAGS:
        assert manifest[flag] is False

    nav_lines = nav_path.read_text(encoding="utf-8").strip().splitlines()
    std_lines = std_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(nav_lines) >= 3
    assert len(std_lines) >= 3
