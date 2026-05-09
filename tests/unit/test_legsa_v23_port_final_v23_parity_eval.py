"""中文说明：测试 port NAV vs final_v23 NAV parity evaluator。"""

import math
from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_final_v23_parity_eval import evaluate_port_vs_final_v23_nav


def _write_port_csv(path: Path) -> None:
    lat_offset = 0.05 / 6378137.0 * 180.0 / math.pi
    path.write_text(
        "time,lat_deg,lon_deg,height_m,roll_deg,pitch_deg,yaw_deg\n"
        + "\n".join(
            f"{i * 0.01:.3f},{30.0 + lat_offset:.10f},120.0,10.02,0.02,0.03,5.04"
            for i in range(120)
        )
        + "\n",
        encoding="utf-8",
    )


def _write_final_nav(path: Path) -> None:
    path.write_text(
        "".join(f"0 {i * 0.01:.3f} 30.0 120.0 10.0 0 0 0 0 0 5.0\n" for i in range(120)),
        encoding="utf-8",
    )


def test_evaluates_synthetic_small_parity(tmp_path):
    port = tmp_path / "EVAL_NAV.csv"
    final = tmp_path / "KF_GINS_Navresult.nav"
    _write_port_csv(port)
    _write_final_nav(final)
    report = evaluate_port_vs_final_v23_nav(port, final, tmp_path / "out")
    assert report["namespace"] == "port_vs_final_v23_nav_parity"
    assert report["aligned_count"] == 120
    assert report["parity_small"] is True
    assert report["absolute_performance_metric"] is False
    assert report["final_v23_output_solver_input"] is False
