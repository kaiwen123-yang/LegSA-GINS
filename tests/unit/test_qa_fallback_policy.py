from dataclasses import replace

from legsa_gins.quality_aware.qa_fallback_policy import (
    LEGSA_FULL_EKF,
    LEGSA_QA_FALLBACK_EKF,
    MeasurementAction,
    PassiveQualityClassifier,
    QAClassifierInput,
    QAReason,
    QAState,
    summarize_qa_decisions,
)


def _nominal(time: float = 0.0, algorithm_id: str = LEGSA_FULL_EKF) -> QAClassifierInput:
    return QAClassifierInput(
        time=time,
        dataset_id="BY2",
        case_id="normal",
        algorithm_id=algorithm_id,
        a1_available=True,
        a1_relpos_diff_valid=True,
        a1_baseline_m=0.52,
        a1_baseline_expected_m=0.5,
        a1_valid_ratio_window=0.98,
        a1_yaw_std_deg=1.5,
        a1_yaw_residual_deg=1.0,
        a1_yaw_jump_deg=0.5,
        gnss_pos_available=True,
        gnss_status_or_fix="fix",
        gnss_pos_std_h_m=0.8,
        gnss_pos_std_u_m=1.2,
        raw_doppler_available=True,
        raw_doppler_count=9,
        go2_body_state_available=True,
        go2_imu_available=True,
        selected_feedback_allowed_nominal=True,
    )


def test_qa1_nominal_maps_to_s0_without_active_changes() -> None:
    decision = PassiveQualityClassifier().classify(_nominal(), active_mode=False)

    assert decision.qa_state == QAState.S0_NORMAL_A1_VALID
    assert decision.passive_only is True
    assert decision.trace_used_for_QA is False
    assert QAReason.TRACE_NOT_USED in decision.reason_bits
    assert decision.a1_measurement_action == MeasurementAction.ACCEPT
    assert decision.gnss_position_action == MeasurementAction.ACCEPT


def test_qa8a_residual_only_nominal_a1_stays_transparent() -> None:
    decision = PassiveQualityClassifier().classify(
        replace(
            _nominal(time=1.0, algorithm_id=LEGSA_QA_FALLBACK_EKF),
            a1_yaw_residual_deg=20.0,
        ),
        active_mode=True,
    )

    assert QAReason.A1_RESIDUAL_HIGH in decision.reason_bits
    assert decision.qa_state == QAState.S0_NORMAL_A1_VALID
    assert decision.a1_measurement_action == MeasurementAction.ACCEPT
    assert decision.yaw_R_scale == 1.0
    assert decision.selected_feedback_action == MeasurementAction.ACCEPT


def test_qa1_invalid_a1_with_good_gnss_maps_to_s2() -> None:
    classifier = PassiveQualityClassifier()
    decision = classifier.classify(
        QAClassifierInput(
            time=1.0,
            dataset_id="PG1",
            case_id="severe",
            a1_available=True,
            a1_relpos_diff_valid=False,
            a1_baseline_m=9.18,
            a1_baseline_expected_m=0.5,
            a1_yaw_std_deg=1.5,
            gnss_pos_available=True,
            gnss_pos_std_h_m=1.0,
            gnss_pos_std_u_m=2.0,
            raw_doppler_available=True,
            raw_doppler_count=8,
            go2_body_state_available=True,
        )
    )

    assert decision.qa_state == QAState.S2_A1_INVALID_GNSS_USABLE
    assert QAReason.A1_BASELINE_INVALID in decision.reason_bits
    assert decision.a1_measurement_action == MeasurementAction.REJECT


def test_qa2_active_policy_rejects_invalid_a1_for_qa_candidate_only() -> None:
    decision = PassiveQualityClassifier().classify(
        QAClassifierInput(
            time=2.0,
            algorithm_id=LEGSA_QA_FALLBACK_EKF,
            a1_available=True,
            a1_relpos_diff_valid=False,
            a1_baseline_m=50.0,
            a1_baseline_expected_m=0.5,
            gnss_pos_available=True,
            gnss_pos_std_h_m=1.0,
            gnss_pos_std_u_m=1.5,
            raw_doppler_available=True,
            raw_doppler_count=8,
            go2_body_state_available=True,
        ),
        active_mode=True,
    )

    assert decision.active_mode is True
    assert decision.passive_only is False
    assert decision.qa_state == QAState.S2_A1_INVALID_GNSS_USABLE
    assert decision.a1_measurement_action == MeasurementAction.REJECT
    assert decision.raw_doppler_action == MeasurementAction.ACCEPT
    assert decision.selected_feedback_action == MeasurementAction.DISABLED


def test_qa2_recovery_requires_consecutive_valid_a1_epochs() -> None:
    classifier = PassiveQualityClassifier()
    classifier.classify(
        QAClassifierInput(
            time=0.0,
            a1_available=True,
            a1_relpos_diff_valid=False,
            a1_baseline_m=12.0,
            gnss_pos_available=True,
            gnss_pos_std_h_m=1.0,
            gnss_pos_std_u_m=1.0,
        ),
        active_mode=True,
    )
    decisions = [
        classifier.classify(_nominal(time=float(idx), algorithm_id=LEGSA_QA_FALLBACK_EKF), active_mode=True)
        for idx in (1, 2, 3)
    ]

    assert decisions[-1].qa_state == QAState.S6_RECOVERY_FAST_A1_REACQUISITION
    assert decisions[-1].a1_measurement_action == MeasurementAction.RECOVERY_RAMP
    assert decisions[-1].recovery_ramp_active is True
    assert decisions[-1].yaw_R_scale > 1.0
    assert decisions[-1].selected_feedback_action == MeasurementAction.DISABLED
    assert decisions[-1].recovery_yaw_correction_cap_deg == 1.0
    assert QAReason.RECOVERY_CONSECUTIVE_A1_VALID in decisions[-1].reason_bits
    post_recovery = classifier.classify(
        _nominal(time=4.0, algorithm_id=LEGSA_QA_FALLBACK_EKF),
        active_mode=True,
    )
    assert post_recovery.qa_state == QAState.S0_NORMAL_A1_VALID




def test_qa8a_s1_jitter_does_not_enter_s6_recovery() -> None:
    classifier = PassiveQualityClassifier()
    degraded = replace(
        _nominal(time=0.0, algorithm_id=LEGSA_QA_FALLBACK_EKF),
        a1_yaw_std_deg=4.0,
    )
    first = classifier.classify(degraded, active_mode=True)
    decisions = [
        classifier.classify(
            _nominal(time=float(idx), algorithm_id=LEGSA_QA_FALLBACK_EKF),
            active_mode=True,
        )
        for idx in (1, 2, 3)
    ]

    assert first.qa_state == QAState.S1_A1_DEGRADED_BUT_USABLE
    assert all(row.qa_state != QAState.S6_RECOVERY_FAST_A1_REACQUISITION for row in decisions)
    assert decisions[-1].qa_state == QAState.S0_NORMAL_A1_VALID

def test_qa3_summary_tracks_state_ratios_and_trace_boundary() -> None:
    classifier = PassiveQualityClassifier()
    rows = [
        classifier.classify(_nominal(time=0.0)),
        classifier.classify(
            QAClassifierInput(
                time=1.0,
                a1_available=False,
                gnss_pos_available=False,
                raw_doppler_available=False,
                go2_body_state_available=False,
            )
        ),
    ]

    summary = summarize_qa_decisions(rows)

    assert summary["total_rows"] == 2
    assert summary["transition_count"] == 1
    assert summary["trace_used_for_QA"] is False
    assert summary["state_duration_ratio"][QAState.S0_NORMAL_A1_VALID.value] > 0.0
    assert summary["state_duration_ratio"][QAState.S5_HOLD_OR_DEAD_RECKONING.value] > 0.0
