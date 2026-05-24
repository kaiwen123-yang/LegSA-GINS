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
- state and covariance propagation.
- GNSS position update.
- receiver velocity update where valid.
- dual yaw update.
- state feedback.
- NAV / STD / EVAL_NAV / RUN_MANIFEST outputs.
- provenance and no-trace/no-final_v23 input boundary checks.

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
- N8K5: fix same-variant cross-category duplicates.
- N8K6: fix A0 feedback applicability blocker.

Final state:

- `status=N8K_final_merge_review_passed`.
- PR #48 merged.
- Tag `N8K-v0.1-BY2-formal-ablation-plot-audit` exists.

## N9A: BY2 Normal Clean

N9A completed the BY2 normal clean audit route after earlier failed attempts exposed output lineage, frame alignment, metric sanity, zero-line, feedback/contact, and yaw convention risks.

## N9B0-N9B0C: Degradation Groundwork

N9B0, N9B0A, N9B0A1, N9B0A2, N9B0B, and N9B0C completed the initial degradation preparation route.

## N9B1A-N9B1G2: Pilot And Preparation Route

Completed:

- N9B1A and N9B1A1.
- N9B1C through N9B1G2.
- N9B1D through N9B1D4.

Current pilot sources:

- N9B1D4 is the current technical pilot source.
- N9B1E passed with C yaw caution and is the current pilot visual/go-no-go source.

## N9B2A-N9B2B: Full-Matrix Preparation And Path Lock

- N9B2A completed.
- N9B2A1 completed.
- N9B2A/N9B2A1 are full-matrix preparation sources.
- N9B2B completed path lock.
- N9B2B locks Windows plus WSL aliases and the future by2-huitu output alias.
- Native Ubuntu migration is deferred.
- Old Chinese output root is read-only historical evidence.
- Future BY2/N9B outputs use `BY2_N9B2_*` aliases.

## N9B2B1-N9C0: Staged N9B Execution And Global Consolidation

N9B2B1 completed the documentation/context update after path lock.

The staged N9B route then completed through N9C0:

- Batch 0 normal smoke complete.
- Batch 1 deterministic complete.
- Batch 2 position noise complete.
- Batch 3 position spike complete.
- Batch 4 yaw noise complete.
- Batch 5 core module-disable complete; module-stress remains deferred.
- Batch 6 selected mixed cases complete.
- final_v23 external baseline complete and integrated.
- N9C0 global staged consolidation precheck complete.

N9C0 active final-only metrics table:

```text
source=<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE
rows=825
```

No full monolithic N9B2 was run. `B_gnss_downsample_2Hz` remains invalid and superseded.

## Current: N9C0A

`N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION` updates tracked docs/context and writes audit reports only. It does not authorize solver, evaluator, N9B2, random generation, degraded-input generation, N9C1 figure generation, or paper claims.

Readiness after pass:

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

Recommended next stage:

```text
human_review_N9C0A_then_N9C1_consolidated_figure_generation
```
