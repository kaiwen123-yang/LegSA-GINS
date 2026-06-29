from pathlib import Path


SCRIPT_NAMES = [
    "scripts/paper10m1r2c1_clean_yaw_semantic_audit.py",
    "scripts/paper10m1r2c1_qm_trace_semantic_audit.py",
    "scripts/paper10m1r2c1_corrected_metric_rebuilder.py",
    "scripts/paper10m1r2c1_result_gate.py",
]


def test_m1r2c1_scripts_do_not_call_solver_or_provider_generation():
    root = Path(__file__).resolve().parents[2]
    forbidden = ["legsa_v23_port_core_demo", "by2_algorithm_runner", "generate_by2_degraded_providers"]
    for name in SCRIPT_NAMES:
        text = (root / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
