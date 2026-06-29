from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
B2_FILES = list((ROOT / "scripts").glob("paper10m1r2b2_*.py")) + list((ROOT / "src/legsa_gins/degradation").glob("*.py"))


def test_b2_code_has_no_solver_or_evaluator_entrypoints() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in B2_FILES)
    forbidden = [
        "legsa_v23_port_core_demo",
        "by2_algorithm_runner",
        "evaluate_nav_trace",
        "PAPER10M1R2C_R1_execute",
        "PAPER10M1R2D_execute",
    ]
    for token in forbidden:
        assert token not in text

