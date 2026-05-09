"""中文说明：测试 reference 只用于 evaluation，不能进入 solver。"""

from legsa_gins.evaluation.legsa_v23_port_reference_independence import analyze_reference_independence


def test_detects_reference_built_from_port_output():
    report = analyze_reference_independence(
        {"trace_solver_input": False, "final_v23_output_solver_input": False},
        {"imupath": "clean.imu", "gnsspath": "clean.gnss"},
        {},
        {"reference_reconstruction_depends_on_port_output": True},
    )
    assert report["reference_independence_ok"] is False


def test_detects_final_v23_output_solver_input():
    report = analyze_reference_independence(
        {"trace_solver_input": False, "final_v23_output_solver_input": True},
        {"imupath": "clean.imu", "gnsspath": "clean.gnss"},
    )
    assert report["final_v23_output_solver_input"] is True
    assert report["reference_independence_ok"] is False


def test_clean_gnss_solver_input_only_is_ok():
    report = analyze_reference_independence(
        {"trace_solver_input": False, "final_v23_output_solver_input": False},
        {"imupath": "clean.imu", "gnsspath": "clean.gnss"},
        {},
        {"evaluation_reference_role": "dual_final_v23_reference_eval_only"},
    )
    assert report["clean_gnss_solver_input"] is True
    assert report["clean_gnss_evaluation_reference"] is False
    assert report["reference_independence_ok"] is True
