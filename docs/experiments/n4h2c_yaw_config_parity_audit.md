# N4H2C yaw config parity audit

N4H2C is the decision-driven follow-up to N4H2. N4H2 replay completed and
position passed the project gate, but yaw did not. This stage plans a yaw
configuration and convention parity audit only.

It does not implement a new EKF, raw Doppler, Go2 priors, source-aware
weighting, LSIM/OIM, or FGO.

## Trigger

From `docs/experiments/n4h2_replay_decision.md`:

- position_replay_gate_pass: true
- yaw_replay_gate_pass: false
- yaw_config_issue: true
- recommended_next_stage: N4H2C_yaw_config_parity_audit

## Audit Targets

- `yaw_sign`
- `yaw_install_offset_deg`
- `yaw_std_mode`
- A1_dual_diff formula
- `yaw_ned = 90 - yaw_body`
- trace yaw convention
- antlever / antenna order
- KF-GINS replay config yaw fields
- process_data-compatible `.gnss` yaw column semantics
- parser and evaluator yaw column semantics

## Required Evidence

The audit must compare the committed N4H1/N4H2 reports with the real local
artifact metadata when available, but it must keep real `.gnss`, `.imu`, NAV,
STD, IMU_ERR, trace, and error-series files out of Git.

Evidence should answer:

- whether generated yaw follows the intended A1 dual-difference formula;
- whether NED yaw conversion is consistent with the external KF-GINS reader;
- whether replay yaw residuals imply a sign, offset, antenna-order, or
  convention mismatch;
- whether trace yaw is being used only after replay for evaluation;
- whether antlever and antenna order evidence is sufficient for a formal offset
  selection.

## Non-Goals

- no trace solver input;
- no output-only correction;
- no epoch deletion;
- no tuning to final_v23;
- no formal offset selection without physical antenna-order evidence;
- no formal numerical performance claim;
- no raw Doppler;
- no Go2 prior;
- no source-aware weighting;
- no LSIM/OIM;
- no FGO;
- no full EKF implementation.

## Expected Output

The eventual N4H2C implementation should produce a small decision artifact with:

- `yaw_sign_audited`
- `yaw_install_offset_audited`
- `yaw_std_mode_audited`
- `a1_dual_diff_formula_audited`
- `yaw_ned_conversion_audited`
- `trace_yaw_evaluation_only`
- `antenna_order_evidence_status`
- `formal_offset_selection_allowed`
- `recommended_next_stage`

Until that evidence exists, N4H2C is a planning/audit stage only.
