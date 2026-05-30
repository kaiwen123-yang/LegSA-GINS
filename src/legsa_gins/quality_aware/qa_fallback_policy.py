from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


LEGSA_QA_FALLBACK_EKF = "LegSA_QA_Fallback_EKF"
LEGSA_FULL_EKF = "LegSA_full_EKF"


class QAState(Enum):
    S0_NORMAL_A1_VALID = "S0_NORMAL_A1_VALID"
    S1_A1_DEGRADED_BUT_USABLE = "S1_A1_DEGRADED_BUT_USABLE"
    S2_A1_INVALID_GNSS_USABLE = "S2_A1_INVALID_GNSS_USABLE"
    S3_GNSS_POSITION_DEGRADED = "S3_GNSS_POSITION_DEGRADED"
    S4_DOPPLER_IMU_GO2_BRIDGE = "S4_DOPPLER_IMU_GO2_BRIDGE"
    S5_HOLD_OR_DEAD_RECKONING = "S5_HOLD_OR_DEAD_RECKONING"
    S6_RECOVERY_FAST_A1_REACQUISITION = "S6_RECOVERY_FAST_A1_REACQUISITION"


class QAReason(Enum):
    A1_MISSING = "A1_MISSING"
    A1_BASELINE_INVALID = "A1_BASELINE_INVALID"
    A1_VALID_RATIO_LOW = "A1_VALID_RATIO_LOW"
    A1_YAW_STD_HIGH = "A1_YAW_STD_HIGH"
    A1_YAW_JUMP = "A1_YAW_JUMP"
    A1_RESIDUAL_HIGH = "A1_RESIDUAL_HIGH"
    GNSS_POS_MISSING = "GNSS_POS_MISSING"
    GNSS_POS_STD_HIGH = "GNSS_POS_STD_HIGH"
    GNSS_POS_INNOV_HIGH = "GNSS_POS_INNOV_HIGH"
    DOPPLER_MISSING = "DOPPLER_MISSING"
    GO2_BODY_STATE_MISSING = "GO2_BODY_STATE_MISSING"
    RECOVERY_CONSECUTIVE_A1_VALID = "RECOVERY_CONSECUTIVE_A1_VALID"
    RECOVERY_A1_REJECTED = "RECOVERY_A1_REJECTED"
    HOLD_TIMEOUT_RISK = "HOLD_TIMEOUT_RISK"
    TRACE_NOT_USED = "TRACE_NOT_USED"


class MeasurementAction(Enum):
    ACCEPT = "ACCEPT"
    DOWNWEIGHT = "DOWNWEIGHT"
    REJECT = "REJECT"
    RECOVERY_RAMP = "RECOVERY_RAMP"
    HOLD = "HOLD"
    UNAVAILABLE = "UNAVAILABLE"
    LIMITED = "LIMITED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class QAConfig:
    expected_a1_baseline_m: float | None = 0.5
    a1_baseline_tolerance_m: float = 0.35
    a1_min_valid_ratio: float = 0.6
    a1_yaw_std_degraded_deg: float = 3.0
    a1_yaw_std_invalid_deg: float = 10.0
    a1_yaw_residual_degraded_deg: float = 6.0
    a1_yaw_residual_invalid_deg: float = 15.0
    a1_yaw_jump_invalid_deg: float = 20.0
    gnss_pos_std_h_degraded_m: float = 3.0
    gnss_pos_std_u_degraded_m: float = 5.0
    gnss_pos_std_h_invalid_m: float = 15.0
    gnss_pos_std_u_invalid_m: float = 25.0
    gnss_pos_innovation_high_m: float = 15.0
    raw_doppler_min_count: int = 5
    recovery_required_consecutive_a1: int = 3
    recovery_yaw_residual_gate_deg: float = 8.0
    recovery_yaw_jump_gate_deg: float = 12.0
    recovery_initial_yaw_r_scale: float = 6.0
    recovery_final_yaw_r_scale: float = 1.0
    recovery_max_yaw_correction_deg: float = 5.0
    s1_yaw_r_scale: float = 4.0
    s3_gnss_pos_r_scale: float = 9.0
    s4_gnss_pos_r_scale: float = 25.0
    s5_hold_timeout_s: float = 5.0


@dataclass(frozen=True)
class QAClassifierInput:
    time: float
    dataset_id: str = ""
    case_id: str = ""
    algorithm_id: str = LEGSA_FULL_EKF
    a1_available: bool = False
    a1_relpos_diff_valid: bool = False
    a1_baseline_m: float | None = None
    a1_baseline_expected_m: float | None = None
    a1_valid_ratio_window: float | None = None
    a1_yaw_std_deg: float | None = None
    a1_yaw_residual_deg: float | None = None
    a1_yaw_jump_deg: float | None = None
    gnss_pos_available: bool = False
    gnss_status_or_fix: str | None = None
    gnss_pos_std_h_m: float | None = None
    gnss_pos_std_u_m: float | None = None
    gnss_pos_innovation_m: float | None = None
    raw_doppler_available: bool = False
    raw_doppler_count: int | None = None
    raw_doppler_residual: float | None = None
    go2_body_state_available: bool = False
    go2_imu_available: bool = False
    go2_velocity_prior_available: bool = False
    go2_attitude_prior_available: bool = False
    selected_feedback_allowed_nominal: bool = False
    filter_output_finite: bool = True
    covariance_finite: bool = True


@dataclass
class QADecision:
    time: float
    dataset_id: str
    case_id: str
    algorithm_id: str
    qa_state: QAState
    previous_qa_state: QAState | None
    reason_bits: list[QAReason]
    a1_valid: bool
    gnss_pos_valid: bool
    time_since_last_trusted_a1_s: float | None
    time_since_last_trusted_gnss_s: float | None
    consecutive_valid_a1_count: int
    active_mode: bool = False
    passive_only: bool = True
    a1_measurement_action: MeasurementAction = MeasurementAction.ACCEPT
    gnss_position_action: MeasurementAction = MeasurementAction.ACCEPT
    raw_doppler_action: MeasurementAction = MeasurementAction.UNAVAILABLE
    go2_aux_action: MeasurementAction = MeasurementAction.UNAVAILABLE
    selected_feedback_action: MeasurementAction = MeasurementAction.ACCEPT
    yaw_R_scale: float = 1.0
    gnss_pos_R_scale: float = 1.0
    doppler_R_scale: float = 1.0
    recovery_ramp_active: bool = False
    requested_yaw_correction_deg: float = 0.0
    yaw_correction_applied_deg: float = 0.0
    recovery_yaw_correction_cap_deg: float = 0.0
    yaw_correction_clipped: bool = False
    state_transition_reason: str = ""
    trace_used_for_QA: bool = False
    source: QAClassifierInput | None = None

    @property
    def state_transition_flag(self) -> bool:
        return self.previous_qa_state is not None and self.previous_qa_state != self.qa_state

    def reason_text(self) -> str:
        return "|".join(reason.value for reason in self.reason_bits)

    def to_log_row(self) -> dict[str, object]:
        source = self.source or QAClassifierInput(time=self.time)
        return {
            "time": self.time,
            "dataset_id": self.dataset_id,
            "case_id": self.case_id,
            "algorithm_id": self.algorithm_id,
            "qa_state": self.qa_state.value,
            "previous_qa_state": self.previous_qa_state.value if self.previous_qa_state else "",
            "state_transition_flag": self.state_transition_flag,
            "reason_bits": self.reason_text(),
            "a1_available": source.a1_available,
            "a1_valid": self.a1_valid,
            "a1_baseline_m": _blank_if_none(source.a1_baseline_m),
            "a1_baseline_expected_m": _blank_if_none(
                source.a1_baseline_expected_m
            ),
            "a1_valid_ratio_window": _blank_if_none(
                source.a1_valid_ratio_window
            ),
            "a1_yaw_std_deg": _blank_if_none(source.a1_yaw_std_deg),
            "a1_yaw_residual_deg": _blank_if_none(source.a1_yaw_residual_deg),
            "a1_yaw_jump_deg": _blank_if_none(source.a1_yaw_jump_deg),
            "time_since_last_trusted_a1_s": _blank_if_none(
                self.time_since_last_trusted_a1_s
            ),
            "consecutive_valid_a1_count": self.consecutive_valid_a1_count,
            "gnss_pos_available": source.gnss_pos_available,
            "gnss_pos_valid": self.gnss_pos_valid,
            "gnss_status_or_fix": source.gnss_status_or_fix or "",
            "gnss_pos_std_h_m": _blank_if_none(source.gnss_pos_std_h_m),
            "gnss_pos_std_u_m": _blank_if_none(source.gnss_pos_std_u_m),
            "time_since_last_trusted_gnss_s": _blank_if_none(
                self.time_since_last_trusted_gnss_s
            ),
            "raw_doppler_available": source.raw_doppler_available,
            "raw_doppler_count": _blank_if_none(source.raw_doppler_count),
            "raw_doppler_residual": _blank_if_none(source.raw_doppler_residual),
            "go2_body_state_available": source.go2_body_state_available,
            "go2_imu_available": source.go2_imu_available,
            "selected_feedback_allowed_nominal": (
                source.selected_feedback_allowed_nominal
            ),
            "passive_only": self.passive_only,
            "trace_used_for_QA": self.trace_used_for_QA,
            "active_mode": self.active_mode,
            "measurement_policy_id": _policy_id(self),
            "a1_measurement_action": self.a1_measurement_action.value,
            "gnss_position_action": self.gnss_position_action.value,
            "raw_doppler_action": self.raw_doppler_action.value,
            "go2_aux_action": self.go2_aux_action.value,
            "selected_feedback_action": self.selected_feedback_action.value,
            "yaw_R_scale": self.yaw_R_scale,
            "gnss_pos_R_scale": self.gnss_pos_R_scale,
            "doppler_R_scale": self.doppler_R_scale,
            "recovery_ramp_active": self.recovery_ramp_active,
            "recovery_consecutive_valid_a1_count": (
                self.consecutive_valid_a1_count
            ),
            "requested_yaw_correction_deg": self.requested_yaw_correction_deg,
            "yaw_correction_applied_deg": self.yaw_correction_applied_deg,
            "recovery_yaw_correction_cap_deg": (
                self.recovery_yaw_correction_cap_deg
            ),
            "yaw_correction_clipped": self.yaw_correction_clipped,
            "state_transition_reason": self.state_transition_reason,
        }


class PassiveQualityClassifier:
    def __init__(self, config: QAConfig | None = None) -> None:
        self.config = config or QAConfig()
        self.previous_state: QAState | None = None
        self.last_trusted_a1_time: float | None = None
        self.last_trusted_gnss_time: float | None = None
        self.consecutive_valid_a1_count = 0
        self.recovery_candidate_active = False

    def classify(
        self, inputs: QAClassifierInput, *, active_mode: bool = False
    ) -> QADecision:
        reasons = [QAReason.TRACE_NOT_USED]
        a1_valid, a1_degraded = self._classify_a1(inputs, reasons)
        gnss_valid, gnss_degraded, gnss_invalid = self._classify_gnss(
            inputs, reasons
        )
        raw_available = self._raw_available(inputs, reasons)
        go2_available = self._go2_available(inputs, reasons)

        if a1_valid:
            self.consecutive_valid_a1_count += 1
            self.last_trusted_a1_time = inputs.time
        else:
            self.consecutive_valid_a1_count = 0
        if gnss_valid:
            self.last_trusted_gnss_time = inputs.time

        time_since_a1 = _elapsed(inputs.time, self.last_trusted_a1_time)
        time_since_gnss = _elapsed(inputs.time, self.last_trusted_gnss_time)
        state = self._state_for(
            inputs=inputs,
            a1_valid=a1_valid,
            a1_degraded=a1_degraded,
            gnss_valid=gnss_valid,
            gnss_degraded=gnss_degraded,
            gnss_invalid=gnss_invalid,
            raw_available=raw_available,
            go2_available=go2_available,
            reasons=reasons,
        )
        decision = QADecision(
            time=inputs.time,
            dataset_id=inputs.dataset_id,
            case_id=inputs.case_id,
            algorithm_id=inputs.algorithm_id,
            qa_state=state,
            previous_qa_state=self.previous_state,
            reason_bits=_dedupe_reasons(reasons),
            a1_valid=a1_valid,
            gnss_pos_valid=gnss_valid,
            time_since_last_trusted_a1_s=time_since_a1,
            time_since_last_trusted_gnss_s=time_since_gnss,
            consecutive_valid_a1_count=self.consecutive_valid_a1_count,
            source=inputs,
        )
        apply_measurement_policy(decision, self.config, active_mode=active_mode)
        self.previous_state = state
        return decision

    def _classify_a1(
        self, inputs: QAClassifierInput, reasons: list[QAReason]
    ) -> tuple[bool, bool]:
        if not inputs.a1_available:
            reasons.append(QAReason.A1_MISSING)
            return False, False

        expected = inputs.a1_baseline_expected_m
        if expected is None:
            expected = self.config.expected_a1_baseline_m
        baseline_invalid = False
        if inputs.a1_baseline_m is not None and expected is not None:
            baseline_invalid = (
                abs(inputs.a1_baseline_m - expected)
                > self.config.a1_baseline_tolerance_m
            )
        if not inputs.a1_relpos_diff_valid or baseline_invalid:
            reasons.append(QAReason.A1_BASELINE_INVALID)

        if (
            inputs.a1_valid_ratio_window is not None
            and inputs.a1_valid_ratio_window < self.config.a1_min_valid_ratio
        ):
            reasons.append(QAReason.A1_VALID_RATIO_LOW)
        if (
            inputs.a1_yaw_std_deg is not None
            and inputs.a1_yaw_std_deg > self.config.a1_yaw_std_degraded_deg
        ):
            reasons.append(QAReason.A1_YAW_STD_HIGH)
        if (
            inputs.a1_yaw_residual_deg is not None
            and abs(inputs.a1_yaw_residual_deg)
            > self.config.a1_yaw_residual_degraded_deg
        ):
            reasons.append(QAReason.A1_RESIDUAL_HIGH)
        if (
            inputs.a1_yaw_jump_deg is not None
            and abs(inputs.a1_yaw_jump_deg) > self.config.a1_yaw_jump_invalid_deg
        ):
            reasons.append(QAReason.A1_YAW_JUMP)

        hard_invalid = (
            not inputs.a1_relpos_diff_valid
            or baseline_invalid
            or (
                inputs.a1_yaw_std_deg is not None
                and inputs.a1_yaw_std_deg > self.config.a1_yaw_std_invalid_deg
            )
            or (
                inputs.a1_yaw_residual_deg is not None
                and abs(inputs.a1_yaw_residual_deg)
                > self.config.a1_yaw_residual_invalid_deg
            )
            or (
                inputs.a1_yaw_jump_deg is not None
                and abs(inputs.a1_yaw_jump_deg)
                > self.config.a1_yaw_jump_invalid_deg
            )
        )
        degraded = any(
            reason
            in {
                QAReason.A1_VALID_RATIO_LOW,
                QAReason.A1_YAW_STD_HIGH,
                QAReason.A1_RESIDUAL_HIGH,
            }
            for reason in reasons
        )
        return not hard_invalid and not degraded, (not hard_invalid and degraded)

    def _classify_gnss(
        self, inputs: QAClassifierInput, reasons: list[QAReason]
    ) -> tuple[bool, bool, bool]:
        if not inputs.gnss_pos_available:
            reasons.append(QAReason.GNSS_POS_MISSING)
            return False, False, True

        h_std = inputs.gnss_pos_std_h_m
        u_std = inputs.gnss_pos_std_u_m
        std_high = (
            (h_std is not None and h_std > self.config.gnss_pos_std_h_degraded_m)
            or (
                u_std is not None
                and u_std > self.config.gnss_pos_std_u_degraded_m
            )
        )
        std_invalid = (
            (h_std is not None and h_std > self.config.gnss_pos_std_h_invalid_m)
            or (u_std is not None and u_std > self.config.gnss_pos_std_u_invalid_m)
        )
        if std_high:
            reasons.append(QAReason.GNSS_POS_STD_HIGH)
        innov_high = (
            inputs.gnss_pos_innovation_m is not None
            and inputs.gnss_pos_innovation_m > self.config.gnss_pos_innovation_high_m
        )
        if innov_high:
            reasons.append(QAReason.GNSS_POS_INNOV_HIGH)
        invalid = std_invalid or (
            inputs.gnss_status_or_fix is not None
            and inputs.gnss_status_or_fix.lower() in {"invalid", "none", "no_fix"}
        )
        degraded = std_high or innov_high
        return not degraded and not invalid, degraded and not invalid, invalid

    def _raw_available(
        self, inputs: QAClassifierInput, reasons: list[QAReason]
    ) -> bool:
        available = inputs.raw_doppler_available and (
            inputs.raw_doppler_count is None
            or inputs.raw_doppler_count >= self.config.raw_doppler_min_count
        )
        if not available:
            reasons.append(QAReason.DOPPLER_MISSING)
        return available

    @staticmethod
    def _go2_available(
        inputs: QAClassifierInput, reasons: list[QAReason]
    ) -> bool:
        available = (
            inputs.go2_body_state_available
            or inputs.go2_imu_available
            or inputs.go2_velocity_prior_available
            or inputs.go2_attitude_prior_available
        )
        if not available:
            reasons.append(QAReason.GO2_BODY_STATE_MISSING)
        return available

    def _state_for(
        self,
        *,
        inputs: QAClassifierInput,
        a1_valid: bool,
        a1_degraded: bool,
        gnss_valid: bool,
        gnss_degraded: bool,
        gnss_invalid: bool,
        raw_available: bool,
        go2_available: bool,
        reasons: list[QAReason],
    ) -> QAState:
        if not inputs.filter_output_finite or not inputs.covariance_finite:
            reasons.append(QAReason.HOLD_TIMEOUT_RISK)
            return QAState.S5_HOLD_OR_DEAD_RECKONING
        degraded_states = {
                QAState.S1_A1_DEGRADED_BUT_USABLE,
                QAState.S2_A1_INVALID_GNSS_USABLE,
                QAState.S3_GNSS_POSITION_DEGRADED,
                QAState.S4_DOPPLER_IMU_GO2_BRIDGE,
                QAState.S5_HOLD_OR_DEAD_RECKONING,
            }
        if (
            self.previous_state == QAState.S6_RECOVERY_FAST_A1_REACQUISITION
            and a1_valid
            and gnss_valid
        ):
            self.recovery_candidate_active = False
        elif self.previous_state in degraded_states and a1_valid and gnss_valid:
            self.recovery_candidate_active = True
        if not a1_valid or not gnss_valid:
            self.recovery_candidate_active = self.previous_state in degraded_states
        recovery_ready = (
            self.recovery_candidate_active
            and a1_valid
            and gnss_valid
            and self.consecutive_valid_a1_count
            >= self.config.recovery_required_consecutive_a1
            and (
                inputs.a1_yaw_residual_deg is None
                or abs(inputs.a1_yaw_residual_deg)
                <= self.config.recovery_yaw_residual_gate_deg
            )
            and (
                inputs.a1_yaw_jump_deg is None
                or abs(inputs.a1_yaw_jump_deg) <= self.config.recovery_yaw_jump_gate_deg
            )
        )
        if recovery_ready:
            reasons.append(QAReason.RECOVERY_CONSECUTIVE_A1_VALID)
            return QAState.S6_RECOVERY_FAST_A1_REACQUISITION
        if self.previous_state in {
            QAState.S1_A1_DEGRADED_BUT_USABLE,
            QAState.S2_A1_INVALID_GNSS_USABLE,
            QAState.S3_GNSS_POSITION_DEGRADED,
            QAState.S4_DOPPLER_IMU_GO2_BRIDGE,
            QAState.S5_HOLD_OR_DEAD_RECKONING,
        } and inputs.a1_available and not a1_valid:
            reasons.append(QAReason.RECOVERY_A1_REJECTED)
        if self.recovery_candidate_active and a1_valid and gnss_valid:
            return QAState.S1_A1_DEGRADED_BUT_USABLE
        if a1_valid and gnss_valid:
            return QAState.S0_NORMAL_A1_VALID
        if a1_degraded and gnss_valid:
            return QAState.S1_A1_DEGRADED_BUT_USABLE
        if not a1_valid and gnss_valid:
            return QAState.S2_A1_INVALID_GNSS_USABLE
        if gnss_degraded:
            return QAState.S3_GNSS_POSITION_DEGRADED
        if gnss_invalid and (raw_available or go2_available):
            return QAState.S4_DOPPLER_IMU_GO2_BRIDGE
        reasons.append(QAReason.HOLD_TIMEOUT_RISK)
        return QAState.S5_HOLD_OR_DEAD_RECKONING


def apply_measurement_policy(
    decision: QADecision, config: QAConfig | None = None, *, active_mode: bool
) -> QADecision:
    cfg = config or QAConfig()
    source = decision.source
    raw_available = bool(source and source.raw_doppler_available)
    go2_available = bool(
        source
        and (
            source.go2_body_state_available
            or source.go2_imu_available
            or source.go2_velocity_prior_available
            or source.go2_attitude_prior_available
        )
    )
    decision.active_mode = active_mode
    decision.passive_only = not active_mode
    decision.raw_doppler_action = (
        MeasurementAction.ACCEPT if raw_available else MeasurementAction.UNAVAILABLE
    )
    decision.go2_aux_action = (
        MeasurementAction.ACCEPT if go2_available else MeasurementAction.UNAVAILABLE
    )
    state = decision.qa_state
    if state == QAState.S0_NORMAL_A1_VALID:
        pass
    elif state == QAState.S1_A1_DEGRADED_BUT_USABLE:
        decision.a1_measurement_action = MeasurementAction.DOWNWEIGHT
        decision.yaw_R_scale = cfg.s1_yaw_r_scale
        decision.selected_feedback_action = MeasurementAction.DISABLED
    elif state == QAState.S2_A1_INVALID_GNSS_USABLE:
        decision.a1_measurement_action = MeasurementAction.REJECT
        decision.selected_feedback_action = MeasurementAction.DISABLED
    elif state == QAState.S3_GNSS_POSITION_DEGRADED:
        decision.gnss_position_action = MeasurementAction.DOWNWEIGHT
        decision.gnss_pos_R_scale = cfg.s3_gnss_pos_r_scale
        if not decision.a1_valid:
            decision.a1_measurement_action = MeasurementAction.REJECT
        decision.selected_feedback_action = MeasurementAction.DISABLED
    elif state == QAState.S4_DOPPLER_IMU_GO2_BRIDGE:
        decision.gnss_position_action = MeasurementAction.REJECT
        decision.gnss_pos_R_scale = cfg.s4_gnss_pos_r_scale
        decision.a1_measurement_action = (
            MeasurementAction.ACCEPT if decision.a1_valid else MeasurementAction.REJECT
        )
        decision.selected_feedback_action = MeasurementAction.DISABLED
    elif state == QAState.S5_HOLD_OR_DEAD_RECKONING:
        decision.gnss_position_action = MeasurementAction.HOLD
        decision.a1_measurement_action = MeasurementAction.REJECT
        decision.raw_doppler_action = (
            MeasurementAction.ACCEPT if raw_available else MeasurementAction.UNAVAILABLE
        )
        decision.go2_aux_action = (
            MeasurementAction.ACCEPT if go2_available else MeasurementAction.UNAVAILABLE
        )
        decision.selected_feedback_action = MeasurementAction.DISABLED
    elif state == QAState.S6_RECOVERY_FAST_A1_REACQUISITION:
        decision.a1_measurement_action = MeasurementAction.RECOVERY_RAMP
        decision.recovery_ramp_active = True
        decision.recovery_yaw_correction_cap_deg = cfg.recovery_max_yaw_correction_deg
        extra = max(
            0,
            cfg.recovery_required_consecutive_a1
            - min(
                decision.consecutive_valid_a1_count,
                cfg.recovery_required_consecutive_a1,
            ),
        )
        step = (
            cfg.recovery_initial_yaw_r_scale - cfg.recovery_final_yaw_r_scale
        ) / max(1, cfg.recovery_required_consecutive_a1)
        decision.yaw_R_scale = max(
            cfg.recovery_final_yaw_r_scale,
            cfg.recovery_initial_yaw_r_scale - step * (cfg.recovery_required_consecutive_a1 - extra),
        )
        decision.selected_feedback_action = MeasurementAction.DISABLED
    decision.state_transition_reason = decision.reason_text()
    return decision


def write_qa_log(path: str | Path, decisions: Iterable[QADecision]) -> None:
    rows = [decision.to_log_row() for decision in decisions]
    if not rows:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize_qa_decisions(
    decisions: list[QADecision], *, sample_interval_s: float = 1.0
) -> dict[str, object]:
    if not decisions:
        return {
            "total_rows": 0,
            "transition_count": 0,
            "state_duration_ratio": {},
            "trace_used_for_QA": False,
        }
    totals = {state.value: 0.0 for state in QAState}
    for index, decision in enumerate(decisions):
        if index + 1 < len(decisions):
            duration = max(0.0, decisions[index + 1].time - decision.time)
        else:
            duration = sample_interval_s
        totals[decision.qa_state.value] += duration
    total_time = sum(totals.values()) or 1.0
    return {
        "total_rows": len(decisions),
        "transition_count": sum(
            1 for decision in decisions if decision.state_transition_flag
        ),
        "first_state": decisions[0].qa_state.value,
        "last_state": decisions[-1].qa_state.value,
        "state_duration_ratio": {
            state: duration / total_time for state, duration in totals.items()
        },
        "state_duration_s": totals,
        "a1_accept_passive_count": sum(1 for row in decisions if row.a1_valid),
        "a1_degraded_or_reject_passive_count": sum(
            1 for row in decisions if not row.a1_valid
        ),
        "gnss_accept_passive_count": sum(
            1 for row in decisions if row.gnss_pos_valid
        ),
        "gnss_degraded_or_reject_passive_count": sum(
            1 for row in decisions if not row.gnss_pos_valid
        ),
        "recovery_candidate_count": sum(
            1
            for row in decisions
            if row.qa_state == QAState.S6_RECOVERY_FAST_A1_REACQUISITION
        ),
        "trace_used_for_QA": any(row.trace_used_for_QA for row in decisions),
    }


def _elapsed(now: float, then: float | None) -> float | None:
    if then is None:
        return None
    return max(0.0, now - then)


def _blank_if_none(value: object | None) -> object:
    return "" if value is None else value


def _dedupe_reasons(reasons: Iterable[QAReason]) -> list[QAReason]:
    seen: set[QAReason] = set()
    out: list[QAReason] = []
    for reason in reasons:
        if reason not in seen:
            out.append(reason)
            seen.add(reason)
    return out


def _policy_id(decision: QADecision) -> str:
    suffix = "active" if decision.active_mode else "passive"
    return f"qa_fallback_{decision.qa_state.value}_{suffix}"


def finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return value if math.isfinite(value) else None
