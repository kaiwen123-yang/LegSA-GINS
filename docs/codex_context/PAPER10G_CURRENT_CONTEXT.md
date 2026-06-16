# PAPER10G Current Context

Stage: `PAPER10G_LEGGED_STATE_ESTIMATION_OBSERVABILITY_DIAGNOSTIC`

Status: `PASS_LEGGED_OBSERVABILITY_DIAGNOSTIC_READY`

## What PAPER10G Closed

- Imported the lightweight PAPER10B, PAPER10B_R1, PAPER10B_R2B, PAPER10C, PAPER10C_R1B, PAPER10B2, PAPER10B2_R1, and PAPER10Y evidence packages.
- Audited GIEngine, Go2 weak-prior entry points, source-aware R scaling, multi-state QM, and dual-antenna yaw update contracts.
- Reviewed primary legged-state-estimation and invariant-filtering sources for the global-position and gravity-axis-yaw unobservability boundary.
- Read BY2/BY3 Go2 high-level logs in read-only mode and summarized field availability and allowed/forbidden roles.
- Generated a lightweight yaw-rate offset diagnostic and a toy symmetry/gauge demo.
- Produced paper-facing theory tables, Go2 role tables, dual-yaw/QM motivation material, claim boundaries, manuscript drafts, teacher consultation package, C export, and Obsidian stage notes.

## Core Conclusion

- IMU plus legged proprioceptive/contact/high-level sensing can provide relative motion and motion-state context, but without a global reference it cannot observe global translation or gravity-axis yaw.
- Gravity can support roll/pitch reasoning, but it does not define absolute heading.
- Go2 high-level state therefore supports LegSA-GINS as weak priors and metadata, not as position/yaw truth.
- Short lateral dual-antenna GNSS yaw remains the absolute heading source; its short-baseline and source-quality risks motivate source-aware weighting and multi-state QM.

## Allowed Roles

- Go2 roll/pitch: weak attitude/tilt prior.
- Go2 horizontal velocity: weak or diagnostic horizontal-motion constraint.
- Go2 readiness/motion-state: first-class LSIM/QM metadata.
- Dual-antenna yaw: absolute heading source after lateral body-yaw semantic conversion and source-quality handling.
- QM: source-level state/action/recovery management, not output replacement.

## Safety Facts

- No DA, LC, GINav, MATLAB, RTKLIB, contact-aided full reproduction, full leg odometry, complete nine-factor FGO, solver/evaluator matrix, degradation matrix, or per-case tuning was run.
- No trace online use occurred.
- No final_v23 output or LegSA output was used as solver input.
- No Go2 yaw or Go2 position was used as truth.
- No receiver `imu-data.csv` was used as Go2 body IMU.
- BY3 yaw remains diagnostic-only.
- Figures are runtime/export artifacts only and must not be staged.
- No push was performed.

## Claim Position

- Allowed: legged proprioceptive/contact sensing alone cannot provide global yaw or global position without a global reference; Go2 and dual-yaw are complementary; QM is motivated by heterogeneous observability/reliability.
- Boundary: PAPER10G is theory/diagnostic evidence, not a full contact-aided implementation or performance proof.
- Forbidden: Go2 yaw/position truth, legged-only absolute yaw, full contact-aided InEKF, full leg odometry, complete nine-factor FGO, universal superiority, final_v23 outperformance, BY3 ordinary yaw generalization, trace online use, output substitution, or solver-input use of final_v23/LegSA outputs.

## Next Route

- Recommended next stage: `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC`.
- PAPER10H should use XB/PG severe-GNSS cases to show source-risk boundaries and QM state/action/recovery timelines, not high-precision main-performance or universal-superiority claims.
