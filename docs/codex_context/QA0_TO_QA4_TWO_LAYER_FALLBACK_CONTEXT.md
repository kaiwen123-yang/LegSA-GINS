# QA0_TO_QA4 Two-Layer Fallback Context

Stage: `QA0_TO_QA4_TWO_LAYER_QUALITY_AWARE_FALLBACK_IMPLEMENTATION`

Runtime alias for this stage: `<QA0_TO_QA4_STAGE_ROOT>`

## Scope

This stage implements and reviews the separate candidate `LegSA_QA_Fallback_EKF`.

`LegSA_QA_Fallback_EKF` is defined as:

- nominal layer: frozen `LegSA_full_EKF` behavior when QA fallback is disabled
- supervisory layer: quality-aware state machine, measurement policy, and QA logs

This stage does not rename or replace `LegSA_full_EKF`, does not modify `final_v23`, and does not implement or claim complete nine-factor FGO.

## Implemented

- QA state enum names:
  - `S0_NORMAL_A1_VALID`
  - `S1_A1_DEGRADED_BUT_USABLE`
  - `S2_A1_INVALID_GNSS_USABLE`
  - `S3_GNSS_POSITION_DEGRADED`
  - `S4_DOPPLER_IMU_GO2_BRIDGE`
  - `S5_HOLD_OR_DEAD_RECKONING`
  - `S6_RECOVERY_FAST_A1_REACQUISITION`
- Passive classifier and per-epoch QA trace fields.
- Active measurement policy under `LegSA_QA_Fallback_EKF` / QA-enabled config only.
- Explicit A1 provenance gate: 15-column yaw alone is not enough to mark A1 relpos-diff valid.
- Selected-feedback disablement in degraded, invalid, hold, bridge, and recovery states.
- S6 gated recovery with consecutive valid A1 count, residual/jump gates, R ramp, capped yaw correction logging, and observed exit back to S0 in toy smoke.
- Runtime manifest QA boundary fields including `qa_trace_used_for_QA=false`.

## Validation Status

SYNC0: passed. WSL was aligned from the PAPER0 commit before QA work and a dedicated QA branch was used.

QA1: passed for passive classifier/logging and default no-op gating.

QA2: passed as implementation and toy/static smoke. Evidence includes QA tests, C++ build, and QA toy trace. This is not real dataset performance evidence.

QA3: conditional/static only. The QA3 package under `<QA0_TO_QA4_STAGE_ROOT>/QA3_VALIDATION_SUMMARIES` parses and marks `real_solver_evaluator_run=false`. Real BY2/BY3/PG validation was not run because confirmed local source paths and locked runtime configs were not available in the active workspace.

QA4: claim-boundary review classifies implementation claims conservatively. `ready_for_paper_claims=false`.

## Claim Boundary

Supported now:

- A separate `LegSA_QA_Fallback_EKF` candidate identity exists.
- QA fallback active policy is gated away from default `LegSA_full_EKF`.
- Toy/static evidence shows invalid/suspect A1 rejection/downweighting, selected-feedback disablement in degraded/recovery states, and S6 recovery logging.
- Trace is not used for QA classification or policy in the implemented path.

Partially supported:

- Invalid A1 prevention and fallback behavior are supported by code and toy/static evidence, but not by real PG1-PG4 validation.
- Graceful degradation is supported as an implementation/logging behavior, not as a performance claim.

Diagnostic-only:

- S6 effect on yaw error accumulation.
- BY3 yaw behavior.

Not supported:

- PG1-PG4 high-precision yaw or positioning performance.
- Comprehensive final_v23 outperformance.
- Complete active nine-factor FGO.
- Any paper-ready QA performance claim.

## Readiness Flags

- `ready_for_QA1`: `completed`
- `ready_for_QA2`: `completed`
- `ready_for_QA3`: `conditional_static_only`
- `ready_for_QA4`: `completed_claim_boundary_review`
- `ready_for_paper_claims`: `false`
- `ready_for_manuscript_drafting`: `false_for_QA_performance_claims`

## Required Next Gate

Recommended next stage: `QA5_REAL_CASE_DISCOVERY_AND_MINIMAL_VALIDATION_GATE`.

Before real validation, restore ignored local data-path mapping outside tracked docs, confirm BY2/BY3/PG source and runtime configs, confirm same-case feedback paths, and produce a runnable/not-runnable matrix. Real runs must remain minimal until the discovery gate passes.
