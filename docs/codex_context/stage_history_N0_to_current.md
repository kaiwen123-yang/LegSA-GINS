# Stage History N0 To Current

## N0-N3: Boundary And Source Policy

Established that LegSA-GINS is not a simple plotting task. The project builds a source-backed GNSS/INS/legged fusion chain while keeping trace truth and final_v23 out of solver inputs.

Key boundaries:

- trace is evaluation-only.
- final_v23/KF-GINS is reference/sanity/evaluation boundary only.
- BY2 is the current primary dataset.
- Windows audit workspace and WSL algorithm source repository are separate.

## N4: Source-Backed EKF Backbone

Built and audited the EKF backbone:

- IMU mechanization.
- State and covariance propagation.
- GNSS position update.
- Receiver velocity update where valid.
- Dual yaw update.
- State feedback.
- NAV / STD / EVAL_NAV / RUN_MANIFEST outputs.
- Provenance and no-trace/no-final_v23 input boundary checks.

## N5: Raw Doppler EKF Factor

Activated RTKLIB-backed Raw Doppler source. Raw Doppler is not NAV-PVT receiver velocity and not the 15-column `.gnss` velocity proxy. It became a real nonzero EKF frontend factor.

## N6: Source-Aware Weighting

Introduced source-aware LSIM/OIM weighting. The conservative policy is acceptable as an R-scaling layer, with stress evidence limited.

## N7: Go2 Proprioceptive Joint Factor

Mature factor definition:

```text
Go2 proprioceptive joint factor = Go2 roll/pitch + Go2 horizontal velocity
```

Not allowed as truth: Go2 absolute position, Go2 yaw, Go2 vertical velocity, and contact truth.

## N8A-N8E: No-Feedback FGO Backend

Built FGO dataset, factor registry, yaw wrap fix, smoothness policy review, Raw Doppler FGO, Go2 joint FGO, and formal engineering ablation.

Important fixes:

- N8A1/N8A2: yaw wrap bug found and fixed.
- N8C2/N8C3: Raw Doppler FGO solver injection bug found and fixed.
- N8D/N8E: weight review and formal engineering ablation with caveats.

## N8F: Legged Candidate Factors

Activated candidate legged factors:

- contact-aware weighting.
- foot kinematic velocity factor.
- Go2 yaw-rate between factor.
- Go2 relative odometry between factor.

These are source/candidate factors, not truth.

## N8G-N8J: FGO Feedback EKF

Selected policy:

```text
mode=horizontal_velocity_attitude_feedback
gate=combined_conservative_gate
covariance=inflation_auto_from_residual_proxy
window=5.0s/1.0s
position_feedback=disabled
feedback_type=EKF pseudo-measurement / error-state update
selected_feedback accepted/rejected=151/24
observations=175
```

Conclusion: engineering closure is demonstrated on BY2 clean, but performance improvement is small. Claims must be limited.

## N8K-N8K6: Formal Ablation Plot Audit

N8K produced many formal ablation figures, but applicable=True figures had placeholder, low-information, duplicate-template, semantic mismatch, and applicability problems.

Resolution chain:

- N8K2: remove applicable placeholders.
- N8K3: fix same-category duplicate semantic plots.
- N8K4: fix semantic filename alignment.
- N8K5: fix same-variant cross-category duplicate outputs.
- N8K6: fix A0 feedback applicability blocker.

Final state:

- `status=N8K_final_merge_review_passed`.
- PR #48 merged.
- Tag `N8K-v0.1-BY2-formal-ablation-plot-audit` exists.

## N9A Initial/R1/R2 Failure Chain

Initial N9A incorrectly treated N8K formal ablation outputs as BY2_normal_clean and treated 30 formal variants as 30 normal cases.

N9A_R1 fixed source lineage but did not produce true algorithm NAV/STD/EVAL output validation.

N9A_R2 found eight algorithm series but still failed:

- frame alignment not passed.
- horizontal RMSE had abnormal scale.
- velocity plots looked like zero lines.
- feedback/contact timelines were availability bars.
- yaw wrap/unit/convention remained confused.
- multiple figures were treated as complete because PNG files existed.

## N9A_R0: Context Rebuild

Current task. Rebuild multi-agent context and documentation only. No algorithm work, no generated figures, and no runtime artifacts. Documentation branch Git publication is a supervisor/human-final-decision action only, never a planner/worker/reviewer action.

## Next: N9A_R3

Run real output and frame alignment gate before any further formal plotting. N9A_R3 must keep `ready_for_N9B=false`.
