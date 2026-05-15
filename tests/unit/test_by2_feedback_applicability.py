from legsa_gins.reporting.by2_feedback_applicability import get_feedback_applicability

# 中文说明：feedback 绘图适用性必须由 variant role 优先决定。


def test_a0_baseline_no_feedback_ignores_raw_rows():
    app = get_feedback_applicability(
        "A0_source_backed_ekf_baseline",
        {"variant_id": "A0_source_backed_ekf_baseline", "n8j_source_variant": "baseline_no_feedback", "feedback_mode": "none"},
        175,
        {"feedback_accept": 0, "feedback_reject": 0},
    )
    assert app.variant_role == "baseline_no_feedback"
    assert app.is_feedback_applicable is False
    assert app.effective_feedback_rows_for_plotting == 0
    assert app.raw_feedback_rows_detected == 175
    assert app.raw_rows_ignored is True
    assert app.raw_rows_ignored_reason == "variant_role_baseline_no_feedback"


def test_selected_feedback_with_rows_is_applicable():
    app = get_feedback_applicability(
        "A8_feedback_selected_conservative_gate",
        {"variant_id": "A8_feedback_selected_conservative_gate", "n8j_source_variant": "n8j_selected_conservative_feedback", "feedback_mode": "horizontal_velocity_attitude_feedback"},
        151,
        {"feedback_accept": 151, "feedback_reject": 24},
    )
    assert app.is_feedback_applicable is True
    assert app.effective_feedback_rows_for_plotting == 151


def test_missing_semantic_spec_fails_instead_of_guessing():
    try:
        get_feedback_applicability("A0_source_backed_ekf_baseline", {}, 175, {})
    except ValueError as exc:
        assert "missing semantic spec" in str(exc)
    else:
        raise AssertionError("missing semantic spec should fail")
