from scripts.experiments import run_by3b_position_up_diagnostic_yaw_planning as by3b


def test_by3b_case_matrix_counts_and_exclusions():
    rows = by3b.build_case_matrix()
    counts = by3b.summarize_cases(rows)

    assert counts["total_case_seed_units"] == 118
    assert counts["primary_position_up_units"] == 75
    assert counts["diagnostic_yaw_units"] == 43
    assert counts["solver_rows_planned"] == 311
    assert not any("2Hz" in row["case_id"] for row in rows)
    assert all(row["paper_claim_allowed"] is False for row in rows)


def test_by3b_yaw_diagnostic_cases_are_not_primary_or_single():
    rows = by3b.build_case_matrix()
    yaw_rows = [row for row in rows if row["metric_scope"] == "yaw_diagnostic_only"]

    assert yaw_rows
    assert all(row["yaw_metric_status"] == "diagnostic_only" for row in yaw_rows)
    assert all(row["single_applicable"] is False for row in yaw_rows)
    assert all(row["execution_requires_human_review"] is True for row in yaw_rows)


def test_by3b_command_templates_are_dry_run_only():
    rows = by3b.build_command_template_plan(by3b.build_case_matrix())

    assert rows
    assert all(row["execute_now"] is False for row in rows)
    assert all(row["dry_run_only"] is True for row in rows)
    assert all(row["HDT_yaw_input_allowed"] is False for row in rows)
    assert all(row["long_relpos_yaw_input_allowed"] is False for row in rows)
    assert all(row["paper_claim_allowed"] is False for row in rows)


def test_by3b_seed_plan_never_generates_arrays():
    rows = by3b.build_seed_plan(by3b.build_case_matrix())

    assert rows
    assert all(row["generated_now"] is False for row in rows)
    assert all(row["random_arrays_generated"] is False for row in rows)
    assert any(row["family"] == "C_position_noise" and row["seeds"] == "0..9" for row in rows)
    assert any(row["family"] == "D_position_spike" and row["seeds"] == "0..9" for row in rows)
    assert next(row for row in rows if row["family"] == "C_position_noise")["random_case_seed_units_in_matrix"] == 30
    assert next(row for row in rows if row["family"] == "M_mixed_yaw_diagnostic")["random_case_seed_units_in_matrix"] == 10


def test_by3b_dependency_plan_forbids_feedback_reuse():
    rows = by3b.build_dependency_plan(by3b.build_case_matrix())
    legsa_rows = [row for row in rows if row["algorithm"] == "LegSA_full_EKF"]

    assert legsa_rows
    assert all(row["BY2_feedback_allowed"] is False for row in rows)
    assert all(row["normal_feedback_reuse_allowed"] is False for row in rows)
    assert all(row["trace_error_columns_allowed_for_feedback"] is False for row in rows)
    assert all(row["feedback_generation_requirement"] is True for row in legsa_rows)
