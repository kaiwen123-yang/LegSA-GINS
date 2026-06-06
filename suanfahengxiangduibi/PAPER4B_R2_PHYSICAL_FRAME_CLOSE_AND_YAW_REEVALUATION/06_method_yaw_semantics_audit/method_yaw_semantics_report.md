# Method Yaw Semantics Audit

Rows with method-level body-yaw metric validity after R2: 18 method-stage entries.

Accepted conversion for PAPER3F/PAPER3G/PAPER3H rows with epoch outputs:

- Native baseline heading is in degrees.
- Native heading is canonical NED heading, `atan2(E, N)`.
- Baseline direction is interpreted as GNSS1->GNSS2 from the DD receiver construction (`gnss2 - gnss1`) and the new user-confirmed port/side mapping.
- Apply the fixed physical transform: `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90)`.

Still blocked:

- PAPER3I Wu EQKF table is a DD/LOS row-heading diagnostic, not a case-level baseline-state epoch output.
- PAPER3I Pavlasek IEKF output has innovation diagnostics but no baseline-heading epoch output for body-yaw reevaluation.

No transform was chosen by RMSE. No per-case offset was searched or applied.
