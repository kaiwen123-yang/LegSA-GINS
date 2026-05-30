# PG_QA0 Quality-Aware Fallback Design Context

Stage: `PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION`

Runtime root: `<PG_QA0_STAGE_ROOT>`

Status: design-only complete.

## Scope

PG_QA0 is a design-only follow-on after PG_MULTI_A0 and XB1A2. It organizes current BY2, BY3, and PG1-PG4 evidence and defines a future quality-aware fallback branch for severe GNSS cases. It does not implement a branch, run solvers, run evaluators, generate degraded inputs, generate random arrays, retune parameters, or create paper claims.

## Evidence Role

- BY2: main full-metric evidence route; position/up/yaw evidence is accepted within the existing BY2 scope.
- BY3: position/up generalization evidence; yaw remains diagnostic-only and should not block the paper.
- PG1-PG4: severe GNSS motivation; all repeats are quality-aware branch candidates because A1 relpos-diff yaw is invalid/nonphysical.

PG evidence is future-work motivation and design input only. It is not robustness evidence, performance evidence, or paper-claim evidence.

## Algorithm Identity

`LegSA_full_EKF` remains the frozen verified mainline for normal/moderate GNSS and BY2/BY3 position-up evidence.

`LegSA_QA_Fallback_EKF` is a separate future candidate. It is a supervisory quality manager plus fallback policy over the existing EKF update core. If implemented later, it must have a separate `algorithm_id`, quality-state logs, measurement enable/disable logs, R-scale logs, and validation package.

QA0 must not relabel `LegSA_full_EKF`, relabel final_v23, force invalid A1 yaw, or use final_v23 output as a solver input.

## State Machine

- `S0_NORMAL_DUAL_YAW`: A1 dual-yaw physical/stable, GNSS position acceptable, normal updates allowed.
- `S1_DEGRADED_DUAL_YAW_CAUTION`: A1 valid but noisy or jumpy, yaw downweighted/gated.
- `S2_YAW_UNAVAILABLE`: A1 relpos-diff nonphysical or valid ratio too low; dual-yaw update disabled.
- `S3_POOR_GNSS_POSITION_DOWNWEIGHT`: GNSS position valid but poor; position R-scale increases.
- `S4_RAW_DOPPLER_VELOCITY_AIDED`: Raw Doppler provider and residual quality acceptable; velocity aid retained.
- `S5_IMU_GO2_BRIDGE`: GNSS unreliable or unavailable; IMU plus Go2 priors bridge short intervals with low confidence.
- `S6_HOLD_OR_REJECT`: all GNSS-derived sources unreliable; unsafe GNSS updates are rejected.

## Measurement And R-Scale Policy

A1 dual-yaw is disabled if relpos-diff baseline geometry is nonphysical. GNSS position is downweighted or rejected using online source indicators such as fix status, satellite count, PDOP, reported standard deviations, correction gaps, and related source-quality fields. Raw Doppler is retained only when the provider exists and residual quality is acceptable. Go2 attitude, horizontal velocity, and joint priors may support bridge states but are not truth and are not full leg odometry.

Thresholds must not be tuned from trace RMSE, final_v23 output, future information, or final-metric-only labels. Acceptable threshold sources include online source indicators, sensor-reported uncertainty, physical baseline geometry, BY2/BY3 accepted source statistics, PG_MULTI_A0 quality profiles, literature/engineering defaults, and human-approved threshold decisions.

## Paper Mainline Decision

Current recommendation:

```text
status=PG_QA0_design_complete_human_review_before_QA1
paper_mainline_recommendation=Option_B_design_extension_now
optional_high_tier_route=Option_C_after_QA1_QA2_QA3
ready_for_QA1=false
ready_for_paper_claims=false
```

Option B keeps the near-term paper focused on the BY2/BY3 position-up mainline and describes quality-aware fallback as a design/limitation extension with no QA performance claim. Option C can become a secondary contribution only after human-approved QA1 classifier/logging, QA2 measurement/R-scale behavior, and QA3 validation.

## Forbidden Follow-On Without Human Review

- QA1 implementation
- quality-aware behavior changes
- solver/evaluator runs
- degraded inputs
- random arrays
- retuning
- trace-tuned thresholds
- paper claims
- PR #52 merge/closure/tag
