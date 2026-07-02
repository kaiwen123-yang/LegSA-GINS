from pathlib import Path


Q2R1_SCRIPTS = [
    Path("scripts/paper10q2r1_storage_slim.py"),
    Path("scripts/paper10q2r1_paper2a_reexport.py"),
    Path("scripts/paper10q2r1_claim_boundary.py"),
]


def test_q2r1_scripts_do_not_invoke_experiment_runners():
    forbidden = [
        "legsa_v23_port_core_demo",
        "by2_algorithm_runner",
        "legsa_gins --run-filter-csv",
        "generate_provider",
        "degradation_matrix_generation",
        "random_generation",
        "subprocess.run([\"legsa",
        "subprocess.run(['legsa",
        "cmake --build",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in Q2R1_SCRIPTS)
    for token in forbidden:
        assert token not in text
