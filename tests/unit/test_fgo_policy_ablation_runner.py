"""中文说明：测试 N8B policy ablation 真实 solver rerun。"""

from legsa_gins.fgo.fgo_policy_ablation_runner import REQUIRED_N8B_VARIANTS, run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def _rows() -> list[dict]:
    return [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0])
    ]


def test_n8b_policy_ablations_are_real_solver_reruns() -> None:
    report, rows_by_variant = run_n8b_policy_ablations(ekf_rows=_rows(), policy_grid=build_n8b_policy_grid())
    assert report["all_required_variants_run"]
    assert sorted(row["variant"] for row in report["variants"]) == sorted(REQUIRED_N8B_VARIANTS)
    assert report["all_variants_real_solver_rerun"]
    assert not any(row["proxy_only"] for row in report["variants"])
    assert len(rows_by_variant["default_active_stack_n8a2"]) == 5
