from legsa_gins.evaluation.yaw_provider_lineage import by2_a1_dual_diff_yaw_from_status_relpos


def test_yaw_lineage_declares_source_basis_not_trace_rmse() -> None:
    lineage = by2_a1_dual_diff_yaw_from_status_relpos(
        gnss1_rel_n_m=0.0,
        gnss1_rel_e_m=0.0,
        gnss1_rel_d_m=0.0,
        gnss2_rel_n_m=0.0,
        gnss2_rel_e_m=-1.0,
        gnss2_rel_d_m=0.0,
    )

    assert lineage.trace_tuned is False
    assert "not trace RMSE" in lineage.selection_basis
