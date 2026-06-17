# PAPER10E0 Basic Dual-Yaw EKF Baseline Context

`PAPER10E0_BASIC_DUAL_YAW_EKF_BASELINE_FREEZE` freezes the Basic Dual-Yaw EKF baseline for later PAPER10E/PAPER10H comparison.

## Status

- Final status: `CONDITIONAL_PASS_BASIC_DUAL_YAW_BY2_READY_BY3_DIAGNOSTIC`.
- Active branch: `paper10e0/basic-dual-yaw-ekf-baseline-freeze`.
- Active code path: `cpp/legsa_v23_port_core`.
- Runtime root: `<PAPER10E0_STAGE_ROOT>`.
- C export root: `<PAPER10E0_C_EXPORT_ROOT>`.
- Obsidian sync root: `<PAPER10E0_OBSIDIAN_SYNC_ROOT>`.
- Push status: false.

## Method Definition

Basic Dual-Yaw EKF is KF-GINS original loose-coupled propagation and GNSS position update plus one optional 1D dual-antenna body-yaw update. It does not change state dimension, INS mechanization, covariance propagation, or `stateFeedback`.

The Basic yaw update uses:

- residual: `dz = wrap(yaw_INS - yaw_dual)`;
- Jacobian: `H(0, PHI_ID + 2) = -1`;
- covariance: fixed `R_yaw = (1.5 deg * pi / 180)^2`;
- update path: existing `EKFUpdate(dz, H, R)`.

## Evidence

- KF-GINS source parse PDF was read and indexed.
- final_v23 `process_data.py`, `run_final_mainline.py`, and docs were audited read-only.
- `process_data.py` contains noise/outlier/outage logic, so PAPER10E0 did not call it for smoke input assembly.
- Basic-specific unit tests passed.
- C++ `legsa_v23_port_core_demo` build passed.
- Yaw Jacobian sign validation passed.
- BY2 B00/B01 normal smoke completed; B01 applied 274 yaw updates with 0 reject/downweight.
- BY3 B00/B01 normal smoke completed as diagnostic-only; B01 applied 286 yaw updates with 0 reject/downweight.
- Lightweight validation pointer: `docs/codex_context/PAPER10E0_VALIDATION_POINTERS.md`.
- Runtime evidence index: `<PAPER10E0_STAGE_ROOT>/PAPER10E0_EXPORT_INDEX.md`.
- C export index: `<PAPER10E0_C_EXPORT_ROOT>/PAPER10E0_EXPORT_INDEX.md`.

## Boundaries

PAPER10E0 did not run BY2/BY3 full degradation matrix, source-aware LSIM/OIM, Go2 weak prior/readiness, QM, Raw Doppler, FGO feedback, DA, LC, GINav, MATLAB, RTKLIB, complete FGO, trace online, final_v23/LegSA solver input, per-case tuning, or official trace RMSE.

BY3 yaw remains diagnostic-only. PAPER10E0 does not authorize performance claims or final method claims.
