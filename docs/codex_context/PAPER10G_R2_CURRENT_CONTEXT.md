# PAPER10G_R2 Current Context

Stage: `PAPER10G_R2_REAL_LEGGED_STATE_ESTIMATION_LITERATURE_REPRODUCTION`

Status: `CONDITIONAL_PASS_REAL_LSE_COMPLETED_WITH_PROXY_BOUNDARIES`

## What R2 Closed

- Locked identity, SHA256, pages, title/author/venue, duplicate decisions, and primary/source roles for the user-provided LSE PDFs.
- Extracted state definitions, process models, measurement models, contact models, sensor contracts, observability boundaries, and fidelity decisions for LSE01-LSE05.
- Built BY2 and BY3 Go2 legged providers from read-only `sportmodestate` logs.
- Executed five independent LSE backends on BY2/BY3 real sequences.
- Reported gauge-aware metrics: relative trajectory error after initial SE(2) alignment, drift per meter/second, end-to-end drift, relative yaw drift after initial alignment, roll/pitch/velocity diagnostics, divergence count, and runtime.
- Generated paper-facing tables, figures, render QA, claim boundaries, teacher package, C export, and Obsidian notes.

## Method Fidelity

- LSE01 Hartley contact-aided InEKF: `FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY`.
- LSE02 QEKF/kinematic contact EKF: `FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY`.
- LSE03 Rotella point/flat-foot EKF: `ADAPTED_FAITHFUL_SUBSET`; Go2 runs the point-foot subset and the humanoid flat-foot branch is not applicable.
- LSE04 FK plus preintegrated contact factor graph: `FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY`.
- LSE05 Teng slippery InEKF velocity update: `ADAPTED_FAITHFUL_SUBSET`; tracking-camera branch is blocked and the camera-off inertial plus leg-kinematic velocity subset ran.

## Provider Boundary

- Used fields: IMUState gyroscope/accelerometer/quaternion/rpy, velocity, yaw_speed, mode/gait_type, foot_force, foot_position_body, foot_speed_body, and body_height.
- `foot_position_body` is a high-level FK-like proxy, not raw joint encoder FK.
- Go2 yaw and Go2 position remain diagnostic-only and were not used as truth.
- GNSS dual-yaw was not input to legged-only methods.

## Safety Facts

- No trace online use occurred; trace is offline evaluation-only after initial alignment.
- No final_v23 output or LegSA-GINS output was used as solver input.
- No DA, LC, GINav, MATLAB, RTKLIB, complete nine-factor FGO, LegSA final matrix, degradation matrix, bad-epoch deletion, output substitution, or per-case tuning was run.
- Runtime provider CSVs over 50 MB remain runtime-only and are excluded from lightweight C export and Git.
- Generated figures are runtime/C-export artifacts only and must not be staged.
- No push was performed.

## Claim Position

- Allowed: formula-level/proxy-bounded LSE reproduction on BY2/BY3 real Go2 high-level data; local proprioceptive odometry support; absolute yaw not applicable; LSE and LegSA-GINS are complementary.
- Boundary: no author-official exact reproduction, no raw joint FK, no full contact-aided exact reproduction, and no tracking-camera branch execution.
- Forbidden: LSE absolute yaw/global position claims, Go2 yaw/position truth, BY3 ordinary yaw generalization, universal superiority, final_v23 outperformance, trace online use, final_v23/LegSA solver input, output substitution, per-case tuning, DA/LC/Ginav/MATLAB/RTKLIB/complete FGO/LegSA final matrix claims.

## Next Route

- Recommended next stage: `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC`.
- PAPER10H should use XB/PG severe-GNSS cases to show source-risk and QM state/action/recovery boundaries, not high-precision main-performance or universal-superiority claims.
