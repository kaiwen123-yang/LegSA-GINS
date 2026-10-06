# Heading-source loss and conditional vertical-velocity pilot

Status before scientific execution: build, raw-input diagnostics, 3D Jacobian and six native-loader admissions PASS; zero new navigation or evaluator runs. Execution requires parent commit/push freeze. This is an exploratory extension of the October 6 diagnostic pilot, not original V3 or a production repair.

## Fixed design and budget

Six existing sealed/evaluated identities are reused with NAV/STD/error-series hashes: C00, D61_20s_seed_00, D62_20s_seed_00, each M0 and M2. Six new scientific native runs are registered: those three scenarios with M3, plus H20 with M0, M2 and M3. No seed expansion, retries, noise search or reference-based selection. Technical failure attempts remain recorded.

- M0: inherited October 4 diagnostic with GNSS-event RP and A1-derived horizontal SDK velocity, using the exact prior pilot binary.
- M2: inherited independent causal RP and two-dimensional body-frame SDK velocity, using the exact prior pilot binary.
- M3: M2 extended to the third body-velocity component, with the same numerical sigma 0.132838 m/s for each dimension and inherited scale 1/0.962142. No z-bias correction or tuning. Same independent 5 Hz timer, causal latest sample, RP age 0.02 s, velocity age 0.08 s, each source sample consumed once. Both horizontal body components are unchanged. M3 uses one three-dimensional velocity EKF update and does not also perform a GNSS-event HV update.

All initial states, process noise, RP settings, GNSS data, antennas, timing, source-aware parameters and evaluation point conventions remain inherited except the explicitly registered input/model changes. M2 to M3 changes velocity residual dimension from 2 to 3, hence the same source-aware rule is evaluated at its actual three-dimensional residual/innovation. This is not a claim of identically calibrated probabilities.

## H20 source semantics and leakage control

H20 uses the same BY2 window and half-open interval [196.2,216.2) as D61/D62. Only the yaw-valid token of 100 GNSS18 rows is set to zero; all position, receiver velocity, Doppler, uncertainty and other GNSS18 bytes are retained.

The event represents heading-source unavailability. M0 must not retain precomputed HV that interpolated the unavailable A1 source. Its legacy 1 Hz A1 times are recovered from the exact SENSOR_V21 base GNSS18 file, A1 rows inside the interval are removed, and the inherited maximum interpolation gap of 1.2 s is reapplied to the old HV support. Its velocity values are preserved but update/support flags are disabled wherever this support is absent. This produces no HV support inside (196,217) and proves no valid old HV sample lies within the native 0.08 s selection tolerance of an outage GNSS event. No future recovery heading fills this hole.

This is not a pure filter yaw-event switch: the dependent legacy HV source is also unavailable, including the necessary interpolation boundary interval. M2/M3 use raw SDK velocity without A1 construction and remain active. Legacy outside-gap interpolation semantics are inherited and are not relabeled globally causal.

## Raw z admission and remaining assumptions

The three fixed raw windows contain finite, nonzero SDK z velocity. Top-two-force no-slip foot proxies have SDK-z correlations approximately 0.54–0.58, but mean differences 0.036–0.047 m/s and substantial tails. That is sufficient for a conditional diagnostic and insufficient for velocity truth, slip-free contact, frame calibration, sensor-point equivalence or covariance calibration. No reference, GNSS or estimator output entered this check.

M3 assumes the same SDK FLU to body FRD mapping as M2 and zero SDK-to-IMU point offset; it applies the inherited scale to all components. Sigma_z is fixed by the same numerical inherited sigma, not estimated from the foot proxy or selected against the evaluation reference. Vertical improvement would support a missing-constraint mechanism only.

## Mathematical and software gates

h = C_bn^T v_n. The inherited error feedback is v <- v-dv, C <- Exp(dphi) C. Therefore H_v=C_bn^T and H_phi=-C_bn^T [v_n]x. Three-dimensional finite differences pass with maximum error 2.97396e-10; the first two analytic rows equal the inherited two-dimensional H exactly. Causal, freshness, duplicate and clock guards are inherited unit checks.

Only the scratch source copy is changed. The production loader and production core remain untouched. The loader retains its historical horizontal-only transport labels; for M3, the isolated GIEngine constructor explicitly changes the effective mode to conditional_body_3d_pilot and vertical_disabled=false after checking the expected inherited transport. This effective dimension, frame, vertical flag, environment mode, binary hash and sandbox source hashes are the scientific identity. The original parser stage/case labels only permit transport and do not assert M3 is the historical method. All six configuration files passed the actual linked native loader before execution.

Track exact NAV time keys, finite outputs, full-window sparse covariance observations, 15 active-state PSD and symmetry (six scale states intentionally frozen), independent aid accepts, and total source-trace counts. M3 GNSS dispatch is disabled for HV, so total accepted HV must agree with independent accepts. Preserve all unfavorable results.

## Evaluation and decision rule

Seal all six native outputs before any of the six new offline evaluations. Reuse the six earlier evaluations by exact hashes; do not rerun them. Use the same frozen evaluator and commercial fused reference with shared GNSS lineage, not independent ground truth. Report full-window, fault, last-supported fault sample and first-five-second recovery H/V/3D/yaw metrics on exact matched time keys. Do not call the last-supported sample the exact 216.2 s endpoint.

The primary new heading question is the H20 M2-versus-M0 yaw trajectory/error and recovery, interpreted together with position/velocity support and actual heading/HV availability. C00 assesses collateral changes; D61/D62 assess the conditional third-dimensional constraint, including adverse H/yaw changes. There is no prespecified claim that D62 must improve. A favorable H result alone cannot establish the paper's heading innovation or a new absolute-heading observation. Shared dual-yaw initialization remains; this does not resolve no-initial-heading cases or global yaw gauge freedom.

The limit remains six new scientific native calls and six evaluations. No candidate replaces V3 or is approved for deployment from this single-sequence, single-event test.
