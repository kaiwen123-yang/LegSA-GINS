from pathlib import Path


SCRIPT_PATHS = [
    Path("scripts/paper10m1r2e_result_review.py"),
    Path("scripts/paper10m1r2e_figure_package.py"),
    Path("scripts/paper10m1r2e_claim_boundary.py"),
]


def test_m1r2e_scripts_do_not_invoke_solver_or_evaluator():
    repo = Path(__file__).resolve().parents[2]
    forbidden = [
        "legsa_v23_port_core_demo",
        "by2_algorithm_runner",
        "--run-filter-csv",
        "paper10m1r2c_r1_yaw_corrected_full_algorithm_matrix.py",
        "paper10m1r2d_r1_internal_ablation_matrix.py",
        "regenerate_yaw_corrected",
    ]
    combined = "\n".join((repo / path).read_text(encoding="utf-8") for path in SCRIPT_PATHS)
    for token in forbidden:
        assert token not in combined
