"""中文说明：测试 absolute trace evaluator 的边界旗标和 namespace。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_absolute_trace_eval import evaluate_nav_vs_trace


def _write_csv(path: Path, yaw_offset: float = 0.0) -> None:
    path.write_text(
        "time,lat_deg,lon_deg,height_m,roll_deg,pitch_deg,yaw_deg\n"
        + "\n".join(
            f"{i * 0.01:.2f},30.0,120.0,10.0,0.0,0.0,{5.0 + yaw_offset}" for i in range(120)
        )
        + "\n",
        encoding="utf-8",
    )


def test_trace_solver_input_false_and_absolute_namespace(tmp_path):
    nav = tmp_path / "nav.csv"
    trace = tmp_path / "trace.csv"
    _write_csv(nav, yaw_offset=0.1)
    _write_csv(trace)
    report = evaluate_nav_vs_trace(nav, None, trace, tmp_path / "out", "port_nav")
    assert report["namespace"] == "port_vs_trace_absolute"
    assert report["absolute_performance_metric"] is True
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False
    assert report["paper_performance_claim"] is False
    assert report["namespace"] != "port_vs_final_v23_nav_parity"
