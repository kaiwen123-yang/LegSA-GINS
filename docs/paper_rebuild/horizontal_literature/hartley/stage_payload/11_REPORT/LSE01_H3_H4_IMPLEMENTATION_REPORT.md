# LSE01 Hartley H3--H4 Implementation and Validation Report

## Validated backend terminal state

`PASS_LSE01_H3_H4_FULL_IJRR_BACKEND_VALIDATED`

All mathematical, synthetic, official-regression, observability, publication, and parity gates required in H3--H4 are validated. This is not a real BY2 navigation or accuracy result.

## Backend identities

- `HARTLEY_IJRR2020_REPORTED_BACKEND`: IJRR Eq. 50 exact zero-order-held mean, analytical right-invariant Eqs. 58/60 transition, and paper-reported Eq. 61 approximate discrete process covariance. This is the faithful production identity.
- `EXACT_QD_REFERENCE_DIAGNOSTIC`: the same Eq. 50 mean and analytical transition with a 64-point Gauss--Legendre evaluation of Eq. 52. A separate DOP853 covariance ODE is the independent oracle.
- `OFFICIAL_CPP_EARLY_REGRESSION`: frozen-R velocity/position mean, `I + A dt`, official mapped process covariance, and pinned early event lifecycle. It is regression-only.

## Numerical results

- Lie primitives: 13 executable cases passed, including continuous zero-rate Gamma/Psi limits, NaN/infinity/finite-overflow rejection, near-pi SO(3) Exp/Log/orthogonality/determinant, independent block-exponential/Frechet Gamma/Psi oracles, branch continuity, and normal/stress adjoint checks.
- Eq. 50: 7 zero/near-zero/normal/large-rate and stress cases passed; maximum reported state-component oracle error was `6.821e-14`.
- Analytical Phi: 30 full nonlinear right-invariant finite-difference cases for zero through four contacts passed, including exact zero-`dt`; maximum absolute coefficient error was `1.310e-09`. The independent Eq. 60 adjoint/exponential construction agreed with the closed-form Eq. 58 transition to maximum relative Frobenius error `1.085e-15`.
- Process covariance: 21 Eq. 61/Eq. 52 comparison cases passed symmetry and PSD tolerances. The branches differ as expected. The independent Eq. 52 DOP853 maximum relative Frobenius error was `3.020e-12`.
- Contact lifecycle: simultaneous and single/mixed add/remove sequences preserved identity ordering, cross-covariance, dimensions, symmetry, and PSD.
- Synthetic recovery: independently generated truth and perturbed filters reduced observable error for static four-contact and switching one/two/three/four-contact walking, including a ten-step flight interval. Pure-synthetic continuous-ASD and typed paper-Table-1 bias/stochastic propagation, the Table-1 one-degree encoder measurement mapped through supplied foot Jacobians and exercised in correction, contact-dwell chattering, and large-attitude/rate ill-conditioned stress cases passed.
- Gauge equivariance: independent truth measurements produced nonzero innovations in normal and stress yaw-plus-translation families; inverse-gauge state/bias recovery, innovation transformation, and relative-Frobenius covariance congruence passed. Native absolute yaw remained separated while relative yaw increments agreed.
- Official regression: the unmodified pinned executable returned zero; the dual public-API comparison consumed 59,976 rows with exact counts (19,992 propagation, 19,780 corrections, 34 additions, 33 removals). Maximum covariance difference after contact-order mapping was `4.799e-10`.
- Ideal observability: all one-through-four-contact ranks/nullities were `12/8/4`, `15/11/4`, `18/14/4`, and `21/17/4`; the gauge basis is three translations plus one gravity-axis rotation.

## Test closure

- Supervisor-scoped H3--H4 tests: `24 passed`; the combined H3--H4 and H0--H2 preservation scope is `74 passed`.
- Supervisor/full `tests/paper_rebuild`: `922 passed, 10 skipped, 2 failed`. The only failures are the unchanged unrelated Phase 4 execution-lock and Phase 5 dirty/untracked snapshot expectations; no Hartley or new failure was introduced.
- C++ configure/build, CTest `1/1`, direct tests `205/205`, and the validator passed. Python compile/import passed for four files. Post-generation parsing passed for 14 JSON, 14 YAML, and 27 CSV files. `git diff --check` passed.

## Go2 Allan interface

`GO2_IMU_ALLAN_90MIN_RECOVERED_V1` enters the backend only as continuous amplitude spectral densities. The production `continuousPsdFromDensity` API squares each density once to form Qc. The separate discrete-sample diagnostic API is not called by production propagation. Bias-instability values remain diagnostic-only. `PaperTable1DiscreteStd` retains all six stochastic parameters; its one-degree joint-encoder standard deviation is a measurement-side angle converted to radians and mapped only as `R = J (sigma_rad^2 I) J^T` through a supplied foot-position Jacobian.

## Stop boundary and execution proof

- Real BY2 Hartley navigation runs: 0.
- Real seven-yaw gauge ensemble runs: 0.
- Reference/trace opens: 0.
- EXT06, HORIZONTAL18, other-method, and Canonical-541 executions: 0.
- Real BY2 navigation output CSV files produced: 0.
- External G-drive publication: the existing LSE01 stage was extended with 23 new and 2 updated payload files. All 69 external files match the tracked payload, and the 46 pre-existing H0--H2 files were preserved before publication.
- Historical H0--H2 report/status SHA-256 values remain `6acde6b5ace54ef5dfddee27ad9d07f65a216bc9507a4f0f4204c3b24a5b07fb` and `83ddb52a79c86a10f8b9744b5536b8548a39c27e14885c68eada5cfd29209eec`.
- Windows reported the mounted exFAT volume as `WARNING / FULL_REPAIR_NEEDED`; byte-for-byte parity was nevertheless verified after publication.
- Commit readiness: true after supervisor publication, parity, and audit closure.
- H5 execution: not authorized here; a new human authorization is required.

The preregistered H5 parameter gate is executable-validated, but it does not authorize H5. This phase stops before any real BY2 run.
