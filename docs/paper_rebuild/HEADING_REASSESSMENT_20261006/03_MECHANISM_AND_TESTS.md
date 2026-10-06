# 03 Mechanism audit and preregistered tests

This review separates receiver solution labels from estimator state propagation. FIX is a NAV-PVT carrier-solution field; the EKF state itself has no integer FIX/FLOAT class.

## Actual current input admission

Exact-iTOW joins of the natural R5 GNSS18 providers to both hash-locked raw NAV-PVT streams give the following runtime-start-exclusive counts. These are valid input rows, not a claim that every EKF innovation was accepted.

| Sequence | Position/RV valid | Both receiver FIX | GNSS1 FIX + GNSS2 FLOAT | Valid yaw |
|---|---:|---:|---:|---:|
| BY2 | 1370 | 1370 | 0 | 1370 |
| BY2H | 1350 | 1350 | 0 | 1350 |
| BY2O | 1885 | 1594 | 291 | 1594 |

No PVT join is missing. BY2O demonstrates position and receiver velocity remain admitted when the second antenna is FLOAT, while the dual-fixed yaw input is removed. All three windows have GNSS1 FIX throughout these inputs, so they provide no direct performance evidence for admitting GNSS1-FLOAT position/RV. The code is not a universal raw-quality certification: CLEAN5_PARITY V2 constructs position/RV from exact HPPOSECEF/PVT epochs, with independent flags, and R5 changes only yaw/value validity. The raw yaw gate explicitly requires both carrSoln fields to equal 2; it must not be described as a new ambiguity solver.

The original V3 and current diagnostic GNSS loader both expose separate position/velocity/yaw valid flags. Native GNSS updates test these flags independently. IMU propagation continues through unavailable GNSS observations. Initialization is another layer: the shared initialized heading comes from a dual-yaw contract; this pilot cannot initialize heading when that source is absent.

Reproduction: count_provider_fix.py; full counts and provider/raw hashes are in PROVIDER_FIX_COUNTS.csv/json.

## Why the earlier result does not settle the heading contribution

Legacy HV rotates SDK velocity with robot roll/pitch and externally supplied A1 heading, then dispatches it from GNSS epochs. M2 changes both measurement construction and scheduling, so its outage H improvement primarily establishes continuity of robot motion aiding. The body observation still predicts through the filter's estimated attitude. It does not measure absolute yaw on its own; without an external horizontal anchor, rotating yaw and horizontal velocity together preserves the observation.

D62 retains heading, yet M2's H RMSE worsened approximately 6.52%. That remains an unresolved adverse result. It cannot be dismissed as proof that more tuning will fix it. Possible causes include changed attitude/velocity coupling, frame or point assumptions and uncalibrated noise/correlation; this audit does not select among them using the reference.

The original M2 uses only forward/right body components. Its velocity measurement has no third row, so an independent down-velocity constraint is absent. D61/D62 vertical degradation is consistent with this weakness, but z bias, attitude coupling, lever-arm and covariance assumptions remain possible contributors. The new M3 is a bounded causal test of adding this row, not a promised remedy.

## Bounded next evidence

See PILOT_CONTRACT.md and PILOT_PREREGISTRATION.json: reuse six sealed C00/D61/D62 M0/M2 identities; run at most six new configurations comprising four M3 cases and H20 M0/M2. H20 deliberately removes the heading source and its legacy-HV interpolation support while retaining GNSS position/RV/Doppler. This makes the heading question explicit without inventing new FIX states or tuning thresholds.

Raw vertical feasibility is conditional: finite nonzero SDK z and moderate foot-proxy association coexist with roughly 4 cm/s mean differences and large per-foot disagreement tails. The exact raw-only results are recorded in VERTICAL_INPUT_CHECK.csv/json. They do not establish physical calibration.
