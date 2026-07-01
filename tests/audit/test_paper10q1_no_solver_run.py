from pathlib import Path


Q1_SCRIPTS = [
    Path("scripts/paper10q1_qm_evidence_review.py"),
    Path("scripts/paper10q1_qm_figure_package.py"),
    Path("scripts/paper10q1_qm_claim_boundary.py"),
]


def test_q1_scripts_do_not_invoke_solver_or_provider_generation():
    forbidden = [
        "legsa_v23_port_core_demo",
        "by2_algorithm_runner",
        "legsa_gins --run-filter-csv",
        "generate_provider",
        "provider_regeneration",
        "degradation_matrix_generation",
        "random_generation",
        "subprocess.run([\"legsa",
        "subprocess.run(['legsa",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in Q1_SCRIPTS)
    for token in forbidden:
        assert token not in text
