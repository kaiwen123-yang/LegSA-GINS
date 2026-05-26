from pathlib import Path

import pytest

from legsa_gins.reporting.by2_n9c1f_to_n9c3_evidence_package import (
    FGO_PLOTS,
    LEGGED_PLOTS,
    run_n9c1f_to_n9c3,
)


def test_n9c1f_runner_requires_no_solver_rerun(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_n9c1f_to_n9c3(
            tmp_path,
            stage_root=tmp_path / "stage",
            matrix_root=tmp_path / "matrix",
            archive_root=tmp_path / "archive",
            no_solver_rerun=False,
        )


def test_n9c1f_package_preserves_claim_boundary(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    archive = tmp_path / "archive"
    matrix_root = workspace / "by2-huitu" / "N9B2_FULL_MATRIX"
    r4n2 = archive / "by2-huitu" / "N9A_R4N2_EXISTING_CANDIDATE_LOG_FIGURE_COMPLETION" / "tables"
    r4o = archive / "by2-huitu" / "N9A_R4O_ACTIVE_FGO_FACTOR_WINDOW_LOGGING" / "05_factor_logs"
    n9c0d = workspace / "by2-huitu" / "N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION" / "matrix"
    n9c1b = workspace / "by2-huitu" / "N9C1A_TO_N9C1B_FIGURE_COVERAGE_AUDIT_AND_PER_CASE_MATERIALIZATION" / "matrix"
    r4n2.mkdir(parents=True)
    r4o.mkdir(parents=True)
    n9c0d.mkdir(parents=True)
    n9c1b.mkdir(parents=True)
    (r4n2 / "factor_window_metrics.csv").write_text(
        "window_id,time_s,factor_type,factor_rows,residual_rows,jacobian_nonzero,mean_abs_whitened_residual,cost_sum_sq,source_stage\n"
        "0,1.0,FootKinematicVelocityFactor,1,2,2,0.2,0.4,N9A_R4N2\n"
        "0,1.0,YawRateBetweenFactor,1,1,2,0.3,0.9,N9A_R4N2\n",
        encoding="utf-8",
    )
    (r4n2 / "factor_residual_rows.csv").write_text(
        "window_id,time_s,factor_type,dimension,raw_residual,whitened_residual,abs_whitened_residual,jacobian_nonzero,source_stage\n"
        "0,1.0,FootKinematicVelocityFactor,vn,0.1,0.2,0.2,1,N9A_R4N2\n"
        "0,1.0,YawRateBetweenFactor,yaw,0.2,0.3,0.3,2,N9A_R4N2\n",
        encoding="utf-8",
    )
    (r4o / "active_factor_window_metrics.csv").write_text("factor_type,status\n", encoding="utf-8")
    (n9c0d / "N9C0D_MODULE_VERIFICATION_BY_CASE.csv").write_text(
        "case_id,go2_joint_update_count,module_verification_passed\nFULL_normal_repeat,274,True\n",
        encoding="utf-8",
    )
    (n9c1b / "N9C1B_FIGURE_INDEX.csv").write_text("category,generated\n10_fgo_factors,false\n12_legged_factors,true\n", encoding="utf-8")
    (n9c1b / "N9C1B_BLOCKED_FIGURES.csv").write_text("category,blocked\n10_fgo_factors,true\n12_legged_factors,true\n", encoding="utf-8")

    result = run_n9c1f_to_n9c3(
        workspace,
        stage_root=workspace / "by2-huitu" / "stage",
        matrix_root=matrix_root,
        archive_root=archive,
        no_solver_rerun=True,
    )

    decision = result["decision"]
    assert decision["status"] == "N9C1F_to_N9C3_logging_blocked_but_report_package_complete"
    assert decision["ready_for_paper_claims"] is False
    assert decision["ready_for_N9B2_execution"] is False
    assert decision["ready_for_full_N9B_execution"] is False
    assert decision["complete_nine_factor_FGO_claim"] is False
    assert result["fgo_generated_count"] > 0
    assert result["still_blocked_count"] > 0
    blocked_names = {row["requested_plot"] for row in result["fgo_audit"] if not row["can_plot_now"]}
    assert "fgo_cost" in blocked_names
    assert "raw_doppler_fgo_residual" in blocked_names
    assert set(FGO_PLOTS)
    assert set(LEGGED_PLOTS)
