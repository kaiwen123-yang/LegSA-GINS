"""中文说明：N4H1 yaw-chain 候选只用于 diagnostic，不允许 formal selection。"""

from legsa_gins.evaluation.final_v23_yaw_chain_audit import (
    compare_final_v23_yaw_column,
    compute_a1_dual_diff_yaw,
    compute_yaw_candidates,
    wrap_deg180,
    wrap_deg360,
)


def test_a1_dual_diff_yaw_and_candidates():
    gnss1 = {"rel_pos_n": "0.0", "rel_pos_e": "0.0"}
    gnss2 = {"rel_pos_n": "1.0", "rel_pos_e": "1.0"}
    a1 = compute_a1_dual_diff_yaw(gnss1, gnss2)
    assert round(a1["yaw_deg"], 6) == 315.0
    candidates = compute_yaw_candidates(gnss1, gnss2)
    assert round(candidates["a1_dual_diff"], 6) == 315.0
    assert round(candidates["a1_dual_diff_plus90"], 6) == 45.0
    assert round(candidates["a1_dual_diff_minus90"], 6) == 225.0
    assert round(candidates["reverse_dual_diff"], 6) == 135.0
    assert candidates["formal_selection_allowed"] is False
    assert wrap_deg360(-10.0) == 350.0
    assert wrap_deg180(190.0) == -170.0


def test_compare_final_v23_yaw_column_matches_a1():
    final_rows = [{"time": 10.0, "yaw": 315.0}]
    gnss1_rows = [{"time": 10.0, "rel_pos_n": "0.0", "rel_pos_e": "0.0"}]
    gnss2_rows = [{"time": 10.0, "rel_pos_n": "1.0", "rel_pos_e": "1.0"}]
    report = compare_final_v23_yaw_column(final_rows, gnss1_rows, gnss2_rows)
    assert report["yaw_column_source_status"] == "matched_a1_dual_diff"
    assert report["best_matching_candidate_to_final_gnss_yaw"] == "a1_dual_diff"
    assert report["a1_dual_diff_matches_final_gnss_yaw"] is True
    assert report["formal_selection_allowed"] is False
