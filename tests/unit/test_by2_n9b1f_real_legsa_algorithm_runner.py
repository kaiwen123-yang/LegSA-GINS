from pathlib import Path

from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (
    AUDIT_ROOT_NAME,
    FORMAL_ALGORITHMS,
    STAGE,
    default_n9b1f_runtime_root,
    run_n9b1f_real_legsa_algorithm_runner,
    validate_n9b1f_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_runtime_root_uses_n9b1f_stage():
    root = default_n9b1f_runtime_root(ROOT)
    assert root.parts[-2] == AUDIT_ROOT_NAME
    assert root.name == STAGE


def test_n9b1f_maps_formal_algorithms_to_port_demo_and_blocks_run_filter_csv(tmp_path):
    runtime_root = tmp_path / "n9b1f"
    result = run_n9b1f_real_legsa_algorithm_runner(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_n9b1f_result(
        ROOT,
        runtime_root,
        result["algorithm_implementation_inventory"],
        result["normal_parity_metrics"],
        result["n9b1d_ready_execution_matrix"],
        result["wsl_dryrun_ready_commands"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    inventory = [row for row in result["algorithm_implementation_inventory"] if row["algorithm"] in FORMAL_ALGORITHMS]
    assert len(inventory) == len(FORMAL_ALGORITHMS)
    assert all(row["runner_path_is_legsa_gins_diagnostic"] is False for row in inventory)
    assert all(row["runner_path"].endswith("legsa_v23_port_core_demo") or not row["runner_path"] for row in inventory)
    for row in result["normal_parity_metrics"]:
        command = " ".join(row.get("solver_command", []) or [])
        assert "--run-filter-csv" not in command
        assert "build/cpp/legsa_gins" not in command
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    assert result["normal_parity_report"]["degradation_execution"] is False
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


def test_n9b1f_tracked_files_do_not_embed_local_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_n9b1f_real_legsa_algorithm_runner.py",
        ROOT / "scripts" / "experiments" / "run_n9b1f_real_legsa_algorithm_runner.py",
        ROOT / "scripts" / "audit_n9b1f_real_legsa_algorithm_runner.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
