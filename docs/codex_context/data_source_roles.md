# Data Source Roles

This file defines what each BY2 source may and may not support.

## GNSS Raw

Aliases: `<GNSS1_RAW>`, `<GNSS2_RAW>`.

Allowed:

- raw observation audit.
- Raw Doppler source audit.
- satellite count, Doppler residual, GNSS observation quality.
- dual-antenna source lineage and time coverage checks.

Not allowed:

- direct algorithm estimate.
- hidden replacement for NAV/EVAL output.

## GNSS Status

Aliases: `<GNSS1_STATUS>`, `<GNSS2_STATUS>`.

Allowed:

- receiver status.
- GNSS standard deviation / quality fields.
- yaw observation and yaw_std if explicit fields exist.
- receiver velocity only if explicit velocity columns exist.

Not allowed:

- `receiver_velocity.png` when velocity columns are absent.
- estimate substitution.

## Trace Reference

Alias: `<TRACE_TRUTH>`.

Allowed:

- truth/reference overlay.
- error computation after frame/time alignment.
- EVAL sanity.
- frame alignment and time alignment audit.

Not allowed:

- solver input.
- tuning parameters, gates, weights, covariance, or feedback.

## Fixposition Receiver IMU

Aliases: `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`.

Allowed:

- receiver IMU diagnostics.
- source lineage audit.
- receiver sensor status and time range checks.

Not allowed:

- fused body IMU.
- replacement for `by2.txt`.
- truth or algorithm estimate.

## Go2 Body IMU / High-Level

Alias: `<GO2_BODY_IMU_HIGHLEVEL>`.

Allowed when fields are explicitly parseable:

- Go2 body IMU / high-level source audit.
- Go2 roll/pitch.
- Go2 horizontal velocity.
- contact / foot source audit.
- legged factor source audit.
- proprioceptive candidate factor evidence.

Not allowed:

- truth.
- algorithm NAV.
- GNSS receiver IMU replacement.
- absolute position truth.

## Algorithm Outputs

NAV, STD, EVAL_NAV, summary files, and RUN_MANIFEST records are the core algorithm output and evaluation chain. Feedback observation CSVs, smoothed FGO NAV, and factor tables are runtime/factor diagnostics. All must be classified by role before plotting:

- estimate.
- covariance/uncertainty.
- evaluation.
- source observation.
- runtime diagnostic.
- factor diagnostic.
- forbidden/substitution risk.

None of these runtime outputs are committable by default.

## final_v23 / KF-GINS Reference

Allowed:

- reference comparison after role classification and alignment.
- sanity oracle for scale and convention checks.
- evaluation boundary when documenting what LegSA-GINS does or does not match.

Not allowed:

- solver input.
- tuning source for gates, weights, covariance, or feedback.
- hidden output substitution.
- basis for outperforming or paper-performance claims without a later approved audit.
