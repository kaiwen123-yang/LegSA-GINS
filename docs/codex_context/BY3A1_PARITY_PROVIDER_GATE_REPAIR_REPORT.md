# BY3A1 Parity Provider Gate Repair Report

BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR audited BY3A0 candidate inputs against the accepted BY2 input chain and repaired only clear runtime input-chain mismatches.

## Decision

```text
status=BY3A1_provider_or_feedback_blocked
repaired_inputs_ready=true
by3_go2_priors_materialized=true
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_providers_or_feedback
```

## What Changed

- BY2 accepted input-chain references were extracted from current BY2 evidence.
- BY3A0 candidate inputs were found to differ from BY2 accepted runtime conventions in delimiter/header, IMU column count, single-baseline schema, and original time-normalization policy.
- Repaired BY3 runtime inputs were generated as no-header whitespace numeric files using a common BY3 body-source time zero.
- BY3 Go2 attitude, horizontal velocity, and joint prior provider files were materialized from `<BY3_GO2_BODY_SOURCE>` with Go2 truth claims disabled.

## Remaining Blockers

- BY3 Raw Doppler provider is blocked under the accepted BY2 RTKLIB/RINEX provider logic because required BY3 RINEX observation/navigation inputs were not found in the receiver CSV tree.
- BY3 same-case selected feedback is blocked until a real BY3 stage1 solver and official evaluation create same-case EVAL_NAV state/estimate rows.
- `single_antenna_gnss1_status_KF_GINS` runner handoff remains unaccepted.
- `final_v23_dual_antenna_EKF` external-baseline runner/input gate remains unvalidated.

No BY3 solver, official evaluator, artificial degradation, degradation matrix, metric figure generation, parameter retuning, trace tuning, final_v23 config mutation, or paper claim was performed.
