from pathlib import Path


Q2_SCRIPTS = [
    Path("scripts/paper10q2_horizontal_reconciliation.py"),
    Path("scripts/paper10q2_horizontal_claim_boundary.py"),
    Path("scripts/paper10q2_horizontal_figure_indexer.py"),
    Path("scripts/paper10q2_next_prompt_builder.py"),
]


def test_q2_scripts_do_not_invoke_experiment_runners():
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
        "cmake --build",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in Q2_SCRIPTS)
    for token in forbidden:
        assert token not in text
